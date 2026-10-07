"""S/2563 Q1 regression (docs/benchmarks/exam_regression_spec_2026-10-06.yaml): two employees with their own wage
and length of service. Severance is computed per employee from that employee's figures — never from the two wages
added together, never skipped as "tenure unknown". Local, no Gemini (facts given as the extractor would)."""

from decimal import Decimal
from pathlib import Path

import pytest

from src.agent.state import AgentState, Facts, IssueSel, PayItem, WorkerFacts

pytestmark = pytest.mark.skipif(not Path("data/processed/rates.yaml").exists(), reason="rate book not built")


def _two_workers(**kw) -> Facts:
    return Facts(workers=[WorkerFacts(name="นายอดิเรก", wage_amount=60000, wage_period="month", service_years=35),
                          WorkerFacts(name="นายพิศาล", wage_amount=36000, wage_period="month", service_years=25)],
                 **kw)


def _calc(facts: Facts, codes=("retirement", "severance_pay")):
    from src.agent.nodes.decide import calculate
    st = AgentState(question="q", facts=facts, issues=[IssueSel(code=c, reason="r") for c in codes])
    return calculate(st)


def test_severance_per_worker_from_own_wage_and_tenure():
    out = _calc(_two_workers())
    calcs = out["calcs"]
    assert calcs["retirement@นายอดิเรก"].amount == Decimal(800000)      # model answer: 400 days of 60,000/month
    assert calcs["retirement@นายพิศาล"].amount == Decimal(480000)       # the "if entitled" amount; entitlement is the draft's
    skipped = out["trace"][0]["summary"]["skipped"]
    assert not any(k.startswith("retirement") for k in skipped) and "termination" in skipped


def test_worker_wages_are_never_summed():
    # the extractor also listed both wages as pay items (seen in the S/2563 run): must not become one 96,000 wage
    items = [PayItem(name=f"ค่าจ้างของ{n}", amount=a, period="month", purpose="work", basis="fixed")
             for n, a in (("นายอดิเรก", 60000), ("นายพิศาล", 36000))]
    calcs = _calc(_two_workers(pay_items=items))["calcs"]
    steps = " ".join(s for r in calcs.values() for s in r.steps)
    assert "96,000" not in steps
    assert calcs["severance_pay@นายอดิเรก"].amount == Decimal(800000)


def test_single_employee_path_unchanged():
    f = Facts(wage_amount=30000, wage_period="month", service_years=5)
    calcs = _calc(f, ("severance_pay",))["calcs"]
    assert list(calcs) == ["severance_pay"]


def test_issue_calc_merges_workers_for_rendering():
    from src.agent.nodes.draft import issue_calc
    st = AgentState(question="q", calcs=_calc(_two_workers())["calcs"])
    steps, cites = issue_calc(st, "retirement")
    from src.agent.nodes.draft import PER_WORKER_NOTE
    assert steps[0] == PER_WORKER_NOTE and steps[1] == "▶ นายอดิเรก" and "▶ นายพิศาล" in steps
    assert any("800,000" in s for s in steps) and cites
    assert issue_calc(st, "annual_leave") == ([], [])
