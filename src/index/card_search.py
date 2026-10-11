"""Per-element retrieval over Holding Cards (M4, FIX_PLAN_v2 §B "Retrieval").

search_cards(query, issue_code, provisions, k, event_date):
  BM25 (pythainlp newmm, src.index.bm25.tokenize) + bge-m3 dense, both over the card's searchable text (headnote
  segments the deciding court decided itself) → Reciprocal Rank Fusion (k = params search.rrf_k) → optional
  cross-encoder rerank (bge-reranker-v2-m3, off by default).
Filters (default): substantive cards only; decided_by not restated_lower_court / procedural_refusal
  (`include_all=True` lifts both); optional issue_code (card.issue_codes) and provisions (any shared "LAW:section").
Court preference: a ฎีกา own holding gets its score multiplied by (1 + margin), margin = 0.03, so it moves above an
  appeal-court (ศาลอุทธรณ์คดีชำนัญพิเศษ) card only when that card scores less than 3 % higher; clearly better
  appeal-court cards keep their place. (With RRF k=60 over two rankings, 3 % ≈ one or two ranks.)
event_date: does not filter (old-regime holdings crosswalked to current sections stay valid authority); each result
  carries `regime_match` = whether the card's regime is the one in force on that date.

Caches (gitignored): data/processed/cards/bm25_<sig>/ and dense_<sig>.npy, sig = hash of the card texts.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import bm25s
import numpy as np

from src.index.bm25 import tokenize
from src.index.cards import HoldingCard, load_cards
from src.index.tools import case_key, case_label, rrf

CARDS_PATH = Path("data/processed/holding_cards.jsonl")
CACHE = Path("data/processed/cards")
MARGIN = 0.03
EXCLUDED = ("restated_lower_court", "procedural_refusal")
LPA_IN_FORCE = date(1998, 8, 19)     # พ.ร.บ.คุ้มครองแรงงาน พ.ศ. 2541 in force 19 ส.ค. 2541
DENSE_CHARS = 2000


class CardIndex:
    def __init__(self, cards: list[HoldingCard], embed_fn: Callable | None = None,
                 vectors: np.ndarray | None = None, cache_dir: Path | None = None):
        self.cards = cards
        self.texts = [c.text for c in cards]
        self.embed_fn = embed_fn
        sig = hashlib.sha1("\x1e".join(f"{c.deka_no}\x1f{t}" for c, t in zip(cards, self.texts))
                           .encode()).hexdigest()[:12]
        self.bm25 = self._bm25(cache_dir / f"bm25_{sig}" if cache_dir else None)
        if vectors is None and embed_fn is not None:
            path = cache_dir / f"dense_{sig}.npy" if cache_dir else None
            if path and path.exists():
                vectors = np.load(path)
            else:
                vectors = np.asarray(embed_fn([t[:DENSE_CHARS] for t in self.texts]), dtype=np.float32)
                if path:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    np.save(path, vectors)
        self.vectors = vectors

    def _bm25(self, path: Path | None) -> bm25s.BM25:
        if path and path.exists():
            return bm25s.BM25.load(str(path))
        model = bm25s.BM25()
        model.index([tokenize(t) or ["∅"] for t in self.texts], show_progress=False)
        if path:
            path.mkdir(parents=True, exist_ok=True)
            model.save(str(path))
        return model

    def _allowed(self, issue_code: str | None, provisions: list[str] | None, include_all: bool) -> list[int]:
        want = {":".join(p.split(":")[:2]) for p in provisions or []}
        out = []
        for i, c in enumerate(self.cards):
            if not include_all and (not c.substantive or c.decided_by in EXCLUDED):
                continue
            if issue_code and issue_code not in c.issue_codes:
                continue
            if want and not want & set(c.provisions):
                continue
            out.append(i)
        return out

    def search(self, query: str, issue_code: str | None = None, provisions: list[str] | None = None,
               k: int = 5, event_date: date | None = None, include_all: bool = False,
               use_rerank: bool = False, pool: int = 100, rerank_pool: int = 20,
               margin: float = MARGIN) -> list[dict]:
        idx = self._allowed(issue_code, provisions, include_all)
        if not idx:
            return []
        rankings = []
        q = tokenize(query)
        if q:
            s = self.bm25.get_scores(q)
            rankings.append([(i, float(s[i])) for i in sorted(idx, key=lambda i: -s[i])[:pool] if s[i] > 0])
        if self.vectors is not None and self.embed_fn is not None:
            qv = np.asarray(self.embed_fn([query]), dtype=np.float32)[0]
            sims = self.vectors[idx] @ qv
            order = np.argsort(-sims)[:pool]
            rankings.append([(idx[j], float(sims[j])) for j in order])
        fused = rrf(*rankings)
        rows: list[dict[str, Any]] = [{"i": i, "score": s, "text": self.texts[i]} for i, s in fused]
        if use_rerank and rows:
            from src.index.tools import rerank
            try:
                rows = rerank(query, rows[:max(k, rerank_pool)])   # tail dropped: scores not comparable
            except OSError:          # reranker weights unavailable → keep RRF order
                pass
        for r in rows:
            c = self.cards[r["i"]]
            boost = margin if c.is_supreme and c.decided_by == "own_holding" else 0.0
            r["adj_score"] = r["score"] + boost * abs(r["score"])
        rows.sort(key=lambda r: -r["adj_score"])
        return [self._result(r, event_date) for r in rows[:k]]

    def _result(self, r: dict, event_date: date | None) -> dict:
        c = self.cards[r["i"]]
        d = c.model_dump(exclude={"segments"})
        d.update(text=r["text"], score=r["score"], adj_score=r["adj_score"], key=case_key(c.deka_no),
                 label=case_label({"deka_no": c.deka_no, "court": c.court, "doc_type": c.doc_type}))
        if event_date is not None:
            d["regime_match"] = c.regime == ("pre2541" if event_date < LPA_IN_FORCE else "post2541")
        return d


@lru_cache(maxsize=1)
def default_card_index() -> CardIndex:
    from src.index.embed import embed
    return CardIndex(load_cards(CARDS_PATH), embed_fn=embed, cache_dir=CACHE)


def search_cards(query: str, issue_code: str | None = None, provisions: list[str] | None = None, k: int = 5,
                 event_date: date | None = None, **kw) -> list[dict]:
    """Holding cards for one (issue × element) principle query, best first (see module docstring)."""
    return default_card_index().search(query, issue_code=issue_code, provisions=provisions, k=k,
                                       event_date=event_date, **kw)
