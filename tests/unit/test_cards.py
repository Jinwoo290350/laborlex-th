"""M4 Holding Cards: schema, crosswalk, procedural tagging, decided_by, card search (tiny fixtures, no models)."""

import json
from pathlib import Path

import numpy as np
import pytest

from src.index.card_search import CardIndex
from src.index.cards import (
    HoldingCard,
    Segment,
    card_from_appeal,
    card_from_deka,
    classify_span,
    headnote_segments,
)

MOI = "ประกาศกระทรวงมหาดไทย เรื่อง การคุ้มครองแรงงาน"


def law(code, name, sec):
    return {"law_code": code, "law_name": name, "law_short": name, "section": sec, "paragraph": ""}


def deka(no, short, long="", laws=()):
    return {"deka_no": no, "short_text": short, "long_text": long, "laws": list(laws), "labour": True,
            "source_url": f"https://deka.supremecourt.or.th/search (เลขที่ {no})"}


# ---------------------------------------------------------------- crosswalk + regime
@pytest.mark.parametrize("code", ["ค77-02", "ค77-04"])
def test_old_clause_46_47_map_to_lpa_118_119(code):
    c = card_from_deka(deka("100/2530", "ลูกจ้างละทิ้งหน้าที่ นายจ้างไม่ต้องจ่ายค่าชดเชย",
                            laws=[law(code, MOI, "46"), law(code, MOI, "47 (3)")]))
    assert {"LPA2541:118", "LPA2541:119"} <= set(c.provisions)
    assert c.old_provisions == ["MOI2515:46", "MOI2515:47"]
    assert c.regime == "pre2541"
    assert "severance_pay" in c.issue_codes and "dismissal_for_cause" in c.issue_codes


def test_old_clause_cited_only_in_headnote_text_is_mapped():
    c = card_from_deka(deka("101/2531", f"จึงไม่เข้าข้อยกเว้นตาม{MOI} ข้อ ๔๗(๓) ที่จะเลิกจ้างโดยไม่ต้องจ่ายค่าชดเชย"))
    assert "LPA2541:119" in c.provisions and c.regime == "pre2541"


def test_post2541_and_headnote_citation_without_laws_field():
    c = card_from_deka(deka("3934/2557", "เงินนั้นจึงไม่ใช่ค่าจ้างตาม พ.ร.บ.คุ้มครองแรงงาน พ.ศ.2541 มาตรา 5 การที่จำเลยย้ายโจทก์"))
    assert c.provisions == ["LPA2541:5"]
    assert c.regime == "post2541" and c.year == 2557
    assert "definition_of_wages" in c.issue_codes


# ---------------------------------------------------------------- procedural tagging
def test_only_procedural_sections_is_not_substantive():
    c = card_from_deka(deka("200/2550", "คำฟ้องของโจทก์ไม่เคลือบคลุม",
                            laws=[law("ป04-01", "ประมวลกฎหมายวิธีพิจารณาความแพ่ง", "172"),
                                  law("จ07-05", "พระราชบัญญัติจัดตั้งศาลแรงงานฯ", "31")]))
    assert c.substantive is False


def test_lca_49_unfair_dismissal_is_substantive():
    c = card_from_deka(deka("201/2550", "การเลิกจ้างมีเหตุผลอันสมควร ไม่เป็นการเลิกจ้างที่ไม่เป็นธรรม",
                            laws=[law("จ07-05", "พระราชบัญญัติจัดตั้งศาลแรงงานฯ", "49"),
                                  law("จ07-05", "พระราชบัญญัติจัดตั้งศาลแรงงานฯ", "54")]))
    assert c.substantive is True


# ---------------------------------------------------------------- decided_by
APPEAL_LONG = (
    "โจทก์ฟ้อง ขอให้บังคับจำเลยชดใช้ค่าเสียหาย\n\nศาลแรงงานกลาง พิพากษายกฟ้อง\n\nโจทก์อุทธรณ์\n\n"
    "ศาลอุทธรณ์คดีชำนัญพิเศษแผนกคดีแรงงานวินิจฉัยว่า ศาลแรงงานกลางฟังข้อเท็จจริงว่า โจทก์ได้รับค่าตอบแทน"
    "เป็นเงินเดือน เดือนละ 33,000 บาท ค่าเช่าบ้านเดือนละ 3,000 บาท เป็นการเหมาจ่าย เงินค่าเช่าบ้านที่จำเลยจ่าย"
    "ให้แก่โจทก์เป็นการจ่ายเพื่อตอบแทนการทำงานในเวลาทำงานปกติของวันทำงานของโจทก์จึงเป็นค่าจ้าง แล้ววินิจฉัยว่า "
    "การเลิกจ้างมีเหตุผลอันสมควร\n\n"
    "มีปัญหาต้องวินิจฉัยตามอุทธรณ์ของโจทก์ว่า โจทก์ถูกเลิกจ้างโดยไม่เป็นธรรมหรือไม่ เห็นว่า การที่จำเลยมีหนังสือ"
    "เตือนโจทก์ถึงการทำงานถึง 2 ครั้ง ทั้งยังลงโทษพักงาน แต่โจทก์ไม่นำพาหรือเชื่อฟังคำสั่ง แสดงให้เห็นว่า"
    "การเลิกจ้างเป็นกรณีที่มีเหตุผลอันสมควรและเพียงพอ ไม่ถือว่าเป็นการเลิกจ้างไม่เป็นธรรม\n\n"
    "ที่โจทก์อุทธรณ์ว่าโจทก์ไม่ได้ออกจากงานก่อนเวลา เป็นอุทธรณ์ในข้อเท็จจริง ศาลอุทธรณ์คดีชำนัญพิเศษไม่รับวินิจฉัย\n\n"
    "พิพากษายืน")
APPEAL_SHORT = ("คำพิพากษาศาลอุทธรณ์คดีชำนัญพิเศษที่ 9/2567\n\nพ.ร.บ. จัดตั้งศาลแรงงานและวิธีพิจารณาคดีแรงงาน พ.ศ. 2522 "
                "มาตรา 49\n\nการที่จําเลยมีหนังสือเตือนโจทก์ถึงการทํางานถึง 2 ครั้ง ทั้งยังลงโทษพักงาน แต่โจทก์ไม่นําพา"
                "หรือเชื่อฟังคําสั่ง แสดงให้เห็นว่าการเลิกจ้างเป็นกรณีที่มีเหตุผลอันสมควรและเพียงพอ")


def test_restated_lower_court_finding_is_not_own_holding():
    span = "เงินค่าเช่าบ้านที่จำเลยจ่ายให้แก่โจทก์เป็นการจ่ายเพื่อตอบแทนการทำงานในเวลาทำงานปกติของวันทำงานของโจทก์จึงเป็นค่าจ้าง"
    assert classify_span(APPEAL_LONG, span) == "restated_lower_court"


def test_appeal_headnote_is_own_holding_and_header_is_stripped():
    row = {"case_no": "ร 9/2567", "court": "ศาลอุทธรณ์คดีชำนัญพิเศษ", "doc_type": "คำพิพากษา",
           "case_no_year": 2567, "holding_short": APPEAL_SHORT, "holding_long": APPEAL_LONG}
    c = card_from_appeal(row, [{"law_code": "LCA_2522", "section": "49"}])
    assert len(c.segments) == 1 and c.segments[0].text.startswith("การที่จําเลย")
    assert c.decided_by == "own_holding" and c.substantive
    assert c.ratio_quote and c.ratio_quote in APPEAL_SHORT
    assert c.provisions == ["LCA2522:49"]


def test_span_in_paragraph_ending_with_refusal_is_procedural():
    span = "ที่โจทก์อุทธรณ์ว่าโจทก์ไม่ได้ออกจากงานก่อนเวลา"
    assert classify_span(APPEAL_LONG, span) == "procedural_refusal"


def test_refusal_segment_and_mixed_card():
    long = ("โจทก์ฟ้องว่า จำเลยเลิกจ้าง\n\nศาลฎีกาแผนกคดีแรงงานวินิจฉัยว่า การภาคทัณฑ์เป็นเพียงหนังสือของโจทก์ผู้ให้สัญญา"
            "แต่ฝ่ายเดียว มิได้มีลักษณะเป็นหนังสือตักเตือนของจำเลยซึ่งเป็นนายจ้าง จึงไม่เข้าข้อยกเว้น "
            "จำเลยให้โจทก์ออกจากงานเพราะทำผิดวินัยตามข้อบังคับ แต่ข้อบังคับดังกล่าวมิได้ถือว่าเป็นความเสียหายถึงร้ายแรง "
            "ฉะนั้นเมื่อจำเลยเลิกจ้างโจทก์โดยมิได้ตักเตือนเป็นหนังสือก่อน จึงไม่เข้าข้อยกเว้นที่จะเลิกจ้างโดยไม่ต้องจ่ายค่าชดเชย\n\n"
            "สำหรับอุทธรณ์ของจำเลยที่ว่าอายุการทำงานของโจทก์ไม่ครบ 1 ปี เป็นอุทธรณ์ในข้อเท็จจริง ศาลฎีกาไม่รับวินิจฉัย")
    short = ("หนังสือของโจทก์ผู้ให้สัญญาแต่ฝ่ายเดียว มิได้มีลักษณะเป็นหนังสือตักเตือนของจำเลยซึ่งเป็นนายจ้าง\n\n"
             "การที่จำเลยอุทธรณ์ว่าอายุการทำงานของโจทก์ไม่ครบ 1 ปี จึงเป็นอุทธรณ์ในข้อเท็จจริง ต้องห้ามตามกฎหมาย")
    c = card_from_deka(deka("1/2526", short, long))
    assert [s.decided_by for s in c.segments] == ["own_holding", "procedural_refusal"]
    assert c.decided_by == "own_holding" and c.substantive
    assert "อายุการทำงาน" not in c.text          # the refused point is not searchable
    only_refused = card_from_deka(deka("2/2526", short.split("\n\n")[1], long))
    assert only_refused.decided_by == "procedural_refusal" and not only_refused.substantive


def test_long_paragraph_deciding_one_point_and_refusing_another_is_mixed():
    from src.index.cards import is_mixed, refusal_marks
    holding = "สัญญาจ้างแรงงานระหว่างโจทก์กับจำเลยเป็นสัญญาที่ไม่มีกำหนดระยะเวลา นายจ้างจึงต้องบอกกล่าวล่วงหน้า " * 5
    refused = "ที่จำเลยอุทธรณ์ว่าโจทก์ทำงานไม่ครบหนึ่งปี เป็นอุทธรณ์ในข้อเท็จจริง ต้องห้ามตามกฎหมาย"
    assert is_mixed(holding + refused, refusal_marks(holding + refused))
    assert not is_mixed(refused, refusal_marks(refused))
    assert refusal_marks("การกระทำที่ต้องห้ามตามมาตรา 121 เป็นการกระทำอันไม่เป็นธรรม") == []


def test_unknown_without_structure():
    assert classify_span("สั้น", "ข้อความใดๆ ที่ยาวพอสมควรสำหรับการทดสอบ") == "unknown"


def test_banner_fragments_dropped():
    segs = headnote_segments("++ เรื่อง คดีแรงงาน ++ ++ " + "ก" * 90 + " ++", "ศาลฎีกา")
    assert segs == ["ก" * 90]


def test_schema_roundtrip():
    c = card_from_deka(deka("3/2560", "ค่าน้ำมันรถเหมาจ่ายไม่เป็นค่าจ้างตาม พ.ร.บ.คุ้มครองแรงงาน พ.ศ. 2541 มาตรา 5"))
    again = HoldingCard.model_validate_json(c.model_dump_json())
    assert again == c and again.legal_question == "" and again.fact_features == {}


# ---------------------------------------------------------------- search
def _card(no, text, court="ศาลฎีกา", provisions=("LPA2541:5",), issues=("definition_of_wages",),
          decided_by="own_holding", substantive=True):
    return HoldingCard(deka_no=no, court=court, year=2550, regime="post2541", provisions=list(provisions),
                       issue_codes=list(issues), decided_by=decided_by, substantive=substantive,
                       ratio_quote=text, segments=[Segment(text=text, decided_by=decided_by)])


def _fake_embed(texts):
    """Deterministic bag-of-characters vectors (no model)."""
    out = np.zeros((len(texts), 128), dtype=np.float32)
    for i, t in enumerate(texts):
        for ch in t:
            out[i, ord(ch) % 128] += 1
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


CARDS = [
    _card("1/2550", "ค่าเช่าบ้านที่นายจ้างจ่ายเพื่อเป็นสวัสดิการไม่เป็นค่าจ้างตามกฎหมาย"),
    _card("ร 2/2565", "ค่าเช่าบ้านที่นายจ้างจ่ายเพื่อเป็นสวัสดิการไม่เป็นค่าจ้าง", court="ศาลอุทธรณ์คดีชำนัญพิเศษ"),
    _card("3/2550", "ค่าเช่าบ้านจึงเป็นค่าจ้าง", decided_by="restated_lower_court"),
    _card("4/2550", "ค่าเช่าบ้าน ศาลฎีกาไม่รับวินิจฉัย", decided_by="procedural_refusal", substantive=False),
    _card("5/2550", "ลูกจ้างประกอบกิจการแข่งขันกับนายจ้าง เป็นการจงใจทำให้นายจ้างได้รับความเสียหาย",
          provisions=("LPA2541:119",), issues=("dismissal_for_cause",)),
    _card("6/2550", "คำฟ้องไม่เคลือบคลุม", provisions=("CPC:172",), issues=(), substantive=False),
]


@pytest.fixture(scope="module")
def index():
    return CardIndex(CARDS, embed_fn=_fake_embed)


def test_search_default_filters(index):
    nos = [r["deka_no"] for r in index.search("ค่าเช่าบ้านเป็นค่าจ้างหรือไม่", k=10)]
    assert "3/2550" not in nos and "4/2550" not in nos and "6/2550" not in nos
    assert nos[0] == "1/2550"


def test_search_issue_and_provision_filters(index):
    assert [r["deka_no"] for r in index.search("นายจ้าง", issue_code="dismissal_for_cause")] == ["5/2550"]
    assert [r["deka_no"] for r in index.search("นายจ้าง", provisions=["LPA2541:119:1"])] == ["5/2550"]
    allc = [r["deka_no"] for r in index.search("ค่าเช่าบ้าน", k=10, include_all=True)]
    assert "3/2550" in allc


def test_supreme_preferred_only_when_close(index):
    res = index.search("ค่าเช่าบ้านที่นายจ้างจ่ายเพื่อเป็นสวัสดิการไม่เป็นค่าจ้าง", k=2)
    assert [r["deka_no"] for r in res] == ["1/2550", "ร 2/2565"]
    plain = index.search("ค่าเช่าบ้านที่นายจ้างจ่ายเพื่อเป็นสวัสดิการไม่เป็นค่าจ้าง", k=2, margin=0.0)
    assert [r["deka_no"] for r in plain] == ["ร 2/2565", "1/2550"]
    assert all("score" in r and r["label"] for r in res)
    far = CardIndex([CARDS[1], _card("7/2550", "ข้อความอื่นที่ไม่เกี่ยวข้องเลย")], embed_fn=_fake_embed)
    assert far.search("ค่าเช่าบ้านที่นายจ้างจ่ายเพื่อเป็นสวัสดิการ", k=2)[0]["deka_no"] == "ร 2/2565"


# ---------------------------------------------------------------- real corpus (skipped when the raw data is absent)
RAW = Path("data/raw")
needs_raw = pytest.mark.skipif(not (RAW / "deka/labour_deka.jsonl").exists(), reason="raw corpora not present")


@pytest.fixture(scope="module")
def raw_rows():
    deka_rows = {}
    for line in (RAW / "deka/labour_deka.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        deka_rows[d["deka_no"]] = d
    legacy = {}
    for line in (RAW / "legacy/cases.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        legacy[d["case_no"]] = d
    return deka_rows, legacy


@needs_raw
def test_crosswalk_covers_every_clause_46_47_decision(raw_rows):
    deka_rows, _ = raw_rows
    hits = [r for r in deka_rows.values()
            if any(law.get("law_code") in ("ค77-02", "ค77-04") and (law.get("section") or "").split()[:1] in (["46"], ["47"])
                   for law in r["laws"])]
    assert len(hits) > 150
    for r in hits:
        c = card_from_deka(r)
        assert {"LPA2541:118", "LPA2541:119"} & set(c.provisions), r["deka_no"]


@needs_raw
def test_known_restated_findings_in_appeal_decisions(raw_rows):
    _, legacy = raw_rows
    long1020 = legacy["ร 1020/2567"]["holding_long"]
    assert classify_span(long1020, "เงินค่าเช่าบ้านที่จำเลยที่ 1 จ่ายให้แก่โจทก์เป็นการจ่ายเพื่อตอบแทนการทำงานในเวลา"
                                   "ทำงานปกติของวันทำงานของโจทก์จึงเป็นค่าจ้าง") == "restated_lower_court"
    long2257 = legacy["ร 2257/2565"]["holding_long"]
    assert classify_span(long2257, "การคำนวณค่าชดเชยจึงต้องใช้ฐานอัตราค่าจ้างขั้นต่ำในอัตราดังกล่าว คิดเป็นเงิน 76,800 บาท"
                         ) == "restated_lower_court"
    for no in ("ร 1020/2567", "ร 2257/2565"):
        c = card_from_appeal(legacy[no], [])
        assert c.decided_by == "own_holding", no


@needs_raw
def test_1252_2526_tenure_point_is_a_procedural_refusal(raw_rows):
    deka_rows, _ = raw_rows
    c = card_from_deka(deka_rows["1252/2526"])
    tenure = [s for s in c.segments if "ครบ 1 ปี" in s.text]
    assert tenure and all(s.decided_by == "procedural_refusal" for s in tenure)
    assert "ครบ 1 ปี" not in c.text
