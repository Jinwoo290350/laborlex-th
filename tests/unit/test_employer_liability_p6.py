"""P6 (FIX_PLAN_v2): who is liable as employer — the ม.5 "นายจ้าง" definition and the ป.พ.พ. partnership sections.
The partnership sections are indexed from CCC.txt, the employer-liability issue retrieves them and distinguishes
juristic person / unlimited partner / meddling limited partner / company director, and the ม.5 "นายจ้าง" paragraph
always reaches the draft and the allowed citations for that issue. Local: no LLM."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.agent.state import AgentState, IssueSel

CODE = "employer_liability_and_representatives"
PARTNERSHIP = ["1025", "1050", "1070", "1077", "1080", "1087", "1088", "1095"]
ISSUES = {i["code"]: i for i in yaml.safe_load(Path("data/processed/issues.yaml").read_text(encoding="utf-8"))}


def _db_ok() -> bool:
    try:
        from src.index.db import connect
        with connect() as c:
            c.execute("select 1")
        return True
    except Exception:  # noqa: BLE001
        return False


needs_db = pytest.mark.skipif(not _db_ok(), reason="Legal Index not loaded")


# ---------- 1. registry and index ----------

def test_registry_includes_partnership_sections():
    ccc = next(e for e in yaml.safe_load(Path("data/processed/laws.yaml").read_text(encoding="utf-8"))
               if e["short_name"] == "CCC")
    for s in PARTNERSHIP:
        assert any(lo <= int(s) <= hi for lo, hi in ccc["include_sections"]), f"ม.{s} not in include_sections"


def test_append_mode_only_adds_missing_keys():
    from src.ingest.parse_statute import ProvisionRow
    from src.ingest.pipeline import new_rows
    row = lambda k: ProvisionRow(chapter=None, section_no=k.split(":")[1], paragraph_no=1, sub_no=None, text="t",
                                 repealed=False, footnotes=[], citation_key=k)
    rows = [row("CCC:583:1"), row("CCC:1077:1")]
    assert [r.citation_key for r in new_rows(rows, {"CCC:583:1"})] == ["CCC:1077:1"]


EXTRA = Path("data/raw/deka/extra/2026-10-11_partnership_s4.html")


@pytest.mark.skipif(not EXTRA.exists(), reason="saved deka page not present")
def test_extra_page_yields_only_named_decisions():
    from src.ingest.load_cases import extra_records
    got = extra_records(EXTRA, ["15199-15200/2558", "2066/2545"])
    assert [d["deka_no"] for d in got] == ["15199-15200/2558", "2066/2545"]
    assert "1077 (2) และ 1087" in got[0]["short_text"]
    with pytest.raises(SystemExit):
        extra_records(EXTRA, ["1/2400"])


@needs_db
def test_partnership_paragraphs_in_db():
    from src.index import tools
    # paragraph structure as printed in data/raw/laws/ocs/CCC.txt
    expect = {"1025": 1, "1050": 1, "1070": 1, "1077": 1, "1080": 2, "1087": 1, "1088": 2, "1095": 2}
    for sec, n in expect.items():
        assert len(tools.get_section("CCC", sec)) == n, f"CCC ม.{sec}"
    assert [r["citation_key"] for r in tools.get_subitems("CCC:1077:1")] == ["CCC:1077:1:(1)", "CCC:1077:1:(2)"]
    assert len(tools.get_subitems("CCC:1095:2")) == 3
    assert tools.get_provision("CCC:1088:1")["text"].startswith("ถ้าผู้เป็นหุ้นส่วนจำพวกจำกัดความรับผิดผู้ใดสอดเข้าไป")
    assert "ไม่มีจำกัดจำนวน" in tools.get_provision("CCC:1077:1:(2)")["text"]


# ---------- 2. taxonomy ----------

def test_issue_lists_employer_definition_and_partnership_sections():
    iss = ISSUES[CODE]
    assert "LPA2541:5" in iss["primary_provisions"]
    for s in ("1077", "1087", "1088", "1095"):
        assert f"CCC:{s}" in iss["primary_provisions"]
        assert f"CCC:{s}" in iss["statutory_provisions"]


def test_issue_elements_distinguish_the_four_kinds_of_defendant():
    els = {e["id"]: e for e in ISSUES[CODE]["elements"]}
    cites = lambda i: set(els[i]["citation_keys"])
    assert "LPA2541:5:2" in cites("is_juristic_person_employer")
    assert {"CCC:1077:1:(2)", "CCC:1087:1"} <= cites("is_unlimited_or_managing_partner")
    assert {"CCC:1088:1", "CCC:1088:2"} <= cites("limited_partner_meddled_in_management")
    assert "ไม่ต้องรับผิดเป็นการส่วนตัว" in els["is_company_director"]["question"]
    derived = els["partner_personally_liable"]
    assert derived["derive"] == {"any": ["is_unlimited_or_managing_partner", "limited_partner_meddled_in_management"]}


def test_statutory_sections_are_primary_without_dev_support():
    from src.agent.nodes.retrieve import primary_sections
    secs = primary_sections(CODE, set())
    for s in ("CCC:1077", "CCC:1087", "CCC:1088", "CCC:1095"):
        assert s in secs
    # dev-supported ranking is unchanged for other issues
    assert not any(s.startswith("CCC:10") for s in primary_sections("severance_pay", set()))


# ---------- 3. the "นายจ้าง" definition reaches the draft and the allowed set ----------

def _state(codes: list[str]) -> AgentState:
    return AgentState(question="ห้างหุ้นส่วนจำกัดเลิกจ้างลูกจ้าง ใครต้องรับผิดในฐานะนายจ้าง",
                      issues=[IssueSel(code=c, reason="r") for c in codes])


@needs_db
def test_employer_definition_key_found_by_text():
    from src.agent.nodes.decide import employer_definition_key
    from src.index import tools
    k = employer_definition_key()
    assert tools.get_provision(k)["text"].startswith("“นายจ้าง” หมายความว่า")


@needs_db
def test_employer_definition_in_draft_and_allowed_when_issue_selected():
    from src.agent.nodes.decide import employer_definition_key
    from src.agent.nodes.draft import _provisions_block, allowed_keys
    k = employer_definition_key()
    st = _state([CODE])
    assert k in allowed_keys(st)
    assert {f"{k}:(1)", f"{k}:(2)"} <= allowed_keys(st)
    assert k in _provisions_block(st)
    other = _state(["severance_pay"])
    assert k not in allowed_keys(other) and k not in _provisions_block(other)


@needs_db
def test_employer_definition_not_duplicated_when_selected():
    from src.agent.nodes.decide import employer_definition_key
    from src.agent.nodes.draft import _provisions_block
    from src.index import tools
    k = employer_definition_key()
    row = tools.get_provision(k)
    st = _state([CODE]).model_copy(update={"selected": {CODE: [k]}, "candidates": {CODE: [row]}})
    assert _provisions_block(st).count(f"{k} ") + _provisions_block(st).count(f"{k}|") <= 1


# ---------- 4. holding rule ----------

def test_hr3_rule_for_partners():
    from src.agent.rules.holding_rules import load_rules, rules_block
    hr3 = next(r for r in load_rules() if r.id == "HR-3")
    assert {"CCC:1077", "CCC:1087", "CCC:1088"} <= set(hr3.provisions)
    assert "1095" in hr3.outcome
    block = rules_block(["CCC:1077:1:(2)"])
    assert "HR-3" in block and "15199-15200/2558" in block
    assert "ศาลอุทธรณ์คดีชำนัญพิเศษที่ 302/2564" in block     # appeal-court rulings keep their court
    assert "HR-3" not in rules_block(["LPA2541:119:1"])
