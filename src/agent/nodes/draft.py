"""⑧ draft_answers · ⑨ verify_select · ⑩ validate_cites"""

from __future__ import annotations

import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from pathlib import Path

from pydantic import BaseModel, Field

from src.agent.answer import AnswerJSON
from src.agent.nodes.common import fmt_facts, fmt_provision, prompt, taxonomy, traced
from src.agent.render import render
from src.agent.state import AgentState
from src.index import tools
from src.index.bm25 import tokenize
from src.llm import generate_json

N_DRAFTS = 2
N_EXAMPLES = 2
REVISE_BELOW = 0.75
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


def pick_examples(state: AgentState, n: int = N_EXAMPLES) -> list[dict]:
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


def _provisions_block(state: AgentState) -> str:
    seen, lines = set(), []
    for code, keys in state.selected.items():
        by_key = {r["citation_key"]: r for r in state.candidates.get(code, [])}
        for k in keys:
            if k in by_key and k not in seen:
                seen.add(k)
                lines.append(fmt_provision(by_key[k], 2500))
    return "\n".join(lines)


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
    return "\n\n".join(f"คำถาม: {r['question']}\nเฉลย: {r['gold_answer']}" for r in ex) or "-"


def draft_prompt(state: AgentState, feedback: str = "") -> str:
    _, body = prompt("draft_answer")
    p = body.format(question=state.question,
                    asked="\n".join(state.facts.asked if state.facts else []),
                    facts=fmt_facts(state), issues=_issue_block(state),
                    provisions=_provisions_block(state), elements=_elements_block(state),
                    calcs=_calcs_block(state), examples=_examples_block(state))
    if feedback:
        p += f"\n\n## ข้อที่ต้องแก้จากร่างก่อน\n{feedback}"
    return p


@traced("draft_answers")
def draft_answers(state: AgentState) -> dict:
    p = draft_prompt(state)
    with ThreadPoolExecutor(N_DRAFTS) as ex:
        drafts = list(ex.map(
            lambda i: generate_json(p, AnswerJSON, name="draft", temperature=0.0 if i == 0 else 0.7,
                                    seed=i),
            range(N_DRAFTS)))
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
    with ThreadPoolExecutor(N_DRAFTS) as ex:
        verdicts = list(ex.map(lambda d: _verify(state, d), state.drafts))
    best = max(range(len(verdicts)), key=lambda i: verdicts[i].score())
    answer, v = state.drafts[best], verdicts[best]
    revised = False
    if v.worst() < REVISE_BELOW and v.feedback.strip():
        answer = generate_json(draft_prompt(state, v.feedback), AnswerJSON, name="revise")
        revised = True
    scores = [v.model_dump() for v in verdicts]
    return {"answer": answer, "draft_scores": scores,
            "_summary": {"picked": best, "scores": [round(v.score(), 2) for v in verdicts],
                         "revised": revised}}


# ---------- ⑩ validate citations ----------

SEC_MENTION = re.compile(r"(?:มาตรา|ม\.)\s*(\d+(?:/\d+)?)")


def _label(r: dict) -> str:
    if r["section_no"] == "0":            # instrument without numbered clauses
        return r["law_name"]
    para = r["paragraph_no"]
    unit = "ข้อ" if r["level"] >= 3 else "มาตรา"
    lab = f"{unit} {r['section_no']}"
    if para and para > 1:
        lab += f" วรรค{THAI_ORD[para] if para < len(THAI_ORD) else para}"
    if r.get("sub_no"):
        lab += f" {r['sub_no']}"
    return f"{lab} {r['law_name']}"


def allowed_keys(state: AgentState) -> set[str]:
    """Citations the answer may use: provisions ⑤ selected, plus those a calculation used."""
    keys = {k for ks in state.selected.values() for k in ks}
    keys |= {k for c in state.calcs.values() for k in c.citations}
    return keys


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
            cache_[key] = tools.get_provision(key, state.event_date)   # None if not in force
        return cache_[key]

    def keep(keys: list[str]) -> list[str]:
        good = [k for k in keys if ok(k)]
        removed.extend(k for k in keys if not ok(k))
        return good

    for p in a.preliminary:
        p.citations = keep(p.citations)
    for iss in a.issues:
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

    # prose may only mention sections that some kept citation refers to
    cited_sections = {ok(k)["section_no"] for k in a.all_citations() if ok(k)}
    prose = a.model_dump_json()
    uncited = sorted({m for m in SEC_MENTION.findall(prose) if m not in cited_sections})

    md = render(a)
    return {"answer": a, "markdown": md, "removed_citations": removed,
            "_summary": {"removed": removed, "uncited_sections_in_text": uncited,
                         "n_citations": len(a.all_citations())}}
