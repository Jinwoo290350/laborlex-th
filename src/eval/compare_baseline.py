"""Compare our run with the client's Gemini baseline answers on the same questions.

Baseline = data/raw/legacy/client-baseline-scores.jsonl, model_code "g" (answers the client
had lawyers grade). Both sides are measured the same way:
  - client criterion: every column-H section is mentioned in the answer text
    (sections extracted from the text with the same parser, src.eval.import_dev100)
  - our LLM judge (same prompt, same gold) — relative comparison only
  - the lawyers' PASS on the baseline answer (free, shown for reference)

  python -m src.eval.compare_baseline --run data/runs/<dir>
"""

from __future__ import annotations

import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.eval.calibrate_judge import answer_md
from src.eval.import_dev100 import resolve_citations
from src.eval.judge import CRITERIA, gold_text, judge
from src.llm import USAGE


def sections(text: str) -> set[str]:
    return set(resolve_citations(text))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--model", default="g")
    a = ap.parse_args()
    run = {json.loads(p.read_text(encoding="utf-8"))["id"]: json.loads(p.read_text(encoding="utf-8"))
           for p in Path(a.run).glob("dev*.json")}
    with open("data/eval/dev100.csv", encoding="utf-8") as f:
        dev = {r["id"]: r for r in csv.DictReader(f)}
    base = {}
    for line in Path("data/raw/legacy/client-baseline-scores.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        qid = "dev" + r["item_id"].split("-")[1]
        if r["model_code"] == a.model and qid in run:
            base[qid] = r
    ids = sorted(set(run) & set(base))

    def score(qid):
        md = answer_md(base[qid]["answers"])
        return qid, md, judge(dev[qid]["question"], gold_text(dev[qid]), md)

    with ThreadPoolExecutor(6) as ex:
        judged = {q: (md, s) for q, md, s in ex.map(score, ids)}

    def full(qid, text):
        gold = {g for g in dev[qid]["gold_citations"].split(";") if g}
        return bool(gold) and gold <= sections(text)

    with_gold = [q for q in ids if dev[q]["gold_citations"]]
    ours_full = sum(full(q, run[q]["markdown"]) for q in with_gold)
    ours_full_keys = sum(run[q]["gold_hit"] == len(run[q]["gold_sections"]) for q in with_gold)
    base_full = sum(full(q, judged[q][0]) for q in with_gold)
    n = len(ids)
    lines = [f"# Ours vs Gemini baseline ({a.model}) — {n} questions ({Path(a.run).name})", "",
             "| metric | ours | Gemini baseline |", "|---|---|---|",
             (f"| cites every column-H section (text parser, same for both) | {ours_full}/{len(with_gold)} | "
              f"{base_full}/{len(with_gold)} |"),
             f"| cites every column-H section (our citation keys) | {ours_full_keys}/{len(with_gold)} | — |",
             (f"| judge PASS (same judge) | {sum(run[q]['pass'] for q in ids)}/{n} | "
              f"{sum(judged[q][1].passed for q in ids)}/{n} |"),
             f"| lawyer PASS | — | {sum(all(base[q]['scores'][c] == 2 for c in CRITERIA) for q in ids)}/{n} |"]
    for c in CRITERIA:
        o = sum(1 for q in ids if run[q]["score"] and run[q]["score"][c] == 2)
        b = sum(getattr(judged[q][1], c) == 2 for q in ids)
        lines.append(f"| judge {c} = 2 | {o}/{n} | {b}/{n} |")
    lines += ["", "## Questions where ours misses a column-H section", ""]
    for q in with_gold:
        if run[q]["gold_hit"] < len(run[q]["gold_sections"]):
            lines.append(f"- {q}: missing {sorted(set(run[q]['gold_sections']) - set(run[q]['cited_sections']))}")
    lines += ["", f"judge calls {USAGE.calls} (cached {USAGE.cached})"]
    out = Path("docs/results") / f"{Path(a.run).name}_vs_baseline_{a.model}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
