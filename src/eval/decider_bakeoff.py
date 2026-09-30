"""Bake-off for node ⑤ select_citations (CLAUDE.md §5.4, Day 10).

For each dev100 question: retrieve candidates, ask the decider "does this provision apply
to these facts?" (noul) per candidate, and compare with gold sections. Reports ROC-AUC,
F1 at the best threshold, ECE, and gold recall@5 when candidates are re-ranked by the
decider vs the retrieval order.

  python -m src.eval.decider_bakeoff --decider openthai --limit 30 --k 15
"""

from __future__ import annotations

import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from src.decision.base import QuestionSpec, get_decider
from src.index import tools

QUESTION = QuestionSpec(type="noul",
                        instructions="บทบัญญัตินี้เป็นกฎหมายที่ต้องใช้วินิจฉัยคำถามนี้โดยตรงหรือไม่")


def ece(ps: list[float], ys: list[int], bins: int = 10) -> float:
    total, err = len(ps), 0.0
    for b in range(bins):
        idx = [i for i, p in enumerate(ps) if b / bins <= p < (b + 1) / bins or (b == bins - 1 and p == 1)]
        if idx:
            conf = sum(ps[i] for i in idx) / len(idx)
            acc = sum(ys[i] for i in idx) / len(idx)
            err += len(idx) / total * abs(conf - acc)
    return err


def auc(ps: list[float], ys: list[int]) -> float:
    pos = [p for p, y in zip(ps, ys) if y]
    neg = [p for p, y in zip(ps, ys) if not y]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decider", default="openthai")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--k", type=int, default=15)
    a = ap.parse_args()

    with open("data/eval/dev100.csv", encoding="utf-8") as f:
        qs = [r for r in csv.DictReader(f) if r["gold_citations"]][: a.limit]
    dec = get_decider(a.decider)

    # retrieval runs sequentially: the embedding model on MPS is not thread-safe
    cand_by_q = {q["id"]: tools.hybrid_search(q["question"], k=a.k, use_rerank=False) for q in qs}

    def run(q):
        gold = set(q["gold_citations"].split(";"))
        cands = cand_by_q[q["id"]]
        res = []
        for rank, c in enumerate(cands):
            d = dec.decide({"คำถาม": q["question"], "บทบัญญัติ": f"{c['citation_key']} {c['law_name']}\n{c['text'][:1500]}"},
                           {"applies": QUESTION})["applies"]
            res.append({"key": c["citation_key"], "rank": rank, "p": d.p,
                        "y": int(f"{c['law']}:{c['section_no']}" in gold)})
        return q["id"], gold, res

    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(run, qs))

    ps = [r["p"] for _, _, rs in results for r in rs]
    ys = [r["y"] for _, _, rs in results for r in rs]
    best = max(((t / 20, *_prf(ps, ys, t / 20)) for t in range(1, 20)), key=lambda x: x[3])

    def section(key: str) -> str:              # "LPA2541:118:1" → "LPA2541:118"
        return ":".join(key.split(":")[:2])

    def recall_at(order_key, n=5) -> float:
        """Of the gold sections present among the candidates, how many reach the top n."""
        hit = tot = 0
        for _, _, rs in results:
            got = {section(r["key"]) for r in sorted(rs, key=order_key)[:n]}
            present = {section(r["key"]) for r in rs if r["y"]}
            hit += len(present & got)
            tot += len(present)
        return hit / tot if tot else float("nan")

    report = {
        "decider": a.decider, "questions": len(results), "pairs": len(ps), "positives": sum(ys),
        "auc": round(auc(ps, ys), 3), "ece": round(ece(ps, ys), 3),
        "best_threshold": best[0], "precision": round(best[1], 3), "recall": round(best[2], 3), "f1": round(best[3], 3),
        "gold_recall@5_retrieval_order": round(recall_at(lambda r: r["rank"]), 3),
        "gold_recall@5_decider_order": round(recall_at(lambda r: -r["p"]), 3),
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    out = Path("docs/results") / f"{datetime.now().astimezone():%Y-%m-%d}_bakeoff_{a.decider}.json"
    out.write_text(json.dumps({"report": report, "results": results}, ensure_ascii=False, indent=1, default=list),
                   encoding="utf-8")


def _prf(ps, ys, t):
    tp = sum(1 for p, y in zip(ps, ys) if p >= t and y)
    fp = sum(1 for p, y in zip(ps, ys) if p >= t and not y)
    fn = sum(1 for p, y in zip(ps, ys) if p < t and y)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return prec, rec, (2 * prec * rec / (prec + rec) if prec + rec else 0.0)


if __name__ == "__main__":
    main()
