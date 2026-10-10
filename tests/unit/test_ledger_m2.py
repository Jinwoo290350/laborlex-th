"""M2 (FIX_PLAN_v2): ป.พ.พ. ม.583 route for notice, asked issues exempt from the issue cap, and the
per-employee ledger that the payment table and a prose consistency check both read. Local only: no LLM, no DB
(key lookups are stubbed)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from src.agent.answer import AnswerJSON, EmployeeOutcome, Point
from src.calc import labor

KEYS = {"m119": "LPA2541:119:1", "notice_exempt": "LPA2541:17:4", "final": "LPA2541:70:2",
        "ccc583": "CCC:583:1"}


@pytest.fixture(autouse=True)
def _stub_keys(monkeypatch):
    from src.agent.nodes import decide
    monkeypatch.setattr(decide, "m119_keys", lambda: dict(KEYS))
    monkeypatch.setenv("LLM_CACHE_ONLY", "1")


def _termination(sev="31500", notice="5250", final="5250") -> labor.Termination:
    c = lambda amt, key: labor.CalcResult(amount=D(amt), steps=[f"step {amt}"], citations=[key])
    return labor.Termination(severance=c(sev, "LPA2541:118:1:(2)"), notice_pay=c(notice, "LPA2541:17/1:1"),
                             final_wage=c(final, "LPA2541:70:2"), effective=date(2027, 1, 15),
                             wage_steps=["ฐานค่าจ้างต่อเดือน = 10,500 บาท"], citations=["LPA2541:118:1:(2)"])


# ---------- calculator: dismissal outcome ----------

def test_ccc583_no_notice_but_severance():
    got = labor.apply_dismissal(D(31500), D(5250), D(5250), m119=False, ccc583=True, keys=KEYS)
    assert (got.severance, got.notice_pay, got.final_wage) == (D(31500), D(0), D(5250))
    assert KEYS["ccc583"] in got.citations and KEYS["notice_exempt"] in got.citations


def test_m119_removes_severance_and_notice():
    got = labor.apply_dismissal(D(31500), D(5250), D(5250), m119=True, ccc583=False, keys=KEYS)
    assert (got.severance, got.notice_pay, got.final_wage) == (D(0), D(0), D(5250))


def test_neither_ground_pays_everything():
    got = labor.apply_dismissal(D(31500), D(5250), D(5250), m119=False, ccc583=False, keys=KEYS)
    assert (got.severance, got.notice_pay, got.final_wage) == (D(31500), D(5250), D(5250))


def test_apply_m119_unchanged():
    old = labor.apply_m119(D(31500), D(5250), D(5250), True, KEYS)
    assert (old.severance, old.notice_pay) == (D(0), D(0))
    old = labor.apply_m119(D(31500), D(5250), D(5250), False, KEYS)
    assert (old.severance, old.notice_pay) == (D(31500), D(5250))


# ---------- ledger: one record per employee; the payment table reads only it ----------

def _answer(*emps: EmployeeOutcome, prelim: list[str] = ()) -> AnswerJSON:
    return AnswerJSON(preliminary=[Point(headline=h, citations=[]) for h in prelim], issues=[],
                      employees=list(emps))


def test_ledger_per_employee_records():
    from src.agent.ledger import build_ledger
    a = _answer(EmployeeOutcome(name="นายแพรวพราว", m119_applies=True, found_ground_keys=["LPA2541:119:1:(2)"]),
                EmployeeOutcome(name="นายซื่อบื้อ", m119_applies=False, ccc583_applies=True))
    led = build_ledger(_termination(), a, KEYS)
    rec = {r.name: r for r in led.employees}
    assert (rec["นายแพรวพราว"].severance, rec["นายแพรวพราว"].notice_pay) == (D(0), D(0))
    assert (rec["นายซื่อบื้อ"].severance, rec["นายซื่อบื้อ"].notice_pay) == (D(31500), D(0))
    assert rec["นายซื่อบื้อ"].notice_exempt and not rec["นายซื่อบื้อ"].severance_exempt
    assert led.total == D(5250) + D(31500) + D(5250)


def test_payment_table_follows_ledger_for_ccc583():
    from src.agent.nodes import draft
    a = _answer(EmployeeOutcome(name="นายซื่อบื้อ", m119_applies=False, ccc583_applies=True))
    draft.payments(a, _termination(), lambda k: {"citation_key": k, "label": k, "section_no": "583"})
    row = a.payments[0]
    assert row.notice_pay == "0" and row.severance == "31,500" and row.total == "36,750"
    assert "583" in row.note
    assert "CCC:583:1" in a.payments_citations


# ---------- prose must agree with the ledger ----------

def test_prose_notice_contradiction_is_flagged():
    from src.agent.ledger import build_ledger, prose_conflicts
    a = _answer(EmployeeOutcome(name="นายซื่อบื้อ", m119_applies=False, ccc583_applies=True),
                prelim=["นายซื่อบื้อมีสิทธิได้รับสินจ้างแทนการบอกกล่าวล่วงหน้า 5,250 บาท"])
    led = build_ledger(_termination(), a, KEYS)
    kinds = {c.kind for c in prose_conflicts(a, led, question="")}
    assert "notice_contradicts_ledger" in kinds


def test_prose_unsupported_amount_is_flagged_but_question_amounts_pass():
    from src.agent.ledger import build_ledger, prose_conflicts
    a = _answer(EmployeeOutcome(name="นายซื่อบื้อ", m119_applies=False),
                prelim=["ค่าชดเชย 31,500 บาท และค่าเช่าบ้านเดือนละ 1,000 บาท", "รวมเงินอื่น 9,999 บาท"])
    led = build_ledger(_termination(), a, KEYS)
    conf = prose_conflicts(a, led, question="ค่าเช่าบ้านเดือนละ 1,000 บาท")
    assert [c.kind for c in conf] == ["amount_not_in_ledger"] and "9,999" in conf[0].detail


def test_consistent_prose_has_no_conflicts():
    from src.agent.ledger import build_ledger, prose_conflicts
    a = _answer(EmployeeOutcome(name="นายซื่อบื้อ", m119_applies=False, ccc583_applies=True),
                prelim=["นายซื่อบื้อได้ค่าชดเชย 31,500 บาท แต่ไม่มีสิทธิได้รับสินจ้างแทนการบอกกล่าวล่วงหน้า"])
    led = build_ledger(_termination(), a, KEYS)
    assert prose_conflicts(a, led, question="") == []


def test_verify_select_revises_on_ledger_conflict(monkeypatch):
    from src.agent.nodes import draft
    from src.agent.state import AgentState
    bad = _answer(EmployeeOutcome(name="นายซื่อบื้อ", m119_applies=False, ccc583_applies=True),
                  prelim=["นายซื่อบื้อมีสิทธิได้รับสินจ้างแทนการบอกกล่าวล่วงหน้า 5,250 บาท"])
    good = _answer(EmployeeOutcome(name="นายซื่อบื้อ", m119_applies=False, ccc583_applies=True),
                   prelim=["นายซื่อบื้อไม่มีสิทธิได้รับสินจ้างแทนการบอกกล่าวล่วงหน้า"])
    fine = draft.Verdict(complete=1, supported=1, consistent=1, focused=1, feedback="")
    revised = []
    monkeypatch.setattr(draft, "_verify", lambda state, d: fine)
    monkeypatch.setattr(draft, "draft_prompt", lambda state, feedback="": feedback)
    monkeypatch.setattr(draft, "generate_json", lambda p, schema, **k: revised.append(p) or good)
    st = AgentState(question="q", drafts=[bad], termination=_termination())
    out = draft.verify_select.__wrapped__(st)
    assert revised and "สินจ้างแทนการบอกกล่าว" in revised[0]
    assert out["answer"] is good and out["_summary"]["conflicts_left"] == []


# ---------- asked issues are not cut by the cap ----------

def test_asked_issue_not_truncated(monkeypatch):
    from src.agent.nodes import understand
    from src.agent.state import AgentState, Facts, IssueSel
    codes = ["employer_liability_and_representatives", "definition_of_wages", "dismissal_for_cause",
             "severance_pay", "advance_notice"]
    monkeypatch.setattr(understand, "generate_json",
                        lambda *a, **k: understand._Issues(issues=[IssueSel(code=c, reason="r") for c in codes]))
    st = AgentState(question="q", facts=Facts(asked=["ห้างฯ ต้องบอกกล่าวล่วงหน้าในการเลิกสัญญาหรือไม่"]))
    out = understand.spot_issues.__wrapped__(st)
    assert [i.code for i in out["issues"]] == codes
    assert out["_summary"]["truncated"] == [] and out["_summary"]["mandatory"] == ["advance_notice"]


def test_unasked_issue_still_truncated(monkeypatch):
    from src.agent.nodes import understand
    from src.agent.state import AgentState, Facts, IssueSel
    codes = ["employer_liability_and_representatives", "definition_of_wages", "dismissal_for_cause",
             "severance_pay", "advance_notice"]
    monkeypatch.setattr(understand, "generate_json",
                        lambda *a, **k: understand._Issues(issues=[IssueSel(code=c, reason="r") for c in codes]))
    st = AgentState(question="q", facts=Facts(asked=["ห้างฯ ต้องจ่ายค่าชดเชยหรือไม่"]))
    out = understand.spot_issues.__wrapped__(st)
    assert "advance_notice" not in [i.code for i in out["issues"]]
    assert out["_summary"]["truncated"] == ["advance_notice"]


# ---------- Huay Khwang replay: the stored state has no contradiction ----------

HK = Path("data/processed/runs/2026-10-09_huaykhwang_fresh/state.json")


@pytest.mark.skipif(not HK.exists(), reason="local evidence run not present")
def test_huaykhwang_replay_has_no_ledger_conflicts():
    from src.agent.ledger import build_ledger, prose_conflicts
    from src.agent.state import AgentState
    st = AgentState.model_validate(json.loads(HK.read_text(encoding="utf-8")))
    led = build_ledger(st.termination, st.answer, KEYS)
    assert prose_conflicts(st.answer, led, question=st.question) == []
