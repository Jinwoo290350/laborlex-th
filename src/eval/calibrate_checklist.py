"""Calibrate the checklist judge (src/eval/checklist_judge.py) against the lawyers' scores.

Data: data/raw/legacy/client-baseline-scores.jsonl — 300 rows = 3 baseline models (ch = ChatGPT,
cl = Claude, g = Gemini) × 100 dev questions; each row holds the model's answer (summary / issues / irac)
and one lawyer's 0/1/2 scores A1..B3.

Split by question (config/dev100_split.json): "tune" questions (and any unlisted) = calibration rows,
"holdout" questions = held-out rows. Mapping rules are fitted by grid search on calibration rows only;
held-out rows are only reported.

  python -m src.eval.calibrate_checklist --dry-run                 # count LLM calls, estimate USD, no calls
  python -m src.eval.calibrate_checklist --max-usd 5 [--limit N]   # run (paid calls stop before the cap)
  python -m src.eval.calibrate_checklist --from-json docs/results/<…>.json   # re-fit offline, no LLM
  … --write-config config/judge_checklist.yaml                     # save the fitted rules

Acceptance (CLAUDE.md §7 / M1): weighted κ ≥ 0.6 on A2 and B1, PASS agreement ≥ 80% — on held-out rows.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import itertools
import json
import math
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from src.config import settings
from src.eval import checklist_judge as cj
from src.eval.calibrate_judge import SCORES, answer_md, weighted_kappa
from src.eval.judge import CRITERIA
from src.llm import USAGE, CacheMiss, cache_path

SPLIT = Path("config/dev100_split.json")
DEV = Path("data/eval/dev100.csv")

# token estimates for the dry run / budget (Gemini, Thai-heavy prompts):
# the 2026-10-01 judge calibration billed 127,760 input tokens for 338,849 prompt chars = 2.65 chars/token
CHARS_PER_TOKEN = 2.5
BUILD_OUT_TOKENS = 800                 # 4 short lists + low thinking
VERIFY_OUT_BASE, VERIFY_OUT_PER_ITEM = 400, 25
EST_ITEMS = 12                         # items per checklist when the checklist is not built yet
EST_ITEMS_CHARS = 1000                 # chars of the item listing when not built yet


# --- cost --------------------------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * settings.gemini_price_in + tokens_out * settings.gemini_price_out) / 1e6


def spent_usd() -> float:
    """USD of fresh (non-cached) calls made by this process."""
    fresh = [c for c in USAGE.log if not c["cached"]]
    return cost_usd(sum(c["in"] for c in fresh), sum(c["out"] for c in fresh))


@dataclass
class Budget:
    max_usd: float | None
    spent: Callable[[], float] = spent_usd

    def allows(self, estimate: float) -> bool:
        return self.max_usd is None or self.spent() + estimate <= self.max_usd + 1e-12


@dataclass
class Call:
    kind: str           # build | verify
    cached: bool
    tokens_in: int
    tokens_out: int

    @property
    def usd(self) -> float:
        return 0.0 if self.cached else cost_usd(self.tokens_in, self.tokens_out)


def plan_build(d: dict) -> Call | None:
    """None = checklist already in the file cache (no call at all)."""
    if cj.cached_checklist(d) is not None:
        return None
    _, p = cj.build_prompt(d)
    hit = cache_path(p, cj.Checklist, thinking=cj.THINKING).exists()
    return Call("build", hit, estimate_tokens(p), BUILD_OUT_TOKENS)


def plan_verify(d: dict, answer: str) -> Call:
    cl = cj.cached_checklist(d)
    if cl is None:
        _, body = cj.prompt("judge_checklist_verify")
        p = body.format(question=d["question"], items="x" * EST_ITEMS_CHARS, answer=answer)
        return Call("verify", False, estimate_tokens(p), VERIFY_OUT_BASE + VERIFY_OUT_PER_ITEM * EST_ITEMS)
    p = cj.verify_prompt(d["question"], answer, cl)
    hit = cache_path(p, cj.Verification, thinking=cj.THINKING).exists()
    return Call("verify", hit, estimate_tokens(p), VERIFY_OUT_BASE + VERIFY_OUT_PER_ITEM * len(cj.items(cl)))


# --- data and split ----------------------------------------------------------------------------------

def load_rows() -> list[dict]:
    rows = []
    for line in SCORES.open(encoding="utf-8"):
        r = json.loads(line)
        r["qid"] = "dev" + r["item_id"].split("-")[1]
        rows.append(r)
    # deterministic mixed order so --limit N takes all models and many questions
    return sorted(rows, key=lambda r: hashlib.md5((r["qid"] + r["model_code"]).encode()).hexdigest())


def split_rows(rows: list[dict], split: dict | None, holdout_frac: float = 0.4) -> tuple[list[dict], list[dict]]:
    """(calibration, held-out) by question: the 3 answers to one question stay on one side."""
    if split is not None:
        hold = set(split["holdout"])
    else:
        qids = sorted({r["qid"] for r in rows}, key=lambda q: hashlib.md5(q.encode()).hexdigest())
        hold = set(qids[:round(holdout_frac * len(qids))])
    return [r for r in rows if r["qid"] not in hold], [r for r in rows if r["qid"] in hold]


# --- agreement ---------------------------------------------------------------------------------------

def confusion(lawyer: list[int], judge: list[int]) -> list[list[int]]:
    m = [[0] * 3 for _ in range(3)]
    for a, b in zip(lawyer, judge):
        m[a][b] += 1
    return m


def agreement(lawyer: list[dict], judged: list[dict]) -> dict:
    n = len(lawyer)
    out: dict = {"n": n}
    for c in CRITERIA:
        la, ju = [x[c] for x in lawyer], [x[c] for x in judged]
        out[c] = {"exact": sum(a == b for a, b in zip(la, ju)) / n if n else float("nan"),
                  "kappa": weighted_kappa(la, ju), "confusion": confusion(la, ju),
                  "lawyer2": la.count(2), "judge2": ju.count(2)}
    lp = [all(x[c] == 2 for c in CRITERIA) for x in lawyer]
    jp = [all(x[c] == 2 for c in CRITERIA) for x in judged]
    out["pass_agreement"] = sum(a == b for a, b in zip(lp, jp)) / n if n else float("nan")
    out["lenient"] = sum(b and not a for a, b in zip(lp, jp))      # judge PASS, lawyer FAIL
    out["strict"] = sum(a and not b for a, b in zip(lp, jp))       # judge FAIL, lawyer PASS
    out["lawyer_pass"], out["judge_pass"] = sum(lp), sum(jp)
    return out


# --- fitting -----------------------------------------------------------------------------------------

HI = [0.34, 0.5, 0.6, 0.67, 0.75, 0.8, 0.9, 1.0]
LO = [0.0, 0.01, 0.2, 0.34, 0.5]
CONTRA = [0, 1, 99]
GRID: dict[str, dict[str, list]] = {
    "A1": {},
    "A2": {"max_contradicted": CONTRA},
    "B0": {"max_extra": [0, 1, 2, 3, 5, 99]},
    "B1": {"max_contradicted": CONTRA, "section_weight": [0.0, 0.25, 0.5, 0.75, 1.0],
           "section_match": ["law", "number"], "nonexistent_cap": [0, 1, 2]},
    "B2": {"max_contradicted": CONTRA, "no_application": [0, 1]},
    "B3": {"max_contradicted": CONTRA},
}


def fit(facts: list[cj.RowFacts], lawyer: list[dict], rules: dict) -> dict:
    """Grid search per criterion (each criterion's score depends only on its own rule):
    maximise weighted κ, then exact agreement. Pass calibration rows only."""
    best_rules = copy.deepcopy(rules)
    for c in CRITERIA:
        la = [x[c] for x in lawyer]
        extra = GRID[c]
        best: tuple | None = None
        for hi, lo in itertools.product(HI, LO):
            if lo > hi:
                continue
            for combo in itertools.product(*extra.values()):
                rule = {**rules["criteria"][c], "hi": hi, "lo": lo, **dict(zip(extra, combo))}
                trial = {"criteria": {**best_rules["criteria"], c: rule}}
                ju = [cj.score(f, trial)[c] for f in facts]
                k = weighted_kappa(la, ju)
                key = (-1.0 if math.isnan(k) else k, sum(a == b for a, b in zip(la, ju)))
                if best is None or key > best[0]:
                    best = (key, rule)
        assert best is not None
        best_rules["criteria"][c] = best[1]
    return best_rules


def judged_scores(facts: list[cj.RowFacts], rules: dict) -> list[dict]:
    return [cj.score(f, rules) for f in facts]


# --- report ------------------------------------------------------------------------------------------

def table(name: str, rep: dict) -> list[str]:
    lines = [f"### {name} — {rep['n']} rows", "",
             "| criterion | exact | weighted κ | lawyer=2 | judge=2 | confusion (rows lawyer 0/1/2 × cols judge 0/1/2) |",
             "|---|---|---|---|---|---|"]
    for c in CRITERIA:
        x = rep[c]
        lines.append(f"| {c} | {x['exact']:.0%} | {x['kappa']:.2f} | {x['lawyer2']} | {x['judge2']} | "
                     f"{x['confusion']} |")
    lines += ["", (f"- **PASS agreement {rep['pass_agreement']:.0%}** · lawyer PASS {rep['lawyer_pass']} · "
                   f"judge PASS {rep['judge_pass']} · too lenient {rep['lenient']} · too strict {rep['strict']}"), ""]
    return lines


def accepted(rep: dict) -> bool:
    return rep["A2"]["kappa"] >= 0.6 and rep["B1"]["kappa"] >= 0.6 and rep["pass_agreement"] >= 0.8


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="count LLM calls and estimate cost; no calls")
    ap.add_argument("--limit", type=int, help="first N rows (deterministic mixed order)")
    ap.add_argument("--max-usd", type=float, help="stop before fresh calls would exceed this many USD")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rules", default=str(cj.RULES_PATH))
    ap.add_argument("--no-fit", action="store_true", help="report the rules as they are")
    ap.add_argument("--from-json", help="re-use the row facts of an earlier run (no LLM)")
    ap.add_argument("--write-config", help="write the fitted rules to this YAML path")
    ap.add_argument("--out", help="report path (default docs/results/<date>_judge_checklist_calibration[_refit].md)")
    a = ap.parse_args()

    with DEV.open(encoding="utf-8") as f:
        dev = {r["id"]: r for r in csv.DictReader(f)}
    split = json.loads(SPLIT.read_text(encoding="utf-8")) if SPLIT.exists() else None
    rules = cj.load_rules(a.rules)

    if a.from_json:
        rows = json.loads(Path(a.from_json).read_text(encoding="utf-8"))["rows"]
        for r in rows:
            r["facts"] = cj.RowFacts.from_dict(r["facts"])
    else:
        rows = load_rows()[:a.limit] if a.limit else load_rows()
        qids = sorted({r["qid"] for r in rows})
        builds = [c for q in qids if (c := plan_build(dev[q])) is not None]
        verifies = [plan_verify(dev[r["qid"]], answer_md(r["answers"])) for r in rows]
        for kind, calls, n in (("build checklists", builds, len(qids)), ("verify rows", verifies, len(rows))):
            fresh = [c for c in calls if not c.cached]
            print(f"{kind}: {n} needed · {n - len(calls)} already built · {len(calls) - len(fresh)} in LLM cache · "
                  f"{len(fresh)} paid calls · est. in {sum(c.tokens_in for c in fresh):,} / "
                  f"out {sum(c.tokens_out for c in fresh):,} tokens · est. ${sum(c.usd for c in fresh):.2f}")
        total = sum(c.usd for c in builds + verifies)
        print(f"total estimate: ${total:.2f} (prices in/out ${settings.gemini_price_in}/${settings.gemini_price_out} "
              f"per 1M; {CHARS_PER_TOKEN} chars/token; output incl. thinking is a guess — cap with --max-usd)")
        if a.dry_run:
            return
        rows = collect_rows(rows, dev, Budget(a.max_usd), a.workers)

    done = [r for r in rows if r.get("facts") is not None]
    print(f"judged {len(done)}/{len(rows)} rows · LLM calls {USAGE.calls} (cached {USAGE.cached}) · "
          f"spent ${spent_usd():.2f}")
    if not done:
        print("nothing to score (cache-only mode or budget exhausted)")
        return
    calib, hold = split_rows(done, split)
    def lawyer(rs: list[dict]) -> list[dict]:
        return [r["scores"] for r in rs]

    def facts(rs: list[dict]) -> list[cj.RowFacts]:
        return [r["facts"] for r in rs]

    fitted = rules if a.no_fit or not calib else fit(facts(calib), lawyer(calib), rules)

    stamp = datetime.now().astimezone()
    lines = [f"# Checklist judge calibration — {stamp:%Y-%m-%d %H:%M}", "",
             (f"rows judged {len(done)}/{len(rows)} · calibration {len(calib)} · held-out {len(hold)} · "
              f"models {dict(Counter(r['model_code'] for r in done))}"
              + (f" · re-fit from {a.from_json}" if a.from_json else "")), "",
             "Fitted on calibration rows only; acceptance is read on held-out rows.", ""]
    for name, rs, rl in (("held-out, fitted rules", hold, fitted), ("held-out, config rules", hold, rules),
                         ("calibration, fitted rules (in-sample)", calib, fitted)):
        if rs:
            lines += table(name, agreement(lawyer(rs), judged_scores(facts(rs), rl)))
    if hold:
        rep = agreement(lawyer(hold), judged_scores(facts(hold), fitted))
        lines.append(f"- acceptance on held-out (κ A2 ≥ 0.6, κ B1 ≥ 0.6, PASS agreement ≥ 80%): "
                     f"**{'MET' if accepted(rep) else 'NOT MET'}**")
    lines += ["", "## Fitted rules", "", "```yaml", yaml.safe_dump(fitted["criteria"], allow_unicode=True,
                                                                     sort_keys=False).strip(), "```",
              "", f"- LLM calls {USAGE.calls} (cached {USAGE.cached}) · spent ${spent_usd():.2f}"]
    out = Path(a.out or f"docs/results/{stamp:%Y-%m-%d}_judge_checklist_calibration"
               f"{'_refit' if a.from_json else ''}.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not a.from_json:          # row facts: lets --from-json re-fit the rules without the LLM
        out.with_suffix(".json").write_text(json.dumps({"rows": [
            {k: r[k] for k in ("item_id", "qid", "model_code", "scores", "reasons")}
            | {"facts": r["facts"].to_dict()} for r in done]}, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.write_config:
        Path(a.write_config).write_text(yaml.safe_dump(
            {"version": rules.get("version", 1) + 1, "criteria": fitted["criteria"]},
            allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("\n".join(lines))


def collect_rows(rows: list[dict], dev: dict, budget: Budget, workers: int) -> list[dict]:
    """Build checklists then verify rows, batch by batch, never starting a batch the budget cannot cover."""
    def build(q: str) -> None:
        try:
            cj.build_checklist(dev[q])
        except CacheMiss:
            pass

    def one(r: dict) -> dict:
        d, ans = dev[r["qid"]], answer_md(r["answers"])
        cl = cj.cached_checklist(d)          # never build here: building was budgeted above
        if cl is None:
            return {**r, "facts": None, "reasons": "no checklist (cache-only or budget)"}
        try:
            v = cj.verify(d["question"], ans, cl)
        except CacheMiss:
            return {**r, "facts": None, "reasons": "not in LLM cache"}
        return {**r, "facts": cj.collect(d, cl, v, ans), "reasons": cj.explain(d, cl, v, ans)}

    out: list[dict] = []
    qids = sorted({r["qid"] for r in rows})
    with ThreadPoolExecutor(workers) as ex:
        for i in range(0, len(qids), workers):
            batch = qids[i:i + workers]
            est = sum(c.usd for q in batch if (c := plan_build(dev[q])) is not None)
            if not budget.allows(est):
                print(f"budget: stop before building {len(qids) - i} checklists (spent ${budget.spent():.2f})")
                break
            list(ex.map(build, batch))
        for i in range(0, len(rows), workers):
            batch = rows[i:i + workers]
            est = sum(plan_verify(dev[r["qid"]], answer_md(r["answers"])).usd for r in batch)
            if not budget.allows(est):
                print(f"budget: stop before verifying {len(rows) - i} rows (spent ${budget.spent():.2f})")
                out += [{**r, "facts": None, "reasons": "budget"} for r in rows[i:]]
                break
            out += list(ex.map(one, batch))
    return out


if __name__ == "__main__":
    main()
