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
from itertools import pairwise
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
    steps: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)

    @classmethod
    def from_dates(cls, start: date, end: date) -> Tenure:
        from dateutil.relativedelta import relativedelta
        rd = relativedelta(end + timedelta(days=1), start)
        return cls(days=(end - start).days + 1, years=rd.years, months=rd.months,
                   source=f"{start.isoformat()} ถึง {end.isoformat()}")

    @classmethod
    def from_service(cls, start: date, last_working_day: date) -> Tenure:
        """Length of service under the Civil Code rules on periods (docs: M3).

        - ป.พ.พ. 193/3 วรรคสอง: the first day is not counted unless the matter begins that day at the
          customary start of business. `start` is taken to be the first working day, worked from the
          start of the working day, so it counts.
        - ป.พ.พ. 193/5: years and months run on the calendar; a period ends on the day before the
          corresponding date of the last month/year, or on that month's last day when it has no
          corresponding date (e.g. a 29 Feb start).
        A year is completed only when `last_working_day` reaches the end of that period, so
        1 Jan → 31 Dec is one year and 1 Jan → 30 Dec is 364 days, not a year. Unlike
        `from_dates` (relativedelta), a 29 Feb start completes a year on 28 Feb, not 27 Feb."""
        if last_working_day < start:
            raise ValueError("วันทำงานวันสุดท้ายอยู่ก่อนวันเริ่มงาน")
        n = 0
        while _period_end(start, n + 1) <= last_working_day:
            n += 1
        years, months = divmod(n, 12)
        days = (last_working_day - start).days + 1
        steps = [
            (f"เริ่มทำงานวันที่ {thai_date(start)} นับวันแรกรวมด้วย เพราะเริ่มการในวันนั้นเองตั้งแต่เวลาเริ่มทำงาน "
             "(ป.พ.พ. มาตรา 193/3 วรรคสอง; สันนิษฐานว่าเริ่มงานตั้งแต่ต้นเวลาทำงานของวันนั้น)"),
            ("ระยะเวลาเป็นเดือนหรือปีคำนวณตามปีปฏิทิน และสิ้นสุดในวันก่อนหน้าวันที่ตรงกับวันเริ่มงาน "
             "ถ้าเดือนสุดท้ายไม่มีวันตรงกันให้สิ้นสุดในวันสุดท้ายของเดือนนั้น (ป.พ.พ. มาตรา 193/5)"),
            f"ทำงานถึงวันที่ {thai_date(last_working_day)} → อายุงาน {years} ปี {months} เดือน (นับรวม {days} วัน)",
        ]
        nxt = _period_end(start, 12 * (years + 1))
        steps.append(f"จะครบ {years + 1} ปีเมื่อทำงานถึงวันที่ {thai_date(nxt)}")
        return cls(days=days, years=years, months=months, steps=steps,
                   citations=list(CCC_PERIOD_KEYS),
                   source=f"{thai_date(start)} ถึง {thai_date(last_working_day)} ตาม ป.พ.พ. 193/3, 193/5")

    @classmethod
    def from_stated(cls, years: int = 0, months: int = 0, days: int = 0) -> Tenure:
        """Only a stated duration is known: day count is approximate for year thresholds."""
        return cls(days=years * 365 + months * 30 + days, years=years, months=months,
                   source=f"ตามที่โจทย์ระบุ {years} ปี {months} เดือน {days} วัน")

    def reaches(self, d: Duration) -> bool:
        return self.years >= d.amount if d.unit == "year" else self.days >= d.amount


CCC_PERIOD_KEYS = ("CCC:193/3:2", "CCC:193/5:1", "CCC:193/5:2")


def _period_end(start: date, months: int) -> date:
    """Last day of a period of `months` calendar months beginning on `start` (ป.พ.พ. 193/5)."""
    import calendar
    y, m = divmod(start.month - 1 + months, 12)
    y, m = start.year + y, m + 1
    last = calendar.monthrange(y, m)[1]
    if start.day > last:                      # no corresponding day → the month's last day
        return date(y, m, last)
    return date(y, m, start.day) - timedelta(days=1)


class Rate(BaseModel):
    key: str                          # e.g. "severance_tiers", "ot_multiplier"
    citation_key: str
    valid_from: date | None = None
    valid_to: date | None = None      # exclusive
    value: Decimal | None = None
    tiers: list[Tier] = Field(default_factory=list)
    localities: list[str] = Field(default_factory=list)   # e.g. provinces a minimum wage applies to
    locality_citation_key: str | None = None   # where the localities are named (default: citation_key)
    valid_from_citation_key: str | None = None  # where the commencement date is stated

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

    def get_local(self, key: str, locality: str, on: date) -> Rate:
        """Like `get`, for rates that differ by locality (e.g. min_wage_daily per province)."""
        hits = [r for r in self.rates if r.key == key and locality in r.localities and r.in_force(on)]
        if len(hits) != 1:
            raise LookupError(f"expected 1 rate '{key}' for '{locality}' in force on {on}, found {len(hits)}")
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
            loc_key = r.locality_citation_key or r.citation_key
            for loc in r.localities:
                if loc not in provision_text.get(loc_key, ""):
                    problems.append(f"{r.key}: locality '{loc}' not found in {loc_key}")
            if r.valid_from_citation_key:
                want = thai_long_date(r.valid_from) if r.valid_from else "?"
                if want not in provision_text.get(r.valid_from_citation_key, ""):
                    problems.append(f"{r.key}: valid_from '{want}' not found in {r.valid_from_citation_key}")
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


# months per pay period (calendar arithmetic, not a legal number)
MONTHS = {"month": Decimal(1), "quarter": Decimal(3), "year": Decimal(12)}


class WageBase(BaseModel):
    monthly: Decimal | None            # None: some wage item cannot be put on a monthly basis
    expr: str                          # "80,000 + 25,000"
    steps: list[str]
    unknown: list[str]


def wage_item_status(purpose: str, basis: str, conditional: bool | None,
                     regardless_of_actual_cost: bool | None = None) -> str:
    """"wage" | "not_wage" | "unknown" under the definition of ค่าจ้าง (LPA ม.5), judged by the
    purpose and character of the payment — never by the item's name, and never by whether
    receipts are required alone (docs/decisions.md #9):
    - conditional on something other than work, or discretionary → not wage
    - welfare purpose → not wage, even when a fixed amount is paid monthly without claims
      (ฎ. 9096/2546, 2967/2555)
    - reimbursement of actual work expenses (basis actual_cost) → not wage
    - note ฎ. 3934/2557 is not an actual-cost case: it holds that a fixed flat sum paid without
      receipts is NOT wage when its purpose is to cover work expenses (not yet reflected below)
    - a fixed work-expense allowance paid in full whatever is actually spent → wage, with or
      without receipts (ฎ. 7402–7403/2544; 7780–7782/2556)
    - a fixed work-expense allowance whose amount follows actual spending → not wage
    - a fixed work-expense allowance where the facts do not show which → unknown (flagged)
    - pay for work, fixed per period or by output → wage"""
    if conditional:
        return "not_wage"
    if purpose == "welfare" or basis in ("actual_cost", "discretionary"):
        return "not_wage"
    if purpose == "expense" and basis == "fixed":
        return {True: "wage", False: "not_wage"}.get(regardless_of_actual_cost, "unknown")
    if purpose == "work" and basis in ("fixed", "output"):
        return "wage"
    return "unknown"


def _proof_note(it: Any) -> str:
    """requires_proof is context for the reader, never the deciding factor."""
    rp = getattr(it, "requires_proof", None)
    return {True: " (แม้มีการแสดงใบเสร็จประกอบ)", False: " และไม่ต้องแสดงหลักฐานค่าใช้จ่าย"}.get(rp, "")


def _reason(it: Any, status: str) -> str:
    if status == "wage":
        if it.purpose == "expense":
            return ("จ่ายเต็มจำนวนแน่นอนทุกเดือนไม่ว่าลูกจ้างจะใช้จ่ายจริงเท่าใด"
                    f"{_proof_note(it)} มีลักษณะเป็นค่าตอบแทนการทำงาน")
        return f"ตอบแทนการทำงาน{'ตามผลงาน' if it.basis == 'output' else ''}"
    if it.conditional:
        return "จ่ายเมื่อเข้าเงื่อนไขอื่นนอกจากการทำงาน"
    if it.purpose == "welfare":
        return "วัตถุประสงค์ของการจ่ายเป็นสวัสดิการ ไม่ใช่ค่าตอบแทนการทำงาน แม้จะจ่ายเป็นจำนวนแน่นอนทุกเดือน"
    if it.basis == "actual_cost" or it.purpose == "expense":
        return "เป็นการชดใช้ค่าใช้จ่ายในการทำงานตามที่ลูกจ้างจ่ายไปจริง ไม่ใช่ค่าตอบแทนการทำงาน"
    if it.basis == "discretionary":
        return "นายจ้างให้ตามดุลพินิจ ไม่ได้ตกลงจ่ายเป็นค่าตอบแทนการทำงาน"
    return ""


def wage_base(items: list[Any], definition_key: str) -> WageBase:
    """Sum the items that are wages, each converted to a monthly amount. Every item gets a
    step saying whether it counts and why, citing the definition of ค่าจ้าง."""
    total, parts, steps, unknown = Decimal(0), [], [], []
    alt = Decimal(0)                      # unknown items that would be added if they are wages
    monthly_ok = True
    for it in items:
        amt = Decimal(str(it.amount))
        st = wage_item_status(it.purpose, it.basis, it.conditional,
                              getattr(it, "regardless_of_actual_cost", None))
        if st == "wage":
            if it.period in MONTHS:
                m = amt / MONTHS[it.period]
                total += m
                parts.append(baht(m))
                per = "" if it.period == "month" else f" (เฉลี่ยต่อเดือน {baht(amt)} ÷ {MONTHS[it.period]} = {baht(m)})"
                steps.append(f"{it.name} {baht(amt)} บาท — เป็นค่าจ้าง ({_reason(it, st)}) นับรวมเป็นฐานค่าจ้าง{per}")
            else:
                monthly_ok = False
                steps.append(f"{it.name} {baht(amt)} บาท — เป็นค่าจ้าง แต่จ่ายเป็นราย{it.period} "
                             "ระบบยังแปลงเป็นรายเดือนอัตโนมัติไม่ได้")
        elif st == "not_wage":
            steps.append(f"{it.name} {baht(amt)} บาท — ไม่นับเป็นค่าจ้าง ({_reason(it, st)})")
        else:
            unknown.append(it.name)
            if it.period in MONTHS:
                alt += amt / MONTHS[it.period]
            hint = ("ถ้าจ่ายเต็มจำนวนแน่นอนไม่ว่าจะใช้จ่ายจริงเท่าใด เป็นค่าจ้าง แต่ถ้าจ่ายตามค่าใช้จ่ายจริง "
                    "ไม่เป็นค่าจ้าง — การมีหรือไม่มีใบเสร็จอย่างเดียวไม่ชี้ขาด" if it.purpose == "expense"
                    else "ถ้าเป็นค่าตอบแทนการทำงานต้องนับรวม")
            steps.append(f"{it.name} {baht(amt)} บาท — ข้อเท็จจริงไม่พอจะบอกว่าเป็นค่าจ้างหรือไม่ "
                         f"(คำนวณโดยไม่นับรวม; {hint})")
    if len(parts) > 1:
        steps.append(f"ฐานค่าจ้างต่อเดือน = {' + '.join(parts)} = {baht(total)} บาท")
    elif parts:
        steps.append(f"ฐานค่าจ้างต่อเดือน = {baht(total)} บาท")
    if parts and alt:
        steps.append(f"ถ้ารายการที่ยังไม่แน่ชัดเป็นค่าจ้าง ฐานค่าจ้างต่อเดือนจะเป็น {baht(total + alt)} บาท")
    return WageBase(monthly=total if monthly_ok and parts else None,
                    expr=" + ".join(parts), steps=steps, unknown=unknown)


def _pay_date(year: int, month: int, day: int) -> date:
    """Pay day `day` of a month; a day past the month's end means the last day (สิ้นเดือน)."""
    import calendar
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def pay_dates_from(start: date, pay_days: list[int], n: int) -> list[date]:
    """The first n pay dates on or after `start`."""
    out, y, m = [], start.year, start.month
    while len(out) < n:
        out += sorted(d for d in (_pay_date(y, m, x) for x in set(pay_days)) if d >= start)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out[:n]


THAI_MONTHS_FULL = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม",
                    "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]


def thai_long_date(d: date) -> str:
    """date(2025, 7, 1) → "1 กรกฎาคม พ.ศ. 2568" (as written in the Royal Gazette)."""
    return f"{d.day} {THAI_MONTHS_FULL[d.month - 1]} พ.ศ. {d.year + 543}"


def thai_date(d: date) -> str:
    months = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    return f"{d.day} {months[d.month - 1]} {d.year + 543}"


class NoticeResult(BaseModel):
    effective: date                    # when notice given on the dismissal day would end the contract
    final_period: CalcResult           # wage of the last pay period worked (ค่าจ้างงวดสุดท้าย)
    notice_pay: CalcResult             # pay in lieu of notice (สินจ้างแทนการบอกกล่าวล่วงหน้า)


def notice_and_final_pay(dismissed: date, pay_days: list[int], monthly: Decimal, daily: Decimal,
                         keys: dict[str, str]) -> NoticeResult:
    """Employer ends an open-ended contract on `dismissed` (the employee leaves that day)
    without notice. Notice given on or before a pay date takes effect on the next pay date
    (ม.17 วรรคสอง), so notice given on `dismissed` would have ended the contract on the
    second pay date on or after `dismissed` (a pay date on `dismissed` itself counts as the
    first). Pay in lieu = wage from the day after leaving to that date
    (ม.17/1), counted in days at the daily wage. The final pay period is paid in full when
    `dismissed` is a pay date (monthly wage ÷ pay dates per month).
    keys: citation_keys {"notice": ม.17 วรรคสอง, "in_lieu": ม.17/1, "final": ม.70 วรรคสอง}."""
    first, second = pay_dates_from(dismissed, pay_days, 2)
    effective = second
    if first != dismissed:
        raise ValueError("วันเลิกจ้างไม่ตรงวันจ่ายค่าจ้าง ระบบยังไม่คำนวณค่าจ้างงวดสุดท้ายแบบเฉลี่ยรายวัน")
    per_period = monthly / len(set(pay_days))
    final = CalcResult(amount=_q(per_period), citations=[keys["final"]], steps=[(
        f"ค่าจ้างงวดสุดท้ายถึงวันเลิกจ้าง {thai_date(dismissed)} (ซึ่งเป็นวันจ่ายค่าจ้าง) = "
        f"{baht(monthly)} ÷ {len(set(pay_days))} งวดต่อเดือน = {baht(per_period)} บาท "
        "ต้องจ่ายภายในสามวันนับแต่วันเลิกจ้าง")])
    days = (effective - dismissed).days
    amt = daily * days
    lieu = CalcResult(amount=_q(amt), citations=[keys["notice"], keys["in_lieu"]], steps=[
        (f"ถ้าบอกกล่าวในวันที่ {thai_date(dismissed)} การเลิกสัญญาจะมีผลในวันจ่ายค่าจ้างคราวถัดไป "
         f"คือ {thai_date(effective)}"),
        (f"สินจ้างแทนการบอกกล่าวล่วงหน้า (ถ้ามีสิทธิ) = {baht(monthly)} ÷ {_q(monthly / daily):.0f} × {days} วัน "
         f"({thai_date(dismissed + timedelta(days=1))} – {thai_date(effective)}) = {baht(amt)} บาท "
         "จ่ายในวันที่ให้ลูกจ้างออกจากงาน")])
    return NoticeResult(effective=effective, final_period=final, notice_pay=lieu)


class Termination(BaseModel):
    """Money on dismissal, computed from the facts alone (whatever issues the LLM chose):
    severance if tenure is known, pay in lieu of notice and the final period's wage."""
    severance: CalcResult | None
    notice_pay: CalcResult
    final_wage: CalcResult
    effective: date
    wage_steps: list[str]
    citations: list[str]


class Entitlement(BaseModel):
    severance: Decimal
    notice_pay: Decimal
    final_wage: Decimal
    steps: list[str]
    citations: list[str]


def apply_dismissal(severance: Decimal, notice_pay: Decimal, final_wage: Decimal, *, m119: bool,
                    ccc583: bool, keys: dict[str, str]) -> Entitlement:
    """Per-employee amounts once the grounds are decided (upstream, with reasons).
    - ม.119 removes severance; notice does not apply to a dismissal under ม.119 (ม.17 วรรคสี่).
    - ป.พ.พ. ม.583 alone removes only the notice requirement (ม.17 วรรคสี่ names both), so severance stays due.
    - Wages already earned are owed either way (ม.70 วรรคสอง).
    keys: {"m119": …, "notice_exempt": …, "final": …, "ccc583": …} (looked up from the DB by text)."""
    if m119:
        return apply_m119(severance, notice_pay, final_wage, True, keys)
    if ccc583:
        return Entitlement(severance=severance, notice_pay=Decimal(0), final_wage=final_wage,
                           citations=[keys["ccc583"], keys["notice_exempt"], keys["final"]], steps=[(
                               f"ไม่เข้าเหตุตามมาตรา 119 → ค่าชดเชย {baht(severance)} บาท "
                               "แต่เข้ามาตรา 583 แห่งประมวลกฎหมายแพ่งและพาณิชย์ → การบอกกล่าวล่วงหน้าไม่ใช้บังคับ "
                               f"จึงไม่มีสินจ้างแทนการบอกกล่าวล่วงหน้า · ค่าจ้างงวดสุดท้าย {baht(final_wage)} บาท")])
    return apply_m119(severance, notice_pay, final_wage, False, keys)


def apply_m119(severance: Decimal, notice_pay: Decimal, final_wage: Decimal, m119_applies: bool,
               keys: dict[str, str]) -> Entitlement:
    """Per-employee amounts once ม.119 is decided (upstream, with reasons). A ม.119 dismissal
    removes severance (ม.119 วรรคหนึ่ง) and the notice requirement (ม.17 วรรคสี่), so pay in
    lieu is also 0; wages already earned are owed either way (ม.70 วรรคสอง).
    keys: {"m119": …, "notice_exempt": …, "final": …}."""
    if m119_applies:
        return Entitlement(severance=Decimal(0), notice_pay=Decimal(0), final_wage=final_wage,
                           citations=[keys["m119"], keys["notice_exempt"], keys["final"]], steps=[
                               "เลิกจ้างด้วยเหตุตามมาตรา 119 → ไม่มีสิทธิได้ค่าชดเชย",
                               "การบอกกล่าวล่วงหน้าไม่ใช้บังคับแก่การเลิกจ้างตามมาตรา 119 → ไม่มีสินจ้างแทนการบอกกล่าวล่วงหน้า",
                               f"ค่าจ้างงวดสุดท้าย {baht(final_wage)} บาท ยังต้องจ่าย"])
    return Entitlement(severance=severance, notice_pay=notice_pay, final_wage=final_wage,
                       citations=[keys["final"]], steps=[(
                           f"ไม่เข้าเหตุตามมาตรา 119 → ค่าชดเชย {baht(severance)} บาท "
                           f"สินจ้างแทนการบอกกล่าวล่วงหน้า {baht(notice_pay)} บาท "
                           f"ค่าจ้างงวดสุดท้าย {baht(final_wage)} บาท")])


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


class SeveranceBranch(BaseModel):
    """One outcome of `severance_branches`: holds for every last working day in [first, last]."""
    condition: str
    first: date
    last: date
    tenure: Tenure
    result: CalcResult


def severance_branches(daily_wage: Decimal, start: date, earliest_last_day: date, latest_last_day: date,
                       book: RateBook, wage_expr: str = "ค่าจ้างรายวัน") -> list[SeveranceBranch]:
    """Severance when the last working day is not known exactly (e.g. "ถ้าทำงานถึงวันที่ 31 ธ.ค.").

    Tenure is counted by `Tenure.from_service` for every candidate last day; consecutive days that
    fall in the same ม.118 tier form one branch, with its condition stated, so a 1 Jan start gives
    a 30-day branch (last day 30 Dec, 364 days) and a 90-day branch (last day 31 Dec, one year).
    The rate book is read as of each candidate last day."""
    if latest_last_day < earliest_last_day:
        raise ValueError("latest_last_day is before earliest_last_day")
    groups: list[tuple[date, date, tuple[Decimal, tuple[str, ...]]]] = []
    d = earliest_last_day
    while d <= latest_last_day:
        r = severance(daily_wage, Tenure.from_service(start, d), d, book, wage_expr)
        sig = (r.amount, tuple(r.citations))
        if groups and groups[-1][2] == sig:
            groups[-1] = (groups[-1][0], d, sig)
        else:
            groups.append((d, d, sig))
        d += timedelta(days=1)
    out = []
    for a, b, _ in groups:
        t = Tenure.from_service(start, a)
        r = severance(daily_wage, t, a, book, wage_expr)
        when = (f"ถ้าทำงานถึงวันที่ {thai_date(a)}" if a == b
                else f"ถ้าวันทำงานวันสุดท้ายอยู่ระหว่าง {thai_date(a)} ถึง {thai_date(b)}")
        res = CalcResult(amount=r.amount, steps=[when, *t.steps, *r.steps],
                         citations=list(dict.fromkeys([*r.citations, *t.citations])))
        out.append(SeveranceBranch(condition=when, first=a, last=b, tenure=t, result=res))
    return out


class MinWageCheck(CalcResult):
    """amount = the wage as a daily equivalent."""
    minimum: Decimal
    below: bool


def _min_wage_keys(r: Rate) -> list[str]:
    keys = [r.citation_key, r.locality_citation_key, r.valid_from_citation_key]
    return [k for k in dict.fromkeys(keys) if k]


def min_wage_check(wage_base_monthly: Decimal, locality: str, on: date, book: RateBook) -> MinWageCheck:
    """Is a monthly wage below the daily minimum wage of `locality` in force on `on`?

    The minimum is a daily rate, so the monthly wage is put on a daily basis with the ม.68
    divisor (`to_daily_wage`). That is an assumption: a monthly-paid employee is paid for every
    day of the month, including rest days."""
    r = book.get_local("min_wage_daily", locality, on)
    assert r.value is not None
    d = to_daily_wage(Decimal(wage_base_monthly), "month", on, book, exact=True)
    below = d.amount < r.value
    steps = [
        ("ข้อสันนิษฐาน: อัตราค่าจ้างขั้นต่ำกำหนดเป็นรายวัน จึงเทียบค่าจ้างรายเดือนเป็นรายวันด้วยวิธีหารตามมาตรา 68 "
         "(ลูกจ้างรายเดือนได้รับค่าจ้างสำหรับทุกวันในเดือนรวมวันหยุด)"),
        *d.steps,
        f"อัตราค่าจ้างขั้นต่ำในท้องที่{locality} ณ วันที่ {thai_date(on)} = วันละ {baht(r.value)} บาท",
        (f"{baht(d.amount)} < {baht(r.value)} → ค่าจ้างต่ำกว่าอัตราค่าจ้างขั้นต่ำ" if below
         else f"{baht(d.amount)} ≥ {baht(r.value)} → ค่าจ้างไม่ต่ำกว่าอัตราค่าจ้างขั้นต่ำ"),
    ]
    return MinWageCheck(amount=_q(d.amount), steps=steps, minimum=r.value, below=below,
                        citations=list(dict.fromkeys([*_min_wage_keys(r), *d.citations])))


def _period_fraction(s: date, e: date) -> tuple[Decimal, str]:
    """Share of a month covered by a pay period: a calendar month = 1; 1st–15th or 16th–month end = 1/2."""
    import calendar
    end_of_month = calendar.monthrange(s.year, s.month)[1]
    if (s.year, s.month) != (e.year, e.month):
        raise ValueError(f"pay period {s}–{e} spans months; split it per month")
    if s.day == 1 and e.day == end_of_month:
        return Decimal(1), "ทั้งเดือน"
    if (s.day, e.day) in ((1, 15), (16, end_of_month)):
        return Decimal(1) / 2, "ครึ่งเดือน"
    raise ValueError(f"unsupported pay period {s}–{e}: only calendar months or 1–15 / 16–month end")


def min_wage_shortfall(pay_periods: list[tuple[date, date, Decimal]], locality: str,
                       book: RateBook) -> CalcResult:
    """Unpaid minimum wage, computed per pay period (start, end, amount paid) so no day is counted
    twice. The minimum for a period = daily rate × the ม.68 divisor (a monthly equivalent; an
    assumption, stated in the steps) × the period's share of a month: 1 for a calendar month and
    1/2 for each half-month period (1st–15th, 16th–month end), whatever the month's length.
    The rate must be the same throughout a period (split a period that spans a rate change)."""
    periods = sorted(pay_periods, key=lambda p: p[0])
    for (s1, e1, _), (s2, _e2, _) in pairwise(periods):
        if s2 <= e1:
            raise ValueError(f"pay periods overlap: {s1}–{e1} and {s2}")
    steps = [
        ("ข้อสันนิษฐาน: อัตราค่าจ้างขั้นต่ำเป็นรายวัน เทียบเป็นรายเดือน = อัตรารายวัน × จำนวนวันตามวิธีคำนวณของมาตรา 68 "
         "งวดครึ่งเดือน (วันที่ 1–15 และ 16–สิ้นเดือน) คิดครึ่งหนึ่งของรายเดือน คำนวณแยกทีละงวดค่าจ้างโดยไม่นับซ้ำ"),
    ]
    cites: list[str] = []
    total = Decimal(0)
    for s, e, paid in periods:
        paid = Decimal(paid)
        frac, label = _period_fraction(s, e)
        r = book.get_local("min_wage_daily", locality, s)
        if book.get_local("min_wage_daily", locality, e) is not r:
            raise ValueError(f"minimum wage changes within pay period {s}–{e}; split it")
        dpm = book.get("days_per_month", s)
        assert r.value is not None and dpm.value is not None
        due = r.value * dpm.value * frac
        short = max(Decimal(0), due - paid)
        total += short
        expr = f"{baht(r.value)} × {dpm.value}" + (" ÷ 2" if frac != 1 else "")
        steps.append(f"งวด {thai_date(s)} – {thai_date(e)} ({label}): ขั้นต่ำ {expr} = {baht(due)} บาท "
                     f"จ่ายจริง {baht(paid)} บาท → " + (f"ขาด {baht(short)} บาท" if short else "ไม่ขาด"))
        cites += [*_min_wage_keys(r), dpm.citation_key]
    steps.append(f"รวมค่าจ้างที่จ่ายต่ำกว่าอัตราค่าจ้างขั้นต่ำ {len(periods)} งวด = {baht(total)} บาท")
    return CalcResult(amount=_q(total), steps=steps, citations=list(dict.fromkeys(cites)))


def surcharge(principal: Decimal, due: date, until: date, book: RateBook) -> CalcResult:
    """เงินเพิ่ม under LPA ม.9 วรรคสอง: a percentage of the unpaid sum for every full period after a
    grace period counted from the due date (rate, grace and period from the RateBook).

    Applies ONLY when the employer "จงใจ" withheld the money "โดยปราศจากเหตุผลอันสมควร". Whether
    that holds is the caller's decision; this function only does the arithmetic.
    Counting conventions (assumptions, stated in the steps): the grace runs from the day after
    `due` (ป.พ.พ. 193/3 วรรคสอง); only completed periods after the grace count; the percentage
    applies to the principal, not compounded."""
    rate = book.get("surcharge_rate", due)
    grace = book.get("surcharge_grace_days", due)
    period = book.get("surcharge_period_days", due)
    assert rate.value is not None and grace.value is not None and period.value is not None
    grace_end = due + timedelta(days=int(grace.value))
    n = max(0, (until - grace_end).days // int(period.value))
    amt = Decimal(principal) * rate.value / 100 * n
    return CalcResult(amount=_q(amt), citations=list(dict.fromkeys(
        [rate.citation_key, grace.citation_key, period.citation_key])), steps=[
        "ใช้เฉพาะกรณีนายจ้างจงใจไม่จ่ายโดยปราศจากเหตุผลอันสมควร",
        (f"ถึงกำหนดจ่าย {thai_date(due)} พ้นกำหนด {grace.value} วันเมื่อสิ้นวันที่ {thai_date(grace_end)} "
         "(ไม่นับวันแรก ตาม ป.พ.พ. มาตรา 193/3 วรรคสอง)"),
        f"ถึงวันที่ {thai_date(until)} ครบระยะเวลา {period.value} วัน {n} ระยะ (นับเฉพาะระยะที่ครบ)",
        f"เงินเพิ่ม = {baht(Decimal(principal))} × {rate.value}% × {n} = {baht(amt)} บาท"])


CALCULATORS: dict[str, Any] = {
    "to_daily_wage": to_daily_wage,
    "severance": severance,
    "rate_pay": rate_pay,
    "unused_leave_pay": unused_leave_pay,
    "notice_pay": notice_pay,
    "interest": interest,
    "surcharge": surcharge,
    "min_wage_check": min_wage_check,
    "min_wage_shortfall": min_wage_shortfall,
    "severance_branches": severance_branches,
}
