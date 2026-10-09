"""LangGraph flow ①–⑩ (CLAUDE.md §5.3). The system fixes the order of reasoning steps."""

from __future__ import annotations

from functools import cache
from itertools import pairwise

from langgraph.graph import END, START, StateGraph

from src.agent.nodes.decide import calculate, check_elements, select_citations
from src.agent.nodes.draft import draft_answers, validate_cites, verify_select
from src.agent.nodes.retrieve import retrieve_cases, retrieve_law
from src.agent.nodes.understand import extract_facts, spot_issues
from src.agent.state import AgentState
from src.agent.status import review_notice

# a failure in these nodes stops the run before any legal answer is drafted (#22)
CRITICAL = {"extract_facts", "check_elements", "verify_select"}

STEPS = [
    ("extract_facts", extract_facts),
    ("spot_issues", spot_issues),
    ("retrieve_law", retrieve_law),
    ("retrieve_cases", retrieve_cases),
    ("select_citations", select_citations),
    ("check_elements", check_elements),
    ("calculate", calculate),
    ("draft_answers", draft_answers),
    ("verify_select", verify_select),
    ("validate_cites", validate_cites),
]


def review_stop(state: AgentState) -> dict:
    """Terminal node after a critical failure: deterministic, no LLM, no legal content."""
    return {"answer": None, "markdown": review_notice(state.degraded),
            "trace": [{"node": "review_stop", "ms": 0, "llm_calls": 0, "cached": 0, "in_tokens": 0,
                       "out_tokens": 0, "summary": {"reasons": state.degraded}}]}


def _after(nxt: str):
    def route(state: AgentState) -> str:
        return "review_stop" if state.status == "needs_review" else nxt
    return route


@cache
def build():
    g = StateGraph(AgentState)
    for name, fn in STEPS:
        g.add_node(name, fn)
    g.add_node("review_stop", review_stop)
    g.add_edge(START, STEPS[0][0])
    for (a, _), (b, _) in [*pairwise(STEPS), (STEPS[-1], (END, None))]:
        if a in CRITICAL:
            g.add_conditional_edges(a, _after(b), [b, "review_stop"])
        else:
            g.add_edge(a, b)
    g.add_edge("review_stop", END)
    return g.compile()


RUN_ONLY = {"trace", "status", "degraded"}     # produced by this run's nodes only, never passed in (#22)


def answer(question: str, **kw) -> AgentState:
    if RUN_ONLY & kw.keys():
        raise TypeError(f"answer() does not accept {sorted(RUN_ONLY & kw.keys())}: status comes from this run only")
    out = build().invoke(AgentState(question=question, **kw))
    return AgentState.model_validate(out)


if __name__ == "__main__":
    import sys

    s = answer(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    print(s.markdown)
    for t in s.trace:
        print(t)
