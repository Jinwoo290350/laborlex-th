# Acceptance benchmark candidate — dev18 (2026-10-07) · STATUS: PROPOSED, NOT FROZEN

Rule from the moment this file exists: **these 18 questions are not used to design or tune anything** (no prompt, taxonomy,
element, retrieval or threshold change may be motivated by their outputs). Frozen when Frank approves; then any change to
the list or the gold file is a new benchmark version. Gold file (local, client data): `data/eval/acceptance_dev18.csv`,
sha256 `139b4e03b3bf7b74689776d061dbca12ebc978f1c7584aed79554b34ddd68d18`.

## 1. How the 18 were chosen (provenance audit)
Start: the 40-question **holdout** of `config/dev100_split.json` (stratified by category × difficulty; the 60 tune
questions were used by `tune_retrieval`, `tune_select`, `calibrate_judge` → excluded; the 13 `seen_during_development` are
all in tune). Then removed every holdout question with **severe** exposure:
| Exposure (severe) | Removed |
|---|---|
| element queries / targets written for it in the retrieval V2 benchmark (`docs/benchmarks/retrieval_validation_elements.yaml`, `small8_spec.yaml`, `retrieval_v2_queries.yaml`) | dev019, 022, 024, 039, 047, 050, 077, 086, 096, 110, 112, 119, 126, 128, 134, 143, 156 |
| gold edited (`config/gold_overrides.yaml`), tests, decisions, or lines added to code/tests after the holdout run | dev014, 022, 039, 087, 102 |
| targeted regression or re-tagging in this session | dev014, 087, 102 |
| id collides with the dataset name (`dev100`) — provenance cannot be checked | dev100 |
| failure written up in the holdout report **and** the related component (ม.5 wage classifier) rebuilt afterwards | dev023 |
Kept with **mild** exposure only: run once in the 2026-10-01 holdout eval; some also in the 09-30 decider bake-off or
BM25 check (measurement, before tuning). dev009 and dev051 had their failures written up, but nothing related changed → kept, flagged.
**No replacement is possible inside dev100:** the clean pool is exactly these 18 (the other 82 are tune, seen or exposed).

Structural leakage that no selection removes (state it with every result): the taxonomy, its elements and
`provision_support` were drafted from all of dev100 (leave-one-out removes only the question's own few-shot example and
its own support). Expected issues = dev100 issue tags (LLM-assisted tagging, not expert-reviewed).

## 2. Coverage of the set — and its gaps
8 categories, Easy 3 / Medium 8 / Hard 7, 11 issues (maternity leave 4, working hours 4, wage deductions 3, s.119 2,
sick leave 2, inspector authority 2, overtime 2, spouse 2, remote work, special severance, other leaves).
**Not covered:** LRA (s.121/123/31), severance/notice calculation with amounts, Supreme Court rulings (no gold ruling in
column H for any of the 18), questions needing more than 2 issues. Exactly these were used for development, so the clean
dev set cannot measure them → a second held-out slice from unused real exam questions is needed for those (§5).

## 3. Gold per question (in the local CSV)
expected_issues (dev tags) · expected_statutes (column H citations) · expected_rulings (none in H) · expected_amounts (none
in H) · expected_conclusion (column H text) · citation requirement (every expected statute cited as a key — the client
criterion).

## 4. Baseline (no Gemini)
\* judge = Gemini judge of the 2026-10-01 eval, not ground truth (shown for history only). The 2026-10-01 system is older
code (before the ม.5, ม.119, retrieval and #13–#20 changes). "Gemini alone, lawyer-scored" = the client's lawyer scores of
plain Gemini answers (`data/raw/legacy/client-baseline-scores.jsonl`, model `g`) — the comparator the client cares about.

| case_id | issue_type | gold (sections · H) | baseline: current staging statute recall (oracle issues) | baseline: system 2026-10-01 (sections · judge*) | baseline: Gemini alone, lawyer-scored | pass/fail (Gemini alone) | failure_category (lawyer criteria) | provenance |
|---|---|---|---|---|---|---|---|---|
| dev002 | maternity_and_paternity_leave | LPA2541:41, LPA2541:41/1 | 2/2 | 2/2 · PASS | {'A1': 2, 'A2': 2, 'B0': 0, 'B1': 0, 'B2': 0, 'B3': 0} | FAIL | application, conclusion, issue_spotting, statute/principle | holdout · run once 10-01; bakeoff_openthai.json |
| dev003 | remote_work | LPA2541:23/1 | 1/1 | 1/1 · PASS | {'A1': 2, 'A2': 2, 'B0': 1, 'B1': 2, 'B2': 2, 'B3': 2} | FAIL | issue_spotting | holdout · run once 10-01; bakeoff_openthai.json |
| dev009 | spouse_status | LPA2541:41/1, CCC:1448, CCC:1458 | 3/3 | 2/3 · PASS | {'A1': 2, 'A2': 2, 'B0': 1, 'B1': 2, 'B2': 2, 'B3': 2} | FAIL | issue_spotting | holdout · run once 10-01; bakeoff_openthai.json, 2257_dev100_6e84cc37_v, dev100_holdout_6e84cc3 ⚠ failure read |
| dev027 | wage_deductions_and_guarantees | LPA2541:76 | 1/1 | 1/1 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 1, 'B2': 1, 'B3': 2} | FAIL | application, statute/principle | holdout · run once 10-01; bakeoff_openthai.json |
| dev044 | maternity_and_paternity_leave | LPA2541:41/1, LPA2541:41 | 2/2 | 2/2 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 0, 'B2': 0, 'B3': 0} | FAIL | application, conclusion, statute/principle | holdout · run once 10-01; bakeoff_openthai.json, retrieval_bm25.json |
| dev049 | dismissal_for_cause, sick_leave | LPA2541:32, LPA2541:119 | 2/2 | 2/2 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01; bakeoff_openthai.json, retrieval_bm25.json |
| dev051 | labor_inspector_authority | LPA2541:123 | 1/1 | 1/1 · FAIL | {'A1': 2, 'A2': 1, 'B0': 1, 'B1': 2, 'B2': 2, 'B3': 2} | FAIL | conclusion, issue_spotting | holdout · run once 10-01; dev100_holdout_6e84cc3 ⚠ failure read |
| dev052 | wage_deductions_and_guarantees | LPA2541:76, LPA2541:77 | 2/2 | 2/2 · PASS | {'A1': 2, 'A2': 0, 'B0': 2, 'B1': 1, 'B2': 0, 'B3': 0} | FAIL | application, conclusion, statute/principle | holdout · run once 10-01; retrieval_bm25.json |
| dev069 | sick_leave | LPA2541:32 | 1/1 | 1/1 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01 |
| dev070 | labor_inspector_authority | LPA2541:123, LPA2541:124 | 2/2 | 2/2 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01 |
| dev075 | special_severance_pay_and_relocation | LPA2541:120 | 1/1 | 1/1 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01 |
| dev078 | overtime_and_holiday_pay, working_hours_and_holidays | LPA2541:23, LPA2541:25, LPA2541:61, LPA2541:68 | 4/4 | 4/4 · PASS | {'A1': 1, 'A2': 1, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | FAIL | completeness, conclusion | holdout · run once 10-01; retrieval_bm25.json |
| dev094 | maternity_and_paternity_leave, working_hours_and_holidays | LPA2541:41, LPA2541:59, LPA2541:56 | 3/3 | 3/3 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01; retrieval_bm25.json |
| dev109 | wage_deductions_and_guarantees | LPA2541:76 | 1/1 | 1/1 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01 |
| dev138 | dismissal_for_cause, working_hours_and_holidays | LPA2541:28, LPA2541:119 | 2/2 | 2/2 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01; retrieval_bm25.json |
| dev141 | maternity_and_paternity_leave, spouse_status | LPA2541:41/1 | 1/1 | 1/1 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01 |
| dev158 | other_leaves | LPA2541:33, LPA2541:35, LPA2541:57, LPA2541:58 | 4/4 | 4/4 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01; retrieval_bm25.json |
| dev160 | overtime_and_holiday_pay, working_hours_and_holidays | LPA2541:29, LPA2541:56, LPA2541:62 | 3/3 | 3/3 · PASS | {'A1': 2, 'A2': 2, 'B0': 2, 'B1': 2, 'B2': 2, 'B3': 2} | PASS | — | holdout · run once 10-01; retrieval_bm25.json |

| Metric | Current staging (free part) | Historical system 2026-10-01 | Gemini alone (lawyer) |
|---|---|---|---|
| issue coverage | needs E2E | — | B0 = 2: 77% |
| statute correctness | retrieval recall with oracle issues **18/18** questions complete | sections cited complete 17/18 | B1 = 2: 77% |
| authority retrieval | not measurable (no gold rulings) | — | — |
| legal conclusion | needs E2E + review | — | A2 = 2: 83% · B3 = 2: 83% |
| calculation | not measurable (no gold amounts) | — | — |
| citation completeness | needs E2E | 17/18 | — |
| overall | needs E2E | judge PASS 17/18 (not trusted) | **PASS 10/18 (56%)** |
Gemini alone on all of dev100: PASS 55/100; on the 40 holdout: 23/40 — the 18 are not an easy subset for legal answers.

## 5. What needs Gemini (not run — waiting for approval)
- **Current staging end-to-end on the 18** (issue coverage, conclusion, citation completeness, overall): 18 × ~$0.24
  ≈ **$4.3**, up to ~$7 with revise rounds; manual 4-point review against column H ≈ 2–3 h.
- **Second held-out slice for the gaps** (LRA, severance calculation, case law, >2 issues): ~10 unused in-scope Ram
  LAW4004 questions (stratified by 1 / 2 / >2 sections), C2 only ≈ $2.5–4, model answers as gold, manual review.

## 6. Adversarial review (2026-10-07) — is dev18 enough? (no Gemini)
Evidence: dev18 Gemini-alone lawyer PASS 10/18 (Wilson 95% CI 0.34–0.75) vs 55/100 on dev100 (0.45–0.64): consistent,
not distinguishable. Paired McNemar needs ≥ 6 one-directional discordant items for p < 0.05 → dev18 can prove only a
net gain of ≥ 6 questions; smaller changes are direction only.
Coverage vs the test160 proxy (dev100): LRA 12% / calculation-issue 38% / ≥ 3 issues 12% · dev18: 0 / 3 / 0.
**Strictness correction:** 15 holdout questions were excluded only for element queries written in the retrieval V2
benchmark, which never shipped to staging or production → not leaked for evaluating the current system. Relaxed set
dev33 = dev18 + dev019, 024, 047, 050, 077, 086, 096, 110, 112, 119, 126, 128, 134, 143, 156 (calculation-issue 10,
≥ 3 issues 2, LRA still 0; Gemini-alone PASS 21/33). Those 15 must stay out of any future V2-retrieval acceptance.
LRA cannot be measured cleanly from dev100 at all (all 12 LRA questions are tune, seen or used this session).
LAW4004: 83 in-scope unused (1 / 2 / >2 sections: 12 / 28 / 43); 33 involve LRA (9 from 2562+); 45 involve money
sections; 63 of 83 are from ≤ 2561 (old-law risk for LPA money questions, much less for LRA s.31/121–124); 13 parse
flags; gold = tutor-written model answers (not official), reviewed by us.
Largest blind spot is the scorer, not the question set: no lawyer score exists for any LaborLex answer; our reviews are
provisional and the Gemini judge is not trusted. The lawyer already scored Gemini's answers on these questions → our
reviewer can be calibrated on them for free.

## 7. Second challenge (2026-10-07) — dev18 vs dev33 vs +LAW4004 (no Gemini)
| | dev18 | +15 (V2-only exposure) | dev33 | LAW4004-8 (proposed) |
|---|---|---|---|---|
| distinct issues | 11/29 | 15/29 | 19/29 | not tagged yet |
| calculation-issue | 3 | 7 | 10 | money sections in 45/83 of the pool |
| s.119 | 2 | 5 | 7 | — |
| LRA | 0 | 0 | 0 | 8 (by design) |
| ≥ 2 issues / ≥ 3 | 6 / 0 | 11 / 2 | 17 / 2 | >2 sections in 43/83 of the pool |
| gold rulings | 0 | 0 | 0 | some model answers (unknown count) |
| Easy / Medium / Hard | 3 / 8 / 7 | 1 / 4 / 10 | 4 / 12 / 17 | bucket-based |
| provenance risk for staging | low | low (excluded only from V2-retrieval acceptance) | low | none for the system; gold = tutor answers, 63/83 from ≤ 2561 |
| Gemini cost (≈ $0.24/q) | ~$4.3 | ~$3.6 marginal | ~$7.9 | ~$2.0 |
LRA failure evidence: pilot (6 LRA / 6 LPA) — C0 fails 5 LRA vs 3 LPA; C1 fails 2 LRA vs 1 LPA; original C2 3/3 LRA wrong;
targeted dev LRA: 2 of 3 failures involve LRA sections (dev099 s.125/s.123, dev120 s.124).
Decision: dev33 first; LAW4004-8 is a gate for merging fix20 (LRA generalisation), not for the next round of changes.

## 8. Final pre-run audit (2026-10-07, no Gemini) — verdict: dev33 CANNOT show that fix20/v8 improved anything
**Provenance, item by item (the 15 V2-only items).** V2 files are untracked and referenced by no src/config/test → V2
exposure is not leakage for staging. Same rule as dev023 (failure analysed after the holdout AND a related component
changed afterwards): **dev077 out** (miss = s.5; s.5 wage classifier rebuilt, 44 added lines) · **dev156 out** (miss
includes s.67 annual-leave pay; staging #15 adds an annual-leave companion rule) · dev050, dev110 kept, flagged (failures
analysed, nothing related changed). Final: **dev31** = dev18 + dev019, 024, 047, 050, 086, 096, 110, 112, 119, 126, 128,
134, 143. (Literal reading "any post-holdout analysis" would also drop dev009, 050, 051, 110 → 27.)

**Deterministic metrics on dev31 (no LLM):** issue coverage vs dev tags (31; tags are LLM-assisted, not expert) · statutes
cited ⊇ column H (31) · citation keys for prose sections (31) · calculation amount vs gold (1: dev024 — the only H with an
amount) · calculation routing done/skipped (10 calculation-issue items, paired with the 2026-10-01 records) ·
date/pay-period extraction: no gold facts (needs human labelling) · worker-level: none (no multi-employee item).
**Human legal review:** conclusion vs H, application, whether extra issues are wrong.

**Change → failure mode → dev31 items that can detect it**
| Change | Failure mode it targets | Fires on dev31? | Can detect |
|---|---|---|---|
| #13 s.31 split | s.31 vs s.121 route confusion | no (0 LRA-issue items) | regression only (taxonomy text seen by spot_issues on all 31) |
| #14/#17 lawful-order sub-elements | compound element verdict | no | nothing |
| #15 open entitlement → annual leave | missed annual-leave pay | no (0/31 trigger) | nothing |
| #16 s.31 ruling ranking | wrong ruling for s.31 | no | nothing |
| #18 v8 workers / per-worker pay items | pooled wages, raw wage, lost table | no split (single employee everywhere) | regression only (v8 extraction prompt on all 31; workers wrongly filled on single-employee items) |
| ม.5 wage classification | wage base | unchanged in staging (src/calc = HEAD) | vs 10-01 only (confounded with 10-02 changes): dev024, 096, 134, 143 |
| #20 consistency + guard | s.121(1) on a lawful order; framing | no | nothing |
| citation/rendering (per-worker note, outcome display, ⑩ strip) | presentation | no per-worker / outcome items | citation completeness on all 31 |
Free "before" available: the 2026-10-01 run of all 31 (older code, before the 10-02 production changes) → usable for
deterministic no-regression only; it cannot attribute anything to fix20/v8.

**Pre-registered acceptance criteria (for any set; set before any run).** Per item, before vs after, same gold, same blind
reviewer. Metrics: M1 issue coverage (expected spotted; extra issues counted) · M2 gold statutes cited · M3 citation keys
for prose sections · M4 calculation amount · M5 conclusion (correct / partly / wrong) · M6 misgrounded rulings.
- item IMPROVED: ≥ 1 metric better, none worse · REGRESSED: any metric worse · **SERIOUS**: M5 correct→partly/wrong or
  partly→wrong, M4 correct→wrong, or a gold statute lost · UNCHANGED · INCONCLUSIVE: reviewer unsure, gold ambiguous or
  old-law, run failed.
- noise rule: a non-deterministic regression is re-run once; it counts only if it persists.
- set verdict: **REGRESSION** = ≥ 1 persistent serious regression, or M1 worse on ≥ 2 items · **PASS** = 0 serious, ≥ 2
  items improved on the items where the change fires, net ≥ 0 elsewhere · **NO REGRESSION, NO IMPROVEMENT** = 0 serious,
  < 2 improved → the change is not called a success · **INCONCLUSIVE** = ≥ 25% items inconclusive. Improvement counts are
  reported separately from no-regression; no significance test is the gate.

**Decision tree.** PASS → keep the change, then the next roadmap step · NO IMPROVEMENT → do not merge on accuracy
grounds; keep only if it fixes a recorded bug; re-scope · REGRESSION → stop, root-cause per item (extraction / issue /
retrieval / element / calculation / drafting / citation), no new run before the cause is written down · INCONCLUSIVE →
report the counts only; no claim; fix the review process first.

**What is missing to answer "did fix20/v8 improve?":** (1) unseen items where the mechanisms fire (LRA s.31/123 dismissal
or transfer, open "มีสิทธิอะไรบ้าง" after termination, several employees with different pay) — only LAW4004 has them
(33 LRA among 83 unused); (2) a paired "before" = production f50f467 on the same items; (3) blind human review.
