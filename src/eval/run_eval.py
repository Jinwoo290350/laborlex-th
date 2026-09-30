"""Run the agent over an eval set, judge, and write docs/results/<date>_<config>.md.

  python -m src.eval.run_eval --set dev100 --leave-one-out [--limit N | --subset30 | --ids a,b]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from src.config import settings
from src.eval.judge import CRITERIA, judge
from src.llm import USAGE


def usage_cost(include_cached: bool = False) -> float:
    """USD for Gemini calls in this process: fresh calls only (= spent now), or including
    cache hits (= what the questions cost end to end)."""
    calls = [c for c in USAGE.log if include_cached or not c["cached"]]
    return (sum(c["in"] for c in calls) * settings.gemini_price_in
            + sum(c["out"] for c in calls) * settings.gemini_price_out) / 1e6

SETS = {"dev100": "data/eval/dev100.csv", "bar_labor": "data/eval/bar_labor.csv"}
RUNS = Path("data/processed/runs")


def config() -> dict:
    from src.agent.graph import STEPS
    from src.agent.nodes import decide, draft
    from src.agent.nodes.common import prompt
    prompts = sorted(p.stem for p in Path("prompts").glob("*.md") if p.stem != "answer_template")
    return {"model": settings.gemini_model, "decider": settings.decider,
            "steps": [n for n, _ in STEPS], "n_drafts": draft.N_DRAFTS,
            "n_examples": draft.N_EXAMPLES, "select_threshold": decide.SELECT_THRESHOLD,
            "prompts": {p: prompt(p)[0] for p in prompts}}


def subset30(rows: list[dict]) -> list[dict]:
    """Stratified by difficulty, deterministic (CLAUDE.md §8.11)."""
    by = {}
    for r in rows:
        by.setdefault(r["difficulty"], []).append(r)
    out = []
    for _, group in sorted(by.items()):
        n = round(30 * len(group) / len(rows))
        out += sorted(group, key=lambda r: hashlib.md5(r["id"].encode()).hexdigest())[:n]
    return out[:30]


def run_one(row: dict, loo: bool, out_dir: Path) -> dict:
    from src.agent.graph import answer
    t0 = time.monotonic()
    try:
        s = answer(row["question"], question_id=row["id"],
                   exclude_example_ids=[row["id"]] if loo else [])
        md, err = s.markdown, None
        trace, removed = s.trace, s.removed_citations
        unknown = next((t["summary"].get("uncited_sections_in_text", []) for t in s.trace
                        if t["node"] == "validate_cites" and isinstance(t.get("summary"), dict)), [])
        answer_json = s.answer.model_dump() if s.answer else None
    except Exception as e:  # noqa: BLE001 — record and continue the batch
        md, err, trace, removed, unknown, answer_json = "", repr(e), [], [], [], None
    latency = time.monotonic() - t0
    cited = {":".join(k.split(":")[:2]) for k in (answer_json and _all_keys(answer_json)) or []}
    gold = {g for g in row.get("gold_citations", "").split(";") if g}
    score = judge(row["question"], row["gold_answer"], md) if md else None
    rec = {"id": row["id"], "difficulty": row.get("difficulty"), "category": row.get("category"),
           "latency_s": round(latency, 1), "error": err, "removed_citations": removed,
           "unknown_sections": unknown, "score": score.model_dump() if score else None,
           "pass": bool(score and score.passed),
           "gold_sections": sorted(gold), "cited_sections": sorted(cited),
           "gold_hit": len(gold & cited), "extra_cited": len(cited - gold),
           "tokens": {"in": sum(t.get("in_tokens", 0) for t in trace),
                      "out": sum(t.get("out_tokens", 0) for t in trace)}}
    (out_dir / f"{row['id']}.json").write_text(json.dumps(
        {**rec, "question": row["question"], "gold": row["gold_answer"], "markdown": md,
         "answer": answer_json, "trace": trace}, ensure_ascii=False, indent=1, default=str),
        encoding="utf-8")
    return rec


CAVEAT = ("> ⚠️ ข้อจำกัดของตัวเลขนี้: taxonomy และองค์ประกอบร่างจากเฉลย dev100 ทั้งชุด "
          "(leave-one-out ตัดเฉพาะ few-shot และมาตราหลัก) → PASS บน dev100 น่าจะสูงกว่า test160 · "
          "judge เป็น Gemini ที่ยังไม่ได้ calibrate กับคะแนนอาจารย์ → ใช้ดูแนวโน้ม")


def _all_keys(answer_json: dict) -> set[str]:
    from src.agent.answer import AnswerJSON
    return AnswerJSON.model_validate(answer_json).all_citations()


def report(recs: list[dict], cfg: dict, name: str, out: Path) -> str:
    scored = [r for r in recs if r["score"]]
    n = len(recs)
    lines = [f"# Eval {name} — {datetime.now().astimezone():%Y-%m-%d %H:%M}", "",
             "```json", json.dumps(cfg, ensure_ascii=False, indent=1), "```", "",
             f"- questions: {n} · errors: {sum(1 for r in recs if r['error'])}",
             f"- **PASS: {sum(r['pass'] for r in recs)}/{n} = {sum(r['pass'] for r in recs) / n:.1%}**"]
    if scored:
        lines.append("- % ได้ 2 ต่อเกณฑ์: " + " · ".join(
            f"{c} {sum(r['score'][c] == 2 for r in scored) / len(scored):.0%}" for c in CRITERIA))
    g_tot = sum(len(r["gold_sections"]) for r in recs)
    g_hit = sum(r["gold_hit"] for r in recs)
    c_tot = sum(len(r["cited_sections"]) for r in recs)
    lines.append(f"- **มาตราในเฉลยที่คำตอบอ้างถึง (ไม่ใช้ judge): {g_hit}/{g_tot} = "
                 f"{g_hit / g_tot:.0%}** · มาตราที่อ้างนอกเฉลย {c_tot - g_hit}/{c_tot}" if g_tot else "")
    lat = sorted(r["latency_s"] for r in recs)
    lines += [f"- latency p50 {statistics.median(lat):.0f}s · p95 {lat[int(0.95 * (n - 1))]:.0f}s",
              (f"- tokens in/out per question: {sum(r['tokens']['in'] for r in recs) / n:.0f} / "
               f"{sum(r['tokens']['out'] for r in recs) / n:.0f}"),
              (f"- **cost per question (agent + judge, full price): ${usage_cost(True) / n:.3f}** · "
               f"spent in this run (cache hits free): ${usage_cost():.2f}"),
              (f"- citations removed by validator: {sum(len(r['removed_citations']) for r in recs)}"
               f" · section numbers in prose without a kept citation: {sum(len(r['unknown_sections']) for r in recs)}"),
              "", CAVEAT,
              "", "## By difficulty", ""]
    by = Counter(r["difficulty"] for r in recs)
    for d, k in sorted(by.items()):
        p = sum(r["pass"] for r in recs if r["difficulty"] == d)
        lines.append(f"- {d}: {p}/{k}")
    fails = [r for r in scored if not r["pass"]][:5]
    lines += ["", "## ตัวอย่างข้อที่ไม่ผ่าน", ""]
    for r in fails:
        low = {c: r["score"][c] for c in CRITERIA if r["score"][c] < 2}
        lines.append(f"- **{r['id']}** {low} — {r['score']['reasons'][:300]}")
    lines += ["", f"raw: `{out}`"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev100", choices=SETS)
    ap.add_argument("--leave-one-out", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--subset30", action="store_true")
    ap.add_argument("--ids")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.set == "test160":  # guarded: phase 2 only via export_for_grading
        raise SystemExit("test160 is not allowed here")

    with open(SETS[a.set], encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if a.ids:
        keep = set(a.ids.split(","))
        rows = [r for r in rows if r["id"] in keep]
    if a.subset30:
        rows = subset30(rows)
    if a.limit:
        rows = rows[:a.limit]

    cfg = config()
    h = hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:8]
    stamp = f"{datetime.now().astimezone():%Y-%m-%d_%H%M}"
    out_dir = RUNS / f"{stamp}_{a.set}_{h}"
    out_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(a.workers) as ex:
        recs = list(ex.map(lambda r: run_one(r, a.leave_one_out, out_dir), rows))
    md = report(recs, cfg, f"{a.set} ({len(rows)}q, {'LOO' if a.leave_one_out else 'no-LOO'})",
                out_dir)
    dest = Path("docs/results") / f"{stamp[:10]}_{a.set}_{h}.md"
    dest.write_text(md, encoding="utf-8")
    print(md)
    print(f"gemini calls={USAGE.calls} cached={USAGE.cached}")


if __name__ == "__main__":
    main()
