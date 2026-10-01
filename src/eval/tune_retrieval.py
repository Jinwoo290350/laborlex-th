"""Tune retrieval parameters on the dev100 TUNE split without any LLM call.

Oracle issues = dev100 issue tags; taxonomy sections use leave-one-out.
Stage 1 (search ranking) metric = recall of the question's gold sections among the union of
its per-issue candidates (section level): among settings within 1 point of the best, take
the cheapest compute (smaller pools), then the literature default for rrf_k.
Stage 2 (quotas) metric = the client's criterion: share of questions whose candidates
contain ALL their gold sections (column H). Among settings within one question of the best,
take the fewest candidates (prompt cost), then smaller primary_max.

  python -m src.eval.tune_retrieval            → docs/results/<date>_tune_retrieval.json
"""

from __future__ import annotations

import csv
import itertools
import json
from datetime import datetime
from pathlib import Path

from src.agent.nodes.common import taxonomy
from src.agent.nodes.retrieve import primary_sections
from src.index import tools
from src.index.bm25 import default_index

TOL = 0.01
BIG_POOL = 200
GRID_SEARCH = {"rrf_k": [10, 30, 60, 100], "pool": [50, 100, 200], "rerank_pool": [0, 30, 50, 100]}
GRID_QUOTA = {"search_rows": [6, 9, 12, 18, 24], "tax_rows": [0, 6, 12, 18],
              "max_paras": [2, 4, 6], "child_rows": [0, 6], "primary_max": [3, 6, 9],
              "min_support": [1, 2]}


def sec(r: dict) -> str:
    return f"{r['law']}:{r['section_no']}"


def main() -> None:
    split = json.loads(Path("config/dev100_split.json").read_text(encoding="utf-8"))
    tags = json.loads(Path("data/processed/dev100_issues.json").read_text(encoding="utf-8"))
    with open("data/eval/dev100.csv", encoding="utf-8") as f:
        dev = {r["id"]: r for r in csv.DictReader(f)}
    qs = [dev[i] for i in split["tune"] if dev[i]["gold_citations"]]
    idx = default_index()
    rows_by_id = {r["id"]: r for r in idx.rows}

    # ---- per (question, issue) query: raw rankings + rerank scores, computed once
    cache: dict[tuple[str, str], dict] = {}
    for n, q in enumerate(qs, 1):
        print(f"  query cache {n}/{len(qs)}", flush=True)
        for code in tags.get(q["id"], []):
            query = f"{taxonomy()[code]['name']}\n{q['question']}"
            bm = idx.search(query, BIG_POOL)
            dn = tools.dense_search(query, BIG_POOL)
            union = list(dict.fromkeys([i for i, _ in bm] + [i for i, _ in dn]))
            rows = [rows_by_id[i] for i in union if i in rows_by_id]
            scores = {r["id"]: r["score"] for r in tools.rerank(query, rows)} if rows else {}
            cache[(q["id"], code)] = {"bm": bm, "dn": dn, "rr": scores}
    print(f"{len(qs)} tune questions · {len(cache)} (question, issue) queries cached")

    def ranked(key, rrf_k, pool, rerank_pool) -> list[int]:
        c = cache[key]
        fused = [i for i, _ in tools.rrf(c["bm"][:pool], c["dn"][:pool], k=rrf_k) if i in rows_by_id]
        if rerank_pool:
            head = sorted(fused[:rerank_pool], key=lambda i: -c["rr"].get(i, -1e9))
            fused = head + fused[rerank_pool:]
        return fused

    def full(cands_by_q: dict[str, set[str]]) -> float:
        ok = sum({g for g in q["gold_citations"].split(";") if g} <= cands_by_q.get(q["id"], set())
                 for q in qs)
        return ok / len(qs)

    def recall(cands_by_q: dict[str, set[str]]) -> float:
        hit = tot = 0
        for q in qs:
            gold = {g for g in q["gold_citations"].split(";") if g}
            hit += len(gold & cands_by_q.get(q["id"], set()))
            tot += len(gold)
        return hit / tot

    # ---- stage 1: search ranking (fixed search_rows=12, no taxonomy) ------------------
    stage1 = []
    for rrf_k, pool, rr in itertools.product(*GRID_SEARCH.values()):
        by_q: dict[str, set[str]] = {}
        for (qid, code) in cache:
            ids = ranked((qid, code), rrf_k, pool, rr)[:12]
            by_q.setdefault(qid, set()).update(sec(rows_by_id[i]) for i in ids)
        stage1.append({"rrf_k": rrf_k, "pool": pool, "rerank_pool": rr, "recall": round(recall(by_q), 4)})
    best1 = max(s["recall"] for s in stage1)
    ok1 = [s for s in stage1 if s["recall"] >= best1 - TOL]
    pick1 = min(ok1, key=lambda s: (s["pool"], s["rerank_pool"], abs(s["rrf_k"] - 60)))
    print("stage 1 best", best1, "→ pick", pick1)

    # ---- stage 2: quotas, using the picked ranking ----------------------------------
    section_cache: dict[tuple[str, str], list[dict]] = {}

    def section_rows(key: str) -> list[dict]:
        if key not in section_cache:
            law, s = key.split(":", 1)
            section_cache[key] = tools.get_section(law, s)
        return section_cache[key]

    child_cache: dict[int, list[dict]] = {}

    def children(pid: int) -> list[dict]:
        if pid not in child_cache:
            child_cache[pid] = tools.expand(pid).get("children", [])
        return child_cache[pid]

    from src.params import P
    long_section = P("retrieve.long_section")
    stage2 = []
    for sr, tr, mp, cr, pm, ms in itertools.product(*GRID_QUOTA.values()):
        by_q: dict[str, set[str]] = {}
        n_cands = []
        for (qid, code) in cache:
            found: dict[int, dict] = {}
            tax = []
            for key in primary_sections(code, {qid}, ms)[:pm]:
                paras = section_rows(key)
                if len(paras) <= long_section:
                    tax += paras[:mp]
            for r in tax[:tr]:
                found.setdefault(r["id"], r)
            n = 0
            for i in ranked((qid, code), pick1["rrf_k"], pick1["pool"], pick1["rerank_pool"]):
                if n >= sr:
                    break
                if i not in found:
                    found[i] = rows_by_id[i]
                    n += 1
            if cr:
                kids = [k for pid in list(found)[:8] for k in children(pid)]
                for k in kids[:cr]:
                    found.setdefault(k["id"], k)
            by_q.setdefault(qid, set()).update(sec(r) for r in found.values())
            n_cands.append(len(found))
        stage2.append({"search_rows": sr, "tax_rows": tr, "max_paras": mp, "child_rows": cr,
                       "primary_max": pm, "min_support": ms, "full": round(full(by_q), 4),
                       "recall": round(recall(by_q), 4),
                       "mean_candidates": round(sum(n_cands) / len(n_cands), 1)})
    best2 = max(s["full"] for s in stage2)
    ok2 = [s for s in stage2 if s["full"] >= best2 - 1 / len(qs) - 1e-9]
    pick2 = min(ok2, key=lambda s: (s["mean_candidates"], s["primary_max"]))
    print("stage 2 best", best2, "→ pick", pick2)

    out = Path("docs/results") / f"{datetime.now().astimezone():%Y-%m-%d}_tune_retrieval.json"
    out.write_text(json.dumps({"questions": len(qs), "queries": len(cache), "tolerance": TOL,
                               "stage1": {"best": best1, "pick": pick1, "grid": stage1},
                               "stage2": {"best": best2, "pick": pick2, "grid": stage2}},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("→", out)


if __name__ == "__main__":
    main()
