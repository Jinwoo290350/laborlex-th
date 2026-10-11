"""⑥b determine_grounds (FIX_PLAN_v2 M5): dismissal grounds decided per employee, before any drafting.

For each dismissed employee the model judges every ม.119 item and ป.พ.พ. ม.583 (the provisions ม.17 วรรคสี่ names)
against that employee's facts, with holding cards retrieved for the two provisions in front of it. Code then decides
by strict majority over `determine.votes` samples; a ground with no majority is unknown, and an unknown ground can
never produce a decision. The result is written to `state.determinations`; the payment table and the prose check
follow it (src/agent/ledger.py)."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from src.agent.nodes.common import fmt_facts, prompt, traced
from src.agent.state import AgentState, EmployeeDetermination, GroundCheck
from src.index import tools
from src.llm import generate_json
from src.params import P

DISMISSAL_ISSUES = {"dismissal_for_cause", "severance_pay", "advance_notice"}


class GroundVote(BaseModel):
    checks: list[GroundCheck]


def _grounds(state: AgentState) -> tuple[list[tuple[str, str]], tuple[str, str]]:
    """(ม.119 items, ป.พ.พ. ม.583) as (key, text), looked up by wording in the DB."""
    from src.agent.nodes.decide import m119_keys
    keys = m119_keys()
    items = [(r["citation_key"], r["text"]) for r in tools.get_subitems(keys["m119"], state.event_date)]
    ccc = tools.get_provision(keys["ccc583"], state.event_date)
    return items, (keys["ccc583"], ccc["text"] if ccc else "")


def _employees(state: AgentState) -> list[str]:
    names = [w.name.strip() for w in (state.facts.workers if state.facts else []) if w.name.strip()]
    return list(dict.fromkeys(names)) or ["ลูกจ้าง"]


def _cards(state: AgentState, name: str) -> list[dict]:
    """Holding cards for this employee: one principle query per provision family, own holdings only."""
    from src.agent.nodes.decide import m119_keys
    from src.index.card_search import search_cards
    facts = " ".join(f for f in (state.facts.key_facts if state.facts else []) if name in f) or state.question[:600]
    keys = m119_keys()
    out: dict[str, dict] = {}
    for prov in (keys["m119"], keys["ccc583"]):
        for c in search_cards(f"{name} {facts}", provisions=[prov], k=P("determine.cards_k"),
                              event_date=state.event_date):
            out.setdefault(c["key"], c)
    return list(out.values())


def combine(name: str, votes: list[GroundVote], m119_items: list[str], ccc583_key: str,
            card_keys: set[str]) -> EmployeeDetermination:
    """Strict majority per ground over all votes; missing or invalid answers count as unknown."""
    keys = [*m119_items, ccc583_key]
    grounds = []
    for k in keys:
        cast = [next((c for c in v.checks if c.key == k), None) for v in votes]
        tally = Counter(c.status if c else "unknown" for c in cast)
        status, n = tally.most_common(1)[0] if tally else ("unknown", 0)
        if n * 2 <= len(votes):
            status = "unknown"
        agree = [c for c in cast if c and c.status == status]
        grounds.append(GroundCheck(key=k, status=status, evidence=agree[0].evidence if agree else "",
                                   cards=sorted({x for c in agree for x in c.cards if x in card_keys})))
    m119 = [g for g in grounds if g.key in m119_items]
    m119_out = True if any(g.status == "met" for g in m119) else (
        False if m119 and all(g.status == "not_met" for g in m119) else None)
    c583 = next(g for g in grounds if g.key == ccc583_key)
    ccc_out = None if m119_out is not False else {"met": True, "not_met": False}.get(c583.status)
    return EmployeeDetermination(name=name, m119=m119_out, ccc583=ccc_out, grounds=grounds,
                                 cards=sorted(card_keys), votes=len(votes))


def _card_lines(cards: list[dict]) -> str:
    return "\n".join(f"{c['key']} | {c.get('court', '')} | {(c.get('ratio_quote') or '')[:400]}" for c in cards) or "-"


@traced("determine_grounds", on_fail="review")
def determine_grounds(state: AgentState) -> dict:
    if not ({i.code for i in state.issues} & DISMISSAL_ISSUES):
        return {"_summary": "skipped: no dismissal issue"}
    items, (c583, c583_text) = _grounds(state)
    grounds = "\n".join(f"{k} | {t}" for k, t in [*items, (c583, c583_text)])
    _, body = prompt("determine_grounds")
    from src.agent.rules.holding_rules import rules_block
    rules = rules_block([k for k, _ in items] + [c583])
    out = []
    for name in _employees(state):
        cards = _cards(state, name)
        p = body.format(name=name, question=state.question, facts=fmt_facts(state), grounds=grounds,
                        cards=_card_lines(cards), rules=rules)
        votes = [generate_json(p, GroundVote, name="determine_grounds", temperature=P("determine.temperature"),
                               seed=i, thinking="low") for i in range(P("determine.votes"))]
        out.append(combine(name, votes, [k for k, _ in items], c583, {c["key"] for c in cards}))
    return {"determinations": out,
            "_summary": {d.name: {"m119": d.m119, "ccc583": d.ccc583,
                                  "met": [g.key for g in d.grounds if g.status == "met"],
                                  "unknown": [g.key for g in d.grounds if g.status == "unknown"],
                                  "cards": d.cards} for d in out}}
