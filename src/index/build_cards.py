"""Build data/processed/holding_cards.jsonl from the raw corpora (deterministic, rule-based, $0).

Sources (same selection as src/ingest/load_cases.py, so cards line up with the `cases` table):
- data/raw/deka/labour_deka.jsonl          ศาลฎีกา, rows with labour=true
- data/raw/legacy/cases.jsonl (+ case_section_links.jsonl)   ศาลอุทธรณ์คดีชำนัญพิเศษ (NOT ฎีกา)

Usage: python -m src.index.build_cards [--raw data/raw] [--out data/processed/holding_cards.jsonl] [--embed]
  --embed also builds the dense/BM25 caches used by src.index.card_search (bge-m3, local GPU, several minutes).
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from src.index.cards import CROSSWALK, card_from_appeal, card_from_deka, issue_index


def build(raw: Path) -> tuple[list, dict]:
    issues = issue_index()
    cards, skipped = [], 0
    for line in (raw / "deka/labour_deka.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        if not row.get("labour"):
            skipped += 1
            continue
        cards.append(card_from_deka(row, issues))
    links: dict[str, list[dict]] = {}
    for line in (raw / "legacy/case_section_links.jsonl").open(encoding="utf-8"):
        lk = json.loads(line)
        links.setdefault(lk["case_no"], []).append(lk)
    for line in (raw / "legacy/cases.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        cards.append(card_from_appeal(row, links.get(row["case_no"], []), issues))
    cards.sort(key=lambda c: (c.court, c.deka_no))
    return cards, {"skipped_non_labour": skipped}


def stats(cards: list, raw: Path) -> dict:
    by = {f: Counter(str(getattr(c, f)) for c in cards) for f in ("court", "regime", "substantive", "decided_by")}
    by["court×decided_by"] = Counter(f"{c.court}|{c.decided_by}" for c in cards)
    xwalk = {}
    for clause, target in (("MOI2515:46", "LPA2541:118"), ("MOI2515:47", "LPA2541:119")):
        citing = [c for c in cards if clause in c.old_provisions]
        xwalk[f"{clause}→{target}"] = f"{sum(target in c.provisions for c in citing)}/{len(citing)}"
    return {**{k: dict(sorted(v.items())) for k, v in by.items()},
            "cards": len(cards),
            "with_provisions": sum(bool(c.provisions) for c in cards),
            "with_issue_codes": sum(bool(c.issue_codes) for c in cards),
            "old_regime_cites": sum(bool(c.old_provisions) for c in cards),
            "crosswalk": xwalk,
            "segments": dict(Counter(s.decided_by for c in cards for s in c.segments))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/processed/holding_cards.jsonl")
    ap.add_argument("--embed", action="store_true")
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out)
    cards, extra = build(raw)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for c in cards:
            f.write(c.model_dump_json() + "\n")
    shutil.copyfile(CROSSWALK, out.parent / "crosswalk.yaml")
    print(json.dumps({**stats(cards, raw), **extra}, ensure_ascii=False, indent=1))
    print(f"wrote {len(cards)} cards → {out}")
    if a.embed:
        from src.index.card_search import default_card_index
        ix = default_card_index()
        print(f"indexed {len(ix.cards)} cards (dense {None if ix.vectors is None else ix.vectors.shape})")


if __name__ == "__main__":
    main()
