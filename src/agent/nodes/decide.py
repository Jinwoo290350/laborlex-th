"""⑤ select_citations · ⑥ check_elements · ⑦ calculate"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, create_model

from src.agent.nodes.common import fmt_facts, fmt_provision, prompt, taxonomy, traced
from src.agent.rules.elements import resolve_elements
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


@traced("check_elements", on_fail="review")
def check_elements(state: AgentState) -> dict:
    """Per issue. An issue whose call fails does not discard the others: their results are kept for
    diagnosis, but the run becomes needs_review and no answer is drafted from them (#22)."""
    _, body = prompt("check_elements")

    def one(code: str) -> tuple[str, list[ElementCheck] | None, str | None, list[str]]:
        try:
            checks, missing = _check_issue(code)
        except Exception as e:  # noqa: BLE001 — isolated per issue, reported below
            return code, None, repr(e), []
        return code, checks, None, missing

    def _check_issue(code: str) -> tuple[list[ElementCheck], list[str]]:
        els = taxonomy()[code].get("elements") or []
        if not els:
            return [], []
        by_key = {r["citation_key"]: r for r in state.candidates.get(code, [])}
        provs = [fmt_provision(by_key[k], P("select.provision_chars"))
                 for k in state.selected.get(code, []) if k in by_key]
        asked = [e for e in els if "derive" not in e]      # derived elements are the system's (#17)
        listing = "\n".join(f"{e['id']}: {e['question']}" for e in asked)
        out = generate_json(body.format(issue_name=taxonomy()[code]["name"], facts=fmt_facts(state),
                                        provisions="\n".join(provs), elements=listing),
                            _Checks, name="check_elements", thinking="low")
        ids = [e["id"] for e in asked]
        kept = [c for c in out.checks if c.id in set(ids)]
        got = {c.id for c in kept}
        return kept, [i for i in ids if i not in got]

    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(one, [i.code for i in state.issues]))
    raw = {code: checks for code, checks, _, _ in results if checks is not None}
    res = resolve_elements(raw, taxonomy())     # derived elements + cross-issue consistency (#17, #20)
    summary: dict = {c: {s: sum(x.status == s for x in v) for s in ("met", "not_met", "unknown")}
                     for c, v in res.items()}
    partial = {code: missing for code, _, err, missing in results if err is None and missing}
    if partial:     # LLM omitted asked ids: recorded only, does not change the status in round 1
        summary["partial"] = partial
    failed = [{"node": "check_elements", "issue": code, "error": err, "kind": "exception"}
              for code, _, err, _ in results if err is not None]
    if not failed:
        return {"elements": res, "_summary": summary}
    summary["failed"] = [f["issue"] for f in failed]
    return {"elements": res, "status": "needs_review", "degraded": failed, "_summary": summary,
            "_error": "; ".join(f"{f['issue']}: {f['error']}" for f in failed)}


def tenure_from_facts(f) -> labor.Tenure | None:
    if f.start_date and f.end_date and f.end_date >= f.start_date:
        return labor.Tenure.from_dates(f.start_date, f.end_date)
    if any(v is not None for v in (f.service_years, f.service_months, f.service_days)):
        return labor.Tenure.from_stated(f.service_years or 0, f.service_months or 0,
                                        f.service_days or 0)
    return None


@cache
def key_by_text(prefix: str, law: str = "LPA2541") -> str:
    """citation_key of the in-force provision of `law` whose text starts with `prefix` (the
    provision is identified by its wording in the DB, not by a remembered number)."""
    from src.index.db import connect
    with connect() as conn:
        row = conn.execute(
            "SELECT citation_key FROM provisions WHERE citation_key LIKE %s "
            "AND text LIKE %s AND valid_to IS NULL AND sub_no IS NULL "
            "ORDER BY valid_from DESC LIMIT 1", (law + ":%", prefix + "%")).fetchone()
    if row is None:
        raise LookupError(f"ไม่พบบทบัญญัติที่ขึ้นต้นว่า “{prefix}” ในฐานข้อมูล")
    return row[0]


def wage_definition_key() -> str:
    return key_by_text("“ค่าจ้าง” หมายความว่า")


def notice_keys() -> dict[str, str]:
    return {"notice": key_by_text("ในกรณีที่สัญญาจ้างไม่มีกำหนดระยะเวลา นายจ้างหรือลูกจ้างอาจบอกเลิกสัญญาจ้าง"),
            "in_lieu": key_by_text("ในกรณีที่นายจ้างบอกเลิกสัญญาจ้างโดยไม่บอกกล่าวล่วงหน้า"),
            "final": key_by_text("ในกรณีที่นายจ้างเลิกจ้างลูกจ้าง ให้นายจ้างจ่ายค่าจ้าง")}


def _wage(f, on, book) -> tuple[Decimal, str, list[str], list[str], labor.CalcResult]:
    """(wage, period, steps, citations, daily) — every item that is ค่าจ้าง (ม.5) when pay
    items are known, else the single stated wage. Raises ValueError when unknown."""
    base = labor.wage_base(f.pay_items, wage_definition_key()) if f and f.pay_items else None
    if base and base.monthly is not None:
        wage, period, steps, cites = base.monthly, "month", base.steps, [wage_definition_key()]
    elif f is None or f.wage_amount is None or f.wage_period in (None, "piece"):
        raise ValueError("ค่าจ้างไม่ทราบหรือเป็นค่าจ้างตามผลงาน")
    else:
        wage, period, steps, cites = Decimal(str(f.wage_amount)), f.wage_period, [], []
    return wage, period, steps, cites, labor.to_daily_wage(wage, period, on, book, exact=True)


def termination_money(f, on, book) -> labor.Termination:
    """Severance (if tenure is known), pay in lieu of notice and the final period's wage,
    from the facts alone. Raises ValueError when a needed fact is missing."""
    if not (f and f.end_date and f.pay_days):
        raise ValueError("ไม่ทราบวันเลิกจ้างหรือกำหนดวันจ่ายค่าจ้าง")
    wage, period, wsteps, wcites, daily = _wage(f, on, book)
    if period != "month":
        raise ValueError("ระบบคำนวณสินจ้างแทนการบอกกล่าวล่วงหน้าเฉพาะค่าจ้างรายเดือน")
    n = labor.notice_and_final_pay(f.end_date, f.pay_days, wage, daily.amount, notice_keys())
    tenure = tenure_from_facts(f)
    sev = (labor.severance(daily.amount, tenure, on, book, wage_expr=f"{labor.baht(wage)} ÷ 30")
           if tenure is not None else None)
    cites = list(dict.fromkeys(wcites + daily.citations + (sev.citations if sev else [])
                               + n.final_period.citations + n.notice_pay.citations))
    return labor.Termination(severance=sev, notice_pay=n.notice_pay, final_wage=n.final_period,
                             effective=n.effective, wage_steps=wsteps + daily.steps, citations=cites)


def worker_views(f) -> list[tuple[str | None, Any, str | None]]:
    """(name, facts, problem) per employee. Only when the question states different wages / pay items / lengths of
    service for two or more employees (Facts.workers): one view per employee, overriding just what that employee's
    figures state. A worker's own pay items go through the same ม.5 classification as shared ones (`_wage`); a raw
    worker wage is used only when no other pay item is listed (an item equal to a worker's stated wage is that wage
    listed twice). Raw worker wages next to allowances listed once for everyone cannot be split per employee →
    `problem`, no amount (#18). Employees on the same figures stay
    one shared view (filled from their common figures where the shared facts are empty), so the shared pay items,
    dates and termination table are kept."""
    def figures(w):
        items = tuple((i.name, i.amount, i.period) for i in w.pay_items)
        return (w.wage_amount, w.wage_period, w.service_years, w.service_months, w.service_days, items)
    ws = [w for w in (f.workers if f else []) if any(v not in (None, ()) for v in figures(w))]
    if not ws:
        return [(None, f, None)]
    if len(ws) < 2 or len({figures(w) for w in ws}) < 2:
        # one set of figures for everyone: the shared view, taking from the workers only what the shared facts lack
        # (the extractor may have put the common pay items / wage / tenure on the workers instead)
        w, fill = ws[0], {}
        if not f.pay_items and w.pay_items:
            fill["pay_items"] = list(w.pay_items)
        if f.wage_amount is None and w.wage_amount is not None:
            fill |= {"wage_amount": w.wage_amount, "wage_period": w.wage_period}
        if (not (f.start_date and f.end_date) and all(v is None for v in (f.service_years, f.service_months,
                                                                          f.service_days))):
            fill |= {"service_years": w.service_years, "service_months": w.service_months,
                     "service_days": w.service_days}
        return [(None, f.model_copy(update=fill) if fill else f, None)]
    # a shared item equal to some worker's stated wage (amount and period) is that wage listed twice, not an allowance
    shared_other = [i for i in f.pay_items
                    if not any(i.amount == w.wage_amount and i.period == w.wage_period for w in ws)]
    views = []
    for w in ws:
        upd: dict[str, Any] = {}
        problem = None
        if w.pay_items:
            upd |= {"pay_items": list(w.pay_items), "wage_amount": w.wage_amount, "wage_period": w.wage_period}
        elif w.wage_amount is not None:
            if shared_other:
                problem = ("โจทย์ระบุรายการเงินรวมโดยไม่แยกรายคน จึงจัดประเภทค่าจ้างตามมาตรา 5 ของแต่ละคนไม่ได้ "
                           "— ไม่คำนวณจากค่าจ้างดิบ")
            upd |= {"wage_amount": w.wage_amount, "wage_period": w.wage_period, "pay_items": []}
        if any(v is not None for v in (w.service_years, w.service_months, w.service_days)):
            upd |= {"start_date": None, "service_years": w.service_years, "service_months": w.service_months,
                    "service_days": w.service_days}
        views.append((w.name, f.model_copy(update=upd), problem))
    return views


def _formula(fk: str, f, on, book) -> labor.CalcResult:
    """One issue's formula for one employee's facts. Raises ValueError when a needed fact is missing."""
    wage, period, pre_steps, pre_cites, daily = _wage(f, on, book)
    if fk == "severance":
        tenure = tenure_from_facts(f)
        if tenure is None:
            raise ValueError("อายุงานไม่ทราบ")
        expr = (f"{labor.baht(wage)} ÷ 30" if period == "month" else "ค่าจ้างรายวัน")
        r = labor.severance(daily.amount, tenure, on, book, wage_expr=expr)
        return labor.CalcResult(amount=r.amount, steps=pre_steps + daily.steps + r.steps,
                                citations=pre_cites + daily.citations + r.citations)
    if fk == "notice_pay":
        t = termination_money(f, on, book)
        return labor.CalcResult(
            amount=t.notice_pay.amount,
            steps=pre_steps + ["▶ ค่าจ้างงวดสุดท้าย"] + t.final_wage.steps
            + ["▶ สินจ้างแทนการบอกกล่าวล่วงหน้า"] + daily.steps + t.notice_pay.steps,
            citations=pre_cites + t.final_wage.citations + daily.citations + t.notice_pay.citations)
    raise ValueError(f"ยังไม่รองรับสูตร {fk} อัตโนมัติ")


@traced("calculate")
def calculate(state: AgentState) -> dict:
    """Deterministic arithmetic (the LLM only extracted dates/amounts). Runs when the issue
    has a formula, the needed facts are known and a rate is in force; otherwise records why.
    Dismissal money (severance, pay in lieu of notice, final wage) is also computed from the
    facts alone, so it never depends on which issues were chosen.
    Several employees with their own figures (Facts.workers): one result per employee, key "<issue>@<name>"."""
    f = state.facts
    rates_path = Path("data/processed/rates.yaml")
    book = labor.RateBook.load(rates_path) if rates_path.exists() else labor.RateBook(rates=[])
    on = state.event_date or (f.end_date if f else None) or datetime.now().astimezone().date()
    out, notes = {}, {}
    views = worker_views(f)
    for iss in state.issues:
        fk = taxonomy()[iss.code].get("formula_key")
        if not fk:
            continue
        for name, wf, problem in views:
            key = iss.code if name is None else f"{iss.code}@{name}"
            if problem:
                notes[key] = problem
                continue
            try:
                out[key] = _formula(fk, wf, on, book)
            except (ValueError, LookupError) as e:
                notes[key] = str(e)
    term = None
    if len(views) > 1:       # the termination table assumes one wage for every employee
        notes["termination"] = "ลูกจ้างแต่ละคนค่าจ้าง/อายุงานต่างกัน — คำนวณรายคนในแต่ละประเด็น"
    else:
        try:
            term = termination_money(views[0][1], on, book)     # the shared view (filled from workers if needed)
        except (ValueError, LookupError) as e:
            notes["termination"] = str(e)
    return {"calcs": out, "termination": term,
            "_summary": {"done": list(out) + (["termination"] if term else []), "skipped": notes}}


def m119_keys() -> dict[str, str]:
    return {"m119": key_by_text("นายจ้างไม่ต้องจ่ายค่าชดเชยให้แก่ลูกจ้างซึ่งเลิกจ้างในกรณีหนึ่งกรณีใด"),
            "notice_exempt": key_by_text("การบอกกล่าวล่วงหน้าตามมาตรานี้ไม่ใช้บังคับแก่การเลิกจ้างตามมาตรา 119"),
            "final": notice_keys()["final"],
            # ป.พ.พ. ม.583 — the other dismissal that ม.17 วรรคสี่ exempts from notice (FIX_PLAN_v2 M2)
            "ccc583": key_by_text("ถ้าลูกจ้างจงใจขัดคำสั่งของนายจ้างอันชอบด้วยกฎหมาย", law="CCC")}
