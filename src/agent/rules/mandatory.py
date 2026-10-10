"""Issues the question explicitly asks about are never cut by the issue cap (FIX_PLAN_v2 M2).

Only issues the spotter itself chose are kept: the cap still limits unasked extras (rubric B0 penalises extra issues).
A trigger is a phrase that, in a sub-question (`facts.asked`), can only mean that issue."""

from __future__ import annotations

import re

ASKED_TRIGGERS: dict[str, re.Pattern] = {
    "advance_notice": re.compile(r"บอกกล่าวล่วงหน้า|สินจ้างแทนการบอกกล่าว"),
    "severance_pay": re.compile(r"ค่าชดเชย(?!พิเศษ)"),
    "annual_leave": re.compile(r"วันหยุดพักผ่อน"),
    "employer_liability_and_representatives": re.compile(r"(รับผิด|ต้องรับผิดชอบ)(ใน)?ฐานะนายจ้าง|ใครเป็นนายจ้าง"),
}


def asked_codes(asked: list[str]) -> set[str]:
    return {code for code, pat in ASKED_TRIGGERS.items() if any(pat.search(a) for a in asked)}
