"""Calc tests use a synthetic RateBook — numbers here are fixtures, not law."""
from datetime import date
from decimal import Decimal as D

import pytest

from src.calc.labor import RateBook, Tenure, numbers_in, rate_pay, severance, to_daily_wage

T = lambda mn, mx, v, k: {"min": mn, "max": mx, "value": v, "citation_key": k}
BOOK = RateBook(rates=[
    {"key": "days_per_month", "citation_key": "X:1:1", "value": "10"},
    {"key": "severance_tiers", "citation_key": "X:2:1", "valid_to": "2020-01-01", "tiers": [
        T({"amount": 100, "unit": "day"}, {"amount": 1, "unit": "year"}, "5", "X:2:1:(1)"),
        T({"amount": 1, "unit": "year"}, None, "7", "X:2:1:(2)")]},
    {"key": "severance_tiers", "citation_key": "X:2:1", "valid_from": "2020-01-01", "tiers": [
        T({"amount": 100, "unit": "day"}, None, "9", "X:2:1:(1)")]},
    {"key": "ot", "citation_key": "X:3:1", "value": "1.5"},
])


def test_monthly_to_daily():
    r = to_daily_wage(D(1000), "month", date(2024, 1, 1), BOOK)
    assert r.amount == D("100.00") and r.citations == ["X:1:1"]


def test_tenure_from_dates_inclusive():
    t = Tenure.from_dates(date(2020, 1, 1), date(2020, 12, 31))
    assert (t.days, t.years) == (366, 1)
    t = Tenure.from_dates(date(2020, 1, 1), date(2020, 12, 30))
    assert t.years == 0


def test_severance_tiers_by_unit_and_version():
    short = Tenure.from_dates(date(2018, 1, 1), date(2018, 6, 1))           # 152 days
    long_ = Tenure.from_dates(date(2015, 1, 1), date(2018, 6, 1))
    assert severance(D(100), short, date(2019, 1, 1), BOOK).amount == D("500.00")
    r = severance(D(100), long_, date(2019, 1, 1), BOOK)
    assert r.amount == D("700.00") and r.citations == ["X:2:1:(2)"]
    assert severance(D(100), short, date(2021, 1, 1), BOOK).amount == D("900.00")
    tiny = Tenure.from_dates(date(2021, 1, 1), date(2021, 2, 1))
    assert severance(D(100), tiny, date(2021, 3, 1), BOOK).amount == 0


def test_rate_pay():
    assert rate_pay("ot", D(10), D(2), date(2024, 1, 1), BOOK, "OT").amount == D("30.00")


def test_missing_rate_raises():
    with pytest.raises(LookupError):
        BOOK.get("nope", date(2024, 1, 1))


def test_verify_against_text():
    problems = BOOK.verify({"X:1:1": "หารด้วย 10", "X:2:1": "", "X:2:1:(1)": "ครบ 100 วัน 1 ปี 5 9",
                            "X:2:1:(2)": "1 7", "X:3:1": "หนึ่ง"})
    assert problems == ["ot: 1.5 not found in X:3:1"]


def test_numbers_in_thai_words():
    assert {D(30), D(180)} <= numbers_in("ค่าจ้างอัตราสุดท้ายสามสิบวัน หรือหนึ่งร้อยแปดสิบวัน")
    assert D("1.5") in numbers_in("ไม่น้อยกว่าหนึ่งเท่าครึ่งของอัตรา")
    assert D(10) in numbers_in("ครบหกปี แต่ไม่ครบสิบปี")


def test_monthly_wage_rounded_once():
    daily = to_daily_wage(D(40000), "month", date(2024, 1, 1),
                          RateBook(rates=[{"key": "days_per_month", "citation_key": "X", "value": "30"}]),
                          exact=True).amount
    assert (daily * 300).quantize(D("0.01")) == D("400000.00")


def _item(name, amount, period, purpose, basis, conditional=None):
    from src.agent.state import PayItem
    return PayItem(name=name, amount=amount, period=period, purpose=purpose, basis=basis,
                   conditional=conditional)


def test_wage_base_dev039_salary_plus_sales_bonus_not_fuel_phone():
    # dev100 gold dev039: wage base 80,000 + 25,000 = 105,000 (fuel and phone excluded)
    from src.calc.labor import wage_base
    b = wage_base([_item("เงินเดือน", 80000, "month", "work", "fixed"),
                   _item("ค่าน้ำมันรถ", 10000, "month", "expense", "fixed"),
                   _item("ค่าโทรศัพท์", 3000, "month", "expense", "fixed"),
                   _item("โบนัสรายเดือนตามยอดขาย", 25000, "month", "work", "output")], "LPA2541:5:11")
    assert b.monthly == D(105000)
    assert any("ไม่นับเป็นค่าจ้าง" in s and "ค่าน้ำมันรถ" in s for s in b.steps)


def test_wage_base_dev022_quarterly_commission_averaged_monthly():
    # dev100 gold dev022: commission is a wage and is averaged per month
    from src.calc.labor import wage_base
    b = wage_base([_item("เงินเดือน", 30000, "month", "work", "fixed"),
                   _item("ค่าคอมมิชชัน", 90000, "quarter", "work", "output")], "LPA2541:5:11")
    assert b.monthly == D(60000)


def test_wage_base_dev040_unconditional_allowance_counts_conditional_does_not():
    from src.calc.labor import wage_base
    b = wage_base([_item("เงินเดือน", 15000, "month", "work", "fixed"),
                   _item("เบี้ยขยันคงที่ไม่มีเงื่อนไข", 3000, "month", "work", "fixed", False)], "k")
    assert b.monthly == D(18000)
    c = wage_base([_item("เงินเดือน", 15000, "month", "work", "fixed"),
                   _item("เบี้ยขยันเมื่อไม่ขาดลามาสาย", 3000, "month", "work", "fixed", True)], "k")
    assert c.monthly == D(15000)


def test_wage_base_unknown_item_is_flagged_not_added():
    from src.calc.labor import wage_base
    b = wage_base([_item("เงินเดือน", 20000, "month", "work", "fixed"),
                   _item("เงินพิเศษ", 1000, "month", "unknown", "unknown")], "k")
    assert b.monthly == D(20000) and b.unknown == ["เงินพิเศษ"]
