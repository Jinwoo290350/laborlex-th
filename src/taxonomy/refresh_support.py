"""Recompute each issue's provision_support from the current dev100 gold and issue tags.

Run after data/eval/dev100.csv changes (e.g. config/gold_overrides.yaml). Only the
data-derived support map is rewritten; elements and pitfalls are left untouched (no LLM).

  python -m src.taxonomy.refresh_support
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

OUT = Path("data/processed/issues.yaml")


def main() -> None:
    tags = json.loads(Path("data/processed/dev100_issues.json").read_text(encoding="utf-8"))
    with open("data/eval/dev100.csv", encoding="utf-8") as f:
        dev = {r["id"]: r for r in csv.DictReader(f)}
    text = OUT.read_text(encoding="utf-8")
    header = "".join(line for line in text.splitlines(keepends=True) if line.startswith("#"))
    issues = yaml.safe_load(text)
    changed = 0
    for iss in issues:
        support: dict[str, list[str]] = {}
        for qid in sorted(q for q, codes in tags.items() if iss["code"] in codes):
            for g in (g for g in dev[qid]["gold_citations"].split(";") if g):
                support.setdefault(g, []).append(qid)
        changed += support != iss.get("provision_support")
        iss["provision_support"] = support
    OUT.write_text(header + yaml.safe_dump(issues, allow_unicode=True, sort_keys=False, width=120),
                   encoding="utf-8")
    print(f"provision_support refreshed · {changed} issues changed")


if __name__ == "__main__":
    main()
