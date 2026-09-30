"""Deterministic labor-law calculations.

No legal number (rate, day count, divisor, tier) is hard-coded here. Every such
parameter comes from a RateBook entry that carries the citation_key it was read
from and its validity window. `RateBook.verify` checks each number against the
provision text stored in the DB, so a rates file cannot drift from the statute.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class CalcResult(BaseModel):
    amount: Decimal
    steps: list[str]
    citations: list[str]


class Tier(BaseModel):
    min_days: int                     # tenure >= min_days
    max_days: int | None = None       # tenure < max_days (None = open-ended)
    value: Decimal


class Rate(BaseModel):
    key: str                          # e.g. "severance_tiers", "ot_multiplier"
    citation_key: str
    valid_from: date | None = None
    valid_to: date | None = None      # exclusive
    value: Decimal | None = None
    tiers: list[Tier] = Field(default_factory=list)

    def in_force(self, d: date) -> bool:
        return (self.valid_from is None or self.valid_from <= d) and (
            self.valid_to is None or d < self.valid_to
        )


class RateBook(BaseModel):
    rates: list[Rate]

    @classmethod
    def load(cls, path: str | Path = "data/processed/rates.yaml") -> RateBook:
        return cls(rates=yaml.safe_load(Path(path).read_text(encoding="utf-8")) or [])

    def get(self, key: str, on: date) -> Rate:
        hits = [r for r in self.rates if r.key == key and r.in_force(on)]
        if len(hits) != 1:
            raise LookupError(f"expected 1 rate '{key}' in force on {on}, found {len(hits)}")
        return hits[0]

    def verify(self, provision_text: dict[str, str]) -> list[str]:
        """Return problems: every number in a rate must appear in its provision's text."""
        problems = []
        for r in self.rates:
            text = provision_text.get(r.citation_key)
            if text is None:
                problems.append(f"{r.key}: citation {r.citation_key} not in DB")
                continue
            found = {Decimal(n) for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))}
            nums = [r.value] if r.value is not None else []
            nums += [t.value for t in r.tiers]
            for n in nums:
                if n not in found:
                    problems.append(f"{r.key}: {n} not found in {r.citation_key}")
        return problems


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def to_daily_wage(amount: Decimal, period: str, on: date, book: RateBook) -> CalcResult:
    """period: 'day' | 'month' | 'hour'. Divisors come from the RateBook."""
    if period == "day":
        return CalcResult(amount=_q(amount), steps=["ค่าจ้างรายวันตามที่ระบุ"], citations=[])
    key = {"month": "days_per_month", "hour": "hours_per_day"}[period]
    r = book.get(key, on)
    assert r.value is not None
    daily = amount / r.value if period == "month" else amount * r.value
    op = "÷" if period == "month" else "×"
    return CalcResult(
        amount=_q(daily),
        steps=[f"ค่าจ้างรายวัน = {amount} {op} {r.value} = {_q(daily)}"],
        citations=[r.citation_key],
    )


def severance(daily_wage: Decimal, tenure_days: int, on: date, book: RateBook) -> CalcResult:
    r = book.get("severance_tiers", on)
    tier = next(
        (t for t in r.tiers if tenure_days >= t.min_days
         and (t.max_days is None or tenure_days < t.max_days)),
        None,
    )
    if tier is None:
        return CalcResult(amount=Decimal(0),
                          steps=[f"อายุงาน {tenure_days} วัน ไม่ถึงเกณฑ์ได้รับค่าชดเชย"],
                          citations=[r.citation_key])
    amt = daily_wage * tier.value
    return CalcResult(
        amount=_q(amt),
        steps=[f"อายุงาน {tenure_days} วัน เข้าเกณฑ์ค่าจ้าง {tier.value} วัน",
               f"ค่าชดเชย = {daily_wage} × {tier.value} = {_q(amt)}"],
        citations=[r.citation_key],
    )


def rate_pay(key: str, hourly_wage: Decimal, hours: Decimal, on: date, book: RateBook,
             label: str) -> CalcResult:
    """Generic multiplier pay: overtime / holiday work / holiday overtime (key selects rate)."""
    r = book.get(key, on)
    assert r.value is not None
    amt = hourly_wage * r.value * hours
    return CalcResult(
        amount=_q(amt),
        steps=[f"{label} = {hourly_wage} × {r.value} × {hours} ชม. = {_q(amt)}"],
        citations=[r.citation_key],
    )


def unused_leave_pay(daily_wage: Decimal, days: Decimal) -> CalcResult:
    """Entitled-day count is decided upstream (elements node) with its own citation."""
    amt = daily_wage * days
    return CalcResult(amount=_q(amt),
                      steps=[f"ค่าจ้างวันหยุดพักผ่อนที่ไม่ได้ใช้ = {daily_wage} × {days} = {_q(amt)}"],
                      citations=[])


def notice_pay(daily_wage: Decimal, days_short: int) -> CalcResult:
    """days_short: days between termination and the date notice would have taken effect,
    computed upstream from pay cycles (rule to be confirmed with professors)."""
    amt = daily_wage * days_short
    return CalcResult(amount=_q(amt),
                      steps=[f"สินจ้างแทนการบอกกล่าวล่วงหน้า = {daily_wage} × {days_short} = {_q(amt)}"],
                      citations=[])


def interest(principal: Decimal, days: int, on: date, book: RateBook,
             key: str = "interest_rate_pa") -> CalcResult:
    r = book.get(key, on)
    assert r.value is not None
    amt = principal * r.value / 100 * days / 365
    return CalcResult(
        amount=_q(amt),
        steps=[f"ดอกเบี้ย = {principal} × {r.value}% × {days}/365 = {_q(amt)}"],
        citations=[r.citation_key],
    )


CALCULATORS: dict[str, Any] = {
    "to_daily_wage": to_daily_wage,
    "severance": severance,
    "rate_pay": rate_pay,
    "unused_leave_pay": unused_leave_pay,
    "notice_pay": notice_pay,
    "interest": interest,
}
