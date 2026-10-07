"""Outcome elements v2 (docs/design/2026-10-07_outcome_elements_redesign_v2.md, 2026-10-07_legal_audit_L1_L2.md).

s.123 (L1, case law: 768/2533, ร 1559/2563, ร 142/2566, 4168/2530, 2329/2532, 3631/2529, 5596/2534, 3043/2541,
8311/2559): a misconduct dismissal during a CBA that fits no exception is prohibited (ULP, employee protected); a valid
written warning or a serious breach makes it permitted; a business-necessity ground is not treated as misconduct.
s.31 (L2): the strict line (2490/2526, 3822/2528) and the flexible line (8137-8138/2543, 2476/2544) conflict, so when the
refused order is the transfer itself the lawful-order element stays unknown, and "act prohibited" is only ever
conditional. Outcomes carry structured markers; there is no phrase guard. #20's forbidden citation is unchanged.
Leaf statuses are ids/statuses only (frozen p1720 leaves, paired8 run, ruling patterns). Local, no Gemini."""

from pathlib import Path

import pytest
import yaml

from src.agent.answer import AnswerJSON, Issue, Point
from src.agent.rules.elements import answer_conflicts, forbidden_citations, resolve_elements
from src.agent.state import AgentState, ElementCheck

TAX = {i["code"]: i for i in yaml.safe_load(Path("data/processed/issues.yaml").read_text(encoding="utf-8"))}
S123, S31, ULP = "employee_committee_and_union_protection", "dispute_protection_s31", "unfair_labor_practices_and_disputes"
K121_1 = "LRA2518:121:1:(1)"
MARKERS = {"OUTCOME_WARNING_REQUIRED", "OUTCOME_DISMISSAL_PROHIBITED", "OUTCOME_DISMISSAL_PERMITTED",
           "OUTCOME_ACT_PROHIBITED", "OUTCOME_ACT_PERMITTED"}
M, N, U = "met", "not_met", "unknown"
# s.31 / L2 is not implemented yet (strict vs flexible line unresolved): its fail-first tests stay, marked xfail
L2_PENDING = pytest.mark.xfail(strict=True, reason="s.31 / L2 deferred (decisions #21)")


def _el(code: str, eid: str) -> dict:
    return next(e for e in TAX[code]["elements"] if e["id"] == eid)


def _resolve(llm: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    raw = {c: [ElementCheck(id=i, status=s, evidence="e") for i, s in st.items()] for c, st in llm.items()}
    return {c: {x.id: x.status for x in v} for c, v in resolve_elements(raw, TAX).items()}


# s.123 leaves: a lawful order (work rule / CBA), refused, not obstructive, CBA in force; vary the rest
BASE123 = {"8": M, "9": N, "9b_a": M, "9b_b": M, "9b_c": N, "9b_d": N}


def _s123(**over) -> dict[str, str]:
    return _resolve({S123: {**BASE123, **over}})[S123]


# ---------- schema ----------

def test_old_outcome_elements_and_phrase_guards_are_gone():
    assert "9b_outcome" not in {e["id"] for e in TAX[S123]["elements"]}
    assert not any("forbid_phrases" in e for issue in TAX.values() for e in issue.get("elements") or [])


def test_5_outcome_is_kept_as_a_pending_legacy_element():
    # L2 not locked: s.31 semantics unchanged in the L1 round (same derive, same display), only the phrase guard is gone
    e = _el(S31, "5_outcome")
    assert e["legacy_outcome"] == "pending_L2" and "outcome" not in e
    assert e["derive"] == {"all": ["2", "3", "5_lawful", {"not": "5_e"}]}


def test_element_8_asks_coverage_only():
    q = _el(S123, "8")["question"]
    assert "นายจ้างได้เลิกจ้าง" not in q and "9b_dismissed" in q


def test_new_s123_elements_exist_with_structured_markers():
    assert "derive" not in _el(S123, "9b_dismissed") and "derive" not in _el(S123, "9b_ground_misconduct")
    want = {"9b_warning_required": "OUTCOME_WARNING_REQUIRED", "9b_dismissal_prohibited": "OUTCOME_DISMISSAL_PROHIBITED",
            "9b_dismissal_permitted": "OUTCOME_DISMISSAL_PERMITTED"}
    for eid, marker in want.items():
        out = _el(S123, eid)["outcome"]
        assert out["marker"] == marker and out["certainty"] == "definitive"
        assert out["guard"] == "none" and out["statement"].strip()


def test_every_outcome_marker_is_known_and_prohibited_has_no_guard():
    for code, issue in TAX.items():
        for e in issue.get("elements") or []:
            if "outcome" in e:
                o = e["outcome"]
                assert o["marker"] in MARKERS, (code, e["id"])
                assert o["certainty"] in {"definitive", "conditional"}
                if o["marker"].endswith("_PROHIBITED"):
                    assert o["guard"] == "none", (code, e["id"])
                if o["certainty"] == "conditional":
                    assert o.get("unmodelled_prerequisites"), (code, e["id"])


def test_9b_e_asks_for_a_valid_warning_or_a_serious_breach():
    q = _el(S123, "9b_e")["question"]
    assert "ร้ายแรง" in q and "ยังมีผล" in q and "เรื่องเดียวกัน" in q   # 2329, 4168, ร 142


def test_prohibited_statement_says_protected_not_unprotected():
    s = _el(S123, "9b_dismissal_prohibited")["outcome"]["statement"]
    assert "ได้รับความคุ้มครอง" in s and "ไม่ได้รับความคุ้มครอง" not in s


# ---------- L1 derivation (every outcome state) ----------

@pytest.mark.parametrize("over, expect", [
    # dismissed for the breach, no valid warning, not serious → prohibited (768, ร 1559, ร 142, 4168)
    ({"9b_dismissed": M, "9b_ground_misconduct": M, "9b_e": N},
     {"9b": N, "9b_warning_required": M, "9b_dismissal_prohibited": M, "9b_dismissal_permitted": N}),
    # valid written warning or serious breach → permitted (2329, 3631, 2211, 5596, 1818)
    ({"9b_dismissed": M, "9b_ground_misconduct": M, "9b_e": M},
     {"9b": M, "9b_warning_required": N, "9b_dismissal_prohibited": N, "9b_dismissal_permitted": M}),
    # another exception (9: e.g. 3 days' abandonment) → permitted even without a warning
    ({"9b_dismissed": M, "9b_ground_misconduct": M, "9b_e": N, "9": M},
     {"9b_dismissal_prohibited": N, "9b_dismissal_permitted": M}),
    # not dismissed yet (s.52 permission request) → only the warning requirement speaks
    ({"9b_dismissed": N, "9b_ground_misconduct": M, "9b_e": N},
     {"9b_warning_required": M, "9b_dismissal_prohibited": N, "9b_dismissal_permitted": N}),
    # warning unknown → no definitive dismissal outcome
    ({"9b_dismissed": M, "9b_ground_misconduct": M, "9b_e": U},
     {"9b_dismissal_prohibited": U, "9b_dismissal_permitted": U}),
    # no CBA in force → s.123 not engaged (3943/2557)
    ({"8": N, "9b_dismissed": M, "9b_ground_misconduct": M, "9b_e": N},
     {"9b_warning_required": N, "9b_dismissal_prohibited": N, "9b_dismissal_permitted": N}),
])
def test_l1_outcome_states(over, expect):
    got = _s123(**over)
    assert {k: got[k] for k in expect} == expect


def test_768_prohibited_even_when_the_orders_basis_is_unknown():
    got = _s123(**{"9b_b": U, "9b_dismissed": M, "9b_ground_misconduct": M, "9b_e": N})
    assert got["9b_lawful"] == U and got["9b"] == N
    assert got["9b_dismissal_prohibited"] == M


def test_2554_dismissed_for_misconduct_without_valid_warning_is_prohibited():
    # fixture leaves of the 2/2554 Q4 run + facts from the source: dismissed at once, ground = the refusal
    llm = {**BASE123, "9b_c": M, "9b_e": N, "9b_dismissed": M, "9b_ground_misconduct": M}
    got = _resolve({S123: llm})[S123]
    assert got["9b_dismissal_prohibited"] == M and got["9b_dismissal_permitted"] == N


def test_business_necessity_is_not_misconduct():
    # 3043/2541, 8311/2559: a necessity / probation ground goes to an unmodelled test, never "prohibited"
    got = _s123(**{"9b_dismissed": M, "9b_ground_misconduct": N, "9b_e": N})
    assert got["9b_dismissal_prohibited"] == N and got["9b_dismissal_permitted"] == N
    missing = _resolve({S123: {**BASE123, "9b_dismissed": M, "9b_e": N}})[S123]   # ground not answered
    assert missing["9b_dismissal_prohibited"] != M


# ---------- renderer: markers, not substrings ----------

def _block(llm: dict) -> str:
    from src.agent.nodes.draft import _elements_block
    raw = {c: [ElementCheck(id=i, status=s, evidence="e") for i, s in st.items()] for c, st in llm.items()}
    return _elements_block(AgentState(question="q", elements=resolve_elements(raw, TAX)))


def test_renderer_prints_met_outcomes_by_marker_only():
    b = _block({S123: {**BASE123, "9b_dismissed": M, "9b_ground_misconduct": M, "9b_e": N}})
    assert "OUTCOME_DISMISSAL_PROHIBITED" in b and "OUTCOME_WARNING_REQUIRED" in b
    assert "OUTCOME_DISMISSAL_PERMITTED" not in b          # not met → not printed
    assert _el(S123, "9b_dismissal_prohibited")["outcome"]["statement"] in b


def test_legacy_5_outcome_is_shown_only_when_met_and_without_marker():
    met = {S31: {"1": M, "2": M, "3": M, "4": N, "5_a": M, "5_b": M, "5_c": N, "5_d": N, "5_e": N}}
    b = _block(met)
    assert "ผลตาม LRA2518:31:1:(3)" in b and "OUTCOME_" not in b
    assert "ผลตาม LRA2518:31:1:(3)" not in _block({S31: {**met[S31], "5_e": M}})


@L2_PENDING
def test_renderer_marks_conditional_outcomes():
    llm = {S31: {"1": M, "2": M, "3": M, "4": N, "5_a": U, "5_b": U, "5_c": U, "5_d": U, "5_e": N}}  # 1-2551-q3 run
    b = _block(llm)
    assert "OUTCOME_ACT_PROHIBITED" in b and "conditional" in b and "ถ้า" in b


# ---------- no phrase guard; #20 unchanged ----------

def _answer(text: str, code: str, cites: list[str]) -> AnswerJSON:
    return AnswerJSON(preliminary=[Point(headline=text, citations=cites)],
                      issues=[Issue(code=code, question="q", consider="c", laws=[], application=[],
                                    conclusion=[Point(headline=text, citations=cites)], opinion="o", basis="b")])


def test_court_wording_for_768_raises_no_conflict():
    raw = {S123: [ElementCheck(id=i, status=s, evidence="e") for i, s in
                  {**BASE123, "9b_dismissed": M, "9b_ground_misconduct": M, "9b_e": N}.items()]}
    r = {c: {x.id: x for x in v} for c, v in resolve_elements(raw, TAX).items()}
    a = _answer("ลูกจ้างได้รับความคุ้มครองตาม ม.123 การเลิกจ้างโดยไม่ได้ตักเตือนเป็นหนังสือเป็นการกระทำอันไม่เป็นธรรม",
                S123, ["LRA2518:123:1"])
    assert answer_conflicts(a, r, TAX) == []


def test_20_forbidden_citation_still_fires_on_the_2554_pattern():
    llm = {S123: {**BASE123, "3": M, "9b_c": M, "9b_e": N, "9b_dismissed": M, "9b_ground_misconduct": M},
           ULP: {"1": U, "2": U, "7": M, "8": U}}
    raw = {c: [ElementCheck(id=i, status=s, evidence="e") for i, s in st.items()] for c, st in llm.items()}
    r = {c: {x.id: x for x in v} for c, v in resolve_elements(raw, TAX).items()}
    assert K121_1 in forbidden_citations(r, TAX)
    kinds = {c.kind for c in answer_conflicts(_answer("เลิกจ้างเพราะยื่นข้อเรียกร้อง", ULP, [K121_1]), r, TAX)}
    assert kinds == {"forbidden_citation"}


# ---------- s.31 (L2: structure only, no doctrine) ----------

S31_REFUSED_TRANSFER = {"1": M, "2": M, "3": M, "4": N, "5_a": M, "5_c": N, "5_d": N, "5_e": N, "5_order_is_act": M}


@pytest.mark.parametrize("b", [pytest.param(M, marks=L2_PENDING), pytest.param(N, marks=L2_PENDING), U])
def test_refused_transfer_that_is_the_protected_act_is_never_forced_lawful_or_unlawful(b):
    # strict (2490, 3822) vs flexible (8137, 2476): 5_b alone must not decide
    got = _resolve({S31: {**S31_REFUSED_TRANSFER, "5_b": b}})[S31]
    assert got["5_lawful"] == U


@L2_PENDING
def test_consent_does_not_resolve_it_either():
    got = _resolve({S31: {**S31_REFUSED_TRANSFER, "5_b": N, "5_c": M}})[S31]
    assert got["5_lawful"] == U


def test_order_issued_before_the_demand_keeps_the_old_logic():
    # 2222/2538: the order is not the barred act (issued before the demand) → 5_b/5_c decide as before
    got = _resolve({S31: {**S31_REFUSED_TRANSFER, "5_order_is_act": N, "5_b": M}})[S31]
    assert got["5_lawful"] == M


@L2_PENDING
def test_act_prohibited_is_only_ever_conditional():
    out = _el(S31, "5_act_prohibited")["outcome"]
    assert out["marker"] == "OUTCOME_ACT_PROHIBITED" and out["certainty"] == "conditional" and out["guard"] == "none"
    assert len(out["unmodelled_prerequisites"]) >= 2      # demand validity/status + strict/flexible transfer doctrine


@L2_PENDING
def test_1_2551_q3_comes_out_conditional():
    got = _resolve({S31: {"1": M, "2": M, "3": M, "4": N, "5_a": U, "5_b": U, "5_c": U, "5_d": U, "5_e": N}})[S31]
    assert got["5_act_prohibited"] == M                      # rendered only with its conditions (renderer test)
    assert _el(S31, "5_act_prohibited")["outcome"]["certainty"] == "conditional"


@L2_PENDING
def test_s31_transfer_without_refusal_is_conditional_not_definitive():
    # 3822/2528 (strict: barred) vs 8137-8138/2543 (flexible: allowed) — same element pattern, opposite holdings
    got = _resolve({S31: {"1": M, "2": M, "3": M, "4": N, "5_a": N, "5_b": U, "5_c": N, "5_d": U, "5_e": U}})[S31]
    assert got["5_act_prohibited"] == M
    assert _el(S31, "5_act_prohibited")["outcome"]["certainty"] == "conditional"
