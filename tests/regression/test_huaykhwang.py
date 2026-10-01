"""Regression case หจก. ห้วยขวางขนส่ง (tests/regression/huaykhwang.yaml). No LLM calls.

Expectations marked `ambiguous` in the YAML are PINNED current behaviour (so a change is
noticed), not legal truth — see the `question` field of each for what an expert must confirm.
"""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
import yaml

from src.agent.state import AgentState, Facts, IssueSel, PayItem
from src.calc import labor

CASE = yaml.safe_load(Path(__file__).with_name("huaykhwang.yaml").read_text(encoding="utf-8"))
F, X = CASE["facts"], CASE["expect"]
ITEMS = [PayItem(**i) for i in F["pay_items"]]
BOOK = labor.RateBook.load(Path("data/processed/rates.yaml"))
END = F["end_date"]


def _db_ok() -> bool:
    try:
        from src.index.db import connect
        with connect() as c:
            return c.execute("SELECT count(*) FROM provisions").fetchone()[0] > 0
    except Exception:  # noqa: BLE001
        return False


needs_db = pytest.mark.skipif(not _db_ok(), reason="Legal Index not loaded")


def _status(item: PayItem) -> str:
    return labor.wage_item_status(item.purpose, item.basis, item.conditional)


# 1. ม.5 classification -------------------------------------------------------------
def test_m5_clear_items():
    salary, _, _, reimbursed = ITEMS
    assert (_status(salary) == "wage") is X["m5_salary"]["wage"]
    assert (_status(reimbursed) == "wage") is X["m5_fuel_reimbursed"]["wage"]


def test_m5_ambiguous_items_pinned():
    _, rent, fuel_fixed, _ = ITEMS
    assert (_status(rent) == "wage") is X["m5_rent"]["pinned_wage"], X["m5_rent"]["question"]
    assert (_status(fuel_fixed) == "wage") is X["m5_fuel_fixed"]["pinned_wage"], X["m5_fuel_fixed"]["question"]


def test_m5_every_item_has_a_stated_classification():
    b = labor.wage_base(ITEMS, "k")
    for it in ITEMS:
        assert any(s.startswith(it.name) for s in b.steps), it.name
    assert any("เบิกตามที่จ่ายจริง" in s for s in b.steps if s.startswith(ITEMS[3].name))


# 2. ม.118 tenure + tier ----------------------------------------------------------------
def test_m118_tenure_reaches_one_year_tier():
    t = labor.Tenure.from_dates(F["start_date"], END)
    assert t.years == X["m118_tenure"]["years"]
    tier = next(x for x in BOOK.get("severance_tiers", END).tiers
                if t.reaches(x.min) and (x.max is None or not t.reaches(x.max)))
    assert tier.value == X["m118_tenure"]["tier_days"]


@pytest.mark.parametrize("base", ["10000", "11000", "11500"])
def test_m118_severance_for_each_possible_wage_base(base):
    t = labor.Tenure.from_dates(F["start_date"], END)
    daily = labor.to_daily_wage(D(base), "month", END, BOOK, exact=True)
    r = labor.severance(daily.amount, t, END, BOOK)
    assert r.amount == X["m118_severance_by_base"][base]


# 4–5. ม.17 notice, ม.17/1 pay in lieu, ม.70 final period ----------------------------------
def test_m17_effective_date_notice_pay_and_final_period_are_separate():
    daily = labor.to_daily_wage(D(10000), "month", END, BOOK, exact=True)
    keys = {"notice": "N", "in_lieu": "L", "final": "F"}
    n = labor.notice_and_final_pay(END, F["pay_days"], D(10000), daily.amount, keys)
    assert n.effective == X["m17_effective_date"]["date"]
    assert n.notice_pay.amount == X["m17_notice_pay"]["amount_base_10000"]
    assert f"10,000 ÷ 30 × {X['m17_notice_pay']['days']} วัน" in n.notice_pay.steps[-1]
    assert n.final_period.amount == X["m70_final_period"]["amount_base_10000"]
    assert n.notice_pay.citations == ["N", "L"] and n.final_period.citations == ["F"]


# 3. ม.119 per person — needs the LLM ------------------------------------------------------
@pytest.mark.skip(reason="ม.119 per-person analysis is drafted by the LLM; needs one recorded run "
                         "(~10 THB) — see expect.m119 in huaykhwang.yaml")
def test_m119_separate_analysis_per_employee():
    pass


# 5–6. through the calculate node and ⑩ (DB, no LLM) ---------------------------------------
def _state() -> AgentState:
    from src.agent.nodes.decide import calculate
    st = AgentState(question="reg-huaykhwang",
                    facts=Facts(start_date=F["start_date"], end_date=END, pay_days=F["pay_days"],
                                pay_items=ITEMS),
                    issues=[IssueSel(code="severance_pay", reason="t"),
                            IssueSel(code="advance_notice", reason="t")])
    st.calcs = calculate(st)["calcs"]
    return st


@needs_db
def test_calculate_node_gives_separate_amounts():
    st = _state()
    sev, notice = st.calcs["severance_pay"], st.calcs["advance_notice"]
    assert sev.amount == X["m118_severance_by_base"]["10000"]          # pinned base: salary only
    assert notice.amount == X["m17_notice_pay"]["amount_base_10000"]
    text = "\n".join(notice.steps)
    assert "▶ ค่าจ้างงวดสุดท้าย" in text and "▶ สินจ้างแทนการบอกกล่าวล่วงหน้า" in text


@needs_db
def test_answer_shows_calc_provisions_and_no_internal_keys():
    from src.agent.answer import AnswerJSON
    from src.agent.nodes.draft import KEY_IN_TEXT, validate_cites
    st = _state()
    issue = {"question": "q", "consider": "-", "application": [], "conclusion": [{"headline": "h"}],
             "opinion": "o", "basis": "b", "laws": [],
             # an LLM copy with an internal key in it — ⑩ must replace it with the calculator's steps
             "calculation": ["ค่าชดเชย = 999 บาท (อ้าง LPA2541:118:1:(2))"]}
    st.answer = AnswerJSON.model_validate({"preliminary": [{"headline": "h"}], "issues": [
        {**issue, "code": "severance_pay"}, {**issue, "code": "advance_notice"}]})
    out = validate_cites(st)
    md, a = out["markdown"], out["answer"]
    assert not KEY_IN_TEXT.search(md), KEY_IN_TEXT.search(md)
    assert "999" not in md
    sev, notice = a.issues
    assert sev.calculation == st.calcs["severance_pay"].steps
    assert set(sev.calculation_citations) == set(st.calcs["severance_pay"].citations)
    assert {law.citation_key for law in notice.laws} >= set(st.calcs["advance_notice"].citations)
    assert md.count("บทบัญญัติที่ใช้ในการคำนวณ") == 2
    assert "ม.17/1" in md and "ม.70 วรรคสอง" in md and "ม.5 “ค่าจ้าง”" in md


def test_fixture_dates():
    assert F["start_date"] == date(2026, 1, 1) and END == date(2026, 12, 31)
