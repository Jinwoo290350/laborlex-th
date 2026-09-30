"""bge-m3 dense embeddings (1024-d) for provisions; stored in provisions.embedding.

Usage: python -m src.index.embed   (embeds rows whose embedding IS NULL)
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

MODEL = "BAAI/bge-m3"


@lru_cache(maxsize=1)
def model():
    import torch
    from sentence_transformers import SentenceTransformer
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    return SentenceTransformer(MODEL, device=device)


def embed(texts: list[str], batch_size: int = 16) -> np.ndarray:
    return model().encode(texts, batch_size=batch_size, normalize_embeddings=True,
                          show_progress_bar=len(texts) > 64, convert_to_numpy=True)


def doc_text(chapter_title: str | None, law: str, section: str, text: str) -> str:
    return f"{chapter_title or ''} มาตรา {section}\n{text}".strip()


def main() -> None:
    from pgvector.psycopg import register_vector

    from src.index.db import connect
    with connect() as conn:
        register_vector(conn)
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
