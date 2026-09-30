"""Parser tests on synthetic text (structure only — no real legal content)."""
from src.ingest.parse_statute import normalize, parse, to_rows

# indent mode (as produced by extract.py): unit starts are indented, wraps are not
SAMPLE = """พระราชบัญญัติทดสอบ
- ๑ -
  หมวด ๑
  บททั่วไป
  มาตรา ๑ ข้อความวรรคแรกของมาตราหนึ่ง
ซึ่งขึ้นบรรทัดใหม่เพราะตัดคำ
  วรรคสองของมาตราหนึ่ง อ้างถึง
มาตรา ๕ ในบรรทัดที่ตัด
  มาตรา ๒ (ยกเลิก) [^4]
  หมวด ๒ การทดสอบ
  มาตรา ๓ ให้ทำสิ่งต่อไปนี้
  (๑) รายการหนึ่ง
ต่อบรรทัด [^7]
(๒) ไม่ใช่อนุมาตราเพราะไม่เยื้อง
  (๒) รายการสอง
  วรรคสองหลังอนุมาตรา
  มาตรา ๓/๑ [^9]
  มาตราแทรก
\u200bหน้า ๒
  บทเฉพาะกาล
  มาตรา ๔ ข้อความ
"""


def test_normalize_digits_and_noise():
    assert normalize("มาตรา ๑๑๘/๑\u200b\n- ๑๒ -\nหน้า 3") == "มาตรา 118/1"
    assert normalize("มาตรา ๔/(๑)ในกรณี") == "มาตรา 4/1ในกรณี"


def test_structure():
    secs = {s.section_no: s for s in parse(SAMPLE)}
    assert list(secs) == ["1", "2", "3", "3/1", "4"]

    s1 = secs["1"]
    assert (s1.chapter, s1.chapter_title) == ("หมวด 1", "บททั่วไป")
    assert len(s1.paragraphs) == 2
    assert s1.paragraphs[0].text == "ข้อความวรรคแรกของมาตราหนึ่งซึ่งขึ้นบรรทัดใหม่เพราะตัดคำ"
    # wrapped cross-reference with a higher number must not open a section
    assert s1.paragraphs[1].text.endswith("มาตรา 5 ในบรรทัดที่ตัด")

    assert secs["2"].repealed and secs["2"].paragraphs[0].fns == ["4"]

    s3 = secs["3"]
    assert (s3.chapter, s3.chapter_title) == ("หมวด 2", "การทดสอบ")
    assert len(s3.paragraphs) == 2
    assert s3.paragraphs[0].subs == [
        ("(1)", "รายการหนึ่งต่อบรรทัด (2) ไม่ใช่อนุมาตราเพราะไม่เยื้อง"), ("(2)", "รายการสอง")]
    assert s3.paragraphs[0].sub_fns["(1)"] == ["7"]

    assert secs["3/1"].paragraphs[0].text == "มาตราแทรก"
    assert secs["3/1"].paragraphs[0].fns == ["9"]
    assert secs["4"].chapter == "บทเฉพาะกาล"


def test_rows_keys_and_footnotes():
    rows = {r.citation_key: r for r in to_rows(parse(SAMPLE), "TEST")}
    assert "TEST:3:1:(1)" in rows and "TEST:3/1:1" in rows
    assert rows["TEST:3:1:(1)"].footnotes == ["7"]
    assert rows["TEST:3:1"].footnotes == ["7"]          # paragraph row aggregates subs
    assert "[^" not in rows["TEST:3:1"].text


def test_plain_mode_without_indentation():
    secs = parse("มาตรา ๑ ก\n(๑) ข\nมาตรา ๒ ค\n\nวรรคสอง")
    assert [s.section_no for s in secs] == ["1", "2"]
    assert secs[0].paragraphs[0].subs == [("(1)", "ข")]
    assert len(secs[1].paragraphs) == 2


def test_unit_kho():
    secs = parse("ข้อ ๑ ข้อความ\nข้อ ๒ อีกข้อ", unit="ข้อ")
    assert [s.section_no for s in secs] == ["1", "2"]


def test_letter_items_nest_in_sub():
    secs = parse("  ข้อ ๑ งานดังนี้\n  (๑) งานหนึ่ง\n  (ก) ย่อยหนึ่ง\n  (ข) ย่อยสอง\n  (๒) งานสอง", unit="ข้อ")
    assert secs[0].paragraphs[0].subs == [("(1)", "งานหนึ่ง\n(ก) ย่อยหนึ่ง\n(ข) ย่อยสอง"), ("(2)", "งานสอง")]


def test_latin_suffix_sections():
    secs = parse("  มาตรา ๑๗ ก\n  มาตรา ๑๗ ทวิ ข\n  มาตรา ๑๗ ตรี ค\n  มาตรา ๑๘ ง")
    assert [s.section_no for s in secs] == ["17", "17ทวิ", "17ตรี", "18"]
    assert secs[1].paragraphs[0].text == "ข"
