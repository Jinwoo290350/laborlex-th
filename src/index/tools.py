"""Retrieval tools used by the agent (CLAUDE.md §5.2)."""

from __future__ import annotations

import threading
from datetime import date
from functools import lru_cache

from src.index.bm25 import default_index
from src.index.db import connect

RRF_K = 60
_COLS = ("p.id, l.short_name AS law, l.name AS law_name, l.level, p.section_no, p.paragraph_no,"
         " p.sub_no, p.chapter, p.chapter_title, p.text, p.citation_key, p.valid_from,"
         " p.valid_to, p.repealed, p.amendment_notes,"
         " (SELECT pl.name FROM laws pl WHERE pl.id = l.parent_law_id) AS parent_law_name")


def _fetch(conn, where: str, params: tuple) -> list[dict]:
    cur = conn.execute(f"SELECT {_COLS} FROM provisions p JOIN laws l ON l.id=p.law_id "
                       f"WHERE {where}", params)
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _in_force(r: dict, on: date | None) -> bool:
    if r["repealed"]:
        return False
    if on is None:
        return True
    return ((r["valid_from"] is None or r["valid_from"] <= on)
            and (r["valid_to"] is None or on < r["valid_to"]))


def dense_ready() -> bool:
    with connect() as conn:
        return conn.execute("SELECT EXISTS (SELECT 1 FROM provisions"
                            " WHERE embedding IS NOT NULL)").fetchone()[0]


def dense_search(query: str, k: int = 50) -> list[tuple[int, float]]:
    """bge-m3 nearest neighbours; empty when the index has no embeddings yet."""
    if not dense_ready():
        return []
    from pgvector.psycopg import register_vector

    from src.index.embed import embed
    q = embed([query])[0]
    with connect() as conn:
        register_vector(conn)
        rows = conn.execute(
            "SELECT id, 1 - (embedding <=> %s) FROM provisions WHERE sub_no IS NULL"
            " AND NOT repealed AND embedding IS NOT NULL ORDER BY embedding <=> %s LIMIT %s",
            (q, q, k)).fetchall()
    return [(i, float(s)) for i, s in rows]


def rrf(*rankings: list[tuple[int, float]], k: int = RRF_K) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, (pid, _) in enumerate(ranking):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


RERANKER = "BAAI/bge-reranker-v2-m3"
RERANK_POOL = 50


@lru_cache(maxsize=1)
def _reranker():
    import torch
    from sentence_transformers import CrossEncoder
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    return CrossEncoder(RERANKER, device=device, max_length=512)


_RERANK_LOCK = threading.Lock()


def rerank(query: str, rows: list[dict]) -> list[dict]:
    with _RERANK_LOCK:                     # MPS models are not thread-safe
        scores = _reranker().predict([(query, r["text"][:1500]) for r in rows], batch_size=16,
                                     show_progress_bar=False)
    return [{**r, "score": float(s)} for s, r in sorted(zip(scores, rows), key=lambda x: -x[0])]


def hybrid_search(query: str, event_date: date | None = None, k: int = 20,
                  pool: int = 100, use_rerank: bool = True) -> list[dict]:
    """BM25 + bge-m3 dense → RRF → filter by validity on event_date → cross-encoder rerank."""
    fused = rrf(default_index().search(query, pool), dense_search(query, pool))
    ids = [pid for pid, _ in fused]
    score = dict(fused)
    with connect() as conn:
        rows = {r["id"]: r for r in _fetch(conn, "p.id = ANY(%s)", (ids,))}
    out = []
    limit = max(k, RERANK_POOL) if use_rerank else k
    for pid in ids:
        r = rows.get(pid)
        if r and _in_force(r, event_date):
            out.append({**r, "score": score[pid]})
        if len(out) >= limit:
            break
    if use_rerank and out:
        try:
            out = rerank(query, out)
        except OSError:          # reranker weights not available → keep RRF order
            pass
    return out[:k]


search_provisions = hybrid_search


def get_provision(citation_key: str, on: date | None = None) -> dict | None:
    with connect() as conn:
        rows = _fetch(conn, "p.citation_key = %s", (citation_key,))
    rows = [r for r in rows if _in_force(r, on)]
    return rows[0] if rows else None


def get_section(law: str, section_no: str) -> list[dict]:
    with connect() as conn:
        return _fetch(conn, "l.short_name=%s AND p.section_no=%s AND p.sub_no IS NULL"
                            " ORDER BY p.paragraph_no", (law, section_no))


def expand(provision_id: int) -> dict:
    """1 hop: whole section, subordinate provisions issued under it, and the parent-law
    sections a subordinate provision was issued under."""
    with connect() as conn:
        base = _fetch(conn, "p.id=%s", (provision_id,))
        if not base:
            return {}
        b = base[0]
        section = _fetch(conn, "l.short_name=%s AND p.section_no=%s AND p.sub_no IS NULL"
                               " ORDER BY p.paragraph_no", (b["law"], b["section_no"]))
        children = _fetch(conn, "p.id IN (SELECT k.from_id FROM links k JOIN provisions t"
                                " ON t.id=k.to_id WHERE k.type IN ('ISSUED_UNDER','REFERS_TO')"
                                " AND t.law_id=(SELECT law_id FROM provisions WHERE id=%s)"
                                " AND t.section_no=%s)", (provision_id, b["section_no"]))
        parents = _fetch(conn, "p.id IN (SELECT to_id FROM links WHERE type='ISSUED_UNDER'"
                               " AND from_id IN (SELECT id FROM provisions WHERE law_id="
                               "(SELECT law_id FROM provisions WHERE id=%s)))", (provision_id,))
    return {"provision": b, "section": section, "children": children, "parents": parents}
