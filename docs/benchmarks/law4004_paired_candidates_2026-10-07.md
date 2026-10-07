# LAW4004 paired-experiment candidates — production f50f467 vs staging fix20/v8 (2026-10-07)

STATUS: candidate discovery + gold/provenance audit only. No Gemini, no system output looked at. Question and answer text
were fetched in memory (tools/exam/run.py `source_text`, ≥ 1.2 s per request) and not stored; the summaries below are ours.

## Method (fixed before fetching)
Pool: 83 in-scope LAW4004 questions not in the pilot 12. Deterministic triggers (`scratchpad discover.py`, mirrors staging
code): T_LRA = needed sections ∩ {LRA 31, 121, 123} · T_OPEN = staging `OPEN_ENTITLEMENT` regex + end-of-employment
signal · T_WORKERS = ≥ 2 named employees + differing amounts/tenures · T_CALC = money sections + an amount · T_MULTI = ≥ 2
needed sections. Hits: T_LRA 17 · T_OPEN 4 · T_WORKERS 7 · T_CALC 21 · T_MULTI 71. Within a mechanism candidates were read
in md5(exam_id) order; nothing was chosen by expected winner. Each candidate then: mechanism really fires (read) · gold
clear and current-law · near-duplicate check (local bge-m3) vs dev100, pilot 12 and other candidates.
Current-law: LRA s.13/31/121/123/124/125 have one version and no amendment footnote in the DB (krisdika check still advised).
LPA s.118 (5)/(6) changed in 2562 → old-law risk only when tenure ≥ 10 years; s.120 changed in 2562.

## Excluded
| case | reason |
|---|---|
| 1-2566-q4 | near-duplicate of dev102 (cosine 0.986) — dev102 analysed in this session |
| S-2567-q3, 1-2567-q4 | same template and legal point as dev102 (0.841 / 0.824) |
| S-2556-q4 | duplicate of 1-2561-q4 (0.826); md5-first kept |
| 2-2552-q4 | INCONCLUSIVE gold: demotion of leaders during an agreement called "no violation" — ignores a possible s.121(1) |
| 1-2555-q2 | INCONCLUSIVE gold: 180-day severance at 2 y 11 m relies on counting the notice period into tenure (contested) |
| 2-2556-q2 | INCONCLUSIVE: hinges on s.120 "relocation", amended 2562 after the 2556 exam |
| S-2553-q1, 1-2566-q2, S-2554-q1 | T_WORKERS false positive (one employee) |
| other T_ORDER hits | employer's transfer/dismissal order, no employee refusal → #17/#20 does not fire |

## Candidates (12)
Cost per case: production + staging ≈ 2 × $0.25 = **~$0.50** (up to ~$1.0 with revise rounds).
| case_id | mechanism | why it triggers | gold quality | expected (our summary) | expected metric |
|---|---|---|---|---|---|
| 2-2555-q4 | #13 s.31 issue (+ strikes) | transfer of a demand participant during negotiation; strike question | clear, current | (a) no strike until an unsettled dispute; (b) transferee protected (s.31) | issues {s.31, strikes}; s.31/s.34; conclusion |
| 1-2551-q3 | #13 s.31 precondition | transfer during negotiation, but union lacked members (s.15) | clear, nuanced | demand invalid (s.15) → transfer not a s.31 breach | s.13/15/31; conclusion |
| 1-2565-q3 | #13/#16 s.31 + route | urgent transfer abroad of a union committee member during negotiation | clear, current | transfer unlawful (s.31) | s.31; conclusion; ruling not misgrounded |
| 1-2561-q4 | s.31 exceptions, per employee | one absent 4 working days (s.31 exception (4)), one transferred | clear | dismissal allowed; transfer barred | s.31; two outcomes per employee |
| S-2558-q4 | **#17/#20 lawful-order refusal (s.31(3))** | two employees refuse transfers; only one is involved in the demand | clear, current | involved: transfer barred (s.31); not involved: transfer allowed, refusal = disobeying an order | s.31; per-employee outcome; no s.121(1) |
| 1-2563-q4 | #20 must NOT fire | employer act against demand leader during negotiation | clear | violation of s.121(1) | s.121(1) cited; no forbidden-key removal |
| R1-2551-q3 | #20 must NOT fire | workdays cut for a demand participant → she resigns | clear | ULP s.121 (constructive dismissal) | s.13/121; conclusion |
| 2-2553-q4 | s.123 + ULP, #20 must NOT fire | employee representative dismissed 3 months after the agreement | clear | ULP; protected | s.121/123; conclusion |
| S-2560-q2 | **#15 open entitlement** + calc | "จะมีสิทธิได้รับอะไรบ้าง" after dismissal for new machinery | clear, amounts | 420,000 total (s.118 240 d = 320,000 + s.121 60 d + s.122) + annual-leave pay | issues incl. annual_leave; s.118/121/122/67; amounts |
| 1-2554-q2 | **#15** + calc + 2 issues | "เรียกร้องสิทธิอะไรได้อีก" after immediate dismissal | clear, amounts | notice wage 12,000 more; severance 144,000; annual leave 4,800; break-time breach (s.27) | issues incl. annual_leave, hours; amounts |
| S-2551-q2 | **#15** + **#18 split** + calc | two employees, one dismissed (3 y), one resigned; "มีสิทธิได้รับอะไร" | clear, amounts | สาม: notice to 31 May, annual leave 1,600, severance 72,000; สี่: annual leave 1,600, no severance | per-worker calc; workers handling; amounts |
| S-2565-q2 | **#18 split** + s.119 per employee + calc | two employees, different pay (30,000 / 40,000) and tenure (7 / 8 y) | clear, amounts | พิธา: s.119(5) no severance; ธนาธร: 320,000 + 80,000 (s.121) + 40,000 (s.122) = 440,000 | per-worker calc (320,000 deterministic); s.119; amounts |

## Mechanism coverage
| mechanism | cases | target 2–3 met? |
|---|---|---|
| #13/#16 s.31 issue and route | 2-2555-q4, 1-2551-q3, 1-2565-q3, 1-2561-q4 | yes |
| #17/#20 lawful-order refusal (positive) | S-2558-q4 | **no — 1 case** (the only refusal pattern in the pool besides the design case 2/2554 Q4) |
| #20 must not fire (s.121(1) kept) | 1-2563-q4, R1-2551-q3, 2-2553-q4 | yes |
| #15 open entitlement | S-2560-q2, 1-2554-q2, S-2551-q2 | yes |
| #18 per-worker split | S-2551-q2, S-2565-q2 | yes (2) |
| #18 collapse (same figures) | none clean (2-2556-q2 inconclusive) | **no** — only Huay Khwang (design case) |
| calculation | S-2560-q2, 1-2554-q2, S-2551-q2, S-2565-q2 | yes |
| ≥ 2 issues | all except 1-2565-q3, R1-2551-q3 | yes |
Limits: s.121/s.122 have no calculator formula in either version, so those amounts are LLM-written in both; the 12 must
stay acceptance-only (dev100 contains adapted Ram questions, so test160 may as well).

## Paired-run design (for approval later)
production = git worktree at f50f467 (its src, prompts, config, issues.yaml) + dev100_issues.json with the three #13
re-tags reversed (dev053, dev087, dev102) · staging = current tree · same DB, model, .env and question text (fetched at run
time) · separate output folders · outputs shuffled to A/B per case with a seeded key stored apart; Frank (or a lawyer)
reviews blind; my review is provisional and not blind. Metrics and verdict rules as pre-registered in
`acceptance_dev18_2026-10-07.md` §8 (per case: staging better / production better / unchanged / inconclusive; set: PASS
≥ 2 cases materially better and no serious regression · NO IMPROVEMENT · REGRESSION ≥ 1 serious · INCONCLUSIVE ≥ 25%).
Estimated cost: 12 cases ≈ **$6** (≤ ~$12 worst case); a 2–3-per-mechanism subset of 8 ≈ $4.

## Final selection (2026-10-07, no Gemini) — 8 cases, claims scoped
What each mechanism needs to fire: #20 suppression and #17 "lawful order recognised" both need an employee refusing an
order that is lawful by agreement/consent and not obstructive — no independent LAW4004 case has it (S-2558-q4: the
involved employee's order is unlawful under s.31; the other employee is outside s.31/123) → **UNTESTED**. #18 collapse
(same figures) → only Huay Khwang (development) → **UNTESTED**.

| case_id | mechanism | independent? | trigger (md5 pos.) | gold quality | expected measurable change (production → staging) |
|---|---|---|---|---|---|
| S-2560-q2 | #15 open entitlement (+ calc, multi-issue) | yes | T_OPEN (14) | clear, amounts | annual_leave issue / s.67 cited; s.118 amount 320,000 deterministic; s.121/122 LLM-written in both |
| 1-2554-q2 | #15 (+ calc, hours issue) | yes | T_OPEN (21) | clear, amounts | annual_leave + s.27 hours covered; 144,000 deterministic |
| S-2565-q2 | #18 per-worker split (+ s.119 per employee) | yes | T_WORKERS (11) | clear, amounts | per-worker severance (ธนาธร 320,000) instead of pooled/skipped; พิธา s.119(5) |
| S-2551-q2 | #18 split + #15 | yes | read: 2 employees, different status (67) | clear, amounts | per-worker 72,000 for สาม only; annual leave both |
| 2-2555-q4 | #13 s.31 issue / #16 ruling (+ strikes) | yes | T_LRA (10) | clear | s.31 issue structure, transferee protected; ruling not misgrounded |
| 1-2551-q3 | #13 s.31 precondition | yes | T_LRA (34) | clear, nuanced | invalid demand (s.15) → no s.31 breach |
| 2-2553-q4 | guard: #20 must NOT fire (s.123 + ULP) | yes | T_LRA (48) | clear | s.121(1) kept, no forbidden-key removal, 9b sub-elements quiet |
| S-2558-q4 | guard: #17 sub-elements must not call an unlawful order lawful; per employee | yes | T_LRA+refusal (68) | clear | involved employee protected (s.31); other may be transferred; no s.121(1) suppression |
| Huay Khwang | #18 collapse, ม.5, s.119 | **no — development** | — | provisional (Frank) | not evidence of generalisation |
| 2/2554, 2/2558, S/2563, 2/2560 | #13–#20, #15, #18 | **no — development/regression** | — | provisional | regression only |

Mechanism status after the run can only be: #15 (3 cases), #18 split (2), #13/#16 (2), #20/#17 no-false-fire (2), shared
paths (8) → PASS / NO IMPROVEMENT / REGRESSION / INCONCLUSIVE; #20 suppression, #17 positive, #18 collapse → UNTESTED.
Cost per independently validated mechanism: 8 cases ≈ $4 / 4 ≈ **$1.0**; 12 cases ≈ $6 / 4 ≈ $1.5 (the extra four —
1-2565-q3, 1-2561-q4, 1-2563-q4, R1-2551-q3 — only duplicate #13 and guard evidence).

**Executed 2026-10-07 (paired8, frozen):** the review actually performed was a structured A/B review, **non-blind** — not
the reviewer-blind design described above. Result and scope: `docs/results/2026-10-07_paired8_f50f467_vs_fix20v8.md`.
