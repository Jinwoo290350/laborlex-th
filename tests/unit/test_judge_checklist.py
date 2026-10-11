"""Checklist judge (M1): mapping rules, section and amount matching, κ, split logic, budget.

The LLM is always stubbed; nothing here reaches Gemini."""

from __future__ import annotations

import copy

import pytest

from src.eval import calibrate_checklist as cal
from src.eval import checklist_judge as cj
from src.eval.calibrate_judge import weighted_kappa

RULES = cj.load_rules()


def facts(**kw) -> cj.RowFacts:
    base = {"n_subq": 2, "subq_addressed": 2, "n_concl": 2, "concl_matched": 2, "concl_contra": 0,
            "n_amounts": 0, "amounts_matched": 0, "n_issues": 2, "issues_found": 2, "n_extra": 0,
            "n_princ": 2, "princ_matched": 2, "princ_contra": 0, "n_gold_sections": 2,
            "sections_law": 2, "sections_number": 2, "cites_nonexistent": False, "applies": True}
    return cj.RowFacts(**{**base, **kw})


# --- mapping rules -------------------------------------------------------------------------------

def test_grade_thresholds():
    rule = {"hi": 1.0, "lo": 0.5, "max_contradicted": 0}
    assert cj.grade(1.0, 0, rule) == 2
    assert cj.grade(1.0, 1, rule) == 1          # a contradiction blocks 2
    assert cj.grade(0.5, 0, rule) == 1
    assert cj.grade(0.49, 0, rule) == 0
    assert cj.grade(2 / 3, 0, {"hi": 2 / 3, "lo": 0.01}) == 2   # float-safe comparison


def test_perfect_answer_scores_all_two():
    s = cj.score(facts(), RULES)
    assert s == {c: 2 for c in cj.CRITERIA}


def test_a2_partial_and_none():
    assert cj.score(facts(concl_matched=1), RULES)["A2"] == 1
    assert cj.score(facts(concl_matched=0), RULES)["A2"] == 0
    assert cj.score(facts(concl_matched=1, concl_contra=1), RULES)["A2"] == 1


def test_amounts_count_as_conclusions():
    assert cj.score(facts(n_amounts=1, amounts_matched=0), RULES)["A2"] == 1
    assert cj.score(facts(n_amounts=1, amounts_matched=1), RULES)["A2"] == 2


def test_a1_counts_addressed_subquestions():
    assert cj.score(facts(subq_addressed=1), RULES)["A1"] == 1
    assert cj.score(facts(subq_addressed=0), RULES)["A1"] == 0


def test_b0_penalises_extra_issues():
    rules = copy.deepcopy(RULES)
    rules["criteria"]["B0"]["max_extra"] = 1
    assert cj.score(facts(n_extra=1), rules)["B0"] == 2
    assert cj.score(facts(n_extra=2), rules)["B0"] == 1
    assert cj.score(facts(issues_found=0, n_extra=5), rules)["B0"] == 0


def test_b1_mixes_sections_and_principles():
    rules = copy.deepcopy(RULES)
    rules["criteria"]["B1"].update(section_weight=0.5, hi=1.0, lo=0.01, section_match="law")
    assert cj.score(facts(sections_law=1), rules)["B1"] == 1
    assert cj.score(facts(sections_law=0, princ_matched=0), rules)["B1"] == 0
    rules["criteria"]["B1"]["section_match"] = "number"       # law mislabel does not count
    assert cj.score(facts(sections_law=1, sections_number=2), rules)["B1"] == 2


def test_b1_nonexistent_section_caps():
    rules = copy.deepcopy(RULES)
    rules["criteria"]["B1"]["nonexistent_cap"] = 1
    assert cj.score(facts(cites_nonexistent=True), rules)["B1"] == 1
    rules["criteria"]["B1"]["nonexistent_cap"] = 0
    assert cj.score(facts(cites_nonexistent=True), rules)["B1"] == 0


def test_b2_requires_application():
    assert cj.score(facts(applies=False), RULES)["B2"] == RULES["criteria"]["B2"]["no_application"]
    assert cj.score(facts(concl_matched=1), RULES)["B2"] == 1


def test_empty_item_lists_do_not_penalise():
    f = facts(n_subq=0, subq_addressed=0, n_issues=0, issues_found=0, n_princ=0, princ_matched=0,
              n_gold_sections=0, sections_law=0, sections_number=0)
    assert cj.score(f, RULES) == {c: 2 for c in cj.CRITERIA}


def test_rowfacts_roundtrip():
    f = facts(n_extra=3)
    assert cj.RowFacts.from_dict(f.to_dict()) == f


# --- section matching (code) ---------------------------------------------------------------------

def test_answer_sections_from_text_and_keys():
    text = "ตามพระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541 มาตรา 118 และ ป.พ.พ. มาตรา 583"
    got = cj.answer_sections(text, ["LPA2541:17/1:2", "CASE:123/2560"])
    assert got == {"LPA2541:118", "CCC:583", "LPA2541:17/1"}


def test_section_hits_law_vs_number():
    gold = ["LPA2541:118", "LRA2518:31"]
    ans = {"LPA2541:118", "LPA2541:31"}            # 31 resolved to the wrong law
    assert cj.section_hits(gold, ans, "law") == 1
    assert cj.section_hits(gold, ans, "number") == 2


def test_nonexistent_sections_from_gold():
    gold = "กฎหมายไม่มีบทบัญญัติเรื่องนี้ มาตรา 41/2 ไม่มีในกฎหมาย\nกฎหมายที่เกี่ยวข้อง: มาตรา 41 และ มาตรา 41/1"
    assert cj.nonexistent_sections(gold) == {"41/2"}


def test_cites_nonexistent():
    assert cj.cites_nonexistent({"41/2"}, {"LPA2541:41/2", "LPA2541:41"})
    assert not cj.cites_nonexistent({"41/2"}, {"LPA2541:41"})
    # an answer that says the section does not exist is not citing it
    said = cj.answer_sections("มาตรา 41/2 ไม่มีอยู่ในกฎหมาย ส่วนมาตรา 41 ให้สิทธิลา")
    assert not cj.cites_nonexistent({"41/2"}, said)


# --- amounts (code) ------------------------------------------------------------------------------

def test_parse_amounts():
    assert cj.parse_amounts("ค่าชดเชย ๑๒,๓๐๐ บาท และดอกเบี้ย 1,250.50 บาท ไม่ใช่ 30 วัน") == [12300.0, 1250.5]
    assert cj.parse_amounts("จำนวนเงิน 90,000.- บาท") == [90000.0]


def test_amounts_matched_with_tolerance():
    assert cj.amounts_matched([12300.0, 500.0], [12300.4, 7.0]) == 1
    assert cj.amounts_matched([12300.0], []) == 0
    assert cj.amounts_matched([], [1.0]) == 0


# --- end to end with a stubbed LLM ---------------------------------------------------------------

ROW = {"id": "dev900", "question": "นายจ้างเลิกจ้างนายแดงซึ่งทำงานมา 4 ปี ต้องจ่ายค่าชดเชยหรือไม่ เท่าใด",
       "gold_answer": "ต้องจ่ายค่าชดเชย 120 วัน เป็นเงิน 60,000 บาท ตามมาตรา 118 (3)",
       "gold_citations": "LPA2541:118", "g_verdict": "", "h_raw": "", "draft_answer": ""}
CHECKLIST = cj.Checklist(sub_questions=["ต้องจ่ายค่าชดเชยหรือไม่", "จำนวนเท่าใด"],
                         conclusions=["นายจ้างต้องจ่ายค่าชดเชย"], issues=["สิทธิได้รับค่าชดเชย"],
                         principles=["อายุงาน 3 ปีแต่ไม่ครบ 6 ปี ได้ค่าชดเชย 180 วัน"])


@pytest.fixture
def stub_llm(monkeypatch, tmp_path):
    calls = []

    def fake(prompt, schema, **kw):
        calls.append(schema.__name__)
        if schema is cj.Checklist:
            return CHECKLIST
        return cj.Verification(items=[
            cj.ItemVerdict(id="Q1", stated=True, contradicted=False),
            cj.ItemVerdict(id="Q2", stated=True, contradicted=False),
            cj.ItemVerdict(id="C1", stated=True, contradicted=False),
            cj.ItemVerdict(id="I1", stated=True, contradicted=False),
            cj.ItemVerdict(id="P1", stated=False, contradicted=True)],
            applies_law_to_facts=True, extra_issues=[])

    monkeypatch.setattr(cj, "generate_json", fake)
    monkeypatch.setattr(cj, "CHECKLISTS", tmp_path)
    return calls


def test_build_checklist_is_cached_on_disk(stub_llm):
    assert cj.build_checklist(ROW) == CHECKLIST
    assert cj.build_checklist(ROW) == CHECKLIST
    assert stub_llm == ["Checklist"]                   # second build read the file cache


def test_build_checklist_rebuilds_when_gold_changes(stub_llm):
    cj.build_checklist(ROW)
    cj.build_checklist({**ROW, "gold_answer": ROW["gold_answer"] + " แก้ไข"})
    assert stub_llm == ["Checklist", "Checklist"]


def test_judge_end_to_end(stub_llm):
    answer = "นายจ้างต้องจ่ายค่าชดเชยตามพระราชบัญญัติคุ้มครองแรงงาน มาตรา 118 เป็นเงิน 60,000 บาท"
    s = cj.judge(ROW, answer)
    assert (s.A1, s.A2, s.B0, s.B3) == (2, 2, 2, 2)
    assert s.B1 == 1                                    # principle contradicted
    assert not s.passed and "P1" in s.reasons


def test_collect_counts_items():
    v = cj.Verification(items=[cj.ItemVerdict(id="Q1", stated=True, contradicted=False),
                               cj.ItemVerdict(id="C1", stated=True, contradicted=True)],
                        applies_law_to_facts=True, extra_issues=["ประเด็นเกิน"])
    f = cj.collect(ROW, CHECKLIST, v, "มาตรา 118 จ่าย 60,000 บาท")
    assert (f.n_subq, f.subq_addressed) == (2, 1)       # Q2 missing from the reply = not addressed
    assert (f.concl_matched, f.concl_contra) == (0, 1)
    assert (f.n_amounts, f.amounts_matched) == (1, 1)
    assert (f.n_gold_sections, f.sections_law, f.n_extra) == (1, 1, 1)


def test_verify_prompt_numbers_items():
    p = cj.verify_prompt("q", "a", CHECKLIST)
    for tag in ("Q1", "Q2", "C1", "I1", "P1"):
        assert f"[{tag}]" in p


# --- agreement, κ, split -------------------------------------------------------------------------

def test_weighted_kappa_known_values():
    assert weighted_kappa([0, 1, 2], [0, 1, 2]) == 1.0
    assert weighted_kappa([0, 1], [1, 0]) == pytest.approx(-1.0)
    sk = pytest.importorskip("sklearn.metrics")
    a, b = [2, 2, 1, 0, 2, 1, 2, 0], [2, 1, 1, 0, 2, 2, 2, 1]
    assert weighted_kappa(a, b) == pytest.approx(sk.cohen_kappa_score(a, b, weights="quadratic"))


def test_confusion_matrix():
    m = cal.confusion([2, 2, 1, 0], [2, 1, 1, 2])
    assert m == [[0, 0, 1], [0, 1, 0], [0, 1, 1]]       # rows lawyer 0..2, columns judge 0..2


def test_agreement_report():
    lawyer = [{c: 2 for c in cj.CRITERIA}, {**{c: 2 for c in cj.CRITERIA}, "A2": 1}]
    judged = [{c: 2 for c in cj.CRITERIA}, {c: 2 for c in cj.CRITERIA}]
    rep = cal.agreement(lawyer, judged)
    assert rep["A2"]["exact"] == 0.5 and rep["A1"]["exact"] == 1.0
    assert rep["pass_agreement"] == 0.5


def _rows(qids):
    return [{"qid": q, "model_code": m} for q in qids for m in ("ch", "cl", "g")]


def test_split_uses_split_file_and_keeps_questions_together():
    split = {"tune": ["dev001", "dev002"], "holdout": ["dev003"]}
    calib, hold = cal.split_rows(_rows(["dev001", "dev002", "dev003", "dev004"]), split)
    assert {r["qid"] for r in hold} == {"dev003"}
    assert {r["qid"] for r in calib} == {"dev001", "dev002", "dev004"}   # unlisted → calibration
    assert len(hold) == 3


def test_split_hash_fallback_is_deterministic_and_disjoint():
    qids = [f"dev{i:03d}" for i in range(100)]
    c1, h1 = cal.split_rows(_rows(qids), None, holdout_frac=0.4)
    c2, h2 = cal.split_rows(_rows(qids), None, holdout_frac=0.4)
    assert h1 == h2 and c1 == c2
    assert not ({r["qid"] for r in c1} & {r["qid"] for r in h1})
    assert 30 <= len({r["qid"] for r in h1}) <= 50


def test_fit_uses_only_calibration_rows():
    # lawyers give A2=2 whenever at least half of the conclusions hold → the fit should lower hi
    fs = [facts(n_concl=2, concl_matched=k) for k in (0, 1, 2)] * 4
    lawyer = [{**{c: 2 for c in cj.CRITERIA}, "A2": {0: 0, 1: 2, 2: 2}[f.concl_matched]} for f in fs]
    tuned = cal.fit(fs, lawyer, RULES)
    assert tuned["criteria"]["A2"]["hi"] <= 0.5
    assert [cj.score(f, tuned)["A2"] for f in fs[:3]] == [0, 2, 2]
    assert RULES["criteria"]["A2"]["hi"] == 1.0          # the input rules are not mutated


# --- cost control ---------------------------------------------------------------------------------

def test_estimate_cost_uses_config_prices(monkeypatch):
    monkeypatch.setattr(cal.settings, "gemini_price_in", 1.0)
    monkeypatch.setattr(cal.settings, "gemini_price_out", 10.0)
    assert cal.cost_usd(1_000_000, 100_000) == pytest.approx(2.0)
    assert cal.estimate_tokens("ก" * 250) == 100


def test_budget_stops_before_cap():
    b = cal.Budget(max_usd=1.0, spent=lambda: 0.7)
    assert b.allows(0.3)
    assert not b.allows(0.31)
    assert cal.Budget(max_usd=None, spent=lambda: 99.0).allows(5.0)


def test_collect_rows_skips_rows_without_checklist(monkeypatch):
    monkeypatch.setattr(cj, "cached_checklist", lambda d: None)
    monkeypatch.setattr(cj, "build_checklist", lambda d: (_ for _ in ()).throw(cal.CacheMiss("x")))
    monkeypatch.setattr(cal, "plan_build", lambda d: None)
    monkeypatch.setattr(cal, "plan_verify", lambda d, a: cal.Call("verify", False, 10, 10))
    rows = [{"qid": "dev900", "model_code": "g", "answers": {"summary": "s"}}]
    out = cal.collect_rows(rows, {"dev900": ROW}, cal.Budget(None), 1)
    assert out[0]["facts"] is None


def test_collect_rows_stops_at_budget(monkeypatch):
    monkeypatch.setattr(cal, "plan_build", lambda d: None)
    monkeypatch.setattr(cal, "plan_verify", lambda d, a: cal.Call("verify", False, 1_000_000, 0))
    monkeypatch.setattr(cj, "verify", lambda *a: pytest.fail("must not call the LLM over budget"))
    rows = [{"qid": "dev900", "model_code": "g", "answers": {"summary": "s"}}]
    out = cal.collect_rows(rows, {"dev900": ROW}, cal.Budget(0.01, spent=lambda: 0.0), 1)
    assert out[0]["facts"] is None and out[0]["reasons"] == "budget"


# --- run_eval wiring ------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["llm", "checklist"])
def test_run_eval_judge_option(monkeypatch, tmp_path, kind):
    from src.agent import graph as G
    from src.agent.state import AgentState
    from src.eval import run_eval
    from src.eval.judge import Score

    ok = Score(**{c: 2 for c in cj.CRITERIA}, reasons="")
    used = []
    monkeypatch.setattr(G, "answer", lambda q, **k: AgentState(question=q, markdown="คำตอบ มาตรา 118", trace=[]))
    monkeypatch.setattr(run_eval, "judge", lambda *a, **k: used.append("llm") or ok)
    monkeypatch.setattr(run_eval.checklist_judge, "judge",
                        lambda row, md, keys: used.append(("checklist", row["id"], md)) or ok)
    row = {"id": "x1", "question": "q", "gold_answer": "g", "gold_citations": "", "difficulty": "easy",
           "category": "c"}
    rec = run_eval.run_one(row, False, tmp_path, kind)
    assert rec["pass"] is True
    assert used == (["llm"] if kind == "llm" else [("checklist", "x1", "คำตอบ มาตรา 118")])
