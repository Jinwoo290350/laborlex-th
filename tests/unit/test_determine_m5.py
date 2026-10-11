"""M5 (FIX_PLAN_v2): per-employee determination of the dismissal grounds (ม.119 items, ป.พ.พ. ม.583), grounded in
holding cards, decided by majority vote in code, written to state before the draft, and enforced on the answer.
Local only: LLM, DB and card search are stubbed."""

from __future__ import annotations

import pytest

from src.agent.answer import AnswerJSON, EmployeeOutcome, Point
from src.agent.nodes import determine
from src.agent.state import AgentState, Facts, GroundCheck, IssueSel, WorkerFacts

G1, G2, C583 = "LPA2541:119:1:(1)", "LPA2541:119:1:(2)", "CCC:583:1"
GROUNDS = [(G1, "ทุจริตต่อหน้าที่…"), (G2, "จงใจทำให้นายจ้างได้รับความเสียหาย")]
CARDS = [{"key": "CASE:239/2545", "label": "คำพิพากษาศาลฎีกาที่ 239/2545", "court": "ศาลฎีกา",
          "ratio_quote": "แย่งลูกค้านายจ้าง…", "decided_by": "own_holding"},
         {"key": "CASE:6237/2545", "label": "คำพิพากษาศาลฎีกาที่ 6237/2545", "court": "ศาลฎีกา",
          "ratio_quote": "นิ่งเสียไม่รายงาน…", "decided_by": "own_holding"}]


def vote(**status) -> determine.GroundVote:
    keys = {"g1": G1, "g2": G2, "c583": C583}
    return determine.GroundVote(checks=[GroundCheck(key=keys[k], status=v, evidence=f"ev {k}",
                                                    cards=["CASE:239/2545"]) for k, v in status.items()])


@pytest.fixture(autouse=True)
def _stubs(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_ONLY", "1")
    monkeypatch.setattr(determine, "_grounds", lambda state: (GROUNDS, (C583, "ถ้าลูกจ้าง…ไม่สมแก่การปฏิบัติหน้าที่")))
    monkeypatch.setattr(determine, "_cards", lambda state, name: CARDS)


# ---------- combining votes (code decides) ----------

def test_majority_met_decides_m119():
    d = determine.combine("A", [vote(g1="not_met", g2="met", c583="met")] * 2 + [vote(g1="not_met", g2="unknown")],
                          [G1, G2], C583, {c["key"] for c in CARDS})
    assert d.m119 is True and d.ccc583 is None          # ม.583 is irrelevant once ม.119 is met
    assert [g.key for g in d.grounds if g.status == "met" and g.key != C583] == [G2]


def test_all_not_met_then_ccc583_decides_notice():
    v = vote(g1="not_met", g2="not_met", c583="met")
    d = determine.combine("B", [v, v, vote(g1="not_met", g2="not_met", c583="not_met")], [G1, G2], C583, set())
    assert d.m119 is False and d.ccc583 is True


def test_unknown_element_blocks_a_decision():
    d = determine.combine("B", [vote(g1="not_met", g2="unknown", c583="met")] * 3, [G1, G2], C583, set())
    assert d.m119 is None and d.ccc583 is None


def test_split_vote_is_unknown():
    d = determine.combine("B", [vote(g1="not_met", g2="met"), vote(g1="not_met", g2="not_met"),
                                vote(g1="not_met", g2="unknown")], [G1, G2], C583, set())
    assert next(g for g in d.grounds if g.key == G2).status == "unknown" and d.m119 is None


def test_invalid_keys_and_cards_are_dropped():
    bad = determine.GroundVote(checks=[GroundCheck(key="LPA2541:999:1", status="met", evidence="x"),
                                       GroundCheck(key=G1, status="met", evidence="y", cards=["CASE:0/0000"])])
    d = determine.combine("A", [bad] * 3, [G1, G2], C583, {"CASE:239/2545"})
    assert {g.key for g in d.grounds} == {G1, G2, C583}
    assert next(g for g in d.grounds if g.key == G1).cards == []


# ---------- the node ----------

def _state(issues=("dismissal_for_cause",), workers=("นายแพรวพราว", "นายซื่อบื้อ")) -> AgentState:
    return AgentState(question="q", issues=[IssueSel(code=c, reason="r") for c in issues],
                      facts=Facts(key_facts=["f"], workers=[WorkerFacts(name=w) for w in workers]))


def test_node_decides_each_employee(monkeypatch):
    plan = {"นายแพรวพราว": vote(g1="not_met", g2="met"), "นายซื่อบื้อ": vote(g1="not_met", g2="not_met", c583="met")}
    prompts = []

    def fake(prompt, schema, **k):
        prompts.append(prompt)
        return next(v for n, v in plan.items() if f"คือ {n}" in prompt)   # every prompt lists all workers
    monkeypatch.setattr(determine, "generate_json", fake)
    out = determine.determine_grounds.__wrapped__(_state())
    by = {d.name: d for d in out["determinations"]}
    assert by["นายแพรวพราว"].m119 is True and by["นายซื่อบื้อ"].m119 is False and by["นายซื่อบื้อ"].ccc583 is True
    assert len(prompts) == 2 * determine.P("determine.votes")
    assert all("CASE:239/2545" in p for p in prompts)       # cards are put in front of the model


def test_node_skips_without_a_dismissal_issue(monkeypatch):
    monkeypatch.setattr(determine, "generate_json", lambda *a, **k: pytest.fail("no LLM call expected"))
    out = determine.determine_grounds.__wrapped__(_state(issues=("overtime_and_holiday_pay",)))
    assert out.get("determinations", []) == []


def test_graph_runs_determine_before_calculate():
    from src.agent import graph
    names = [n for n, _ in graph.STEPS]
    assert names.index("check_elements") < names.index("determine_grounds") < names.index("calculate")
    assert "determine_grounds" in graph.CRITICAL


# ---------- the answer must follow the determinations ----------

def test_answer_employees_follow_determinations():
    from src.agent.ledger import apply_determinations
    st = _state()
    st.determinations = [
        determine.combine("นายแพรวพราว", [vote(g1="not_met", g2="met")] * 3, [G1, G2], C583, set()),
        determine.combine("นายซื่อบื้อ", [vote(g1="not_met", g2="not_met", c583="met")] * 3, [G1, G2], C583, set())]
    a = AnswerJSON(preliminary=[Point(headline="x")], issues=[],
                   employees=[EmployeeOutcome(name="นายซื่อบื้อ", m119_applies=True, found_ground_keys=[G1],
                                              alleged_ground_keys=[G1, G2])])
    apply_determinations(a, st)
    by = {e.name: e for e in a.employees}
    assert by["นายแพรวพราว"].m119_applies is True and by["นายแพรวพราว"].found_ground_keys == [G2]
    assert by["นายซื่อบื้อ"].m119_applies is False and by["นายซื่อบื้อ"].ccc583_applies is True
    assert by["นายซื่อบื้อ"].found_ground_keys == [] and by["นายซื่อบื้อ"].alleged_ground_keys == [G1, G2]


def test_draft_prompt_shows_determinations(monkeypatch):
    from src.agent.nodes import draft
    st = _state()
    st.determinations = [determine.combine("นายซื่อบื้อ", [vote(g1="not_met", g2="not_met", c583="met")] * 3,
                                           [G1, G2], C583, {"CASE:6237/2545"})]
    block = draft._determinations_block(st)
    assert "นายซื่อบื้อ" in block and "583" in block and "ไม่เข้ามาตรา 119" in block
