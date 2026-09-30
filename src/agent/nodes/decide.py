"""⑤ select_citations · ⑥ check_elements · ⑦ calculate"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from src.agent.nodes.common import fmt_facts, fmt_provision, prompt, taxonomy, traced
from src.agent.state import AgentState, ElementCheck
from src.calc import labor
from src.llm import generate_json

SELECT_THRESHOLD = 0.5
MAX_SELECTED = 8


class _Pick(BaseModel):
    citation_key: str
    p: float
    reason: str


class _Picks(BaseModel):
    picks: list[_Pick]


@traced("select_citations")
def select_citations(state: AgentState) -> dict:
    """Batch judgement per issue (Gemini). Only candidate keys can be selected — the model
    cannot introduce a citation that retrieval did not return."""
    _, body = prompt("select_citations")

    def one(code: str) -> tuple[str, list[str], dict]:
        cands = state.candidates.get(code, [])
        if not cands:
            return code, [], {}
        listing = "\n".join(fmt_provision(r, 700) for r in cands)
        out = generate_json(body.format(issue_name=taxonomy()[code]["name"],
                                        facts=fmt_facts(state), candidates=listing),
                            _Picks, name="select_citations")
        allowed = {r["citation_key"] for r in cands}
        ps = {p.citation_key: p.p for p in out.picks if p.citation_key in allowed}
        chosen = sorted((k for k, p in ps.items() if p >= SELECT_THRESHOLD), key=lambda k: -ps[k])
        if not chosen and ps:                      # never leave an issue without law
            chosen = [max(ps, key=ps.get)]
        return code, chosen[:MAX_SELECTED], ps

    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, [i.code for i in state.issues]))
    return {"selected": {c: keys for c, keys, _ in res},
            "_summary": {c: {"selected": keys, "p": {k: round(v, 2) for k, v in ps.items()}}
                         for c, keys, ps in res}}


class _Checks(BaseModel):
    checks: list[ElementCheck]


@traced("check_elements")
def check_elements(state: AgentState) -> dict:
    _, body = prompt("check_elements")

    def one(code: str) -> tuple[str, list[ElementCheck]]:
        els = taxonomy()[code].get("elements") or []
        if not els:
            return code, []
        by_key = {r["citation_key"]: r for r in state.candidates.get(code, [])}
        provs = [fmt_provision(by_key[k], 900) for k in state.selected.get(code, []) if k in by_key]
        listing = "\n".join(f"{e['id']}: {e['question']}" for e in els)
        out = generate_json(body.format(issue_name=taxonomy()[code]["name"], facts=fmt_facts(state),
                                        provisions="\n".join(provs), elements=listing),
                            _Checks, name="check_elements")
        ids = {e["id"] for e in els}
        return code, [c for c in out.checks if c.id in ids]

    with ThreadPoolExecutor(4) as ex:
        res = dict(ex.map(one, [i.code for i in state.issues]))
    return {"elements": res,
            "_summary": {c: {s: sum(x.status == s for x in v) for s in ("met", "not_met", "unknown")}
                         for c, v in res.items()}}


@traced("calculate")
def calculate(state: AgentState) -> dict:
    """Deterministic arithmetic. Runs only when the issue has a formula, the needed facts
    are known, and the rate book has an entry in force; otherwise records why not."""
    f = state.facts
    rates_path = Path("data/processed/rates.yaml")
    book = labor.RateBook.load(rates_path) if rates_path.exists() else labor.RateBook(rates=[])
    on = state.event_date or __import__("datetime").date.today()
    out, notes = {}, {}
    for iss in state.issues:
        fk = taxonomy()[iss.code].get("formula_key")
        if not fk:
            continue
        try:
            if f is None or f.wage_amount is None or f.wage_period in (None, "piece"):
                raise ValueError("ค่าจ้างไม่ทราบ")
            daily = labor.to_daily_wage(Decimal(str(f.wage_amount)), f.wage_period, on, book)
            if fk == "severance":
                if f.tenure_days is None:
                    raise ValueError("อายุงานไม่ทราบ")
                r = labor.severance(daily.amount, f.tenure_days, on, book)
                out[iss.code] = labor.CalcResult(amount=r.amount, steps=daily.steps + r.steps,
                                                 citations=daily.citations + r.citations)
            else:
                raise ValueError(f"ยังไม่รองรับสูตร {fk} อัตโนมัติ")
        except (ValueError, LookupError) as e:
            notes[iss.code] = str(e)
    return {"calcs": out, "_summary": {"done": list(out), "skipped": notes}}
