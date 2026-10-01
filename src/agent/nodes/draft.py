"""⑧ draft_answers · ⑨ verify_select · ⑩ validate_cites"""

from __future__ import annotations

import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from pathlib import Path

from pydantic import BaseModel, Field

from src.agent.answer import AnswerJSON, LawRef
from src.agent.nodes.common import fmt_facts, fmt_provision, prompt, taxonomy, traced
from src.agent.render import render
from src.agent.rules.hierarchy import pair_notes
from src.agent.state import AgentState
from src.index import tools
from src.index.bm25 import tokenize
from src.llm import generate_json
from src.params import P

THAI_ORD = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า", "สิบ"]


# ---------- dynamic few-shot (dev100, verified gold, leave-one-out) ----------

@cache
def _example_bank() -> tuple[list[dict], dict[str, list[str]]]:
    path, tags = Path("data/eval/dev100.csv"), Path("data/processed/dev100_issues.json")
    if not path.exists() or not tags.exists():
        return [], {}
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows, json.loads(tags.read_text(encoding="utf-8"))


def pick_examples(state: AgentState, n: int | None = None) -> list[dict]:
    n = P("draft.n_examples") if n is None else n
    rows, tags = _example_bank()
    mine = {i.code for i in state.issues}
    exclude = set(state.exclude_example_ids) | ({state.question_id} if state.question_id else set())
    qtok = set(tokenize(state.question))

    def score(r: dict) -> tuple[int, float]:
        overlap = len(mine & set(tags.get(r["id"], [])))
        t = set(tokenize(r["question"]))
        return overlap, len(qtok & t) / (len(qtok | t) or 1)

    pool = [r for r in rows if r["id"] not in exclude and r["gold_answer"]]
    best = sorted(pool, key=score, reverse=True)[:n]
    return [r for r in best if score(r)[0] > 0]


# ---------- ⑧ draft ----------

def _issue_block(state: AgentState) -> str:
    tax = taxonomy()
    return "\n".join(f"{n}. [{i.code}] {tax[i.code]['name']} — {i.reason}"
                     for n, i in enumerate(state.issues, 1))


def _selected_rows(state: AgentState) -> list[dict]:
    seen, rows = set(), []
    for code, keys in state.selected.items():
        by_key = {r["citation_key"]: r for r in state.candidates.get(code, [])}
        for k in keys:
            if k in by_key and k not in seen:
                seen.add(k)
                rows.append(by_key[k])
    return rows


def _provisions_block(state: AgentState) -> str:
    rows = _selected_rows(state)
    lines = [fmt_provision(r, P("draft.provision_chars")) for r in rows]
    notes = pair_notes(rows)
    if notes:
        lines += ["", "ลำดับชั้นกฎหมาย (ระบบกำหนด):"] + [f"- {n}" for n in notes]
    return "\n".join(lines)


HEADER_LINE = re.compile(r"^(คำ(พิพากษา|วินิจฉัย|สั่ง)|พ\.ร\.บ\.|พ\.ร\.ก|ป\.พ\.พ\.|ป\.วิ\.|ประมวล|พระราช)")


def case_summary(holding: str, n: int | None = None) -> str:
    """Headnote without its header lines (case number and list of cited sections)."""
    lines = [ln.strip() for ln in (holding or "").split("\n") if ln.strip()]
    body = [ln for ln in lines if not HEADER_LINE.match(ln)]
    return " ".join(body)[: n or P("cases.summary_chars")]


def _cases_block(state: AgentState) -> str:
    seen, lines = set(), []
    for hits in state.cases.values():
        for h in hits:
            if h["key"] not in seen:
                seen.add(h["key"])
                lines.append(f"{h['key']} | {h['label']} | {case_summary(h.get('holding'))}")
    return "\n".join(lines) or "-"


def _elements_block(state: AgentState) -> str:
    tax = taxonomy()
    out = []
    for code, checks in state.elements.items():
        qs = {e["id"]: e["question"] for e in tax[code].get("elements", [])}
        out.append(f"[{code}]")
        out += [f"- {c.status}: {qs.get(c.id, c.id)} — {c.evidence}" for c in checks]
    return "\n".join(out) or "-"


def _calcs_block(state: AgentState) -> str:
    return "\n".join(f"[{c}] " + " ; ".join(r.steps) + f" (อ้าง {', '.join(r.citations)})"
                     for c, r in state.calcs.items()) or "- (ไม่มีการคำนวณ)"


def _examples_block(state: AgentState) -> str:
    ex = pick_examples(state)
    from src.eval.judge import gold_text
    return "\n\n".join(f"คำถาม: {r['question']}\nเฉลย: {gold_text(r)}" for r in ex) or "-"


def draft_prompt(state: AgentState, feedback: str = "") -> str:
    _, body = prompt("draft_answer")
    p = body.format(question=state.question,
                    asked="\n".join(state.facts.asked if state.facts else []),
                    facts=fmt_facts(state), issues=_issue_block(state),
                    provisions=_provisions_block(state), elements=_elements_block(state),
                    calcs=_calcs_block(state), examples=_examples_block(state),
                    cases=_cases_block(state))
    if feedback:
        p += f"\n\n## ข้อที่ต้องแก้จากร่างก่อน\n{feedback}"
    return p


@traced("draft_answers")
def draft_answers(state: AgentState) -> dict:
    p = draft_prompt(state)
    n = P("draft.n_drafts")
    with ThreadPoolExecutor(n) as ex:
        drafts = list(ex.map(
            lambda i: generate_json(p, AnswerJSON, name="draft", temperature=P("llm.temperature"),
                                    seed=i),
            range(n)))
    return {"drafts": drafts, "_summary": {"n": len(drafts),
                                           "examples": [r["id"] for r in pick_examples(state)]}}


# ---------- ⑨ verify & select ----------

class Verdict(BaseModel):
    complete: float = Field(ge=0, le=1)
    supported: float = Field(ge=0, le=1)
    consistent: float = Field(ge=0, le=1)
    focused: float = Field(ge=0, le=1)
    feedback: str

    def score(self) -> float:
        return (self.complete + self.supported + self.consistent + self.focused) / 4

    def worst(self) -> float:
        return min(self.complete, self.supported, self.consistent, self.focused)


def _verify(state: AgentState, draft: AnswerJSON) -> Verdict:
    _, body = prompt("verify_answer")
    return generate_json(body.format(question=state.question, facts=fmt_facts(state),
                                     provisions=_provisions_block(state),
                                     draft=draft.model_dump_json(indent=1)),
                         Verdict, name="verify", thinking="low")


def _verify_fallback(state: AgentState, e: Exception) -> dict:
    return {"answer": state.drafts[0] if state.drafts else None}


@traced("verify_select", fallback=_verify_fallback)
def verify_select(state: AgentState) -> dict:
    with ThreadPoolExecutor(max(len(state.drafts), 1)) as ex:
        verdicts = list(ex.map(lambda d: _verify(state, d), state.drafts))
    best = max(range(len(verdicts)), key=lambda i: verdicts[i].score())
    answer, v = state.drafts[best], verdicts[best]
    revised = False
    if v.worst() < P("draft.revise_below") and v.feedback.strip():
        answer = generate_json(draft_prompt(state, v.feedback), AnswerJSON, name="revise")
        revised = True
    scores = [v.model_dump() for v in verdicts]
    return {"answer": answer, "draft_scores": scores,
            "_summary": {"picked": best, "scores": [round(v.score(), 2) for v in verdicts],
                         "revised": revised}}


# ---------- ⑩ validate citations ----------

KEY_IN_TEXT = re.compile(r"\[?\b((?:LPA|LRA|LCA)\d{4}|CCC|RD-[A-Z-]+|MR-[A-Z0-9-]+|ANN-[A-Z0-9-]+|CASE)"
                         r"(:(?:[ก-ฮ]\s)?[0-9ก-๙/]+(?::\d+)?(?::\(\d+\))?)\]?")
SEC_MENTION = re.compile(r"(?:มาตรา|ม\.)\s*(\d+(?:/\d+)?)")


def _label(r: dict) -> str:
    if "section_no" not in r:              # a court decision (see tools.case_label)
        return r["label"]
    if r["section_no"] == "0":            # instrument without numbered clauses
        return r["law_name"]
    para = r["paragraph_no"]
    unit = "ข้อ" if r["level"] >= 3 else "มาตรา"
    lab = f"{unit} {r['section_no']}"
    term = re.match(r"\s*“([^”]+)”\s*หมายความว่า", r.get("text") or "")
    if term:                                # definitions section: name the defined term
        return f"{lab} นิยามคำว่า “{term.group(1)}” {r['law_name']}"
    if para and para > 1:
        lab += f" วรรค{THAI_ORD[para] if para < len(THAI_ORD) else para}"
    if r.get("sub_no"):
        lab += f" {r['sub_no']}"
    return f"{lab} {r['law_name']}"


def short_label(r: dict) -> str:
    """Compact inline reference: "ม.118 วรรคหนึ่ง", "ม.582 ประมวลกฎหมายแพ่งและพาณิชย์",
    "ข้อ 2 (1) ประกาศ…", or the court decision label."""
    if "section_no" not in r:
        return r["label"]
    if r["section_no"] == "0":
        return r["law_name"]
    unit = "ข้อ" if r["level"] >= 3 else "ม."
    lab = f"{unit}{'' if unit == 'ม.' else ' '}{r['section_no']}"
    para = r["paragraph_no"]
    term = re.match(r"\s*“([^”]+)”\s*หมายความว่า", r.get("text") or "")
    if term:
        lab += f" “{term.group(1)}”"
    elif para and para > 1:
        lab += f" วรรค{THAI_ORD[para] if para < len(THAI_ORD) else para}"
    if r.get("sub_no"):
        lab += f" {r['sub_no']}"
    return lab if r.get("law") == "LPA2541" else f"{lab} {r['law_name']}"


def allowed_keys(state: AgentState) -> set[str]:
    """Citations the answer may use: provisions ⑤ selected, plus those a calculation used."""
    keys = {k for ks in state.selected.values() for k in ks}
    keys |= {k for c in state.calcs.values() for k in c.citations}
    keys |= {h["key"] for hits in state.cases.values() for h in hits}
    return keys


def humanize_keys(a: AnswerJSON, ok) -> None:
    """Replace internal citation keys the LLM copied into prose ("ตาม LPA2541:11:1") with the
    DB label; keys that fail validation are dropped from the text."""
    def sub(m: re.Match) -> str:
        r = ok(m.group(1) + m.group(2))
        return _label(r) if r else ""

    def walk(obj):
        for name, val in obj:
            if isinstance(val, str) and name not in ("citation_key", "code"):
                setattr(obj, name, KEY_IN_TEXT.sub(sub, val))
            elif isinstance(val, list):
                for i, x in enumerate(val):
                    if isinstance(x, str) and name not in ("citations", "calculation_citations"):
                        val[i] = KEY_IN_TEXT.sub(sub, x)
                    elif hasattr(x, "model_fields"):
                        walk(x)
            elif hasattr(val, "model_fields"):
                walk(val)
    walk(a)


def version_notes(a: AnswerJSON, ok, event_date) -> list[str]:
    """Deterministic §4.4 notes: the index holds the current consolidated text only, so say
    so, and list the amendment footnotes of every cited provision."""
    notes: dict[str, None] = {}
    for key in sorted(a.all_citations()):
        r = ok(key)
        for n in (r or {}).get("amendment_notes") or []:
            notes[normalize_digits(n)] = None
    if not notes:
        return []
    head = ("คำตอบนี้ใช้ตัวบทฉบับปัจจุบัน หากข้อเท็จจริงเกิดก่อนการแก้ไขต่อไปนี้ หลักเกณฑ์อาจแตกต่าง"
            if event_date is None else
            f"ระบบมีเฉพาะตัวบทฉบับปัจจุบัน ยังไม่ได้ตรวจตัวบท ณ วันที่ {event_date.isoformat()} — "
            "มาตราที่อ้างมีการแก้ไขดังนี้")
    return [head, *notes]


def normalize_digits(s: str) -> str:
    return s.translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789"))


@traced("validate_cites")
def validate_cites(state: AgentState) -> dict:
    """Every citation must be one the system selected, exist in the DB and be in force on
    event_date. Labels and the summary table's legal basis are rebuilt from the DB, so a
    section number there can never be wrong. Section numbers written in prose that no kept
    citation supports are reported (they cannot be rewritten safely)."""
    a = state.answer or (state.drafts[0] if state.drafts else None)
    if a is None:
        return {"markdown": "ไม่สามารถสร้างคำตอบได้", "_summary": "no answer"}
    a = a.model_copy(deep=True)
    allowed = allowed_keys(state)
    removed: list[str] = []
    cache_: dict[str, dict | None] = {}

    def ok(key: str) -> dict | None:
        if key not in allowed:
            return None
        if key not in cache_:
            cache_[key] = (tools.get_case(key) if key.startswith("CASE:")
                           else tools.get_provision(key, state.event_date))  # None if not in force
        return cache_[key]

    def keep(keys: list[str]) -> list[str]:
        good = [k for k in keys if ok(k)]
        removed.extend(k for k in keys if not ok(k))
        return good

    for p in a.preliminary:
        p.citations = keep(p.citations)
    for iss in a.issues:
        # the calculation section is the calculator's own output, never the LLM's copy
        calc = state.calcs.get(iss.code)
        iss.calculation = list(calc.steps) if calc else []
        iss.calculation_citations = [k for k in dict.fromkeys(calc.citations) if ok(k)] if calc else []
        # provisions a calculation used are part of the issue's law even if the draft omitted them
        listed = {law.citation_key for law in iss.laws}
        for k in (calc.citations if calc else []):
            r = ok(k)
            if r and k not in listed:
                iss.laws.append(LawRef(citation_key=k, label=_label(r),
                                       explanation="บทที่ระบบใช้ในการคำนวณของประเด็นนี้",
                                       topic="ฐานการคำนวณ"))
                listed.add(k)
        laws = []
        for law in iss.laws:
            r = ok(law.citation_key)
            if r:
                law.label = _label(r)
                laws.append(law)
            else:
                removed.append(law.citation_key)
        iss.laws = laws
        iss.basis = ", ".join(dict.fromkeys(law.label for law in laws)) or "-"
        for ap in iss.application:
            ap.citations = keep(ap.citations)
        for p in iss.conclusion:
            p.citations = keep(p.citations)

    a.version_notes = version_notes(a, ok, state.event_date)
    humanize_keys(a, ok)

    # prose may only mention sections that some kept citation refers to
    cited_sections = {ok(k)["section_no"] for k in a.all_citations()
                      if ok(k) and "section_no" in ok(k)}
    prose = a.model_dump_json()
    uncited = sorted({m for m in SEC_MENTION.findall(prose) if m not in cited_sections})

    md = render(a, {k: short_label(ok(k)) for k in a.all_citations() if ok(k)})
    return {"answer": a, "markdown": md, "removed_citations": removed,
            "_summary": {"removed": removed, "uncited_sections_in_text": uncited,
                         "n_citations": len(a.all_citations())}}
