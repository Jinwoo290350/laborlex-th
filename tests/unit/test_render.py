from src.agent.answer import AnswerJSON
from src.agent.render import render

A = AnswerJSON.model_validate({
    "preliminary": [{"headline": "ข้อสรุป ก", "detail": "เหตุผล", "citations": ["T:1:1"]}],
    "issues": [{
        "question": "ประเด็นหนึ่งหรือไม่", "consider": "ต้องพิจารณา",
        "laws": [{"citation_key": "T:1:1", "label": "มาตรา 1 กฎหมายทดสอบ",
                  "explanation": "หลัก", "topic": "หัวข้อ"}],
        "application": [{"heading": "มาตรา 1 (หัวข้อ)", "steps": [["ข้อเท็จจริง", "ผล"]]}],
        "conclusion": [{"headline": "สรุป", "citations": ["T:1:1"]}],
        "opinion": "ได้", "basis": "ม.1"}],
})


def test_render_sections_in_client_order():
    md = render(A)
    order = ["# คำตอบทางกฎหมาย", "## คำตอบเบื้องต้น", "## ประเด็นทางกฎหมายที่ต้องพิจารณา",
             "## 1. ประเด็นหนึ่งหรือไม่", "### สิ่งที่ต้องพิจารณา", "### กฎหมายที่เกี่ยวข้อง",
             "### การปรับบทกฎหมายกับข้อเท็จจริง", "### ข้อสรุปประเด็นนี้", "## ความเห็นทางกฎหมาย"]
    pos = [md.index(h) for h in order]
    assert pos == sorted(pos)
    assert "- ข้อเท็จจริง → ผล" in md and "ข้อเท็จจริงที่ต้องถามเพิ่ม" not in md


def test_all_citations():
    assert A.all_citations() == {"T:1:1"}
