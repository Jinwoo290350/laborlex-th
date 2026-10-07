"""Derived elements (docs/decisions.md #17).

A taxonomy element with `derive` is never put to the LLM: check_elements asks only the factual sub-elements, and
the system combines their statuses with three-valued logic (met / not_met / unknown). Used where one compound
question hid which condition failed — the lawful-order exception of LRA s.123(3) and s.31(3).

`derive` grammar: an element id, {"all": [...]}, {"any": [...]} or {"not": <expr>}.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel

from src.agent.state import ElementCheck

Status = Literal["met", "not_met", "unknown"]
MET: Status = "met"
NOT_MET: Status = "not_met"
UNKNOWN: Status = "unknown"


def combine(expr: Any, status: Mapping[str, Status]) -> Status:
    if isinstance(expr, str):
        return status.get(expr, UNKNOWN)
    if "all" in expr:
        vals = [combine(e, status) for e in expr["all"]]
        return NOT_MET if NOT_MET in vals else MET if all(v == MET for v in vals) else UNKNOWN
    if "any" in expr:
        vals = [combine(e, status) for e in expr["any"]]
        return MET if MET in vals else NOT_MET if all(v == NOT_MET for v in vals) else UNKNOWN
    if "not" in expr:
        v = combine(expr["not"], status)
        return NOT_MET if v == MET else MET if v == NOT_MET else UNKNOWN
    raise ValueError(f"bad derive expression: {expr!r}")


def _ids(expr: Any) -> list[str]:
    if isinstance(expr, str):
        return [expr]
    return [i for sub in (expr.get("all") or expr.get("any") or [expr.get("not")]) for i in _ids(sub)]


def derive_checks(elements: list[dict], llm: list[ElementCheck]) -> list[ElementCheck]:
    """LLM checks of the factual elements, then each derived element in taxonomy order (a derived element may use
    an earlier derived one). Any LLM verdict on a derived element is discarded."""
    derived = {e["id"]: e for e in elements if "derive" in e}
    out = [c for c in llm if c.id not in derived]
    status: dict[str, Status] = {c.id: c.status for c in out}
    for eid, e in derived.items():
        s = combine(e["derive"], status)
        basis = ", ".join(f"{i}={status.get(i, UNKNOWN)}" for i in dict.fromkeys(_ids(e["derive"])))
        status[eid] = s
        out.append(ElementCheck(id=eid, status=s, evidence=f"ระบบสรุปจากองค์ประกอบย่อย ({basis})"))
    return out


# ---------- cross-issue consistency (docs/decisions.md #20) ----------
# An element may carry
#   defeated_by: {when: <expr over "issue/id">, status: not_met|unknown, reason: str, forbid_citations: [keys]}
# When `when` is met, the element takes `status` with the system's reason, and `forbid_citations` may not be cited by
# the answer's preliminary points or conclusions.
# An element may carry `outcome: {marker, certainty, unmodelled_prerequisites, statement, guard}` (decisions #21): a
# conclusion the system states to the draft when the element is met. Outcomes are selected by marker, never by
# matching Thai phrases in the answer; no outcome has a guard yet (guard: none).
OUTCOME_MARKERS = frozenset({"OUTCOME_WARNING_REQUIRED", "OUTCOME_DISMISSAL_PROHIBITED", "OUTCOME_DISMISSAL_PERMITTED",
                             "OUTCOME_ACT_PROHIBITED", "OUTCOME_ACT_PERMITTED"})


def _qualified(resolved: Mapping[str, Mapping[str, ElementCheck]]) -> dict[str, Status]:
    return {f"{code}/{i}": c.status for code, checks in resolved.items() for i, c in checks.items()}


def resolve_elements(raw: Mapping[str, list[ElementCheck]], tax: Mapping[str, dict]) -> dict[str, list[ElementCheck]]:
    """Per-issue derived elements, then the cross-issue `defeated_by` rules (one pass, taxonomy order)."""
    per = {code: derive_checks(tax[code].get("elements") or [], checks) for code, checks in raw.items()}
    status = _qualified({c: {x.id: x for x in v} for c, v in per.items()})
    out: dict[str, list[ElementCheck]] = {}
    for code, checks in per.items():
        rules = {e["id"]: e["defeated_by"] for e in tax[code].get("elements") or [] if "defeated_by" in e}
        fixed = []
        for c in checks:
            rule = rules.get(c.id)
            if rule and c.status == MET and combine(rule["when"], status) == MET:
                c = ElementCheck(id=c.id, status=rule.get("status", NOT_MET),
                                 evidence=f"ระบบ: {rule['reason']} (เดิม LLM: {c.evidence})")
            fixed.append(c)
        out[code] = fixed
    return out


def _fired(resolved: Mapping[str, Mapping[str, ElementCheck]], tax: Mapping[str, dict]):
    status = _qualified(resolved)
    for code, checks in resolved.items():
        for e in tax[code].get("elements") or []:
            c = checks.get(e["id"])
            if c is None:
                continue
            rule = e.get("defeated_by")
            if rule and c.evidence.startswith("ระบบ:") and combine(rule["when"], status) == MET:
                yield code, e


def forbidden_citations(resolved: Mapping[str, Mapping[str, ElementCheck]], tax: Mapping[str, dict]) -> set[str]:
    return {k for _, e in _fired(resolved, tax) for k in e["defeated_by"].get("forbid_citations", [])}


class Conflict(BaseModel):
    kind: str          # forbidden_citation
    issue: str
    detail: str


def answer_conflicts(answer: Any, resolved: Mapping[str, Mapping[str, ElementCheck]],
                     tax: Mapping[str, dict]) -> list[Conflict]:
    """Where a draft contradicts what the system decided (#20). Pure; the caller asks for a revision / strips keys."""
    out: list[Conflict] = []
    banned = forbidden_citations(resolved, tax)
    points = [("preliminary", p) for p in answer.preliminary] + [(i.code, p) for i in answer.issues for p in i.conclusion]
    for where, p in points:
        for k in sorted(set(p.citations) & banned):
            out.append(Conflict(kind="forbidden_citation", issue=where,
                                detail=f"อ้าง {k} ทั้งที่ระบบตัดเหตุนี้แล้ว: " + next(
                                    e["defeated_by"]["reason"] for _, e in _fired(resolved, tax)
                                    if k in e["defeated_by"].get("forbid_citations", []))))
    return out
