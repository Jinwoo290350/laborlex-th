"""M4 acceptance: Recall@k of expected decisions, baseline case retrieval vs Holding-Card search ($0, no LLM).

Baseline = src.index.tools.search_cases (production: dense similarity over cases.embedding, kept only when linked to
or naming one of the issue's sections; sections = the issue's primary_provisions).
New = src.index.card_search.search_cards with the same query (and issue_code), several variants.

Usage: python -m src.index.eval_cards [--k 5] [--out data/processed/cards/benchmark.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

BENCH = Path(__file__).with_name("card_benchmark.yaml")


def recall(found: list[str], expected: list[str]) -> float:
    return len(set(found) & set(expected)) / len(expected)


def summarize(rows: list[dict], name: str) -> dict:
    hits = sum(len(set(r[name]) & set(r["expected"])) for r in rows)
    total = sum(len(r["expected"]) for r in rows)
    return {"micro": hits / total, "macro": sum(recall(r[name], r["expected"]) for r in rows) / len(rows),
            "hits": f"{hits}/{total}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--out", default="data/processed/cards/benchmark.json")
    a = ap.parse_args()

    from src.index.card_search import default_card_index, search_cards
    from src.index.cards import issue_index
    from src.index.tools import search_cases

    items = yaml.safe_load(BENCH.read_text(encoding="utf-8"))
    known = {c.deka_no for c in default_card_index().cards}
    missing = [d for it in items for d in it["expected"] if d not in known]
    assert not missing, f"expected decisions not in the corpus: {missing}"
    sections: dict[str, set[str]] = {}
    for prov, codes in issue_index().items():
        for code in codes:
            sections.setdefault(code, set()).add(prov)

    variants = {
        "baseline_search_cases": lambda it: [c["deka_no"] for c in
                                             search_cases(it["query"], sections[it["issue_code"]], k=a.k)],
        "cards_issue": lambda it: [c["deka_no"] for c in search_cards(it["query"], it["issue_code"], k=a.k)],
        "cards_no_issue": lambda it: [c["deka_no"] for c in search_cards(it["query"], k=a.k)],
        "cards_issue_rerank": lambda it: [c["deka_no"] for c in
                                          search_cards(it["query"], it["issue_code"], k=a.k, use_rerank=True)],
    }
    rows = []
    for it in items:
        row = {"id": it["id"], "expected": it["expected"]}
        for name, fn in variants.items():
            row[name] = fn(it)
        rows.append(row)
    summary = {name: summarize(rows, name) for name in variants}
    cards = {c.deka_no: c for c in default_card_index().cards}
    notes = {d: {"decided_by": cards[d].decided_by, "substantive": cards[d].substantive,
                 "issue_codes": cards[d].issue_codes} for it in items for d in it["expected"]}
    out = {"k": a.k, "summary": summary, "rows": rows, "expected_cards": notes}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
