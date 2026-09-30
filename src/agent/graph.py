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


@cache
def build():
    g = StateGraph(AgentState)
    for name, fn in STEPS:
        g.add_node(name, fn)
    g.add_edge(START, STEPS[0][0])
    for (a, _), (b, _) in pairwise(STEPS):
        g.add_edge(a, b)
    g.add_edge(STEPS[-1][0], END)
    return g.compile()


def answer(question: str, **kw) -> AgentState:
    out = build().invoke(AgentState(question=question, **kw))
    return AgentState.model_validate(out)


if __name__ == "__main__":
    import sys

    s = answer(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    print(s.markdown)
    for t in s.trace:
        print(t)
