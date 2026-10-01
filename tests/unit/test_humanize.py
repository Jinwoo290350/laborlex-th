from src.agent.answer import AnswerJSON
from src.agent.nodes.draft import humanize_keys

LPA118 = {"citation_key": "LPA2541:118:1", "section_no": "118", "paragraph_no": 1, "level": 1,
          "law": "LPA2541", "law_name": "พระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541", "text": ""}


def _ok(k):
    return LPA118 if k == "LPA2541:118:1" else None


def _run(text: str) -> str:
    a = AnswerJSON.model_validate({"preliminary": [{"headline": text}], "issues": []})
    humanize_keys(a, _ok)
    return a.preliminary[0].headline


def test_removed_reference_takes_its_connective_with_it():
    got = _run("หจก. มีสถานะเป็นนายจ้างตาม LPA2541:5:3 และลูกจ้างทั้งสองมีสถานะเป็นลูกจ้างตาม "
               "LPA2541:5:2 ภายใต้สัญญาจ้างแรงงานตาม CCC:575:1")
    assert got == "หจก. มีสถานะเป็นนายจ้าง และลูกจ้างทั้งสองมีสถานะเป็นลูกจ้าง ภายใต้สัญญาจ้างแรงงาน"
    assert "ตาม" not in got


def test_valid_reference_keeps_connective_and_gets_label():
    assert _run("ต้องจ่ายตาม LPA2541:118:1") == "ต้องจ่ายตาม มาตรา 118 พระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541"


def test_no_empty_brackets_or_trailing_conjunction():
    assert _run("ต้องจ่าย (ดู LPA2541:999:1) และ (อ้าง LPA2541:998:1, LPA2541:997:1)") == "ต้องจ่าย"


def test_citation_lists_are_not_rewritten():
    a = AnswerJSON.model_validate({"preliminary": [{"headline": "h", "citations": ["LPA2541:118:1"]}],
                                   "issues": [], "payments_citations": ["LPA2541:118:1"]})
    humanize_keys(a, _ok)
    assert a.preliminary[0].citations == ["LPA2541:118:1"] and a.payments_citations == ["LPA2541:118:1"]


def test_ground_key_lists_stay_database_keys():
    a = AnswerJSON.model_validate({"preliminary": [{"headline": "h"}], "issues": [], "employees": [
        {"name": "ก", "m119_applies": True, "alleged_ground_keys": ["LPA2541:118:1"],
         "found_ground_keys": ["LPA2541:118:1"], "not_found_reason": "ตาม LPA2541:118:1"}]})
    humanize_keys(a, _ok)
    e = a.employees[0]
    assert e.alleged_ground_keys == ["LPA2541:118:1"] and e.found_ground_keys == ["LPA2541:118:1"]
    assert e.not_found_reason == "ตาม มาตรา 118 พระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541"   # prose still humanized
