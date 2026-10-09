"""Failure handling (decisions #22, docs/design/2026-10-08_failure_handling_design.md).

A failure in extract_facts, check_elements or verify_select ends the run with status NEEDS_REVIEW:
no draft, verify or citation step runs and no legal answer is returned. The retrieve_cases / select_citations
fallbacks are unchanged in round 1, but their runs carry status "degraded" and are never treated as normal.
API, UI helper and eval must all see the status. Local only: every LLM call is stubbed (Gemini = 0)."""

from __future__ import annotations

import pytest

from src.agent import graph as G
from src.agent.answer import AnswerJSON, Point
from src.agent.nodes import common, decide, draft, retrieve, understand
from src.agent.state import AgentState, ElementCheck, Facts, IssueSel

A, B = "dismissal_for_cause", "employee_committee_and_union_protection"
CALLS: list[str] = []


@pytest.fixture(autouse=True)
def _no_api(monkeypatch):
    """Gemini = 0: any LLM call that is not stubbed fails with CacheMiss instead of reaching the API."""
    monkeypatch.setenv("LLM_CACHE_ONLY", "1")


def _answer() -> AnswerJSON:
    return AnswerJSON(preliminary=[Point(headline="คำตอบปกติ", citations=[])], issues=[])


# stub steps (no DB, no LLM); names must match the real STEPS so the graph wiring applies
def s_facts(state): CALLS.append("extract_facts"); return {"facts": Facts(key_facts=["f"], asked=["q"])}
def s_spot(state): CALLS.append("spot_issues"); return {"issues": [IssueSel(code=A, reason="r"), IssueSel(code=B, reason="r")]}
def s_law(state): CALLS.append("retrieve_law"); return {"candidates": {A: [], B: []}}
def s_cases(state): CALLS.append("retrieve_cases"); return {"cases": {}}
def s_select(state): CALLS.append("select_citations"); return {"selected": {A: [], B: []}}
def s_elements(state): CALLS.append("check_elements"); return {"elements": {}}
def s_calc(state): CALLS.append("calculate"); return {}
def s_draft(state): CALLS.append("draft_answers"); return {"drafts": [_answer()]}
def s_verify(state): CALLS.append("verify_select"); return {"answer": state.drafts[0]}
def s_validate(state): CALLS.append("validate_cites"); return {"markdown": "NORMAL ANSWER"}


STUBS = {"extract_facts": s_facts, "spot_issues": s_spot, "retrieve_law": s_law, "retrieve_cases": s_cases,
         "select_citations": s_select, "check_elements": s_elements, "calculate": s_calc,
         "draft_answers": s_draft, "verify_select": s_verify, "validate_cites": s_validate}


def run(monkeypatch, **real) -> AgentState:
    """Run the real graph wiring with stubs, replacing the named steps by real node functions."""
    CALLS.clear()
    steps = [(n, real.get(n, STUBS[n])) for n, _ in G.STEPS]
    monkeypatch.setattr(G, "STEPS", steps)
    G.build.cache_clear()
    try:
        return G.answer("คำถามทดสอบ")
    finally:
        G.build.cache_clear()


def boom(*a, **k):
    raise RuntimeError("Gemini failed after 3 attempts: 503 UNAVAILABLE")


def assert_review(s: AgentState, node: str):
    assert s.status == "needs_review"
    assert s.answer is None
    assert "NEEDS_REVIEW" in s.markdown and "คำตอบปกติ" not in s.markdown
    assert any(d["node"] == node for d in s.degraded)
    names = [n for n, _ in G.STEPS]
    for later in names[names.index(node) + 1:]:
        assert later not in CALLS, f"{later} ran after {node} failed"


# ---------- normal path ----------

def test_normal_path_is_unchanged(monkeypatch):
    s = run(monkeypatch)
    assert s.status == "ok" and s.degraded == []
    assert s.markdown == "NORMAL ANSWER" and s.answer is not None
    assert CALLS == [n for n, _ in G.STEPS]


# ---------- critical nodes → NEEDS_REVIEW, nothing after ----------

def test_extract_facts_failure_stops_before_anything_else(monkeypatch):
    monkeypatch.setattr(understand, "generate_json", boom)
    s = run(monkeypatch, extract_facts=understand.extract_facts)
    assert_review(s, "extract_facts")
    assert CALLS == []                       # not even spot_issues


def _checks_for(ok_codes):
    def fake(prompt, schema, **k):
        tax = common.taxonomy()
        for code in ok_codes:
            if tax[code]["name"] in prompt:
                return schema(checks=[ElementCheck(id=e["id"], status="unknown", evidence="e")
                                      for e in tax[code]["elements"] if "derive" not in e])
        raise RuntimeError("Gemini failed after 3 attempts: 429 RESOURCE_EXHAUSTED")
    return fake


def test_check_elements_partial_failure_keeps_successful_issue_and_stops(monkeypatch):
    monkeypatch.setattr(decide, "generate_json", _checks_for([A]))
    s = run(monkeypatch, check_elements=decide.check_elements)
    assert_review(s, "check_elements")
    assert s.elements.get(A)          # the successful issue is kept (diagnostic)
    assert B not in s.elements
    failed = [d for d in s.degraded if d["node"] == "check_elements"]
    assert [d.get("issue") for d in failed] == [B]
    assert "draft_answers" not in CALLS


def test_check_elements_total_failure(monkeypatch):
    monkeypatch.setattr(decide, "generate_json", _checks_for([]))
    s = run(monkeypatch, check_elements=decide.check_elements)
    assert_review(s, "check_elements")
    assert {d.get("issue") for d in s.degraded} == {A, B}


def test_verify_failure_ships_nothing(monkeypatch):
    monkeypatch.setattr(draft, "_verify", boom)
    s = run(monkeypatch, verify_select=draft.verify_select)
    assert_review(s, "verify_select")
    assert "validate_cites" not in CALLS


def test_revise_failure_ships_nothing(monkeypatch):
    low = draft.Verdict(complete=0.1, supported=0.1, consistent=0.1, focused=0.1, feedback="แก้")
    monkeypatch.setattr(draft, "_verify", lambda state, d: low)
    monkeypatch.setattr(draft, "generate_json", boom)          # the revise call
    monkeypatch.setattr(draft, "draft_prompt", lambda state, feedback="": "p")
    s = run(monkeypatch, verify_select=draft.verify_select)
    assert_review(s, "verify_select")


def test_no_draft_even_if_a_later_step_is_reached_with_needs_review(monkeypatch):
    called = []
    monkeypatch.setattr(draft, "generate_json", lambda *a, **k: called.append(1))
    monkeypatch.setattr(draft, "draft_prompt", lambda state, feedback="": "p")
    st = AgentState(question="q", status="needs_review")
    with pytest.raises(RuntimeError, match="needs_review"):
        draft.draft_answers(st)
    assert called == []


# ---------- round-1 fallbacks stay, but the run is not "ok" ----------

def test_retrieve_cases_fallback_is_kept_but_marked_degraded(monkeypatch):
    monkeypatch.setattr(retrieve.tools, "search_cases", boom)
    s = run(monkeypatch, retrieve_cases=retrieve.retrieve_cases)
    assert s.cases == {} and "draft_answers" in CALLS            # behaviour unchanged
    assert s.status == "degraded" and any(d["node"] == "retrieve_cases" for d in s.degraded)
    assert s.markdown == "NORMAL ANSWER"                          # output unchanged; status carries the flag
    from src.agent.status import effective_status
    assert effective_status(s) == "degraded"


def test_effective_status_counts_any_trace_error():
    from src.agent.status import effective_status
    assert effective_status(AgentState(question="q")) == "ok"
    assert effective_status(AgentState(question="q", trace=[{"node": "x", "error": "E"}])) == "degraded"
    assert effective_status(AgentState(question="q", status="needs_review")) == "needs_review"
    assert effective_status({"status": "ok", "trace": [{"node": "x", "error": "E"}]}) == "degraded"


# ---------- API / UI / eval see the status ----------

def _review_state() -> AgentState:
    return AgentState(question="q", status="needs_review", markdown="⚠️ … NEEDS_REVIEW",
                      degraded=[{"node": "check_elements", "issue": B, "error": "E", "kind": "exception"}],
                      trace=[{"node": "check_elements", "error": "E"}])


def test_api_returns_status_and_no_answer(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api import main
    monkeypatch.setattr(G, "answer", lambda q, **k: _review_state())
    main.app.dependency_overrides[main.auth] = lambda: None
    try:
        r = TestClient(main.app).post("/ask", json={"question": "คำถามทดสอบยาวพอ"})
    finally:
        main.app.dependency_overrides.clear()
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "needs_review" and j["answer"] is None and j["citations"] == []
    assert j["review_reasons"] and j["review_reasons"][0]["node"] == "check_elements"


def test_ui_helpers_show_status_and_errors():
    from src.ui.status import status_banner, trace_line
    assert status_banner({"status": "ok", "trace": []}) is None
    assert "NEEDS_REVIEW" in status_banner({"status": "needs_review", "review_reasons": [{"node": "check_elements"}], "trace": []})
    assert status_banner({"status": "degraded", "review_reasons": [], "trace": []})
    assert "E" in trace_line({"node": "check_elements", "ms": 1, "llm_calls": 0, "error": "E"})


@pytest.mark.parametrize("state", [_review_state(),
                                   AgentState(question="q", markdown="m", trace=[{"node": "retrieve_cases", "error": "E"}])])
def test_eval_never_scores_a_degraded_run(monkeypatch, tmp_path, state):
    from src.eval import run_eval
    judged = []
    monkeypatch.setattr(G, "answer", lambda q, **k: state)
    monkeypatch.setattr(run_eval, "judge", lambda *a, **k: judged.append(1))
    row = {"id": "x1", "question": "q", "gold_answer": "g", "gold_citations": "", "difficulty": "easy", "category": "c"}
    rec = run_eval.run_one(row, False, tmp_path)
    assert judged == [] and rec["score"] is None and rec["pass"] is False
    assert rec["invalid"] is True and rec["status"] in ("needs_review", "degraded")
    md = run_eval.report([rec], {"model": "m"}, "t", tmp_path)
    assert "invalid" in md and "x1" in md


# ---------- status comes from the current run only ----------

def test_status_and_trace_errors_do_not_leak_between_runs(monkeypatch):
    """The compiled graph is cached (no checkpointer): a failed run must leave nothing behind for the next."""
    monkeypatch.setattr(understand, "generate_json", boom)
    CALLS.clear()
    steps = [(n, understand.extract_facts if n == "extract_facts" else STUBS[n]) for n, _ in G.STEPS]
    monkeypatch.setattr(G, "STEPS", steps)
    G.build.cache_clear()
    try:
        first = G.answer("คำถามที่ล้ม")
        monkeypatch.setattr(understand, "generate_json",
                            lambda *a, **k: Facts(key_facts=["f"], asked=["q"]))
        second = G.answer("คำถามปกติ")          # same compiled graph object
    finally:
        G.build.cache_clear()
    assert first.status == "needs_review"
    from src.agent.status import effective_status
    assert second.status == "ok" and second.degraded == [] and effective_status(second) == "ok"
    assert not any(t.get("error") for t in second.trace)
    assert [t["node"] for t in second.trace] == ["extract_facts"]     # only this run's traced node (stubs are untraced)
    assert second.markdown == "NORMAL ANSWER" and CALLS[-1] == "validate_cites"


@pytest.mark.parametrize("kw", [{"trace": [{"node": "x", "error": "old"}]}, {"status": "ok"},
                                {"degraded": [{"node": "x"}]}])
def test_answer_refuses_injected_run_state(kw):
    with pytest.raises(TypeError):
        G.answer("คำถาม", **kw)


# ---------- transitions: ok → degraded → needs_review, never back ----------

ORDER = ["ok", "degraded", "needs_review"]


@pytest.mark.parametrize("a", ORDER)
@pytest.mark.parametrize("b", ORDER)
def test_reducer_never_improves(a, b):
    from src.agent.state import worst_status
    assert worst_status(a, b) == ORDER[max(ORDER.index(a), ORDER.index(b))]


def test_graph_transition_ok_degraded_needs_review(monkeypatch):
    seen = {}

    def cases_degraded(state):
        CALLS.append("retrieve_cases"); seen["before"] = state.status
        return {"cases": {}, "status": "degraded", "degraded": [{"node": "retrieve_cases", "kind": "exception"}]}

    def select_tries_reset(state):           # a later node cannot make the run look better
        CALLS.append("select_citations"); seen["after_cases"] = state.status
        return {"selected": {}, "status": "ok"}

    monkeypatch.setattr(decide, "generate_json", _checks_for([]))
    s = run(monkeypatch, retrieve_cases=cases_degraded, select_citations=select_tries_reset,
            check_elements=decide.check_elements)
    assert seen == {"before": "ok", "after_cases": "degraded"}
    assert_review(s, "check_elements")
    assert [d["node"] for d in s.degraded] == ["retrieve_cases", "check_elements", "check_elements"]


def test_degraded_run_continues_and_stays_degraded(monkeypatch):
    def late_reset(state):
        CALLS.append("validate_cites"); return {"markdown": "NORMAL ANSWER", "status": "ok"}
    monkeypatch.setattr(retrieve.tools, "search_cases", boom)
    s = run(monkeypatch, retrieve_cases=retrieve.retrieve_cases, validate_cites=late_reset)
    assert s.status == "degraded" and s.answer is not None and "validate_cites" in CALLS


# ---------- API contract: ok / degraded / needs_review ----------

def _cited_answer() -> AnswerJSON:
    return AnswerJSON(preliminary=[Point(headline="คำตอบปกติ", citations=["LPA2541:118:1"])], issues=[])


def _post(monkeypatch, state):
    from fastapi.testclient import TestClient

    from src.api import main
    from src.index import tools
    monkeypatch.setattr(G, "answer", lambda q, **k: state)
    monkeypatch.setattr(tools, "get_provision", lambda k, d=None: {
        "citation_key": k, "law": "LPA2541", "law_name": "พ.ร.บ.คุ้มครองแรงงาน", "level": 1, "section_no": "118",
        "paragraph_no": 1, "sub_no": None, "text": "t"})
    main.app.dependency_overrides[main.auth] = lambda: None
    try:
        return TestClient(main.app).post("/ask", json={"question": "คำถามทดสอบยาวพอ"})
    finally:
        main.app.dependency_overrides.clear()


def test_api_ok_returns_answer_and_citations(monkeypatch):
    from src.ui.status import status_banner
    r = _post(monkeypatch, AgentState(question="q", answer=_cited_answer(), markdown="NORMAL ANSWER",
                                      trace=[{"node": "validate_cites"}]))
    j = r.json()
    assert r.status_code == 200 and j["status"] == "ok" and j["review_reasons"] == []
    assert j["answer"] is not None and [c["citation_key"] for c in j["citations"]] == ["LPA2541:118:1"]
    assert status_banner(j) is None


@pytest.mark.parametrize("flag", ["status", "trace_only"])
def test_api_degraded_keeps_answer_but_says_degraded(monkeypatch, flag):
    from src.ui.status import status_banner
    extra = ({"status": "degraded", "degraded": [{"node": "retrieve_cases", "error": "E", "kind": "exception"}]}
             if flag == "status" else {})             # trace_only: the trace error alone must be enough
    st = AgentState(question="q", answer=_cited_answer(), markdown="NORMAL ANSWER",
                    trace=[{"node": "retrieve_cases", "error": "E"}], **extra)
    j = _post(monkeypatch, st).json()
    assert j["status"] == "degraded"
    assert j["answer"] is not None and j["markdown"] == "NORMAL ANSWER" and len(j["citations"]) == 1
    assert "degraded" in status_banner(j)


def test_api_needs_review_has_reasons(monkeypatch):
    from src.ui.status import status_banner
    j = _post(monkeypatch, _review_state()).json()
    assert j["status"] == "needs_review" and j["answer"] is None and j["citations"] == []
    assert j["follow_up_questions"] == []
    assert j["review_reasons"] == [{"node": "check_elements", "issue": B, "error": "E", "kind": "exception"}]
    assert "NEEDS_REVIEW" in status_banner(j)
