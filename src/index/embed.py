"""bge-m3 dense embeddings (1024-d) for provisions; stored in provisions.embedding.

Usage: python -m src.index.embed   (embeds rows whose embedding IS NULL)
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from src.index.gpu import DEVICE_LOCK

MODEL = "BAAI/bge-m3"


@lru_cache(maxsize=1)
def model():
    import torch
    from sentence_transformers import SentenceTransformer
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    return SentenceTransformer(MODEL, device=device)


def embed(texts: list[str], batch_size: int = 16) -> np.ndarray:
    with DEVICE_LOCK:
        return model().encode(texts, batch_size=batch_size, normalize_embeddings=True,
                              show_progress_bar=len(texts) > 64, convert_to_numpy=True)


def doc_text(chapter_title: str | None, law: str, section: str, text: str) -> str:
    return f"{chapter_title or ''} มาตรา {section}\n{text}".strip()


def embed_cases(conn) -> None:
    """Case vectors from the headnote plus the start of the reasoning."""
    rows = conn.execute("SELECT id, holding, full_text FROM cases WHERE embedding IS NULL"
                        " ORDER BY id").fetchall()
    if not rows:
        print("no cases to embed")
        return
    vecs = embed([f"{h or ''}\n{(t or '')[:1200]}" for _, h, t in rows])
    with conn.cursor() as cur:
        cur.executemany("UPDATE cases SET embedding=%s WHERE id=%s",
                        [(v, r[0]) for v, r in zip(vecs, rows)])
    print(f"embedded {len(rows)} cases")


def main() -> None:
    import sys

    from pgvector.psycopg import register_vector

    from src.index.db import connect
    with connect() as conn:
        register_vector(conn)
        if "--cases" in sys.argv:
            embed_cases(conn)
            return
        rows = conn.execute(
            "SELECT p.id, p.chapter_title, l.short_name, p.section_no, p.text FROM provisions p"
            " JOIN laws l ON l.id=p.law_id WHERE p.embedding IS NULL ORDER BY p.id").fetchall()
        if not rows:
            print("nothing to embed")
            return
        vecs = embed([doc_text(ct, law, sec, t) for _, ct, law, sec, t in rows])
        with conn.cursor() as cur:
            cur.executemany("UPDATE provisions SET embedding=%s WHERE id=%s",
                            [(v, r[0]) for v, r in zip(vecs, rows)])
        print(f"embedded {len(rows)} provisions")


if __name__ == "__main__":
    main()
