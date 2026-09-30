"""Recompute every kind=data parameter from the data and write value + evidence back
into config/params.yaml. Deterministic; run after ingest or re-importing dev100.

  python -m src.params_derive
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import yaml

from src.index.db import connect
from src.params import PATH


def up(x: float, step: int = 100) -> int:
    return int(math.ceil(x / step) * step)


def main() -> None:
    reg = yaml.safe_load(PATH.read_text(encoding="utf-8"))
    with open("data/eval/dev100.csv", encoding="utf-8") as f:
        dev = list(csv.DictReader(f))
    tags = json.loads(Path("data/processed/dev100_issues.json").read_text(encoding="utf-8"))
    with connect() as c:
        para = np.array([r[0] for r in c.execute(
            "SELECT length(text) FROM provisions WHERE sub_no IS NULL AND NOT repealed")])
        per_sec = np.array([r[0] for r in c.execute(
            "SELECT count(*) FROM provisions WHERE sub_no IS NULL GROUP BY law_id, section_no")])
        heads = np.array([r[0] for r in c.execute("SELECT length(holding) FROM cases")])

    n_issues = [len(v) for v in tags.values()]
    n_gold = [len([k for k in r["gold_citations"].split(";") if k]) for r in dev]
    q_len = [len(r["question"]) for r in dev]
    derived = {
        "agent.max_issues": (max(n_issues),
                             f"issues per question {dict(sorted({n: n_issues.count(n) for n in set(n_issues)}.items()))}"),
        "select.max_selected": (max(n_gold), f"gold sections per question: max {max(n_gold)}, mean {np.mean(n_gold):.1f}"),
        "select.provision_chars": (up(np.percentile(para, 99)),
                                   f"paragraph chars p50 {int(np.percentile(para, 50))}, p99 {int(np.percentile(para, 99))}, n={len(para)}"),
        "draft.provision_chars": (up(para.max()), f"longest paragraph {int(para.max())} chars"),
        "cases.summary_chars": (up(np.percentile(heads, 95)),
                                f"headnote chars p50 {int(np.percentile(heads, 50))}, p95 {int(np.percentile(heads, 95))}, n={len(heads)}"),
        "api.max_question_chars": (up(3 * max(q_len)), f"longest dev question {max(q_len)} chars"),
        "retrieve.long_section": (int(np.percentile(per_sec, 99)),
                                  f"paragraphs per section p50 {int(np.percentile(per_sec, 50))}, p99 {int(np.percentile(per_sec, 99))}, max {int(per_sec.max())}"),
    }
    # cases.per_issue: the case block (per issue) should not exceed the median block of
    # provisions ⑤ actually selected per issue in logged runs
    blocks = []
    with connect() as c:
        for f in Path("data/processed/runs").glob("*/*.json"):
            run = json.loads(f.read_text(encoding="utf-8"))
            for t in run.get("trace", []):
                if t["node"] == "select_citations" and isinstance(t.get("summary"), dict):
                    for v in t["summary"].values():
                        keys = v.get("selected", []) if isinstance(v, dict) else []
                        if keys:
                            n = c.execute("SELECT coalesce(sum(length(text)),0) FROM provisions"
                                          " WHERE citation_key = ANY(%s)", (keys,)).fetchone()[0]
                            blocks.append(n)
    if blocks:
        med_block, med_head = float(np.median(blocks)), float(np.percentile(heads, 50))
        derived["cases.per_issue"] = (
            max(1, int(med_block // med_head)),
            (f"median selected-provision block per issue {int(med_block)} chars over {len(blocks)} "
             f"issue-runs; median headnote {int(med_head)} chars → floor(block/headnote)"))

    for name, (value, evidence) in derived.items():
        assert reg[name]["kind"] in ("data", "design"), name
        reg[name]["value"], reg[name]["evidence"] = int(value), evidence
        print(f"{name:26} = {int(value):6}  ({evidence})")

    header = "".join(ln + "\n" for ln in PATH.read_text(encoding="utf-8").splitlines() if ln.startswith("#"))
    PATH.write_text(header + "\n" + yaml.safe_dump(reg, allow_unicode=True, sort_keys=False, width=120),
                    encoding="utf-8")


if __name__ == "__main__":
    main()
