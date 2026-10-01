"""⑤ select_citations · ⑥ check_elements · ⑦ calculate"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, create_model

from src.agent.nodes.common import fmt_facts, fmt_provision, prompt, taxonomy, traced
from src.agent.state import AgentState, ElementCheck
from src.calc import labor
from src.config import settings
from src.decision.base import QuestionSpec, get_decider
from src.llm import generate_json
from src.params import P

APPLIES = QuestionSpec(type="noul",
                       instructions="บทบัญญัตินี้เป็นกฎหมายที่ต้องใช้วินิจฉัยประเด็นนี้กับข้อเท็จจริงนี้โดยตรงหรือไม่")


def _p_gemini_batch(state: AgentState, code: str, cands: list[dict]) -> dict[str, float]:
    """One Gemini call judges all candidates of an issue (cheaper than one call each).
    The response schema has one required field per candidate (c1…cN), so every candidate
    gets a probability — a free-form list let the model score only the few it liked."""
    _, body = prompt("select_citations")
    ids = [f"c{i}" for i in range(1, len(cands) + 1)]
    listing = "\n".join(f"[{i}] {fmt_provision(r, P('select.provision_chars'))}"
                         for i, r in zip(ids, cands))
    schema = create_model("Scores", **{i: (float, Field(ge=0, le=1)) for i in ids})
    out = generate_json(body.format(issue_name=taxonomy()[code]["name"],
                                    facts=fmt_facts(state), candidates=listing),
                        schema, name="select_citations", thinking="low")
    return {r["citation_key"]: getattr(out, i) for i, r in zip(ids, cands)}


def _p_decider(state: AgentState, code: str, cands: list[dict]) -> dict[str, float]:
    """System-One decider: one short state (facts + issue + one provision) per candidate."""
    dec = get_decider()
    facts = fmt_facts(state)

    def ask(r: dict) -> tuple[str, float]:
        d = dec.decide({"ข้อเท็จจริง": facts, "ประเด็น": taxonomy()[code]["name"],
                        "บทบัญญัติ": fmt_provision(r, P("select.provision_chars"))},
                       {"applies": APPLIES})
        return r["citation_key"], d["applies"].p

    with ThreadPoolExecutor(4) as ex:
        return dict(ex.map(ask, cands))


def _select_fallback(state: AgentState, e: Exception) -> dict:
    """Decider unavailable: keep the top retrieved candidates rather than no law at all."""
    return {"selected": {c: [r["citation_key"] for r in rs[:5]] for c, rs in state.candidates.items()}}


def cap_sections(keys: list[str], n: int) -> list[str]:
    """Keep keys (best first) until n distinct sections are used; the cap's evidence
    (max gold sections per dev question) counts sections, not paragraphs."""
    out, secs = [], set()
    for k in keys:
        sec = ":".join(k.split(":")[:2])
        if sec not in secs and len(secs) >= n:
            continue
        secs.add(sec)
        out.append(k)
    return out


@traced("select_citations", fallback=_select_fallback)
def select_citations(state: AgentState) -> dict:
    """p(applies) per candidate from the configured DECIDER. Only candidate keys can be
    selected — no backend can introduce a citation that retrieval did not return."""
    judge = _p_gemini_batch if settings.decider == "gemini" else _p_decider

    def one(code: str) -> tuple[str, list[str], dict]:
        cands = state.candidates.get(code, [])
        if not cands:
            return code, [], {}
        allowed = {r["citation_key"] for r in cands}
        ps = {k: p for k, p in judge(state, code, cands).items() if k in allowed}
        chosen = sorted((k for k, p in ps.items() if p >= P("select.threshold")),
                        key=lambda k: -ps[k])
        if not chosen and ps:                      # never leave an issue without law
            chosen = [max(ps, key=ps.get)]
        return code, cap_sections(chosen, P("select.max_selected")), ps

    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, [i.code for i in state.issues]))
    return {"selected": {c: keys for c, keys, _ in res},
            "_summary": {c: {"selected": keys, "p": {k: round(v, 2) for k, v in ps.items()}}
                         for c, keys, ps in res}}


class _Checks(BaseModel):
    checks: list[ElementCheck]


@traced("check_elements", fallback=lambda state, e: {"elements": {}})
def check_elements(state: AgentState) -> dict:
    _, body = prompt("check_elements")

    def one(code: str) -> tuple[str, list[ElementCheck]]:
        els = taxonomy()[code].get("elements") or []
        if not els:
            return code, []
        by_key = {r["citation_key"]: r for r in state.candidates.get(code, [])}
        provs = [fmt_provision(by_key[k], P("select.provision_chars"))
                 for k in state.selected.get(code, []) if k in by_key]
        listing = "\n".join(f"{e['id']}: {e['question']}" for e in els)
        out = generate_json(body.format(issue_name=taxonomy()[code]["name"], facts=fmt_facts(state),
                                        provisions="\n".join(provs), elements=listing),
                            _Checks, name="check_elements", thinking="low")
        ids = {e["id"] for e in els}
        return code, [c for c in out.checks if c.id in ids]

    with ThreadPoolExecutor(4) as ex:
        res = dict(ex.map(one, [i.code for i in state.issues]))
    return {"elements": res,
            "_summary": {c: {s: sum(x.status == s for x in v) for s in ("met", "not_met", "unknown")}
                         for c, v in res.items()}}


def tenure_from_facts(f) -> labor.Tenure | None:
    if f.start_date and f.end_date and f.end_date >= f.start_date:
        return labor.Tenure.from_dates(f.start_date, f.end_date)
    if any(v is not None for v in (f.service_years, f.service_months, f.service_days)):
        return labor.Tenure.from_stated(f.service_years or 0, f.service_months or 0,
                                        f.service_days or 0)
    return None


@lru_cache(maxsize=1)
def wage_definition_key() -> str:
    """citation_key of the in-force definition of “ค่าจ้าง”, found by its text in the DB."""
    from src.index.db import connect
    with connect() as conn:
        row = conn.execute(
            "SELECT citation_key FROM provisions WHERE citation_key LIKE 'LPA2541:%%' "
            "AND text LIKE %s AND valid_to IS NULL ORDER BY valid_from DESC LIMIT 1",
            ("“ค่าจ้าง” หมายความว่า%",)).fetchone()
    if row is None:
        raise LookupError("ไม่พบนิยามค่าจ้างในฐานข้อมูล")
    return row[0]


@traced("calculate")
def calculate(state: AgentState) -> dict:
    """Deterministic arithmetic (the LLM only extracted dates/amounts). Runs when the issue
    has a formula, the needed facts are known and a rate is in force; otherwise records why."""
    f = state.facts
    rates_path = Path("data/processed/rates.yaml")
    book = labor.RateBook.load(rates_path) if rates_path.exists() else labor.RateBook(rates=[])
    on = state.event_date or (f.end_date if f else None) or datetime.now().astimezone().date()
    out, notes = {}, {}
    for iss in state.issues:
        fk = taxonomy()[iss.code].get("formula_key")
        if not fk:
            continue
        try:
            pre_steps, pre_cites = [], []
            base = labor.wage_base(f.pay_items, wage_definition_key()) if f and f.pay_items else None
            if base and base.monthly is not None:      # wage = every item that is ค่าจ้าง (ม.5)
                wage, period = base.monthly, "month"
                pre_steps, pre_cites = base.steps, [wage_definition_key()]
            elif f is None or f.wage_amount is None or f.wage_period in (None, "piece"):
                raise ValueError("ค่าจ้างไม่ทราบหรือเป็นค่าจ้างตามผลงาน")
            else:
                wage, period = Decimal(str(f.wage_amount)), f.wage_period
            daily = labor.to_daily_wage(wage, period, on, book, exact=True)
            if fk == "severance":
                tenure = tenure_from_facts(f)
                if tenure is None:
                    raise ValueError("อายุงานไม่ทราบ")
                expr = (f"{labor.baht(wage)} ÷ 30" if period == "month" else "ค่าจ้างรายวัน")
                r = labor.severance(daily.amount, tenure, on, book, wage_expr=expr)
                out[iss.code] = labor.CalcResult(amount=r.amount,
                                                 steps=pre_steps + daily.steps + r.steps,
                                                 citations=pre_cites + daily.citations + r.citations)
            else:
                raise ValueError(f"ยังไม่รองรับสูตร {fk} อัตโนมัติ")
        except (ValueError, LookupError) as e:
            notes[iss.code] = str(e)
    return {"calcs": out, "_summary": {"done": list(out), "skipped": notes}}
