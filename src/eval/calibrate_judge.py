"""Calibrate the LLM judge against the lawyers' per-question scores (CLAUDE.md §7).

Data: data/raw/legacy/client-baseline-scores.jsonl — 300 rows (Gemini, ChatGPT, Claude ×
100 dev questions), each scored A1..B3 by a lawyer. Only TUNE-split questions are used, so
the holdout stays untouched. Selection is deterministic: per model, lawyer-PASS and
lawyer-FAIL rows alternately, each list ordered by md5(item_id + model).

Acceptance (pre-registered, docs/improvement_plan.md): quadratic-weighted κ ≥ 0.6 per
criterion and PASS agreement ≥ 80%.

  python -m src.eval.calibrate_judge --n 60 [--offset 0]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from src.eval.judge import CRITERIA, gold_text, judge
from src.llm import USAGE

SCORES = Path("data/raw/legacy/client-baseline-scores.jsonl")


def weighted_kappa(a: list[int], b: list[int], k: int = 3) -> float:
    """Quadratic-weighted Cohen's κ for ordinal 0..k-1 scores."""
    n = len(a)
    if n == 0:
        return float("nan")
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x][y] += 1
    ra, rb = Counter(a), Counter(b)
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / (k - 1) ** 2
            num += w * obs[i][j]
            den += w * ra[i] * rb[j] / n
    return 1 - num / den if den else 1.0      # all identical & agreeing → perfect


def answer_md(ans: dict) -> str:
    return "\n\n".join(x for x in (ans.get("summary"), ans.get("issues"), ans.get("irac")) if x)


def _order(r: dict) -> str:
    return hashlib.md5((r["item_id"] + r["model_code"]).encode()).hexdigest()


def select(rows: list[dict], tune: set[str], n: int, offset: int) -> list[dict]:
    per_model = n // 3
    out = []
    for model in sorted({r["model_code"] for r in rows}):
        rs = [r for r in rows if r["model_code"] == model and r["qid"] in tune]
        good = sorted((r for r in rs if r["lawyer_pass"]), key=_order)
        bad = sorted((r for r in rs if not r["lawyer_pass"]), key=_order)
        mixed = [x for pair in zip(good, bad) for x in pair] + good[len(bad):] + bad[len(good):]
        out += mixed[offset:offset + per_model]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--offset", type=int, default=0, help="use unseen rows for a re-check")
    ap.add_argument("--reference", choices=["reviewed", "draft"], default="reviewed",
                    help="reviewed = G + review H (our gold); draft = G only (what the lawyers may have used)")
    a = ap.parse_args()

    split = json.loads(Path("config/dev100_split.json").read_text(encoding="utf-8"))
    with open("data/eval/dev100.csv", encoding="utf-8") as f:
        dev = {r["id"]: r for r in csv.DictReader(f)}
    rows = []
    for line in SCORES.open(encoding="utf-8"):
        r = json.loads(line)
        r["qid"] = "dev" + r["item_id"].split("-")[1]
        r["lawyer_pass"] = all(r["scores"][c] == 2 for c in CRITERIA)
        rows.append(r)
    picked = select(rows, set(split["tune"]), a.n, a.offset)

    def run(r):
        d = dev[r["qid"]]
        ref = gold_text(d) if a.reference == "reviewed" else (d.get("draft_answer") or d["gold_answer"])
        s = judge(r["question"], ref, answer_md(r["answers"]))
        return r, s

    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(run, picked))

    lines = [f"# Judge calibration — {datetime.now().astimezone():%Y-%m-%d %H:%M}", "",
             (f"rows: {len(results)} (offset {a.offset}, reference {a.reference}) · models "
              f"{dict(Counter(r['model_code'] for r, _ in results))}"
              f" · lawyer PASS {sum(r['lawyer_pass'] for r, _ in results)}"), "",
             "| criterion | exact agreement | weighted κ | lawyer=2 | judge=2 |", "|---|---|---|---|---|"]
    ks = {}
    for c in CRITERIA:
        la = [r["scores"][c] for r, _ in results]
        ju = [getattr(s, c) for _, s in results]
        ks[c] = weighted_kappa(la, ju)
        agree = sum(x == y for x, y in zip(la, ju)) / len(la)
        lines.append(f"| {c} | {agree:.0%} | {ks[c]:.2f} | {la.count(2)} | {ju.count(2)} |")
    pa = sum(r["lawyer_pass"] == s.passed for r, s in results) / len(results)
    tp = sum(r["lawyer_pass"] and s.passed for r, s in results)
    fp = sum((not r["lawyer_pass"]) and s.passed for r, s in results)
    fn = sum(r["lawyer_pass"] and not s.passed for r, s in results)
    ok = all(k >= 0.6 for k in ks.values()) and pa >= 0.8
    lines += ["", (f"- **PASS agreement: {pa:.0%}** · judge PASS when lawyer FAIL (too lenient): {fp} · "
                   f"judge FAIL when lawyer PASS (too strict): {fn} · both PASS: {tp}"),
              f"- acceptance (κ ≥ 0.6 every criterion and PASS agreement ≥ 80%): **{'MET' if ok else 'NOT MET'}**",
              f"- cost: {USAGE.calls} calls, in {USAGE.input_tokens} / out {USAGE.output_tokens} tokens"]
    out = Path("docs/results") / f"{datetime.now().astimezone():%Y-%m-%d}_judge_calibration_o{a.offset}_{a.reference}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path(str(out).replace(".md", ".json")).write_text(json.dumps(
        [{"item": r["item_id"], "model": r["model_code"], "lawyer": r["scores"],
          "judge": {c: getattr(s, c) for c in CRITERIA}, "reasons": s.reasons} for r, s in results],
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
