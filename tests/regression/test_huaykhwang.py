"""Regression case หจก. ห้วยขวางขนส่ง (tests/regression/huaykhwang.yaml). No LLM calls.

Legal conclusions and authorities are recorded in the YAML (provisional, from Frank's
Supreme Court research 2026-10-02). Whether ม.119 applies to each employee is taken from the
fixture: that judgement is made by the LLM in production and is not exercised here.
"""
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
BASE = D(X["wage_base_monthly"])


def _db_ok() -> bool:
    try:
        from src.index.db import connect
        with connect() as c:
            return c.execute("SELECT count(*) FROM provisions").fetchone()[0] > 0
    except Exception:  # noqa: BLE001
        return False


needs_db = pytest.mark.skipif(not _db_ok(), reason="Legal Index not loaded")


# 1. ม.5 classification -------------------------------------------------------------------
@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.name)
def test_m5_classification(item):
    exp = X["wage_classification"][item.name]
    status = labor.wage_item_status(item.purpose, item.basis, item.conditional,
                                    item.regardless_of_actual_cost)
    assert (status == "wage") is exp["wage"]
    step = next(s for s in labor.wage_base([item], "k").steps if s.startswith(item.name))
    if "reason_must_mention" in exp:
        assert exp["reason_must_mention"] in step, step
    if "reason_must_not_mention" in exp:
        assert exp["reason_must_not_mention"] not in step, step


def test_wage_base_is_salary_plus_flat_fuel():
    b = labor.wage_base(ITEMS, "k")
    assert b.monthly == BASE and not b.unknown
    assert "10,000 + 500 = 10,500" in "\n".join(b.steps)


# 2. ม.118 tenure + tier ---------------------------------------------------------------------
def test_m118_tenure_reaches_one_year_tier():
    t = labor.Tenure.from_dates(F["start_date"], END)
    assert t.years == X["tenure"]["years"]
    tier = next(x for x in BOOK.get("severance_tiers", END).tiers
                if t.reaches(x.min) and (x.max is None or not t.reaches(x.max)))
    assert tier.value == X["tenure"]["tier_days"]


# 3–5. per employee: ม.119 → severance / notice pay / final wage kept separate -----------------
def _amounts() -> tuple[D, labor.NoticeResult]:
    t = labor.Tenure.from_dates(F["start_date"], END)
    daily = labor.to_daily_wage(BASE, "month", END, BOOK, exact=True).amount
    sev = labor.severance(daily, t, END, BOOK).amount
    n = labor.notice_and_final_pay(END, F["pay_days"], BASE, daily,
                                   {"notice": "N", "in_lieu": "L", "final": "F"})
    return sev, n


def test_m17_effective_date():
    assert _amounts()[1].effective == X["notice_effective_date"]


@pytest.mark.parametrize("name", list(X["employees"]))
def test_per_employee_entitlement(name):
    e = X["employees"][name]
    sev, n = _amounts()
    got = labor.apply_m119(sev, n.notice_pay.amount, n.final_period.amount, e["m119_applies"],
                           {"m119": "M119", "notice_exempt": "M17_4", "final": "F"})
    assert (got.severance, got.notice_pay, got.final_wage) == (e["severance"], e["notice_pay"], e["final_wage"])


def test_total():
    sev, n = _amounts()
    total = sum(sum((g.severance, g.notice_pay, g.final_wage)) for g in (
        labor.apply_m119(sev, n.notice_pay.amount, n.final_period.amount, e["m119_applies"],
                         {"m119": "a", "notice_exempt": "b", "final": "c"})
        for e in X["employees"].values()))
    assert total == X["total"]


@pytest.mark.skip(reason="whether ม.119 applies (and on which ground) is decided by the LLM per "
                         "employee; not exercised without a recorded run — see expect.employees")
def test_m119_decided_separately_by_the_agent():
    pass


# authorities and statute keys exist in the Legal Index -----------------------------------
@needs_db
def test_authorities_in_db_match_fixture():
    from src.index.tools import get_case, get_provision
    for no, a in CASE["authorities"].items():
        assert (get_case(a["key"]) is not None) is a["in_db"] if a["key"] else not a["in_db"], no
    for e in X["employees"].values():
        for k in e["alleged_ground_keys"] + e["found_ground_keys"]:
            assert get_provision(k) is not None, k


# 6. through the calculate node and ⑩ (DB, no LLM) ---------------------------------------
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
def test_calculate_node_amounts_are_separate():
    st = _state()
    sev, notice = st.calcs["severance_pay"], st.calcs["advance_notice"]
    assert sev.amount == X["employees"]["ซื่อบื้อ"]["severance"]
    assert notice.amount == X["employees"]["ซื่อบื้อ"]["notice_pay"]
    text = "\n".join(notice.steps)
    assert "▶ ค่าจ้างงวดสุดท้าย" in text and "▶ สินจ้างแทนการบอกกล่าวล่วงหน้า" in text
    assert "10,500 ÷ 2 งวดต่อเดือน = 5,250" in text


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


# Issue 1: dismissal money is computed from the facts even when no money issue was chosen --
def _state_without_money_issues() -> AgentState:
    from src.agent.nodes.decide import calculate
    st = AgentState(question="reg-huaykhwang",
                    facts=Facts(start_date=F["start_date"], end_date=END, pay_days=F["pay_days"],
                                pay_items=ITEMS),
                    issues=[IssueSel(code="definition_of_wages", reason="t")])   # no formula
    out = calculate(st)
    st.calcs, st.termination = out["calcs"], out["termination"]
    return st


def _answer(employees):
    from src.agent.answer import AnswerJSON
    return AnswerJSON.model_validate({
        "preliminary": [{"headline": "h"}], "employees": employees,
        "issues": [{"code": "definition_of_wages", "question": "q", "consider": "-", "laws": [],
                    "application": [], "conclusion": [{"headline": "h"}], "opinion": "o", "basis": "b"}]})


@needs_db
def test_termination_money_without_money_issues():
    st = _state_without_money_issues()
    t, su = st.termination, X["employees"]["ซื่อบื้อ"]
    assert not st.calcs                      # no issue had a formula
    assert (t.severance.amount, t.notice_pay.amount, t.final_wage.amount) == (
        su["severance"], su["notice_pay"], su["final_wage"])
    assert t.effective == X["notice_effective_date"]


def _employees() -> list[dict]:
    """The per-employee decision as the drafter would record it (keys from the fixture)."""
    out = []
    for name, e in X["employees"].items():
        out.append({"name": f"นาย{name}", "m119_applies": e["m119_applies"],
                    "alleged_ground_keys": e["alleged_ground_keys"],
                    "found_ground_keys": e["found_ground_keys"],
                    "not_found_reason": "" if e["found_ground_keys"] else "ไม่มีส่วนร่วม"})
    return out


def _with_exemption_selected(st: AgentState) -> AgentState:
    from src.agent.nodes.decide import m119_keys
    st.selected = {"dismissal_for_cause": [m119_keys()["m119"]]}
    return st


@needs_db
def test_per_employee_table_and_total():
    from src.agent.nodes.draft import KEY_IN_TEXT, validate_cites
    st = _with_exemption_selected(_state_without_money_issues())
    st.answer = _answer(_employees())
    out = validate_cites(st)
    a, md = out["answer"], out["markdown"]
    rows = {r.name: r for r in a.payments}
    pw, sb = rows["นายแพรวพราว"], rows["นายซื่อบื้อ"]
    assert (pw.severance, pw.notice_pay, pw.final_wage, pw.total) == ("0", "0", "5,250", "5,250")
    assert (sb.severance, sb.notice_pay, sb.final_wage, sb.total) == ("31,500", "5,250", "5,250", "42,000")
    assert a.payments_total == f"{X['total']:,}" == "47,250"
    assert pw.note == "เข้า ม.119 (2)" and sb.note == "ไม่เข้ามาตรา 119"
    assert "| นายแพรวพราว | 0 | 0 | 5,250 | **5,250** |" in md
    assert "| นายซื่อบื้อ | 31,500 | 5,250 | 5,250 | **42,000** |" in md
    assert "**รวมทั้งสิ้น 47,250 บาท**" in md
    assert X["employees"]["แพรวพราว"]["m119_key"] in a.payments_citations
    assert "LPA2541:119:1:(1)" not in a.payments_citations      # alleged but not found
    assert "ม.17 วรรคสี่" in md
    assert not KEY_IN_TEXT.search(md)


@needs_db
def test_conclusions_cite_only_found_grounds():
    from src.agent.nodes.draft import validate_cites
    st = _with_exemption_selected(_state_without_money_issues())
    st.answer = _answer(_employees())
    st.answer.preliminary[0].citations = ["LPA2541:119:1:(1)", "LPA2541:119:1:(2)"]
    a = validate_cites(st)["answer"]
    assert a.preliminary[0].citations == ["LPA2541:119:1:(2)"]


@needs_db
def test_applies_without_a_valid_found_ground_becomes_undecided():
    from src.agent.nodes.draft import validate_cites
    st = _with_exemption_selected(_state_without_money_issues())
    st.answer = _answer([{"name": "ก", "m119_applies": True, "found_ground_keys": ["LPA2541:118:1:(2)"]},
                         {"name": "ข", "m119_applies": True, "found_ground_keys": []}])
    a = validate_cites(st)["answer"]
    assert [e.found_ground_keys for e in a.employees] == [[], []]
    assert [e.m119_applies for e in a.employees] == [None, None]
    assert all("ยังไม่ชัด" in r.note for r in a.payments)


@needs_db
def test_grounds_need_the_exemption_paragraph_selected():
    from src.agent.nodes.draft import validate_cites
    st = _state_without_money_issues()              # ⑤ selected nothing
    st.answer = _answer(_employees())
    a = validate_cites(st)["answer"]
    assert all(not e.found_ground_keys and e.m119_applies is not True for e in a.employees)


@needs_db
def test_undecided_m119_is_shown_as_conditional_not_guessed():
    from src.agent.nodes.draft import validate_cites
    st = _state_without_money_issues()
    st.answer = _answer([])                  # LLM gave no per-employee decision
    a = validate_cites(st)["answer"]
    (row,) = a.payments
    assert row.m119_applies is None and "ยังไม่ชัด" in row.note
    assert row.total == "42,000" and "กรณีที่ยังไม่ชัด" in a.payments_total
