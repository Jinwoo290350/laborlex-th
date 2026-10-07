"""Statute extraction for exam answers (tools/exam/statutes.py). Phrasings are taken from C2 output patterns
(our own system's answers), not exam text. No Gemini; DB only for `unknown`."""

import pytest

from tools.exam import framework as fw
from tools.exam.statutes import family, normalise, statutes, unknown

LRA_ANSWER = ("ลูกจ้างได้รับความคุ้มครองตามพระราชบัญญัติแรงงานสัมพันธ์ พ.ศ. 2518\n"
              "- **ฟ้องศาลแรงงานได้ทันทีในมูลฝ่าฝืนมาตรา 31 หรือเลือกยื่นคำร้องต่อ ครส.** "
              "ฐานกระทำอันไม่เป็นธรรมตามมาตรา 121(1) ภายใน 60 วันตามมาตรา 124 วรรคหนึ่ง\n"
              "`[ม.31 พระราชบัญญัติแรงงานสัมพันธ์ พ.ศ. 2518]` `[ม.124 พระราชบัญญัติแรงงานสัมพันธ์ พ.ศ. 2518]`")


def test_court_name_is_not_the_labour_court_act():
    keys = statutes(LRA_ANSWER)
    assert not any(k.startswith("LCA2522") for k in keys)
    assert keys == ["LRA2518:31", "LRA2518:121", "LRA2518:124"]


def test_labour_court_act_named_by_its_own_name():
    t = "ตาม พ.ร.บ.แรงงานสัมพันธ์ พ.ศ. 2518 มาตรา 31 วรรคหนึ่ง และอำนาจศาลแรงงานตาม พ.ร.บ.จัดตั้งศาลแรงงานฯ มาตรา 8"
    assert statutes(t) == ["LRA2518:31", "LCA2522:8"]
    assert statutes("`[ม.8 วรรคสอง พระราชบัญญัติจัดตั้งศาลแรงงานและวิธีพิจารณาคดีแรงงาน พ.ศ. 2522]`") == ["LCA2522:8"]


def test_bare_section_defaults_to_the_answers_law():
    t = "ตามพระราชบัญญัติแรงงานสัมพันธ์ ข้อตกลงมีผลผูกพัน\n- นายอุทิศเป็นกรรมการลูกจ้างตามมาตรา 52 หรือไม่"
    assert statutes(t) == ["LRA2518:52"]
    assert family(t) == "LRA2518"
    assert statutes("ค่าชดเชยตามมาตรา 118") == ["LPA2541:118"]       # no law named anywhere → LPA


def test_list_of_law_then_section_pairs():
    t = ("พระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541 มาตรา 5 พระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541 มาตรา 76 "
         "ประมวลกฎหมายแพ่งและพาณิชย์ มาตรา 341")
    assert statutes(t) == ["LPA2541:5", "LPA2541:76", "CCC:341"]


def test_short_form_and_thai_digits():
    assert normalise("[ม.๑๑๘/๑ วรรคสอง]") == "[มาตรา 118/1 วรรคสอง]"
    assert statutes("ตาม พ.ร.บ.คุ้มครองแรงงาน `[ม.118/1 วรรคสอง]` `[ม.67]` ใน ม.ค.") == ["LPA2541:118/1", "LPA2541:67"]


def test_law_after_the_section_beats_the_line_context():
    t = "ตามพระราชบัญญัติคุ้มครองแรงงาน มาตรา 118 และ มาตรา 575 แห่งประมวลกฎหมายแพ่งและพาณิชย์"
    assert statutes(t) == ["LPA2541:118", "CCC:575"]
    assert statutes("มาตรา 31 และ 121 แห่งพระราชบัญญัติแรงงานสัมพันธ์") == ["LRA2518:31", "LRA2518:121"]
    assert statutes("พ.ร.บ.คุ้มครองแรงงาน มาตรา 118 และ ป.พ.พ. มาตรา 583") == ["LPA2541:118", "CCC:583"]


def test_existing_framework_behaviour_kept():
    t = "ตาม พ.ร.บ.คุ้มครองแรงงาน มาตรา 118 วรรคหนึ่ง (3) และมาตรา 17 กับมาตรา 17/1 ประกอบ ป.พ.พ. มาตรา 583"
    assert fw.section_set(t) == ["LPA2541:118", "LPA2541:17", "LPA2541:17/1", "CCC:583"]
    assert fw.section_set("มาตรา 41/2 ที่อ้างถึง ไม่มีอยู่ในกฎหมาย") == []


def test_auto_checks_report_unknown_keys_separately(monkeypatch):
    monkeypatch.setattr(fw, "unknown", lambda keys: [k for k in keys if k == "LRA2518:999"])
    chk = fw.auto_checks(["LRA2518:31"], "ตามพระราชบัญญัติแรงงานสัมพันธ์ มาตรา 31 และมาตรา 999", "")
    assert chk["cited"] == ["LRA2518:31"] and chk["unknown_cited"] == ["LRA2518:999"]
    assert chk["section_recall"] == 1.0


def _db_ok():
    try:
        from src.index.db import connect
        with connect() as c:
            return c.execute("SELECT count(*) FROM provisions").fetchone()[0] > 0
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _db_ok(), reason="Legal Index not available")
def test_unknown_flags_sections_the_law_does_not_have():
    assert unknown(["LRA2518:31", "LCA2522:121", "LPA2541:118", "CCC:341"]) == ["LCA2522:121"]


def test_full_labour_court_act_title_counts_once_for_the_family():
    t = ("ฝ่าฝืนพระราชบัญญัติแรงงานสัมพันธ์ ฟ้องตามพระราชบัญญัติจัดตั้งศาลแรงงานและวิธีพิจารณาคดีแรงงาน มาตรา 8\n"
         "- การเลิกจ้างเป็นการฝ่าฝืนมาตรา 31 วรรคหนึ่ง")
    assert family(t) == "LRA2518"
    assert statutes(t) == ["LCA2522:8", "LRA2518:31"]


def test_comma_separated_section_law_pairs_take_the_law_after():
    t = ("มาตรา 31 พระราชบัญญัติแรงงานสัมพันธ์ พ.ศ. 2518, มาตรา 8 (2) "
         "พระราชบัญญัติจัดตั้งศาลแรงงานและวิธีพิจารณาคดีแรงงาน พ.ศ. 2522")
    assert statutes(t) == ["LRA2518:31", "LCA2522:8"]
