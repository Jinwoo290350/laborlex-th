"""2/2554 Q4 regression (docs/benchmarks/exam_regression_spec_2026-10-06.yaml): the lawful-order exception of
s.123(3) / s.31(3) is decided by the system from factual sub-elements, not by one compound LLM verdict.
Fact pattern: the transfer is permitted by the collective agreement, the employee asked for it, then refuses.
Expected: lawful order refused = met; the (3) exception still needs a written warning. Refusal alone never
makes the order lawful. Local, no Gemini (sub-element statuses given as check_elements would return them)."""

from pathlib import Path

import yaml

from src.agent.rules.elements import combine, derive_checks
from src.agent.state import ElementCheck

ISSUES = {i["code"]: i for i in yaml.safe_load(Path("data/processed/issues.yaml").read_text(encoding="utf-8"))}
S123, S31 = "employee_committee_and_union_protection", "dispute_protection_s31"


def _derived(code: str, **status) -> dict[str, str]:
    els = ISSUES[code]["elements"]
    llm = [ElementCheck(id=i, status=s, evidence="e") for i, s in status.items()]
    return {c.id: c.status for c in derive_checks(els, llm)}


def _ids(code: str) -> tuple[str, str]:
    """(lawful-order element id, exception (3) element id) — the derived elements of the issue."""
    der = [e for e in ISSUES[code]["elements"] if "derive" in e]
    lawful = next(e["id"] for e in der if "ตักเตือน" not in e["question"])
    exc = next(e["id"] for e in der if "ตักเตือน" in e["question"])
    return lawful, exc


def _sub(code: str) -> dict[str, str]:
    """role → sub-element id, from each sub-element's `role` field."""
    return {e["role"]: e["id"] for e in ISSUES[code]["elements"] if "role" in e}


def test_three_valued_logic():
    st = {"a": "met", "b": "not_met", "c": "unknown"}
    assert combine({"all": ["a", {"any": ["b", "a"]}]}, st) == "met"
    assert combine({"all": ["a", "b"]}, st) == "not_met"
    assert combine({"all": ["a", "c"]}, st) == "unknown"
    assert combine({"any": ["b", "c"]}, st) == "unknown"
    assert combine({"not": "b"}, st) == "met" and combine({"not": "c"}, st) == "unknown"
    assert combine("missing", st) == "unknown"


def test_sub_elements_exist_for_s123_and_s31():
    for code in (S123, S31):
        assert set(_sub(code)) == {"refused", "per_agreement", "employee_consent", "obstruction", "warning"}
        assert all(e.get("citation_keys") for e in ISSUES[code]["elements"] if "role" in e)


def test_agreement_and_consent_then_refusal_is_a_lawful_order_refused_but_needs_warning():
    for code in (S123, S31):
        r, lawful, exc = _sub(code), *_ids(code)
        out = _derived(code, **{r["refused"]: "met", r["per_agreement"]: "met", r["employee_consent"]: "met",
                                r["obstruction"]: "not_met", r["warning"]: "not_met"})
        assert out[lawful] == "met", code
        assert out[exc] == "not_met", code          # no written warning → cannot dismiss at once


def test_refusal_alone_is_not_a_lawful_order():
    for code in (S123, S31):
        r, lawful, exc = _sub(code), *_ids(code)
        out = _derived(code, **{r["refused"]: "met", r["per_agreement"]: "not_met",
                                r["employee_consent"]: "not_met", r["obstruction"]: "unknown", r["warning"]: "met"})
        assert out[lawful] == "not_met" and out[exc] == "not_met", code
        out = _derived(code, **{r["refused"]: "met", r["warning"]: "met"})      # nothing known about the order
        assert out[lawful] == "unknown", code


def test_order_issued_to_obstruct_is_not_lawful():
    r, lawful, _ = _sub(S123), *_ids(S123)
    out = _derived(S123, **{r["refused"]: "met", r["per_agreement"]: "met", r["obstruction"]: "met"})
    assert out[lawful] == "not_met"


def test_llm_never_rules_on_derived_elements():
    els = ISSUES[S123]["elements"]
    lawful, _ = _ids(S123)
    llm = [ElementCheck(id=lawful, status="not_met", evidence="LLM compound verdict")]
    out = {c.id: c for c in derive_checks(els, llm)}
    assert out[lawful].status == "unknown" and "ระบบ" in out[lawful].evidence
