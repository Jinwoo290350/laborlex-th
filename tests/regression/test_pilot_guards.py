"""Guards for the Ram pilot cases beyond 2/2554 (docs/design/2026-10-06_fix_123_trace.md, decisions #18, #20).
- 2/2560 Q4: s.31 protection holds — the #20 rules must not fire, "ได้รับความคุ้มครอง" stays allowed.
- dev102 pattern (transfer ordered right after the demand, no refusal): s.121(1) stays available (dev gold: 31 + 121(1)).
- S/2563 Q1: the 480,000 computed for the employee who is not entitled is shown only as an "if entitled" amount.
Element fixtures hold ids and statuses only. Answer-record checks use local run records and skip without them."""

import json
import re
from pathlib import Path

import pytest
import yaml

from src.agent.answer import AnswerJSON, Issue, Point
from src.agent.rules.elements import answer_conflicts, forbidden_citations, resolve_elements
from src.agent.state import ElementCheck

FIXTURES = Path(__file__).parent / "fixtures"
ANSWERS = Path("data/eval/exams/ram_law4004/answers")
TAX = {i["code"]: i for i in yaml.safe_load(Path("data/processed/issues.yaml").read_text(encoding="utf-8"))}
S123, ULP, S31 = "employee_committee_and_union_protection", "unfair_labor_practices_and_disputes", "dispute_protection_s31"
K121_1 = "LRA2518:121:1:(1)"


def _resolve(llm: dict) -> dict:
    raw = {c: [ElementCheck(id=i, status=s, evidence="e") for i, s in st.items()] for c, st in llm.items()}
    return {c: {x.id: x for x in v} for c, v in resolve_elements(raw, TAX).items()}


def _point_answer(headline: str, code: str, cites: list[str]) -> AnswerJSON:
    return AnswerJSON(preliminary=[Point(headline=headline, citations=cites)],
                      issues=[Issue(code=code, question="q", consider="c", laws=[], application=[],
                                    conclusion=[Point(headline=headline, citations=cites)], opinion="o", basis="b")])


# ---------- 2/2560 Q4 ----------

def test_2560_s31_protection_is_not_overridden():
    llm = json.loads((FIXTURES / "ram_2560_fix20_elements.json").read_text(encoding="utf-8"))["llm_status"]
    r = _resolve(llm)
    assert r[S31]["5_outcome"].status != "met"                     # outcome "not protected" not reached
    assert not any(x.evidence.startswith("ระบบ:") for d in r.values() for x in d.values())   # no rule fired
    assert forbidden_citations(r, TAX) == set()
    a = _point_answer("จักรได้รับความคุ้มครองจากการถูกเลิกจ้าง ฟ้องศาลแรงงานได้ทันที", S31, ["LRA2518:31:1"])
    assert answer_conflicts(a, r, TAX) == []


def test_2560_outcome_not_shown_to_the_draft():
    from src.agent.nodes.draft import _elements_block
    from src.agent.state import AgentState
    llm = json.loads((FIXTURES / "ram_2560_fix20_elements.json").read_text(encoding="utf-8"))["llm_status"]
    raw = {c: [ElementCheck(id=i, status=s, evidence="e") for i, s in st.items()] for c, st in llm.items()}
    block = _elements_block(AgentState(question="q", elements=resolve_elements(raw, TAX)))
    assert "ผลตาม LRA2518:31:1:(3)" not in block


@pytest.mark.skipif(not (ANSWERS / "ram-law4004-2-2560-q4_C2-fix20.json").exists(), reason="local run record")
def test_2560_fix20_answer_still_says_protected():
    md = json.loads((ANSWERS / "ram-law4004-2-2560-q4_C2-fix20.json").read_text(encoding="utf-8"))["answer"]["markdown"]
    pre = md.split("## คำตอบเบื้องต้น", 1)[1].split("## ประเด็นทางกฎหมาย", 1)[0]
    assert re.search(r"(?<!ไม่)ได้รับความคุ้มครอง", pre)
    assert "10293/2546" in md and "5061/2533" not in md


# ---------- dev102 pattern: transfer during the demand, no refusal ----------

def test_transfer_without_refusal_keeps_s121_1():
    llm = {S31: {"1": "met", "2": "met", "3": "met", "4": "not_met", "5_a": "not_met", "5_b": "unknown",
                 "5_c": "not_met", "5_d": "met", "5_e": "unknown"},
           ULP: {"1": "met", "2": "met", "7": "met", "8": "unknown"}}
    r = _resolve(llm)
    assert r[ULP]["7"].status == "met" and r[S31]["5_lawful"].status == "not_met"
    assert K121_1 not in forbidden_citations(r, TAX)
    assert r[S31]["5_outcome"].status == "not_met"


# ---------- S/2563 Q1 ----------

def test_per_worker_amounts_are_conditional():
    from src.agent.nodes.draft import PER_WORKER_NOTE, issue_calc
    from src.agent.state import AgentState
    from src.calc.labor import CalcResult
    st = AgentState(question="q", calcs={
        "retirement@นายอดิเรก": CalcResult(amount=800000, steps=["ค่าชดเชย (ถ้ามีสิทธิ) = 60,000 ÷ 30 × 400 = 800,000 บาท"], citations=[]),
        "retirement@นายพิศาล": CalcResult(amount=480000, steps=["ค่าชดเชย (ถ้ามีสิทธิ) = 36,000 ÷ 30 × 400 = 480,000 บาท"], citations=[])})
    steps, _ = issue_calc(st, "retirement")
    assert steps[0] == PER_WORKER_NOTE
    assert all("(ถ้ามีสิทธิ)" in s for s in steps if "บาท" in s and "=" in s)


def test_severance_step_wording_is_conditional():
    from datetime import date
    from decimal import Decimal

    from src.calc import labor
    book = labor.RateBook.load(Path("data/processed/rates.yaml"))
    r = labor.severance(Decimal(1200), labor.Tenure.from_stated(25, 0, 0), date(2023, 9, 16), book, "36,000 ÷ 30")
    assert any("(ถ้ามีสิทธิ)" in s and "480,000" in s for s in r.steps)


@pytest.mark.skipif(not (ANSWERS / "ram-law4004-S-2563-q1_C2-fix20.json").exists(), reason="local run record")
def test_2563_fix20_answer_never_states_480000_as_received():
    md = json.loads((ANSWERS / "ram-law4004-S-2563-q1_C2-fix20.json").read_text(encoding="utf-8"))["answer"]["markdown"]
    for line in md.splitlines():
        if "480,000" in line:
            assert "(ถ้ามีสิทธิ)" in line, line
    pre = md.split("## คำตอบเบื้องต้น", 1)[1].split("## ประเด็นทางกฎหมาย", 1)[0]
    concl = " ".join(s.split("\n## ", 1)[0] for s in md.split("### ข้อสรุปประเด็นนี้")[1:])
    assert "480,000" not in pre and "480,000" not in concl
    assert "800,000" in pre
