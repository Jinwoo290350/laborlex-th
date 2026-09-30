"""① extract_facts · ② spot_issues"""

from __future__ import annotations

from pydantic import BaseModel

from src.agent.nodes.common import fmt_facts, prompt, taxonomy, traced
from src.agent.state import AgentState, Facts, IssueSel
from src.llm import generate_json


def _facts_fallback(state: AgentState, e: Exception) -> dict:
    return {"facts": Facts(key_facts=[state.question], asked=[state.question])}


@traced("extract_facts", fallback=_facts_fallback)
def extract_facts(state: AgentState) -> dict:
    _, body = prompt("extract_facts")
    facts = generate_json(body.format(question=state.question), Facts, name="extract_facts", thinking="low")
    return {"facts": facts, "event_date": state.event_date or facts.event_date,
            "_summary": {"asked": facts.asked, "n_facts": len(facts.key_facts)}}


class _Issues(BaseModel):
    issues: list[IssueSel]


@traced("spot_issues")
def spot_issues(state: AgentState) -> dict:
    tax = taxonomy()
    listing = "\n".join(f"{c} — {i['name']}: {i['description']}" for c, i in tax.items())
    _, body = prompt("spot_issues")
    out = generate_json(
        body.format(question=state.question, asked="\n".join(state.facts.asked if state.facts else []),
                    facts=fmt_facts(state), taxonomy=listing),
        _Issues, name="spot_issues", thinking="low")
    # system control: only taxonomy codes survive, no duplicates, at most 4
    seen, issues = set(), []
    for i in out.issues:
        if i.code in tax and i.code not in seen:
            seen.add(i.code)
            issues.append(i)
    dropped = [i.code for i in out.issues if i.code not in tax]
    return {"issues": issues[:4],
            "_summary": {"issues": [i.code for i in issues[:4]], "dropped": dropped}}
