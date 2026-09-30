"""Calc tests use a synthetic RateBook — numbers here are fixtures, not law."""
from datetime import date
from decimal import Decimal as D

import pytest

from src.calc.labor import RateBook, rate_pay, severance, to_daily_wage

BOOK = RateBook(rates=[
    {"key": "days_per_month", "citation_key": "X:1:1", "value": "10"},
    {"key": "severance_tiers", "citation_key": "X:2:1", "valid_to": "2020-01-01",
     "tiers": [{"min_days": 100, "max_days": 200, "value": "5"},
               {"min_days": 200, "value": "7"}]},
    {"key": "severance_tiers", "citation_key": "X:2:1", "valid_from": "2020-01-01",
     "tiers": [{"min_days": 100, "value": "9"}]},
    {"key": "ot", "citation_key": "X:3:1", "value": "1.5"},
])


def test_monthly_to_daily():
    r = to_daily_wage(D(1000), "month", date(2024, 1, 1), BOOK)
    assert r.amount == D("100.00") and r.citations == ["X:1:1"]


def test_severance_by_date_version():
    assert severance(D(100), 150, date(2019, 1, 1), BOOK).amount == D("500.00")
    assert severance(D(100), 250, date(2019, 1, 1), BOOK).amount == D("700.00")
    assert severance(D(100), 150, date(2021, 1, 1), BOOK).amount == D("900.00")
    assert severance(D(100), 50, date(2021, 1, 1), BOOK).amount == 0


def test_rate_pay():
    assert rate_pay("ot", D(10), D(2), date(2024, 1, 1), BOOK, "OT").amount == D("30.00")


def test_missing_rate_raises():
    with pytest.raises(LookupError):
        BOOK.get("nope", date(2024, 1, 1))


def test_verify_against_text():
    problems = BOOK.verify({"X:1:1": "หารด้วย 10", "X:2:1": "5 7 9", "X:3:1": "หนึ่ง"})
    assert problems == ["ot: 1.5 not found in X:3:1"]


def test_numbers_in_thai_words():
    from src.calc.labor import numbers_in
    assert {D(30), D(180)} <= numbers_in("ค่าจ้างอัตราสุดท้ายสามสิบวัน หรือหนึ่งร้อยแปดสิบวัน")
