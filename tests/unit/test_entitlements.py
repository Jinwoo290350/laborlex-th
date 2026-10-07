"""T3 (docs/benchmarks/exam_regression_spec_2026-10-06.yaml): an open "what rights" question about a termination or
retirement also considers annual-leave pay. Local, no Gemini."""

from src.agent.rules.entitlements import add_companion_issues
from src.agent.state import IssueSel


def _codes(issues):
    return [i.code for i in issues]


def test_t3_open_question_adds_annual_leave():
    issues = [IssueSel(code="retirement", reason="r"), IssueSel(code="severance_pay", reason="s")]
    out = add_companion_issues(issues, "เช่นนี้ นายอดิเรกและนายพิศาลจะมีสิทธิอะไรบ้าง อย่างไรบ้าง", [], cap=4)
    assert _codes(out) == ["retirement", "severance_pay", "annual_leave"]
    assert out[-1].reason


def test_t3_closed_question_unchanged():
    issues = [IssueSel(code="severance_pay", reason="s")]
    assert _codes(add_companion_issues(issues, "นายจ้างต้องจ่ายค่าชดเชยหรือไม่", [], cap=4)) == ["severance_pay"]


def test_t3_no_termination_issue_unchanged():
    issues = [IssueSel(code="overtime_and_holiday_pay", reason="o")]
    assert _codes(add_companion_issues(issues, "ลูกจ้างมีสิทธิอะไรบ้าง", [], cap=4)) == ["overtime_and_holiday_pay"]


def test_t3_respects_cap_and_no_duplicates():
    full = [IssueSel(code=c, reason="x") for c in ("severance_pay", "advance_notice", "dismissal_for_cause", "retirement")]
    assert _codes(add_companion_issues(full, "มีสิทธิได้รับเงินอะไรบ้าง", [], cap=4)) == _codes(full)
    already = [IssueSel(code="severance_pay", reason="s"), IssueSel(code="annual_leave", reason="a")]
    assert _codes(add_companion_issues(already, "มีสิทธิอะไรบ้าง", [], cap=4)) == ["severance_pay", "annual_leave"]


def test_t3_open_signal_can_come_from_asked():
    issues = [IssueSel(code="severance_pay", reason="s")]
    out = add_companion_issues(issues, "ข้อเท็จจริงยาว", ["ลูกจ้างจะได้รับเงินใดบ้าง"], cap=4)
    assert "annual_leave" in _codes(out)
