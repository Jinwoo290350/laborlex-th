"""Parser tests on synthetic HTML that mimics the page structure (made-up text, not exam content)."""

from tools.exam.parse_mjsheet import parse_page, term_year

NEW_FMT = """<h1>LAW4104 (LAW4004) กฎหมายแรงงานและการประกันสังคม 1/2567</h1>
<div class="td-post-content tagdiv-type"><p>คำชี้แจง</p><script>ad()</script>
<div class="apMainContainer">โฆษณา</div>
<div><p>ข้อ ๑. นายจ้างเลิกจ้างลูกจ้างที่ทำงานมาสามปี</p>
<p>ธงคําตอบ</p><p>หลักกฎหมาย พ.ร.บ.คุ้มครองแรงงาน มาตรา 118 และมาตรา 119 บัญญัติว่า</p>
<p>วินิจฉัย</p><p>กรณีนี้นายจ้างต้องจ่ายตามมาตรา 118</p><p>สรุป</p><p>ต้องจ่าย</p>
<p>ข้อ 2. สหภาพแรงงานยื่นข้อเรียกร้อง</p><p>บริษัทมีข้อบังคับ</p>
<p>ข้อ 1 ให้ยกเลิกระเบียบเดิม</p>
<p>ตอบ</p><p>หลักกฎหมาย พ.ร.บ.แรงงานสัมพันธ์ มาตรา 13 และมาตรา 31</p>
<p>วินิจฉัย</p><p>จากข้อเท็จจริงเป็นไปตามมาตรา 31</p></div></div>
<div class="sidebar">ข้อ 3. เนื้อหาอื่นของเว็บ มาตรา 999</div>"""

OLD_FMT = """<h1>LAW4004 กฎหมายแรงงานและการประกันสังคม การสอบไล่ภาคฤดูร้อน ปีการศึกษา 2552</h1>
<div class="td-post-content"><div><p>ข้อ 1 ลูกจ้างทำงานล่วงเวลา</p><p>แนวคำตอบ</p>
<p>มาตรา 61 กำหนดค่าล่วงเวลา ดังนั้นตามมาตรา 61 ลูกจ้างได้รับ</p>
<p>ข้อ 2 ลูกจ้างประสบอันตราย</p><p>แนวคำตอบ</p><p>พ.ร.บ.เงินทดแทน มาตรา 5 นิยาม</p></div></div>"""


def test_new_format_pairs_and_ignores_quoted_clauses_and_sidebar():
    rows = parse_page(NEW_FMT, "https://example/x/")
    assert [r["question_no"] for r in rows] == [1, 2]
    r1, r2 = rows
    assert r1["exam_year"] == "2567" and r1["semester"] == "1" and r1["exam_id"] == "ram-law4004-1-2567-q1"
    assert r1["question"].startswith("นายจ้างเลิกจ้าง") and r1["model_answer"].startswith("ธงคำตอบ")
    assert r1["sections_all"] == "LPA2541:118;LPA2541:119"
    assert r1["sections_needed_draft"] == "LPA2541:118" and r1["sections_supporting_draft"] == "LPA2541:119"
    assert "ข้อ 1 ให้ยกเลิก" in r2["question"]           # quoted clause stays inside question 2
    assert r2["sections_needed_draft"] == "LRA2518:31" and r2["sections_supporting_draft"] == "LRA2518:13"
    assert all("999" not in r["sections_all"] and "โฆษณา" not in r["question"] for r in rows)
    assert all(r["parse_flags"] == "" for r in rows)


def test_old_format_and_summer_term():
    rows = parse_page(OLD_FMT, "u")
    assert len(rows) == 2 and rows[0]["semester"] == "S" and rows[0]["exam_year"] == "2552"
    assert rows[0]["sections_needed_draft"] == "LPA2541:61"
    assert rows[1]["sections_all"] == "WCA2537:5" and "NO_APPLICATION_PART" in rows[1]["parse_flags"]


def test_term_year_variants():
    assert term_year("LAW4004 กฎหมายแรงงาน ซ่อม 1/2551") == ("R1", "2551")
    assert term_year("LAW4004 กฎหมายแรงงาน S/2560") == ("S", "2560")
    assert term_year("LAW4004 การสอบไล่ภาค 2 ปีการศึกษา 2553") == ("2", "2553")


def test_missing_answer_is_flagged():
    rows = parse_page('<h1>LAW4004 1/2560</h1><div class="td-post-content"><p>ข้อ 1. โจทย์</p>'
                      '<p>ข้อ 2. โจทย์</p></div>', "u")
    assert [r["parse_flags"] for r in rows] == ["NO_ANSWER;NO_APPLICATION_PART"] * 2


def test_scope_rules():
    from tools.exam.parse_mjsheet import scope
    assert scope(["LPA2541:118", "LRA2518:31"])[0] == "yes"
    s, reason, inside, other = scope(["WCA2537:5", "WCA2537:18"])
    assert s == "no" and "WCA2537" in reason and inside == [] and other == ["WCA2537:5", "WCA2537:18"]
    s, reason, inside, other = scope(["LPA2541:118", "CCC:583"])
    assert s == "review" and inside == ["LPA2541:118"] and other == ["CCC:583"]
    assert scope([])[0] == "review"


def test_parsed_rows_carry_scope_and_keep_other_laws_out_of_needed():
    rows = parse_page(OLD_FMT, "u")
    assert rows[0]["in_scope"] == "yes" and rows[0]["sections_needed_draft"] == "LPA2541:61"
    wca = rows[1]
    assert wca["in_scope"] == "no" and wca["sections_needed_draft"] == ""
    assert wca["sections_needed_other_draft"] == "WCA2537:5" and "WCA2537" in wca["scope_reason"]


def test_ccc_bleed_and_family():
    from tools.exam.parse_mjsheet import answer_family, fix_ccc_bleed
    assert fix_ccc_bleed(["CCC:150", "CCC:17/1", "CCC:118", "CCC:583"], "LPA2541") == \
        ["CCC:150", "LPA2541:17/1", "LPA2541:118", "CCC:583"]
    assert fix_ccc_bleed(["CCC:17"], "WCA2537") == ["CCC:17"]
    assert fix_ccc_bleed(["CCC:17", "CCC:583", "CCC:150"], "CCC") == ["LPA2541:17", "CCC:583", "CCC:150"]
    assert answer_family("พ.ร.บ.แรงงานสัมพันธ์ … พ.ร.บ.แรงงานสัมพันธ์ … คุ้มครองแรงงาน") == "LRA2518"
    assert answer_family("ไม่มีชื่อกฎหมาย") == "LPA2541"


def test_body_stops_at_post_end_despite_void_and_unclosed_tags():
    html = ('<h1>LAW4004 1/2560</h1><div class="td-post-content"><p>ข้อ 1. โจทย์<input type="hidden">'
            '<p>แนวคำตอบ<br>มาตรา 118 ดังนั้นตามมาตรา 118 ต้องจ่าย<meta name="x"><img src="a.png">'
            '<div class="apMainContainer"><p>โฆษณา</div></div>'
            '<div class="sidebar">ประเภทยอดนิยม LAW1001 มาตรา 999</div><footer>error: Content is protected</footer>')
    rows = parse_page(html, "u")
    assert len(rows) == 1 and rows[0]["sections_all"] == "LPA2541:118"
    assert "ประเภทยอดนิยม" not in rows[0]["model_answer"] and "โฆษณา" not in rows[0]["model_answer"]
    assert "protected" not in rows[0]["model_answer"]
