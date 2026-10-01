from src.agent.nodes.draft import short_label


def _r(**kw):
    return {"section_no": "118", "paragraph_no": 1, "sub_no": None, "level": 1, "law": "LPA2541",
            "law_name": "พระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541", "text": "", **kw}


def test_short_labels():
    assert short_label(_r()) == "ม.118"
    assert short_label(_r(paragraph_no=2)) == "ม.118 วรรคสอง"
    assert short_label(_r(section_no="5", paragraph_no=11, text="“ค่าจ้าง” หมายความว่า เงิน")) == "ม.5 “ค่าจ้าง”"
    assert short_label(_r(law="CCC", law_name="ป.พ.พ.", section_no="582")) == "ม.582 ป.พ.พ."
    assert short_label(_r(level=4, law="ANN-X", law_name="ประกาศ", section_no="2", sub_no="(1)")) == "ข้อ 2 (1) ประกาศ"
    assert short_label({"label": "คำพิพากษาศาลฎีกาที่ 1/2560"}) == "คำพิพากษาศาลฎีกาที่ 1/2560"
