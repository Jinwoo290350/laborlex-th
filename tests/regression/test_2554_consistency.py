"""2/2554 Q4 regression (docs/benchmarks/exam_regression_spec_2026-10-06.yaml, decisions #20).

Reproduces the C2 fix123 failure from the run's own element statuses (fixtures/ram_2554_fix123_elements.json, ids and
statuses only): the lawful-order elements are right, but the same "conflict" fact still made the s.121(1) causation
elements met and the answer concluded "ได้รับความคุ้มครอง" + s.121(1). Expected after #20: the s.121(1) ground is
excluded by the system, the outcome element states the model answer's result, and an answer that still says
"protected" or cites s.121(1) is flagged and its s.121(1) citations are removed. Local, no Gemini."""

import json
from pathlib import Path

import yaml

from src.agent.answer import AnswerJSON, Issue, Point
from src.agent.rules.elements import answer_conflicts, forbidden_citations, resolve_elements
from src.agent.state import ElementCheck

FIX = json.loads((Path(__file__).parent / "fixtures" / "ram_2554_fix123_elements.json").read_text(encoding="utf-8"))
TAX = {i["code"]: i for i in yaml.safe_load(Path("data/processed/issues.yaml").read_text(encoding="utf-8"))}
S123, ULP, S31 = "employee_committee_and_union_protection", "unfair_labor_practices_and_disputes", "dispute_protection_s31"
K121_1 = "LRA2518:121:1:(1)"


def _resolved(llm=FIX["llm_status"]):
    raw = {c: [ElementCheck(id=i, status=s, evidence="e") for i, s in st.items()] for c, st in llm.items()}
    return {c: {x.id: x for x in v} for c, v in resolve_elements(raw, TAX).items()}


def test_s121_1_ground_excluded_when_the_order_was_lawful_and_not_obstructive():
    r = _resolved()
    assert r[S123]["9b_lawful"].status == "met"
    assert r[S123]["3"].status == "not_met" and r[S123]["3"].evidence.startswith("ระบบ")
    assert r[ULP]["7"].status != "met"
    assert K121_1 in forbidden_citations(_resolved(), TAX)


def test_outcome_element_states_not_protected_but_warning_required():
    out = _resolved()[S123]["9b_outcome"]
    q = next(e["question"] for e in TAX[S123]["elements"] if e["id"] == "9b_outcome")
    assert out.status == "met"
    assert "ไม่ได้รับความคุ้มครอง" in q and "ตักเตือนเป็นหนังสือ" in q


def test_no_exclusion_when_obstruction_unknown_or_order_not_lawful():
    for change in ({"9b_d": "unknown"}, {"9b_d": "met"}, {"9b_b": "not_met", "9b_c": "not_met"}):
        llm = {c: dict(v) for c, v in FIX["llm_status"].items()}
        llm[S123].update(change)
        r = _resolved(llm)
        assert r[S123]["3"].status == "met" and r[ULP]["7"].status == "met", change
        assert K121_1 not in forbidden_citations(r, TAX)
        assert r[S123]["9b_outcome"].status != "met"


def _answer(prelim: str, concl: dict[str, tuple[str, list[str]]]) -> AnswerJSON:
    return AnswerJSON(
        preliminary=[Point(headline=prelim, citations=["LRA2518:123:1", K121_1])],
        issues=[Issue(code=c, question="q", consider="c", laws=[], application=[],
                      conclusion=[Point(headline=h, citations=k)], opinion="o", basis="b")
                for c, (h, k) in concl.items()])


def test_guard_flags_the_fix123_answer_shape():
    # same shape as the fix123 output: "protected" in the s.123 conclusion, s.121(1) in preliminary + ULP conclusion
    a = _answer("ลูกจ้างได้รับความคุ้มครอง เลิกจ้างทันทีไม่ได้ และเป็นการกระทำอันไม่เป็นธรรม",
                {S123: ("ลูกจ้างได้รับความคุ้มครอง และนายจ้างเลิกจ้างทันทีไม่ได้", ["LRA2518:123:1"]),
                 ULP: ("การเลิกจ้างเป็นการกระทำอันไม่เป็นธรรม", [K121_1, "LRA2518:124:1"])})
    kinds = sorted({c.kind for c in answer_conflicts(a, _resolved(), TAX)})
    assert kinds == ["forbidden_citation", "outcome_contradicted"]


def test_guard_accepts_the_expected_answer():
    a = _answer("ลูกจ้างไม่ได้รับความคุ้มครองเพราะฝ่าฝืนคำสั่งอันชอบด้วยกฎหมาย แต่นายจ้างต้องตักเตือนเป็นหนังสือก่อน",
                {S123: ("ไม่ได้รับความคุ้มครอง แต่เลิกจ้างทันทีไม่ได้", ["LRA2518:123:1:(3)"])})
    a.preliminary[0].citations = ["LRA2518:123:1:(3)"]
    assert answer_conflicts(a, _resolved(), TAX) == []


# ---------- pipeline wiring (⑨ revise, ⑩ strip) — no Gemini: verifier and LLM are stubbed ----------

def _state(answer):
    from src.agent.state import AgentState
    raw = {c: [ElementCheck(id=i, status=s, evidence="e") for i, s in st.items()] for c, st in FIX["llm_status"].items()}
    return AgentState(question="q", elements=resolve_elements(raw, TAX), drafts=[answer],
                      selected={S123: ["LRA2518:123:1"], ULP: ["LRA2518:121:1", "LRA2518:124:1"]})


def _bad():
    return _answer("ลูกจ้างได้รับความคุ้มครอง และเป็นการกระทำอันไม่เป็นธรรม",
                   {S123: ("ลูกจ้างได้รับความคุ้มครอง", ["LRA2518:123:1"]), ULP: ("ไม่เป็นธรรม", [K121_1])})


def test_verify_revises_a_draft_that_contradicts_the_system(monkeypatch):
    from src.agent.nodes import draft as D
    perfect = D.Verdict(complete=1, supported=1, consistent=1, focused=1, feedback="")
    monkeypatch.setattr(D, "_verify", lambda state, d: perfect)          # the LLM verifier scored fix123 1.0
    seen = {}

    def fake_llm(prompt, schema, **kw):
        seen["prompt"] = prompt
        fixed = _answer("ลูกจ้างไม่ได้รับความคุ้มครอง แต่ต้องตักเตือนเป็นหนังสือก่อน",
                        {S123: ("ไม่ได้รับความคุ้มครอง", ["LRA2518:123:1"])})
        fixed.preliminary[0].citations = ["LRA2518:123:1:(3)"]
        return fixed
    monkeypatch.setattr(D, "generate_json", fake_llm)
    monkeypatch.setattr(D, "draft_prompt", lambda state, feedback="": feedback)
    out = D.verify_select(_state(_bad()))
    summary = out["trace"][0]["summary"]
    assert summary["revised"] and summary["conflicts"] and not summary["conflicts_left"]
    assert K121_1 in seen["prompt"] and "ได้รับความคุ้มครอง" in seen["prompt"]


def _db_ok():
    try:
        from src.index.db import connect
        with connect() as c:
            return c.execute("SELECT count(*) FROM provisions").fetchone()[0] > 0
    except Exception:  # noqa: BLE001
        return False


import pytest


@pytest.mark.skipif(not _db_ok(), reason="Legal Index not available")
def test_validate_never_keeps_the_excluded_s121_1_citation():
    from src.agent.nodes.draft import validate_cites
    st = _state(_bad())
    st.answer = _bad()
    out = validate_cites(st)
    keys = {k for p in out["answer"].preliminary for k in p.citations}
    keys |= {k for i in out["answer"].issues for p in i.conclusion for k in p.citations}
    assert K121_1 not in keys and "[ม.121 (1)" not in out["markdown"]
    assert "LRA2518:123:1" in keys                      # other citations untouched


def test_outcome_shown_to_the_draft_only_when_met():
    from src.agent.nodes.draft import _elements_block
    from src.agent.state import AgentState
    st = _state(_bad())
    assert "ผลตาม LRA2518:123:1:(3)" in _elements_block(st)
    st.elements[S123] = [c if c.id != "9b_outcome" else c.model_copy(update={"status": "unknown"})
                         for c in st.elements[S123]]
    assert "ผลตาม LRA2518:123:1:(3)" not in _elements_block(AgentState(question="q", elements=st.elements))
