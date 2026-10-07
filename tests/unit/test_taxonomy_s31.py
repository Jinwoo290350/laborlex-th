"""T1/T2 (docs/benchmarks/exam_regression_spec_2026-10-06.yaml): s.31 protection is its own issue without the
committee route; the lawful-order exception is a checkable element for s.31 and s.123. Local, no Gemini."""

import json
from pathlib import Path

import yaml

ISSUES = {i["code"]: i for i in yaml.safe_load(Path("data/processed/issues.yaml").read_text(encoding="utf-8"))}
TAGS = json.loads(Path("data/processed/dev100_issues.json").read_text(encoding="utf-8"))
S31 = "dispute_protection_s31"
ULP = "unfair_labor_practices_and_disputes"
S123 = "employee_committee_and_union_protection"


def _cites(issue: dict) -> list[str]:
    return [k for e in issue.get("elements", []) for k in e.get("citation_keys", [])]


def test_t1_s31_issue_exists_without_committee_route():
    assert S31 in ISSUES
    s31 = ISSUES[S31]
    assert not any(k.startswith("LRA2518:124") for k in _cites(s31)), "s.31 must not carry the s.124 complaint element"
    route = [e for e in s31["elements"] if "ศาลแรงงาน" in e["question"]]
    assert route and any("LRA2518:31:1" in e["citation_keys"] for e in route), "s.31 needs a court-route element"


def test_t1_ulp_no_longer_holds_s31_elements():
    assert not any(k.startswith("LRA2518:31") for k in _cites(ISSUES[ULP]))
    assert any(k.startswith("LRA2518:124") for k in _cites(ISSUES[ULP])), "s.121 keeps the committee route"


def test_t1_dev_tags_and_support_follow_the_split():
    assert S31 in TAGS["dev053"] and S31 in TAGS["dev102"]
    from src.agent.nodes.retrieve import primary_sections
    secs = primary_sections(S31, set())
    assert "LRA2518:31" in secs and "LRA2518:124" not in secs


def test_t2_lawful_order_exception_is_its_own_element():
    for code, key in ((S31, "LRA2518:31:1"), (S123, "LRA2518:123:1")):
        els = [e for e in ISSUES[code]["elements"] if key in e.get("citation_keys", [])
               and "คำสั่งอันชอบด้วยกฎหมาย" in e["question"]]
        assert els, f"{code}: no lawful-order element"
        assert any("ตักเตือนเป็นหนังสือ" in e["question"] for e in els), f"{code}: written-warning condition missing"


def test_d_section_support_weights_the_issue_anchor_highest():
    from src.agent.nodes.retrieve import section_support
    w = section_support(S31, set())
    assert max(w, key=w.get) == "LRA2518:31"
    assert all(v >= 1 for v in w.values())
    # leave-one-out: with every dev question excluded there is no evidence, so no preference
    assert section_support(S31, set(TAGS)) == {}


def test_d_link_preference_is_opt_in_per_issue():
    from src.params import P
    assert P("cases.prefer_linked") == [S31], "widening needs eval evidence (decisions #16: 77% of dev slots change)"
