"""Tests for the exam framework on synthetic data. No Gemini, no DB."""

import subprocess
import sys

from tools.exam import framework as fw


def test_section_set_collapses_paragraphs_keeps_slash_sections():
    t = "ตาม พ.ร.บ.คุ้มครองแรงงาน มาตรา 118 วรรคหนึ่ง (3) และมาตรา 17 กับมาตรา 17/1 ประกอบ ป.พ.พ. มาตรา 583"
    assert fw.section_set(t) == ["LPA2541:118", "LPA2541:17", "LPA2541:17/1", "CCC:583"]


def test_bucket():
    assert [fw.bucket(n) for n in (0, 1, 2, 3, 7)] == ["0", "1", "2", ">2", ">2"]


def test_validate_intake():
    rows = [{"exam_id": "a", "source": "bar", "question": "q", "model_answer": ""},
            {"exam_id": "a", "source": "bar", "question": "", "model_answer": "x"}]
    errs = fw.validate_intake(rows)
    assert "duplicate exam_id a" in errs and any("no model answer" in e for e in errs)
    assert any("empty question" in e for e in errs)
    assert fw.validate_intake([{"exam_id": "a"}])[0].startswith("missing columns")


def test_tag_rows_cross_act_and_confirmed_override():
    t = fw.tag_rows([{"exam_id": "x", "source": "bar", "exam_year": "",
                      "model_answer": "พ.ร.บ.คุ้มครองแรงงาน มาตรา 118 และ ป.พ.พ. มาตรา 583"}])[0]
    assert t["bucket"] == "2" and t["cross_act"] == "Y"
    assert fw.confirmed_sections({**t, "sections_confirmed": "LPA2541:118"}) == ["LPA2541:118"]


def test_auto_checks_sections_and_amounts():
    c = fw.auto_checks(["LPA2541:118", "LPA2541:17/1"], "ตามมาตรา 118 ได้ค่าชดเชย 90,000 บาท",
                       "ค่าชดเชย 90,000.00 บาท")
    assert c["missing"] == ["LPA2541:17/1"] and not c["all_sections"] and c["section_recall"] == 0.5
    assert c["amounts_match"] is True
    assert fw.auto_checks([], "x", "ไม่มีตัวเลข")["amounts_match"] is None


def test_diagnose():
    assert fw.diagnose(True, True, True, True) == "solved"
    assert fw.diagnose(False, False, False, True) == "reasoning_gap"
    assert fw.diagnose(False, True, False, False) == "retrieval_gap"
    assert fw.diagnose(False, True, False, True) == "system_reasoning_gap"
    assert fw.diagnose(False, True, True, True) == "knowledge_gap_fixed"
    assert fw.diagnose(None, True, True, True) == "incomplete"


def _tag(eid, src, secs):
    return {"exam_id": eid, "source": src, "sections_confirmed": secs}


def test_report_stamps_pilot_and_counts():
    tags = [_tag("a", "dev100_pilot", "LPA2541:118"), _tag("b", "dev100_pilot", "LPA2541:5;LPA2541:118")]
    answers = {("a", c): {"all_sections": True} for c in fw.CONDITIONS}
    reviews = {("a", "C0"): {"conclusion": "ผิด", "main_cause": "section_selection"},
               ("a", "C1"): {"conclusion": "ถูก"}, ("a", "C2"): {"conclusion": "ถูก"}}
    text = fw.report(tags, answers, reviews, "dev100_pilot")
    assert "PILOT — ไม่ใช่ผลข้อสอบราม/เนติ" in text
    assert "| 1 มาตรา | 1 | 0/1 ถูก · 1/1 มาตราครบ | 1/1 ถูก" in text
    real = fw.report([_tag("a", "bar", "LPA2541:118")], {}, {}, "bar_set")
    assert "PILOT" not in real


def test_live_run_refuses_without_flags():
    r = subprocess.run([sys.executable, "-m", "tools.exam.run", "run", "--dataset", "x", "--ids", "a"],
                       capture_output=True, text=True, check=False)
    assert r.returncode != 0 and "need --live" in r.stderr
    r = subprocess.run([sys.executable, "-m", "tools.exam.run", "run", "--dataset", "x", "--ids", "a", "--live"],
                       capture_output=True, text=True, check=False, env={"PATH": "/usr/bin:/bin"})
    assert r.returncode != 0 and "EXAM_ALLOW_GEMINI" in r.stderr


def test_tag_rows_prefers_needed_draft_over_all_citations():
    t = fw.tag_rows([{"exam_id": "x", "source": "ram", "exam_year": "2567",
                      "model_answer": "มาตรา 118 มาตรา 119 มาตรา 17 มาตรา 5",
                      "sections_needed_draft": "LPA2541:118"}])[0]
    assert t["auto_sections"] == "LPA2541:118" and t["bucket"] == "1"


def test_scoped_bucket_counts_only_lpa_lra_needed_sections():
    t = fw.tag_rows([{"exam_id": "x", "source": "ram", "exam_year": "2560", "model_answer": "",
                      "sections_needed_draft": "LPA2541:118;CCC:583;WCA2537:5", "in_scope": "review",
                      "scope_reason": "LPA/LRA plus CCC"}])[0]
    assert t["auto_sections"] == "LPA2541:118" and t["bucket"] == "1" and t["in_scope"] == "review"


def test_runnable_and_report_skip_out_of_scope():
    assert fw.runnable({"in_scope": ""}) and fw.runnable({"in_scope": "yes"})
    assert not fw.runnable({"in_scope": "review"}) and not fw.runnable({"in_scope": "no"})
    tags = [{"exam_id": "a", "source": "ram", "in_scope": "yes", "sections_confirmed": "LPA2541:118"},
            {"exam_id": "b", "source": "ram", "in_scope": "no", "sections_confirmed": "LPA2541:5"},
            {"exam_id": "c", "source": "ram", "in_scope": "review", "scope_reason": "LPA/LRA plus CCC",
             "sections_confirmed": "LPA2541:17;LPA2541:118"}]
    summ = fw.scope_summary(tags)
    assert "in_scope no 1 · review 1 · yes 1" in summ and "runnable (in_scope = yes) 1" in summ
    text = fw.report(tags, {}, {}, "ram_set")
    assert "| 1 มาตรา | 1 |" in text and "| 2 มาตรา | 0 |" in text
