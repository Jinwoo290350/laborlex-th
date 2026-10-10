"""Determination Ledger (FIX_PLAN_v2 M2): one record per dismissed employee, decided once.

The payment table and the prose check both read this record, so the notice / severance outcome per person has a single
source. Grounds come from the drafted `EmployeeOutcome` (ม.119 grounds are validated by `check_grounds`; ป.พ.พ. ม.583 is
relevant only when ม.119 is not met). Every amount comes from the calculator (`labor.Termination` + `apply_dismissal`).
"""

from __future__ import annotations

import re
from decimal import Decimal
from itertools import combinations

from pydantic import BaseModel

from src.agent.answer import AnswerJSON, EmployeeOutcome
from src.agent.rules.elements import Conflict
from src.calc import labor

AMOUNT = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*บาท")
NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
NOTICE = "สินจ้างแทนการบอกกล่าว"
# "<negation> … สินจ้างแทนการบอกกล่าว" or "สินจ้างแทนการบอกกล่าว… 0 บาท / ไม่มี"
NOTICE_DENIED = re.compile(r"(ไม่มีสิทธิ|ไม่ได้รับ|ไม่ต้องจ่าย|ไม่ต้องชำระ)[^\n·]{0,60}" + NOTICE
                           + "|" + NOTICE + r"[^\n·]{0,30}(?<!\d)0 บาท")


class EmployeeRecord(BaseModel):
    name: str
    m119: bool | None
    ccc583: bool | None
    severance_exempt: bool
    notice_exempt: bool
    severance: Decimal
    notice_pay: Decimal
    final_wage: Decimal
    total: Decimal
    steps: list[str]
    citations: list[str]


class Ledger(BaseModel):
    employees: list[EmployeeRecord]
    total: Decimal
    severance_known: bool
    system_amounts: list[Decimal]          # every number the calculator wrote in its steps


def _num(s: str) -> Decimal:
    return Decimal(s.replace(",", ""))


def build_ledger(t: labor.Termination, a: AnswerJSON, keys: dict[str, str]) -> Ledger:
    people = a.employees or [EmployeeOutcome(name="ลูกจ้าง")]
    sev = t.severance.amount if t.severance else Decimal(0)
    recs = []
    for e in people:
        m119 = bool(e.m119_applies)
        ccc583 = bool(e.ccc583_applies) and not m119
        got = labor.apply_dismissal(sev, t.notice_pay.amount, t.final_wage.amount, m119=m119, ccc583=ccc583,
                                    keys=keys)
        recs.append(EmployeeRecord(
            name=e.name, m119=e.m119_applies, ccc583=e.ccc583_applies, severance_exempt=m119,
            notice_exempt=m119 or ccc583, severance=got.severance, notice_pay=got.notice_pay,
            final_wage=got.final_wage, total=got.severance + got.notice_pay + got.final_wage,
            steps=got.steps, citations=got.citations))
    steps = t.wage_steps + (t.severance.steps if t.severance else []) + t.notice_pay.steps + t.final_wage.steps
    nums = {_num(n) for s in steps for n in NUMBER.findall(s)}
    return Ledger(employees=recs, total=sum((r.total for r in recs), Decimal(0)),
                  severance_known=t.severance is not None, system_amounts=sorted(nums))


def _texts(a: AnswerJSON) -> list[tuple[str, str]]:
    """(where, text) of everything the drafter wrote; calculator sections are excluded (the system writes them)."""
    out = [("preliminary", f"{p.headline} {p.detail}") for p in a.preliminary]
    for i in a.issues:
        out += [(i.code or i.question[:30], f"{p.headline} {p.detail}") for p in i.conclusion]
        out += [(i.code or i.question[:30], f"{s.fact} → {s.result}") for ap in i.application for s in ap.steps]
        out.append((i.code or i.question[:30], i.opinion))
    return out


def _allowed(led: Ledger, question: str) -> set[Decimal]:
    ok = set(led.system_amounts) | {_num(n) for n in NUMBER.findall(question)} | {Decimal(0), led.total}
    for r in led.employees:
        parts = [r.severance, r.notice_pay, r.final_wage]
        ok |= set(parts) | {r.total} | {x + y for x, y in combinations(parts, 2)}
    return ok


def _segments(text: str, names: list[str]) -> list[tuple[str, str]]:
    """Split a text at each employee name: (name, text from that name up to the next name)."""
    hits = sorted((m.start(), n) for n in names for m in re.finditer(re.escape(n), text))
    return [(n, text[pos:hits[k + 1][0] if k + 1 < len(hits) else len(text)]) for k, (pos, n) in enumerate(hits)]


def prose_conflicts(a: AnswerJSON, led: Ledger, question: str) -> list[Conflict]:
    """Where the drafted text disagrees with the ledger: an amount the system never computed (and the question
    never stated), or a per-person statement on pay in lieu of notice with the opposite polarity."""
    out: list[Conflict] = []
    allowed = _allowed(led, question)
    by_name = {r.name: r for r in led.employees}
    for where, text in _texts(a):
        for m in AMOUNT.finditer(text):
            if _num(m.group(1)) not in allowed:
                out.append(Conflict(kind="amount_not_in_ledger", issue=where,
                                    detail=f"จำนวน {m.group(1)} บาท ไม่ตรงกับผลการคำนวณของระบบหรือข้อเท็จจริงในโจทย์: "
                                           f"“{text[max(0, m.start() - 60):m.end() + 20].strip()}”"))
        for name, seg in _segments(text, list(by_name)):
            if NOTICE not in seg:
                continue
            r, denied = by_name[name], bool(NOTICE_DENIED.search(seg))
            if r.notice_exempt and not denied:
                why = "เข้ามาตรา 119" if r.m119 else "เข้ามาตรา 583 แห่งประมวลกฎหมายแพ่งและพาณิชย์"
                out.append(Conflict(kind="notice_contradicts_ledger", issue=where,
                                    detail=f"{name}{why} จึงไม่มีสินจ้างแทนการบอกกล่าวล่วงหน้า แต่ข้อความระบุว่ามีสิทธิ: "
                                           f"“{seg[:120].strip()}”"))
            elif not r.notice_exempt and denied and r.notice_pay > 0:
                out.append(Conflict(kind="notice_contradicts_ledger", issue=where,
                                    detail=f"{name}ไม่เข้าเหตุยกเว้นการบอกกล่าวล่วงหน้า จึงมีสิทธิได้รับสินจ้างแทนการบอกกล่าวล่วงหน้า "
                                           f"{labor.baht(r.notice_pay)} บาท แต่ข้อความระบุว่าไม่มีสิทธิ: “{seg[:120].strip()}”"))
    return out
