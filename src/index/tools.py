"""Retrieval tools used by the agent (CLAUDE.md §5.2)."""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from src.index.bm25 import default_index
from src.index.db import connect
from src.index.gpu import DEVICE_LOCK
from src.params import P

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


def rrf(*rankings: list[tuple[int, float]], k: int | None = None) -> list[tuple[int, float]]:
    k = P("search.rrf_k") if k is None else k
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, (pid, _) in enumerate(ranking):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


RERANKER = "BAAI/bge-reranker-v2-m3"


@lru_cache(maxsize=1)
def _reranker():
    import torch
    from sentence_transformers import CrossEncoder
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    return CrossEncoder(RERANKER, device=device, max_length=512)


def rerank(query: str, rows: list[dict]) -> list[dict]:
    with DEVICE_LOCK:
        scores = _reranker().predict([(query, r["text"][:1500]) for r in rows], batch_size=16,
                                     show_progress_bar=False)
    return [{**r, "score": float(s)} for s, r in sorted(zip(scores, rows), key=lambda x: -x[0])]


def hybrid_search(query: str, event_date: date | None = None, k: int = 20,
                  pool: int | None = None, use_rerank: bool = True) -> list[dict]:
    """BM25 + bge-m3 dense → RRF → filter by validity on event_date → cross-encoder rerank."""
    pool = P("search.pool") if pool is None else pool
    fused = rrf(default_index().search(query, pool), dense_search(query, pool))
    ids = [pid for pid, _ in fused]
    score = dict(fused)
    with connect() as conn:
        rows = {r["id"]: r for r in _fetch(conn, "p.id = ANY(%s)", (ids,))}
    out = []
    limit = max(k, P("rerank.pool")) if use_rerank else k
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


def case_key(deka_no: str) -> str:
    return f"CASE:{deka_no}"


def case_label(c: dict) -> str:
    """e.g. "คำพิพากษาศาลอุทธรณ์คดีชำนัญพิเศษที่ 2063/2567 (แผนกคดีแรงงาน)" — the court is
    always named; decisions of other courts are never presented as ฎีกา."""
    no = c["deka_no"].split(" ", 1)[-1]
    kind = c.get("doc_type") or "คำพิพากษา"
    return f"{kind}{c['court']}ที่ {no}"


def search_cases(query: str, sections: set[str], k: int = 3, min_overlap: int = 1,
                 pool: int = 200) -> list[dict]:
    """Decisions that cite at least `min_overlap` of the candidate sections ("LPA2541:118"),
    ordered by similarity of their headnote to the question. `pool` bounds the dense scan
    (886 cases: the pool covers ~23% of them)."""
    from pgvector.psycopg import register_vector

    from src.index.embed import embed
    q = embed([query])[0]
    with connect() as conn:
        register_vector(conn)
        rows = conn.execute(
            "SELECT c.id, c.deka_no, c.court, c.doc_type, c.year, c.holding, c.source_url,"
            " 1 - (c.embedding <=> %s) AS sim,"
            " ARRAY(SELECT DISTINCT l.short_name || ':' || p.section_no FROM case_links cl"
            "   JOIN provisions p ON p.id = cl.provision_id JOIN laws l ON l.id = p.law_id"
            "   WHERE cl.case_id = c.id) AS sections"
            " FROM cases c WHERE c.embedding IS NOT NULL ORDER BY c.embedding <=> %s LIMIT %s",
            (q, q, pool)).fetchall()
    out = []
    for r in rows:
        d = dict(zip(("id", "deka_no", "court", "doc_type", "year", "holding", "source_url",
                      "sim", "sections"), r))
        d["overlap"] = sorted(set(d["sections"]) & sections)
        if len(d["overlap"]) < min_overlap:
            continue
        d["score"] = float(d["sim"])
        d["key"] = case_key(d["deka_no"])
        d["label"] = case_label(d)
        out.append(d)
    return sorted(out, key=lambda d: -d["score"])[:k]


def get_case(key: str) -> dict | None:
    if not key.startswith("CASE:"):
        return None
    with connect() as conn:
        r = conn.execute("SELECT deka_no, court, doc_type, year, source_url FROM cases"
                         " WHERE deka_no=%s", (key[5:],)).fetchone()
    if not r:
        return None
    d = dict(zip(("deka_no", "court", "doc_type", "year", "source_url"), r))
    return {**d, "key": key, "label": case_label(d)}
