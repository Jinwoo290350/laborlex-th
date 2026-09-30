"""BM25 over provision paragraphs, tokenised with pythainlp newmm.

PostgreSQL full-text search cannot segment Thai, so the lexical index lives in Python
and is cached under data/processed/bm25/ (rebuilt when the provision set changes).
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

import bm25s
from pythainlp.corpus import thai_stopwords
from pythainlp.tokenize import word_tokenize

CACHE = Path("data/processed/bm25")
STOP = frozenset(thai_stopwords())
_KEEP = re.compile(r"[฀-๿A-Za-z0-9]")


def tokenize(text: str) -> list[str]:
    toks = word_tokenize(text, engine="newmm", keep_whitespace=False)
    return [t.lower() for t in toks if _KEEP.search(t) and t not in STOP]


def _doc_text(row: dict) -> str:
    # chapter title carries topical words ("ค่าชดเชย") absent from many paragraphs
    return f"{row.get('chapter_title') or ''} {row['text']}"


class BM25Index:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.ids = [r["id"] for r in rows]
        sig = hashlib.sha1(json.dumps([(r["id"], r["text"]) for r in rows],
                                      ensure_ascii=False).encode()).hexdigest()[:12]
        path = CACHE / sig
        if path.exists():
            self.model = bm25s.BM25.load(str(path))
        else:
            self.model = bm25s.BM25()
            self.model.index([tokenize(_doc_text(r)) for r in rows], show_progress=False)
            path.mkdir(parents=True, exist_ok=True)
            self.model.save(str(path))

    def search(self, query: str, k: int = 50) -> list[tuple[int, float]]:
        """Return [(provision_id, score)] best first."""
        q = tokenize(query)
        if not q:
            return []
        docs, scores = self.model.retrieve([q], k=min(k, len(self.ids)), show_progress=False)
        return [(self.ids[i], float(s)) for i, s in zip(docs[0], scores[0]) if s > 0]


def load_rows(conn) -> list[dict]:
    """Retrievable units: paragraph rows (sub-items are contained in their paragraph)."""
    cur = conn.execute(
        "SELECT p.id, l.short_name AS law, p.section_no, p.paragraph_no, p.chapter_title, p.text,"
        " p.citation_key, p.repealed FROM provisions p JOIN laws l ON l.id = p.law_id"
        " WHERE p.sub_no IS NULL AND NOT p.repealed ORDER BY p.id")
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


@lru_cache(maxsize=1)
def default_index() -> BM25Index:
    from src.index.db import connect
    with connect() as conn:
        return BM25Index(load_rows(conn))
