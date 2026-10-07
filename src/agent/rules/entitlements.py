"""Open entitlement questions (docs/decisions.md #15).

When a question asks generally what an employee is entitled to ("มีสิทธิอะไรบ้าง", "ได้รับเงินใดบ้าง") about a
termination or retirement, the money that falls due when employment ends must all be considered — not only the
issue the question names. System rule, applied after spot_issues; the issue cap still applies.
"""

from __future__ import annotations

import re

from src.agent.state import IssueSel

OPEN_ENTITLEMENT = re.compile(r"(มี)?สิทธิ(ได้รับ)?(อะไร|ใด|ประการใด)(บ้าง)?|ได้รับ(เงิน)?(อะไร|ใด)บ้าง|ได้รับอะไร")
END_OF_EMPLOYMENT = {"severance_pay", "retirement", "dismissal_for_cause", "advance_notice",
                     "special_severance_pay_and_relocation", "definition_of_dismissal_and_outstanding_payments"}
COMPANIONS = {"annual_leave": "สิทธิที่ต้องพิจารณาเมื่อสัญญาจ้างสิ้นสุด: ค่าจ้างสำหรับวันหยุดพักผ่อนประจำปีที่ลูกจ้างมีสิทธิ "
                              "(คำถามถามสิทธิทั้งหมด จึงต้องตรวจด้วยแม้โจทย์ไม่ได้ระบุ)"}


def is_open_entitlement(question: str, asked: list[str]) -> bool:
    return bool(OPEN_ENTITLEMENT.search(question) or any(OPEN_ENTITLEMENT.search(a) for a in asked))


def add_companion_issues(issues: list[IssueSel], question: str, asked: list[str], cap: int) -> list[IssueSel]:
    """Append companion entitlement issues for open questions about the end of employment, up to `cap`."""
    codes = {i.code for i in issues}
    if not (codes & END_OF_EMPLOYMENT) or not is_open_entitlement(question, asked):
        return issues
    out = list(issues)
    for code, reason in COMPANIONS.items():
        if code not in codes and len(out) < cap:
            out.append(IssueSel(code=code, reason=reason))
    return out
