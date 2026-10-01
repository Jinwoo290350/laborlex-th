"""Node-level tuning of ⑤ select_citations' threshold on the dev100 TUNE split.

Cheap by design: issues = dev100 tags (oracle) and facts = the question text, so only ⑤
calls Gemini (one batch call per issue). Retrieval uses the production parameters.
Labels: a candidate is positive if its section is among the question's gold sections.

Rule (config/params.yaml select.threshold): highest precision among thresholds whose
section-level recall of gold sections present among candidates is ≥ 0.95; if none reaches
the floor, maximise recall, then precision, then prefer the higher threshold.

  python -m src.eval.tune_select
"""

from __future__ import annotations

import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from src.agent.nodes.decide import _p_gemini_batch
from src.agent.nodes.retrieve import retrieve_law
from src.agent.state import AgentState, IssueSel
from src.llm import USAGE
from src.params import P

RECALL_FLOOR = 0.95


def section(key: str) -> str:
    return ":".join(key.split(":")[:2])


def main() -> None:
    split = json.loads(Path("config/dev100_split.json").read_text(encoding="utf-8"))
    tags = json.loads(Path("data/processed/dev100_issues.json").read_text(encoding="utf-8"))
    with open("data/eval/dev100.csv", encoding="utf-8") as f:
        dev = {r["id"]: r for r in csv.DictReader(f)}
    qs = [dev[i] for i in split["tune"] if dev[i]["gold_citations"] and tags.get(i)]

    # retrieval first, sequentially (MPS models), then the LLM calls in parallel
    states = []
    for q in qs:
        st = AgentState(question=q["question"], question_id=q["id"], exclude_example_ids=[q["id"]],
                        issues=[IssueSel(code=c, reason="oracle tag") for c in tags[q["id"]]])
        st.candidates = retrieve_law(st)["candidates"]
        states.append((q, st))

    def judge(item):
        q, st = item
        out = []
        for code, cands in st.candidates.items():
            if cands:
                ps = _p_gemini_batch(st, code, cands)
                out += [(q["id"], r["citation_key"], ps.get(r["citation_key"], 0.0)) for r in cands]
        return out

    with ThreadPoolExecutor(6) as ex:
        triples = [t for chunk in ex.map(judge, states) for t in chunk]

    gold = {q["id"]: {g for g in q["gold_citations"].split(";") if g} for q in qs}
    present = {qid: {section(k) for (i, k, _) in triples if i == qid} & gold[qid] for qid in gold}
    n_present = sum(len(v) for v in present.values())

    def at(t: float) -> dict:
        sel = [(i, k) for (i, k, p) in triples if p >= t]
        got = {}
        for i, k in sel:
            got.setdefault(i, set()).add(section(k))
        hit = sum(len(got.get(i, set()) & present[i]) for i in present)
        tp = sum(1 for i, k in sel if section(k) in gold[i])
        return {"t": t, "recall": round(hit / n_present, 4),
                "precision": round(tp / len(sel), 4) if sel else 0.0, "selected": len(sel)}

    curve = [at(t / 20) for t in range(1, 20)]
    ok = [c for c in curve if c["recall"] >= RECALL_FLOOR]
    if ok:
        pick = max(ok, key=lambda c: (c["precision"], c["t"]))
    else:  # floor unreachable: maximise recall, then precision, then the higher threshold
        pick = max(curve, key=lambda c: (c["recall"], c["precision"], c["t"]))
    selected = {(i, section(k)) for (i, k, p) in triples if p >= pick["t"]}
    missed = sorted(f"{i} {g}" for i in present for g in present[i] if (i, g) not in selected)
    # client criterion: a question passes only if ALL its gold sections are covered
    cand_secs = {}
    for i, k, _ in triples:
        cand_secs.setdefault(i, set()).add(section(k))
    full = {"retrieval": [], "selection": []}
    for i, g in gold.items():
        if not g <= cand_secs.get(i, set()):
            full["retrieval"].append(f"{i} missing {sorted(g - cand_secs.get(i, set()))}")
        elif not g <= {s for (j, s) in selected if j == i}:
            full["selection"].append(f"{i} missing {sorted(g - {s for (j, s) in selected if j == i})}")
    n_ok = len(gold) - len(full["retrieval"]) - len(full["selection"])
    coverage = {"questions_all_gold_selected": f"{n_ok}/{len(gold)} = {n_ok / len(gold):.0%}",
                "fail_at_retrieval": full["retrieval"], "fail_at_selection": full["selection"]}
    cost = (sum(c["in"] for c in USAGE.log if not c["cached"]) * 1.5
            + sum(c["out"] for c in USAGE.log if not c["cached"]) * 9) / 1e6
    report = {"questions": len(qs), "pairs": len(triples), "gold_sections_present": n_present,
              "current": at(P("select.threshold")), "pick": pick, "missed_at_pick": missed, "coverage": coverage,
              "curve": curve,
              "calls": USAGE.calls, "cost_usd": round(cost, 3),
              "approximation": "oracle issues (dev tags) and question text as facts"}
    out = Path("docs/results") / f"{datetime.now().astimezone():%Y-%m-%d}_tune_select.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "curve"}, ensure_ascii=False, indent=1))
    for c in curve:
        print(c)


if __name__ == "__main__":
    main()
