"""Checklist judge (M1): score an answer by atomic items derived from the gold, not by one holistic call.

1. Gold → checklist, built once per question by an LLM and cached in data/processed/judge_checklists/:
   sub-questions (A1), conclusions (A2/B3), issues (B0), principles (B1). Sections, non-existent sections
   and amounts are NOT asked of the LLM: they come from the gold by code.
2. Answer × checklist → one LLM call that answers, per item, "is it stated?" and "is it contradicted?"
   (+ "is the law applied to the facts?" and the extra issues raised).
3. Code: gold-section recall (tools/exam/statutes.py parser + the answer's citation keys), citation of a
   section the gold says does not exist, gold amounts found in the answer (number parsing).
4. Explicit rules in config/judge_checklist.yaml map item counts to 0/1/2 per criterion;
   src/eval/calibrate_checklist.py fits them against the lawyers' scores.

`collect()` returns `RowFacts` — everything the mapping needs — so rules can be re-fitted without the LLM.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from src.agent.nodes.common import prompt
from src.eval.import_dev100 import NONEXISTENT_RE, SECTION_RE
from src.eval.judge import CRITERIA, Score, gold_text
from src.llm import generate_json
from tools.exam.statutes import normalise, statutes

RULES_PATH = Path("config/judge_checklist.yaml")
CHECKLISTS = Path("data/processed/judge_checklists")
THINKING = "low"
AMOUNT_ABS_TOL = 1.0          # baht: rounding of satang / per-day rates
AMOUNT_REL_TOL = 0.001


class Checklist(BaseModel):
    sub_questions: list[str]
    conclusions: list[str]
    issues: list[str]
    principles: list[str]


class ItemVerdict(BaseModel):
    id: str
    stated: bool
    contradicted: bool


class Verification(BaseModel):
    items: list[ItemVerdict]
    applies_law_to_facts: bool
    extra_issues: list[str]


@dataclass(frozen=True)
class RowFacts:
    n_subq: int
    subq_addressed: int
    n_concl: int
    concl_matched: int          # stated and not contradicted
    concl_contra: int
    n_amounts: int
    amounts_matched: int
    n_issues: int
    issues_found: int
    n_extra: int
    n_princ: int
    princ_matched: int
    princ_contra: int
    n_gold_sections: int
    sections_law: int           # gold sections cited, law and number equal
    sections_number: int        # gold sections cited, number equal (law ignored)
    cites_nonexistent: bool
    applies: bool

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> RowFacts:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})


# --- mapping rules -------------------------------------------------------------------------------

def load_rules(path: Path | str = RULES_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def grade(ratio: float, contradicted: int, rule: dict) -> int:
    eps = 1e-9
    if ratio >= rule["hi"] - eps and contradicted <= rule.get("max_contradicted", math.inf):
        return 2
    return 1 if ratio >= rule["lo"] - eps else 0


def _ratio(k: int, n: int) -> float:
    return 1.0 if n == 0 else k / n


def score(f: RowFacts, rules: dict) -> dict[str, int]:
    c = rules["criteria"]
    concl = _ratio(f.concl_matched + f.amounts_matched, f.n_concl + f.n_amounts)
    out = {"A1": grade(_ratio(f.subq_addressed, f.n_subq), 0, c["A1"]),
           "A2": grade(concl, f.concl_contra, c["A2"]),
           "B3": grade(concl, f.concl_contra, c["B3"])}

    b0 = grade(_ratio(f.issues_found, f.n_issues), 0, c["B0"])
    out["B0"] = min(b0, 1) if f.n_extra > c["B0"].get("max_extra", math.inf) else b0

    r1 = c["B1"]
    hits = f.sections_law if r1.get("section_match", "law") == "law" else f.sections_number
    w = r1.get("section_weight", 0.5)
    if f.n_gold_sections == 0:
        w = 0.0
    elif f.n_princ == 0:
        w = 1.0
    ratio = w * _ratio(hits, f.n_gold_sections) + (1 - w) * _ratio(f.princ_matched, f.n_princ)
    b1 = grade(ratio, f.princ_contra, r1)
    out["B1"] = min(b1, r1.get("nonexistent_cap", 2)) if f.cites_nonexistent else b1

    out["B2"] = (grade(concl, f.concl_contra, c["B2"]) if f.applies
                 else c["B2"].get("no_application", 0))
    return {k: out[k] for k in CRITERIA}


# --- code checks: sections and amounts -----------------------------------------------------------

def answer_sections(text: str, cited_keys: Iterable[str] = ()) -> set[str]:
    """Section-level keys ("LPA2541:118") named in the answer text or in its citation keys."""
    keys = {":".join(k.split(":")[:2]) for k in cited_keys if k and not k.startswith("CASE:")}
    return set(statutes(text or "")) | keys


def section_hits(gold: Iterable[str], answer: set[str], mode: str) -> int:
    if mode == "law":
        return len(set(gold) & answer)
    numbers = {k.split(":", 1)[1] for k in answer if ":" in k}
    return sum(1 for g in set(gold) if g.split(":", 1)[-1] in numbers)


def nonexistent_sections(gold: str) -> set[str]:
    """Section numbers the gold says do not exist ("มาตรา 41/2 ไม่มีในกฎหมาย")."""
    text = normalise(gold)
    out: set[str] = set()
    for m in SECTION_RE.finditer(text):
        clause = re.split(r"มาตรา|\n", text[m.end():m.end() + 120], maxsplit=1)[0]
        if NONEXISTENT_RE.search(clause):
            out.update(re.findall(r"\d+(?:/\d+)?", m.group(0)))
    return out


def cites_nonexistent(nonexistent: set[str], answer: set[str]) -> bool:
    return any(k.split(":", 1)[-1] in nonexistent for k in answer)


_AMOUNT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(?:\.-)?\s*บาท")


def parse_amounts(text: str) -> list[float]:
    out = []
    for m in _AMOUNT.finditer(normalise(text)):
        s = m.group(1).replace(",", "")
        try:
            out.append(float(s))
        except ValueError:
            continue
    return out


def amounts_matched(gold: Iterable[float], answer: Iterable[float]) -> int:
    ans = list(answer)
    return sum(1 for g in gold
               if any(abs(a - g) <= max(AMOUNT_ABS_TOL, AMOUNT_REL_TOL * abs(g)) for a in ans))


# --- LLM steps -----------------------------------------------------------------------------------

def build_prompt(row: dict) -> tuple[str, str]:
    version, body = prompt("judge_checklist_build")
    return version, body.format(question=row["question"], gold=gold_text(row))


def _checklist_file(row: dict) -> Path:
    return CHECKLISTS / f"{row['id']}.json"


def _build_key(row: dict) -> str:
    version, p = build_prompt(row)
    return hashlib.sha256(f"{version}\x1f{p}".encode()).hexdigest()


def cached_checklist(row: dict) -> Checklist | None:
    """The checklist from the file cache, or None (never calls the LLM)."""
    path = _checklist_file(row)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("key") == _build_key(row):
            return Checklist.model_validate(data["checklist"])
    return None


def build_checklist(row: dict) -> Checklist:
    """Gold → checklist; one LLM call per question, then read from data/processed/judge_checklists/."""
    if (hit := cached_checklist(row)) is not None:
        return hit
    version, p = build_prompt(row)
    cl = generate_json(p, Checklist, name=f"judge_checklist_build_v{version}", thinking=THINKING)
    path = _checklist_file(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"key": _build_key(row), "gold_sha": hashlib.sha256(
        gold_text(row).encode()).hexdigest()[:12], "checklist": cl.model_dump()},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return cl


PREFIX = {"sub_questions": "Q", "conclusions": "C", "issues": "I", "principles": "P"}


def items(cl: Checklist) -> list[tuple[str, str]]:
    return [(f"{PREFIX[field]}{i}", text) for field in PREFIX
            for i, text in enumerate(getattr(cl, field), 1)]


def verify_prompt(question: str, answer: str, cl: Checklist) -> str:
    _, body = prompt("judge_checklist_verify")
    listing = "\n".join(f"[{i}] {t}" for i, t in items(cl)) or "(ไม่มีรายการ)"
    return body.format(question=question, items=listing, answer=answer)


def verify(question: str, answer: str, cl: Checklist) -> Verification:
    version, _ = prompt("judge_checklist_verify")
    return generate_json(verify_prompt(question, answer, cl), Verification,
                         name=f"judge_checklist_verify_v{version}", thinking=THINKING)


# --- facts and scoring ---------------------------------------------------------------------------

def collect(row: dict, cl: Checklist, v: Verification, answer: str,
            cited_keys: Iterable[str] = ()) -> RowFacts:
    got = {it.id: it for it in v.items}

    def count(prefix: str, n: int) -> tuple[int, int, int]:
        verdicts = [got.get(f"{prefix}{i}") for i in range(1, n + 1)]
        stated = sum(1 for x in verdicts if x and x.stated)
        matched = sum(1 for x in verdicts if x and x.stated and not x.contradicted)
        contra = sum(1 for x in verdicts if x and x.contradicted)
        return stated, matched, contra

    subq, _, _ = count("Q", len(cl.sub_questions))
    _, concl_ok, concl_bad = count("C", len(cl.conclusions))
    issues, _, _ = count("I", len(cl.issues))
    _, princ_ok, princ_bad = count("P", len(cl.principles))

    gold = row.get("gold_answer", "")
    gold_amounts = sorted(set(parse_amounts(gold)))
    gold_secs = [g for g in row.get("gold_citations", "").split(";") if g]
    ans_secs = answer_sections(answer, cited_keys)
    return RowFacts(
        n_subq=len(cl.sub_questions), subq_addressed=subq,
        n_concl=len(cl.conclusions), concl_matched=concl_ok, concl_contra=concl_bad,
        n_amounts=len(gold_amounts), amounts_matched=amounts_matched(gold_amounts, parse_amounts(answer)),
        n_issues=len(cl.issues), issues_found=issues, n_extra=len(v.extra_issues),
        n_princ=len(cl.principles), princ_matched=princ_ok, princ_contra=princ_bad,
        n_gold_sections=len(gold_secs), sections_law=section_hits(gold_secs, ans_secs, "law"),
        sections_number=section_hits(gold_secs, ans_secs, "number"),
        cites_nonexistent=cites_nonexistent(nonexistent_sections(gold), ans_secs),
        applies=v.applies_law_to_facts)


def explain(row: dict, cl: Checklist, v: Verification, answer: str, cited_keys: Iterable[str] = ()) -> str:
    """Short reasons: the items that failed (shown in reports next to the scores)."""
    got = {it.id: it for it in v.items}
    out = []
    for iid, text in items(cl):
        x = got.get(iid)
        if x and x.contradicted:
            out.append(f"{iid} ขัดกับ: {text}")
        elif not (x and x.stated):
            out.append(f"{iid} ไม่พบ: {text}")
    ans_secs = answer_sections(answer, cited_keys)
    missing = [g for g in row.get("gold_citations", "").split(";") if g and g not in ans_secs]
    if missing:
        out.append("มาตราในเฉลยที่ไม่ได้อ้าง: " + ", ".join(missing))
    bad = nonexistent_sections(row.get("gold_answer", ""))
    if cites_nonexistent(bad, ans_secs):
        out.append("อ้างมาตราที่เฉลยระบุว่าไม่มีอยู่: " + ", ".join(sorted(bad)))
    gold_amounts = sorted(set(parse_amounts(row.get("gold_answer", ""))))
    ans_amounts = parse_amounts(answer)
    lost = [a for a in gold_amounts if not amounts_matched([a], ans_amounts)]
    if lost:
        out.append("จำนวนเงินในเฉลยที่ไม่พบ: " + ", ".join(f"{a:,.2f}" for a in lost))
    if v.extra_issues:
        out.append("ประเด็นเกิน: " + "; ".join(v.extra_issues))
    if not v.applies_law_to_facts:
        out.append("ไม่ได้ปรับบทกับข้อเท็จจริง")
    return " · ".join(out) or "ครบทุกรายการ"


def judge(row: dict, answer_md: str, cited_keys: Iterable[str] = (), rules: dict | None = None) -> Score:
    """Drop-in for src.eval.judge.judge: `row` is the dev100 row (question, gold, gold_citations)."""
    cited_keys = list(cited_keys)
    cl = build_checklist(row)
    v = verify(row["question"], answer_md, cl)
    s = score(collect(row, cl, v, answer_md, cited_keys), rules or load_rules())
    return Score(**s, reasons=explain(row, cl, v, answer_md, cited_keys))
