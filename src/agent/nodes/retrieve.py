"""③ retrieve_law · ④ retrieve_cases"""

from __future__ import annotations

import logging
from collections import Counter

from src.agent.nodes.common import taxonomy, traced
from src.agent.state import AgentState
from src.index import tools
from src.params import P

log = logging.getLogger(__name__)


def primary_sections(code: str, exclude: set[str], need: int | None = None) -> list[str]:
    """Taxonomy sections for an issue: sections cited by the gold of at least two dev
    questions tagged with the issue, or by one question when an element also cites it.
    Support from excluded (leave-one-out) questions never counts — element citations were
    drafted from the same gold, so on their own they are not evidence."""
    issue = taxonomy()[code]
    support = issue.get("provision_support") or {}
    from_elements = {":".join(k.split(":")[:2])            # "LPA2541:118:1:(1)" → "LPA2541:118"
                     for e in issue.get("elements", []) for k in e.get("citation_keys", [])}
    ranked = sorted(((sec, len(set(qs) - exclude)) for sec, qs in support.items()),
                    key=lambda x: -x[1])
    need = P("retrieve.primary_min_support") if need is None else need
    return [sec for sec, n in ranked
            if n >= need or (n >= 1 and sec in from_elements)][:P("retrieve.primary_max")]


def _search(query: str, event_date, k: int) -> tuple[list[dict], str | None]:
    """Hybrid search; on failure BM25 only. Returns (rows, fallback reason or None)."""
    try:
        return tools.hybrid_search(query, event_date=event_date, k=k), None
    except Exception as e:  # noqa: BLE001 — dense index/model missing → lexical only
        log.warning("hybrid search unavailable (%s); using BM25 only", e)
        from src.index.bm25 import default_index
        ids = [pid for pid, _ in default_index().search(query, k * 2)]
        with tools.connect() as conn:
            rows = {r["id"]: r for r in tools._fetch(conn, "p.id = ANY(%s)", (ids,))}
        return ([rows[i] for i in ids if i in rows and tools._in_force(rows[i], event_date)][:k],
                f"bm25_only: {e!r}")


def _add(found: dict[int, dict], rows: list[dict], via: str, quota: int) -> None:
    """Add up to `quota` new, non-repealed rows from one source."""
    n = 0
    for r in rows:
        if n >= quota:
            break
        if r["id"] not in found and not r.get("repealed"):
            found[r["id"]] = {**r, "via": via}
            n += 1


@traced("retrieve_law")
def retrieve_law(state: AgentState) -> dict:
    """Per issue: taxonomy sections, hybrid search and subordinate law, each with its own
    quota so no source can crowd out the others."""
    exclude = set(state.exclude_example_ids)
    cands: dict[str, list[dict]] = {}
    fallbacks = []
    for iss in state.issues:
        name = taxonomy()[iss.code]["name"]
        found: dict[int, dict] = {}

        tax_rows = []
        for key in primary_sections(iss.code, exclude):
            law, sec = key.split(":", 1)
            paras = tools.get_section(law, sec)
            if len(paras) <= P("retrieve.long_section"):
                tax_rows += paras[:P("retrieve.max_paras_per_section")]
        _add(found, tax_rows, "taxonomy", P("retrieve.tax_rows"))

        hits, fb = _search(f"{name}\n{state.question}", state.event_date,
                           P("retrieve.search_rows") * 2)
        if fb:
            fallbacks.append(fb)
        _add(found, hits, "search", P("retrieve.search_rows"))

        children = [c for pid in list(found)[:8] for c in tools.expand(pid).get("children", [])]
        _add(found, children, "issued_under", P("retrieve.child_rows"))

        cands[iss.code] = [{k: v for k, v in r.items() if k not in ("valid_from", "valid_to")}
                           for r in found.values()]
    summary: dict = {c: {"n": len(v), "via": dict(Counter(r["via"] for r in v))}
                     for c, v in cands.items()}
    if fallbacks:
        summary["fallbacks"] = fallbacks
    return {"candidates": cands, "_summary": summary}


@traced("retrieve_cases", fallback=lambda state, e: {"cases": {}})
def retrieve_cases(state: AgentState) -> dict:
    """Court decisions per issue: similar facts, boosted when they cite the issue's
    candidate sections. Only these can be cited (checked at ⑩)."""
    out: dict[str, list[dict]] = {}
    for iss in state.issues:
        sections = {f"{r['law']}:{r['section_no']}" for r in state.candidates.get(iss.code, [])}
        hits = tools.search_cases(state.question, sections, k=P("cases.per_issue"),
                                  min_overlap=P("cases.min_section_overlap"))
        out[iss.code] = [{k: v for k, v in h.items() if k != "sections"} for h in hits]
    return {"cases": out,
            "_summary": {c: [h["label"] for h in v] for c, v in out.items()}}
