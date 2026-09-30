"""Deterministic labor-law calculations.

No legal number (rate, day count, divisor, tier) is hard-coded here. Every such
parameter comes from a RateBook entry that carries the citation_key it was read
from and its validity window. `RateBook.verify` checks each number against the
provision text stored in the DB, so a rates file cannot drift from the statute.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class CalcResult(BaseModel):
    amount: Decimal
    steps: list[str]
    citations: list[str]


class Duration(BaseModel):
    amount: int
    unit: Literal["day", "year"]


class Tier(BaseModel):
    min: Duration                     # tenure reaches min ("ครบ …")
    max: Duration | None = None       # tenure has not reached max ("แต่ไม่ครบ …"); None = open
    value: Decimal                    # days of last-rate wages
    citation_key: str


class Tenure(BaseModel):
    """Length of service computed in code (never by the LLM).

    Day counts are inclusive of the first and last day; completed years count whole
    calendar years from the start date. (Convention to confirm with the professors.)"""
    days: int
    years: int
    months: int
    source: str

    @classmethod
    def from_dates(cls, start: date, end: date) -> Tenure:
        from dateutil.relativedelta import relativedelta
        rd = relativedelta(end + timedelta(days=1), start)
        return cls(days=(end - start).days + 1, years=rd.years, months=rd.months,
                   source=f"{start.isoformat()} ถึง {end.isoformat()}")

    @classmethod
    def from_stated(cls, years: int = 0, months: int = 0, days: int = 0) -> Tenure:
        """Only a stated duration is known: day count is approximate for year thresholds."""
        return cls(days=years * 365 + months * 30 + days, years=years, months=months,
                   source=f"ตามที่โจทย์ระบุ {years} ปี {months} เดือน {days} วัน")

    def reaches(self, d: Duration) -> bool:
        return self.years >= d.amount if d.unit == "year" else self.days >= d.amount


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
            found = numbers_in(text)
            nums = [r.value] if r.value is not None else []
            for n in nums:
                if n not in found:
                    problems.append(f"{r.key}: {n} not found in {r.citation_key}")
            for t in r.tiers:
                t_found = numbers_in(provision_text.get(t.citation_key, ""))
                for n in [t.value, t.min.amount] + ([t.max.amount] if t.max else []):
                    if Decimal(n) not in t_found:
                        problems.append(f"{r.key}: {n} not found in {t.citation_key}")
        return problems


MULTIPLE_WORDS = {"หนึ่งเท่าครึ่ง": Decimal("1.5"), "หนึ่งเท่า": Decimal(1), "สองเท่า": Decimal(2),
                  "สามเท่า": Decimal(3)}


def numbers_in(text: str) -> set[Decimal]:
    """Digits, Thai number words ("หนึ่งร้อยแปดสิบ" → 180) and multiples ("หนึ่งเท่าครึ่ง")."""
    from pythainlp.util import text_to_num, thaiword_to_num
    nums = {Decimal(n) for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))}
    nums |= {v for w, v in MULTIPLE_WORDS.items() if w in text}
    for tok in text_to_num(text):
        if re.fullmatch(r"\d+(?:\.\d+)?", tok):
            nums.add(Decimal(tok))
        elif re.fullmatch(r"[ก-๙]+", tok):
            try:                      # text_to_num misses some bare words, e.g. "สิบ"
                nums.add(Decimal(thaiword_to_num(tok)))
            except ValueError:
                pass
    return nums


def baht(x: Decimal) -> str:
    """40000 → "40,000"; 1333.333 → "1,333.33"."""
    q = _q(Decimal(x))
    return f"{q:,.0f}" if q == q.to_integral() else f"{q:,.2f}"


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def to_daily_wage(amount: Decimal, period: str, on: date, book: RateBook,
                  exact: bool = False) -> CalcResult:
    """period: 'day' | 'month' | 'hour'. Divisors come from the RateBook.
    exact=True keeps full precision so a later multiplication is rounded only once
    (40,000 ÷ 30 × 300 = 400,000, not 1,333.33 × 300 = 399,999)."""
    if period == "day":
        return CalcResult(amount=_q(amount), steps=["ค่าจ้างรายวันตามที่ระบุ"], citations=[])
    key = {"month": "days_per_month", "hour": "hours_per_day"}[period]
    r = book.get(key, on)
    assert r.value is not None
    daily = amount / r.value if period == "month" else amount * r.value
    op = "÷" if period == "month" else "×"
    return CalcResult(
        amount=daily if exact else _q(daily),
        steps=[f"ค่าจ้างรายวัน = {baht(amount)} {op} {r.value} = {baht(daily)} บาท"],
        citations=[r.citation_key],
    )


def severance(daily_wage: Decimal, tenure: Tenure, on: date, book: RateBook,
              wage_expr: str = "ค่าจ้างรายวัน") -> CalcResult:
    """wage_expr: how the daily wage is written in the final step, e.g. "40,000 ÷ 30"."""
    r = book.get("severance_tiers", on)
    tier = next((t for t in r.tiers
                 if tenure.reaches(t.min) and (t.max is None or not tenure.reaches(t.max))), None)
    base = f"อายุงาน {tenure.years} ปี {tenure.months} เดือน ({tenure.days} วัน; {tenure.source})"
    if tier is None:
        return CalcResult(amount=Decimal(0), steps=[f"{base} ไม่ถึงเกณฑ์ขั้นต่ำที่ได้รับค่าชดเชย"],
                          citations=[r.tiers[0].citation_key] if r.tiers else [r.citation_key])
    amt = daily_wage * tier.value
    return CalcResult(
        amount=_q(amt),
        steps=[f"{base} เข้าเกณฑ์ค่าจ้างอัตราสุดท้าย {tier.value} วัน",
               f"ค่าชดเชย (ถ้ามีสิทธิ) = {wage_expr} × {tier.value} = {baht(amt)} บาท"],
        citations=[tier.citation_key],
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
