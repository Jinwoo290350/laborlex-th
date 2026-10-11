"""M5 part 2 (docs/decisions.md #23–#27): wage items, tenure through the dismissal date (ป.พ.พ. 193/3, 193/5),
the minimum-wage floor for severance and notice pay, the per-period minimum-wage shortfall (a code-triggered issue)
and ม.9 interest as rules from the rate book. Uses the local Legal Index for provision keys; no LLM."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from src.agent.state import AgentState, Facts, IssueSel, PayItem


def _db_ok() -> bool:
    try:
        from src.agent.nodes.decide import m119_keys
        m119_keys()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _db_ok(), reason="Legal Index not loaded")

Q = "นายจ้างเลิกจ้างลูกจ้างโดยไม่จ่ายค่าชดเชย และมิได้บอกกล่าวล่วงหน้า"


def _facts(province: str | None = "กรุงเทพมหานคร", salary: float = 10000) -> Facts:
    items = [PayItem(name="เงินเดือน", amount=salary, period="month", purpose="work", basis="fixed"),
             PayItem(name="ค่าเช่าบ้าน", amount=1000, period="month", purpose="welfare", basis="fixed",
                     regardless_of_actual_cost=True),
             PayItem(name="ค่าน้ำมันรถส่วนเหมาจ่าย", amount=500, period="month", purpose="expense", basis="fixed",
                     regardless_of_actual_cost=True, requires_proof=False),
             PayItem(name="ค่าน้ำมันรถส่วนเบิกตามจริง", amount=500, period="month", purpose="expense",
                     basis="actual_cost", requires_proof=True)]
    return Facts(start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), pay_days=[15, 31], pay_items=items,
                 workplace_province=province, key_facts=["f"])


def _calc(facts: Facts, issues=("severance_pay",)) -> dict:
    from src.agent.nodes import decide
    st = AgentState(question=Q, facts=facts, event_date=date(2026, 12, 31),
                    issues=[IssueSel(code=c, reason="r") for c in issues])
    return decide.calculate.__wrapped__(st)


def test_tenure_runs_through_the_dismissal_date_by_ccc193():
    out = _calc(_facts())
    sev = out["termination"].severance
    assert any("193/5" in s for s in sev.steps) and any(k.startswith("CCC:193/") for k in sev.citations)
    assert any("วันที่การเลิกจ้างมีผล" in s for s in sev.steps)       # the D2 assumption is stated


def test_minimum_wage_floor_for_severance_and_notice():
    t = _calc(_facts())["termination"]
    assert t.severance.amount == D("36000.00")       # 400 × 90, not 10,500 ÷ 30 × 90 = 31,500
    assert t.notice_pay.amount == D("6000.00")       # 400 × 15
    assert t.final_wage.amount == D("5250.00")       # wages earned at the agreed rate; the gap is the shortfall
    assert any("ต่ำกว่าอัตราค่าจ้างขั้นต่ำ" in s for s in t.wage_steps)
    assert "LPA2541:90:1" in t.citations


def test_shortfall_is_a_triggered_issue_with_its_own_calculation():
    out = _calc(_facts())
    mw = out["calcs"]["minimum_wage"]
    assert mw.amount == D("18000.00")                 # (12,000 − 10,500) × 12, per half-month period
    assert "minimum_wage" in [i.code for i in out["issues"]]


def test_no_floor_and_no_issue_at_or_above_the_minimum():
    out = _calc(_facts(salary=11500))                 # 11,500 + 500 = 12,000 = 400 × 30
    assert out["termination"].severance.amount == D("36000.00")
    assert "minimum_wage" not in out["calcs"]
    assert "minimum_wage" not in [i.code for i in out.get("issues", [])]


def test_unknown_province_means_no_floor_and_a_recorded_reason():
    out = _calc(_facts(province=None))
    assert out["termination"].severance.amount == D("31500.00")
    assert "minimum_wage" in out["_summary"]["skipped"]


def test_interest_rule_when_money_was_withheld():
    out = _calc(_facts())
    it = out["calcs"]["interest_m9"]
    assert "LPA2541:9:1" in it.citations and "LPA2541:9:2" in it.citations
    assert any("15" in s for s in it.steps) and any("เหตุผลอันสมควร" in s for s in it.steps)


def test_taxonomy_has_the_triggered_issue():
    from src.agent.nodes.common import taxonomy
    assert "LPA2541:90" in taxonomy()["minimum_wage"]["primary_provisions"]


# ---------- one-line contrary notes with the calculator's alternative figure (decisions #23, #24, #27) ----------

def test_housing_note_gives_the_alternative_base():
    t = _calc(_facts())["termination"]
    note = next(s for s in t.wage_steps if "ค่าเช่าบ้าน" in s and "หาก" in s)
    assert "11,500" in note and "172/2524" in note


def test_tenure_boundary_note_gives_the_shorter_branch():
    sev = _calc(_facts())["termination"].severance
    note = next(s for s in sev.steps if s.startswith("หมายเหตุ") and "30 ธ.ค." in s)
    assert "30 วัน" in note and "12,000" in note        # 400 × 30 on the minimum-wage base
