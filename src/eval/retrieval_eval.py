"""Section-level Recall@k of retrieval against dev100 gold_citations.

A question counts its gold sections that exist in the index; a gold section is hit
when any retrieved paragraph belongs to it. Reports micro recall and per-question
all-hit rate."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def evaluate(search, rows_by_id: dict[int, dict], k: int, dataset: str) -> dict:
    with open(dataset, encoding="utf-8") as f:
        qs = list(csv.DictReader(f))
    indexed = {f"{r['law']}:{r['section_no']}" for r in rows_by_id.values()}
    hit = total = allhit = nq = 0
    misses = []
    for q in qs:
        gold = [g for g in q["gold_citations"].split(";") if g in indexed]
        if not gold:
            continue
        nq += 1
        got = {f"{rows_by_id[i]['law']}:{rows_by_id[i]['section_no']}"
               for i, _ in search(q["question"], k)}
        h = [g for g in gold if g in got]
        hit, total = hit + len(h), total + len(gold)
        allhit += len(h) == len(gold)
        if len(h) < len(gold):
            misses.append({"id": q["id"], "missed": [g for g in gold if g not in got]})
    return {"k": k, "questions": nq, "gold_sections": total,
            f"recall@{k}": round(hit / total, 3), "all_hit_rate": round(allhit / nq, 3),
            "misses": misses}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retriever", default="bm25", choices=["bm25", "hybrid"])
    ap.add_argument("--k", type=int, nargs="+", default=[10, 20])
    ap.add_argument("--set", default="data/eval/dev100.csv")
    a = ap.parse_args()

    from src.index.bm25 import default_index
    idx = default_index()
    rows_by_id = {r["id"]: r for r in idx.rows}
    if a.retriever == "bm25":
        search = idx.search
    else:
        from src.index.tools import hybrid_search
        def search(q, k):
            return [(r["id"], r["score"]) for r in hybrid_search(q, k=k)]

    results = [evaluate(search, rows_by_id, k, a.set) for k in a.k]
    for r in results:
        print({k: v for k, v in r.items() if k != "misses"})
    out = Path("docs/results") / f"{datetime.now().astimezone().date()}_retrieval_{a.retriever}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("→", out)


if __name__ == "__main__":
    main()
