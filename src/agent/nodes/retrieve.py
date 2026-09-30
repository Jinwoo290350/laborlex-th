"""③ retrieve_law · ④ retrieve_cases"""

from __future__ import annotations

import logging

from src.agent.nodes.common import taxonomy, traced
from src.agent.state import AgentState
from src.index import tools

log = logging.getLogger(__name__)
PER_ISSUE = 24


def primary_sections(code: str, exclude: set[str]) -> list[str]:
    """Taxonomy sections for an issue, ignoring support that comes only from excluded
    (leave-one-out) questions."""
    issue = taxonomy()[code]
    support = issue.get("provision_support") or {}
    ranked = sorted(((sec, len(set(qs) - exclude)) for sec, qs in support.items()),
                    key=lambda x: -x[1])
    return [sec for sec, n in ranked if n > 0][:6]


def _search(query: str, event_date, k: int) -> list[dict]:
    try:
        return tools.hybrid_search(query, event_date=event_date, k=k)
    except Exception as e:  # noqa: BLE001 — dense index missing → lexical only
        log.warning("hybrid search unavailable (%s); using BM25 only", e)
        from src.index.bm25 import default_index
        ids = [pid for pid, _ in default_index().search(query, k * 2)]
        with tools.connect() as conn:
            rows = {r["id"]: r for r in tools._fetch(conn, "p.id = ANY(%s)", (ids,))}
        return [rows[i] for i in ids if i in rows and tools._in_force(rows[i], event_date)][:k]


@traced("retrieve_law")
def retrieve_law(state: AgentState) -> dict:
    exclude = set(state.exclude_example_ids)
    cands: dict[str, list[dict]] = {}
    for iss in state.issues:
        name = taxonomy()[iss.code]["name"]
        found: dict[int, dict] = {}
        for key in primary_sections(iss.code, exclude):
            law, sec = key.split(":", 1)
            for r in tools.get_section(law, sec):
                found.setdefault(r["id"], {**r, "via": "taxonomy"})
        for r in _search(f"{name}\n{state.question}", state.event_date, 12):
            found.setdefault(r["id"], {**r, "via": "search"})
        # 1 hop to subordinate law issued under the found sections
        for pid in list(found)[:8]:
            for r in tools.expand(pid).get("children", []):
                found.setdefault(r["id"], {**r, "via": "issued_under"})
        cands[iss.code] = [
            {k: v for k, v in r.items() if k not in ("valid_from", "valid_to")}
            for r in list(found.values())[:PER_ISSUE]]
    return {"candidates": cands,
            "_summary": {c: len(v) for c, v in cands.items()}}


@traced("retrieve_cases")
def retrieve_cases(state: AgentState) -> dict:
    # Supreme Court case data not delivered yet (CLAUDE.md §9) — keep the node so the
    # flow and trace are complete; it returns nothing until `cases` is populated.
    return {"cases": {}, "_summary": "no case data loaded"}
