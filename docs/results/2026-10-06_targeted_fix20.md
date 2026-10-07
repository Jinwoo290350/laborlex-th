# Targeted regression — staging fix20 (feat/taxonomy-s31-split, uncommitted) · 2026-10-06

Scope: all 10 dev questions tagged with an s.121 / s.123 / s.31 issue (2 also run the severance / notice calculation)
+ the Huay Khwang demo question. Leave-one-out few-shot. No `make eval-dev`, no Gemini judge.
Check = gold (column H, section level) + which #13–#20 mechanisms fired. Raw records:
`data/processed/runs/2026-10-06_targeted_fix20/` (local).

| Case | Gold sections hit | 2026-10-01 run | #20 fired | ⑨ conflicts | Result | Root cause of the miss |
|---|---|---|---|---|---|---|
| dev014 | 1/1 | 1/1 | no | 0 | pass | — |
| dev053 | 1/1 (conclusion "lawful dismissal" consistent with gold s.31(4)) | — | no | 0 | pass | — |
| dev087 | 4/4 | 3/4 | no | 0 | pass (better) | — |
| dev099 | 2/4 (missing 123, 125) | — | no | 0 | **fail** | s.125 retrieval (not retrieved) · s.123 element/drafting: element 8 "agreement in force" unknown → draft dropped s.123 instead of a conditional answer |
| dev102 | 3/3 (s.121(1) kept) | 3/3 | no | 0 | pass | — |
| dev116 | 2/2 | — | no | 0 | pass | — |
| dev120 | 4/5 as citation keys (s.124 in prose only) | — | no | 0 | pass in substance / fail strict | drafting/rendering: s.124 retrieved, selected (p 1.0), written in text, not attached as a citation |
| dev124 | 1/1 | — | no | 0 | pass | — |
| dev150 | 2/2 (s.121 kept) | 2/2 | no | 0 | pass | — |
| dev152 | 3/5 (missing 41, 59) | — | no | 0 | **fail** | s.41 drafting (selected, not cited) · s.59 selection (p 0.1) — pregnancy issue, untouched by staging; severance skipped correctly (no tenure in the question) |
| Huay Khwang | table 5,250 / 42,000 / 47,250 = production | — | no | 0 | **pass** | extractor DID fill `workers` (2 × 10,000, 1 y, same figures) → #18 guard kept one shared view, ม.5 pay items + dates kept |

Strict: 7/10 dev pass, 3 fail (dev099, dev120, dev152). In substance: 8/10. None of the misses comes from a fix20 mechanism
(#20 fired nowhere; no guard conflicts); attribution to "pre-existing" cannot be proven for dev099 / 120 / 152 — no
earlier run of those three exists.

Cost: 95 new Gemini calls, **$2.6586** (estimate was $2.2–2.5). Session total from the LLM cache ≈ $6.45 at project pricing.
Latent #18 risk seen here: a `workers` wage is the raw salary (10,000) — if workers' figures had differed, the per-worker view
would bypass the ม.5 wage base (10,500 here).

## Follow-up (local, no Gemini) — failure analysis and #18 wage base
| Case | Category | Blocker for fix20 |
|---|---|---|
| dev099 s.125 | retrieval coverage (never retrieved) | no |
| dev099 s.123 | gold-vs-output: s.123 needs an agreement/award in force; facts give only a demand two weeks earlier (element 8 unknown) — omission defensible | no |
| dev120 s.124 | drafting/citation: in the text, not attached as a citation; substance correct (severance 200,000 from the calculator) | no |
| dev152 s.41 / s.59 | issue spotting (maternity leave not spotted, issue cap 4 reached) → selection/drafting; real content gap in Q4 | no for fix20 (area untouched); yes for test160 quality |

#18: per-worker view bypassed ม.5 (raw 10,000 instead of 10,500). Fixed with per-worker pay items through the existing
classifier; ambiguous raw wages + shared allowances → no amount with a reason. Fail-first tests reproduced 30,000 (raw)
instead of the ม.5-based amount. Huay Khwang re-checked on the real staging facts (workers filled): base 10,000 + 500 =
10,500, table 5,250 / 42,000, total 47,250. 147 passed · ruff clean · mypy no new errors.
Side effect: the schema/prompt change (extract_facts v8) invalidates every cached extract_facts output — the 4 pilot
cases and the 11 targeted runs are no longer replayable from cache.

## Minimum E2E after #18 v8 — 2026-10-07 (4 regression cases + Huay Khwang)
Gemini: 41 new calls, **$1.2317** (cache entries; 4 cases $0.7241, Huay Khwang $0.5075).
| Case | Result | Note |
|---|---|---|
| 2/2554 Q4 | **partly right** | elements right (9b_lawful met, 9b_outcome met, s.121(1) excluded — no ULP issue this run); guard flagged 2 conflicts, forced revise left 1: preliminary says "ไม่ได้รับความคุ้มครองจากการย้าย … แต่ได้รับความคุ้มครองจากการเลิกจ้างทันทีโดยไม่มีหนังสือเตือน" — same legal effect as the model answer, framing still mixed (drafting; known one-revise limit) |
| 2/2558 Q4 | right | 10293/2546; direct court route; choose one route |
| S/2563 Q1 | right (section s.30 not cited) | per-employee 800,000 / 480,000; นายพิศาล not entitled; annual-leave pay via s.67 |
| 2/2560 Q4 | right | protected under s.31; 10293/2546; no 5061/2533 |
| Huay Khwang | **fail** (E2E) → fixed locally | calculation: extractor moved all pay items onto identical workers, shared facts empty → no wage → no table. Local fix (shared view filled from common worker figures; termination uses it) + fail-first test; recomputed from the run's real facts: base 10,000 + 500 = 10,500, table 5,250 / 42,000, total 47,250. Not yet re-run end to end |
148 passed · ruff clean.

## Huay Khwang E2E after the shared-view fix — 2026-10-07: PASS
Gemini: 12 calls, 2 new (draft + verify; extract → check_elements from cache), **$0.1903**.
extract: 2 identical workers holding all 4 pay items, shared pay items empty → collapsed shared view filled from them ·
classify (ม.5, unchanged): salary 10,000 wage · rent 1,000 not wage · flat fuel 500 wage · reimbursed fuel 500 not wage →
**base 10,000 + 500 = 10,500**, daily 350 · calculate: severance 31,500, notice 5,250, final wage 5,250 · draft: ม.119 applies
to แพรวพราว, not to ซื่อบื้อ; verify 1.0, no conflicts · table: แพรวพราว **5,250** · ซื่อบื้อ **42,000** · total **47,250**
(= production). 148 passed · ruff clean.
Still open (not #18): 2/2554 residual wording conflict after one revise (recorded); 10 targeted questions last run on
extract_facts v7 (not re-run on v8, by decision).
