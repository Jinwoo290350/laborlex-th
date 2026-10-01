from src.agent.answer import AnswerJSON
from src.agent.render import render

LABELS = {"LPA2541:118:1": "ม.118", "LPA2541:118:2": "ม.118 วรรคสอง",
          "CCC:582:1": "ม.582 ประมวลกฎหมายแพ่งและพาณิชย์", "CASE:1/2560": "คำพิพากษาศาลฎีกาที่ 1/2560"}


def _md(app: dict, laws: list[dict]) -> str:
    a = AnswerJSON.model_validate({"preliminary": [{"headline": "h"}], "issues": [{
        "code": "c", "question": "q", "consider": "-", "laws": laws, "application": [app],
        "conclusion": [{"headline": "h"}], "opinion": "o", "basis": "b"}]})
    return render(a, LABELS)


LAW118 = {"citation_key": "LPA2541:118:1", "label": "มาตรา 118 …", "explanation": "e", "topic": "ค่าชดเชย"}
STEP = [{"fact": "f", "result": "r"}]


def test_heading_is_section_plus_topic():
    md = _md({"heading": "การคำนวณอายุงานและอัตราค่าชดเชยตามกฎหมาย", "steps": STEP,
              "citations": ["LPA2541:118:1"]}, [LAW118])
    assert "**มาตรา 118 (ค่าชดเชย)**" in md
    assert "การคำนวณอายุงานและอัตราค่าชดเชยตามกฎหมาย" not in md
    assert "LPA2541" not in md                       # no internal keys
    assert "- f → r `[ม.118]`" in md                 # bullets and their citations unchanged


def test_topic_from_same_section_and_case_citations_skipped():
    md = _md({"heading": "x", "steps": STEP, "citations": ["CASE:1/2560", "LPA2541:118:2"]}, [LAW118])
    assert "**มาตรา 118 วรรคสอง (ค่าชดเชย)**" in md


def test_other_law_keeps_its_name():
    law = {"citation_key": "CCC:582:1", "label": "l", "explanation": "e", "topic": "การบอกเลิกสัญญา"}
    md = _md({"heading": "x", "steps": STEP, "citations": ["CCC:582:1"]}, [law])
    assert "**มาตรา 582 ประมวลกฎหมายแพ่งและพาณิชย์ (การบอกเลิกสัญญา)**" in md


def test_fallbacks_keep_the_drafted_heading():
    for app, laws in [
        ({"heading": "ไม่มีการอ้างอิง", "steps": STEP, "citations": []}, [LAW118]),
        ({"heading": "อ้างแต่คำพิพากษา", "steps": STEP, "citations": ["CASE:1/2560"]}, [LAW118]),
        ({"heading": "ไม่มีหัวข้อของมาตรานี้", "steps": STEP, "citations": ["CCC:582:1"]}, [LAW118]),
        ({"heading": "ไม่มี label", "steps": STEP, "citations": ["LPA2541:999:1"]}, [LAW118]),
    ]:
        assert f"**{app['heading']}**" in _md(app, laws)
