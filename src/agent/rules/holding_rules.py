"""Verified holding rules (config/holding_rules.yaml; FIX_PLAN_v2 rule rows). A rule states a condition on the facts
and the outcome the cited own holdings give; determine_grounds shows the rules for the provisions it judges so the
model applies settled case law instead of its own view. Quotes are verified verbatim against the DB."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel

RULES = Path("config/holding_rules.yaml")


class RuleCase(BaseModel):
    deka_no: str
    decided_by: str
    quote: str


class HoldingRule(BaseModel):
    id: str
    provisions: list[str]
    condition: str
    outcome: str
    caveat: str = ""
    cases: list[RuleCase]


@cache
def load_rules() -> tuple[HoldingRule, ...]:
    return tuple(HoldingRule.model_validate(r) for r in yaml.safe_load(RULES.read_text(encoding="utf-8")) or [])


def _section(key: str) -> str:
    return ":".join(key.split(":")[:2])


def rules_block(ground_keys: list[str]) -> str:
    want = {_section(k) for k in ground_keys}
    lines = []
    for r in load_rules():
        if want & {_section(p) for p in r.provisions}:
            cites = ", ".join(f"คำพิพากษาศาลฎีกาที่ {c.deka_no} “{c.quote}”" for c in r.cases)
            lines.append(f"- [{r.id}] ถ้า {r.condition} → {r.outcome} ({cites})" + (f" · {r.caveat}" if r.caveat else ""))
    return "\n".join(lines) or "-"


def verify_rules() -> list[str]:
    """Problems: a cited decision missing from the DB, or a quote that is not verbatim in its text."""
    from src.index.db import connect
    squash = lambda t: re.sub(r"\s+", " ", t or "")
    bad = []
    with connect() as c:
        for r in load_rules():
            for case in r.cases:
                row = c.execute("SELECT holding, full_text FROM cases WHERE deka_no=%s", (case.deka_no,)).fetchone()
                if row is None:
                    bad.append(f"{r.id}: {case.deka_no} not in DB")
                elif squash(case.quote) not in squash(row[0]) + " " + squash(row[1]):
                    bad.append(f"{r.id}: quote not found in {case.deka_no}")
    return bad
