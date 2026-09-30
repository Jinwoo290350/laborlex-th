"""Parser tests on synthetic text (structure only — no real legal content)."""
from src.ingest.parse_statute import normalize, parse, to_rows

SAMPLE = """พระราชบัญญัติทดสอบ
- ๑ -
หมวด ๑
บททั่วไป
มาตรา ๑ ข้อความวรรคแรกของมาตราหนึ่ง
ซึ่งขึ้นบรรทัดใหม่เพราะตัดคำ
  วรรคสองของมาตราหนึ่ง อ้างถึง
มาตรา ๑ ในบรรทัดที่ตัด
มาตรา ๒ (ยกเลิก)
หมวด ๒
การทดสอบ
มาตรา ๓ ให้ทำสิ่งต่อไปนี้
(๑) รายการหนึ่ง
ต่อบรรทัด
(๒) รายการสอง
  วรรคสองหลังอนุมาตรา
[มาตรา ๓ แก้ไขเพิ่มเติมโดยกฎหมายทดสอบ]
มาตรา ๓/๑ มาตราแทรก
\u200bหน้า ๒
มาตรา ๔
  ข้อความขึ้นบรรทัดใหม่
"""


def test_normalize_digits_and_noise():
    n = normalize("มาตรา ๑๑๘/๑\u200b\n- ๑๒ -\nหน้า 3")
    assert n == "มาตรา 118/1"


def test_structure():
    secs = {s.section_no: s for s in parse(SAMPLE)}
    assert list(secs) == ["1", "2", "3", "3/1", "4"]

    s1 = secs["1"]
    assert s1.chapter == "หมวด 1"
    assert len(s1.paragraphs) == 2
    assert s1.paragraphs[0].text == "ข้อความวรรคแรกของมาตราหนึ่งซึ่งขึ้นบรรทัดใหม่เพราะตัดคำ"
    # wrapped back-reference must not open a new section
    assert s1.paragraphs[1].text.endswith("มาตรา 1 ในบรรทัดที่ตัด")

    assert secs["2"].repealed

    s3 = secs["3"]
    assert s3.chapter == "หมวด 2"
    assert len(s3.paragraphs) == 2
    assert s3.paragraphs[0].subs == [("(1)", "รายการหนึ่งต่อบรรทัด"), ("(2)", "รายการสอง")]
    assert s3.notes == ["มาตรา 3 แก้ไขเพิ่มเติมโดยกฎหมายทดสอบ"]

    assert secs["4"].paragraphs[0].text == "ข้อความขึ้นบรรทัดใหม่"


def test_rows_keys_unique():
    rows = to_rows(parse(SAMPLE), "TEST")
    keys = [r.citation_key for r in rows]
    assert "TEST:3:1:(1)" in keys and "TEST:3/1:1" in keys
    assert len(keys) == len(set(keys))


def test_unit_kho():
    secs = parse("ข้อ ๑ ข้อความ\nข้อ ๒ อีกข้อ", unit="ข้อ")
    assert [s.section_no for s in secs] == ["1", "2"]
