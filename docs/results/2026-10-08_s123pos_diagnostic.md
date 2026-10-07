# s.123 positive-path diagnostic — 1336/2527 + 822/2536 (2026-10-08) — for audit

Diagnostic evidence only; staging is not compared on totals. Frozen set: `docs/benchmarks/s123pos_freeze_2026-10-08.json`
(file sha256 1b34e96f…; question/expected/taxonomy unchanged by the metadata update). 1159/2531 not run.

## Run record
Outputs are in `data/processed/runs/2026-10-08_s123pos/` (raw states, `run_info.json`, `deterministic.json`, `blind/`,
`key/`).
- **Versions:** production f50f467 vs staging 3bd6b18; the same DB, model and `.env` as p1720.
- **Gemini:** production 18 calls / $0.561 · staging 14 calls / $0.393 · **total $0.954** · 0 errors · all new calls.
- **Analysis:** scratchpad `s123pos_analyse.py`, deterministic only.

## 1336/2527 — positive path (label: source ruling not retrieved / same-principle design ruling retrieved)
| | production | staging |
|---|---|---|
| issues | ULP, disciplinary actions (no s.123 issue) | employee_committee_and_union_protection |
| sections cited | LRA 123 | LRA 123 |
| rulings in state / cited | **1336/2527 (source)** + 2329/2532 / source cited | **2329/2532 only** / none cited |
| outcome vs gold | ✔ dismissal lawful (repeat after written warning) | ✔ dismissal lawful; exception applies |

Staging leaves (C1): **8/8 scored leaves match**:
- **9b_e = met**, with the reason "a clear warning letter, form irrelevant, then repeated";
- dismissed = met, ground = met, 8 = met.

Derived, staging, against the frozen expected states:
- 9b_lawful, 9b and **9b_dismissal_permitted = unknown**; expected met.
- **OUTCOME_DISMISSAL_PERMITTED did not fire.**
- Cause: the LLM gave 9b_b = unknown, an accepted leaf value. 9b_b asks whether "the order" is authorised by the
  agreement or work rules. Here the breach is of the work rules themselves, so the question fits a rule breach poorly
  → **taxonomy semantics (9b_b is order-shaped)**.
- Second cause: **expected-state construction**. Derived states were frozen from the primary leaf values while the
  accept lists allow U (the same pattern as p1720 10251).

Reading:
- The positive-path *leaf* (9b_e) works.
- The marker path to PERMITTED does not complete when 9b_b is unknown.
- The correct final outcome in staging came from the draft. Its evidence was the 9b_e line plus 2329/2532, a
  same-principle design ruling. **It is not evidence that the marker path works.**
- Production reached the same outcome with the source ruling in hand (leakage).

## 822/2536 — exception path + #20 (element level only)
| | production | staging |
|---|---|---|
| issues | s.123 protection, strikes | s.123 protection, strikes |
| sections cited | LRA 123, 34, 52, 99 | LRA 123, 34, 52 |
| rulings in state | 1062/2525, 7362/2559 (**source not retrieved**) | same (source not retrieved) |
| outcome vs gold (all nine may be dismissed with permission) | 8 of 9 permitted; "the ninth cannot be dismissed" ✘ | same ✘ |

Staging leaves:
- **9 = met** (the stoppage in breach of the CBA, and the statement);
- **9b_dismissed = not_met** (permission request only);
- 3 = not_met; 8 = met; 9b_a, 9b_b, 9b_d = unknown (accepted; non-scored or accepted).

Derived: no dismissal outcome (as pre-registered). 9b_lawful = unknown (expected met: the same accept/derived artifact).

**#20 at element level:**
- Element 3 = not_met, so the pre-registered condition (element 3 called met) did not occur.
- defeated_by did **not** fire and no key was forbidden.
- This is not a misfire; **the #20 positive path is still untested.**

**The "ninth employee" error is a question-construction defect (mine), not a system error:**
- The frozen question says "eight of them" made the statement and "seven of them" joined the stoppage, without saying
  that the two groups together cover all nine.
- In the judgment they do (respondents 1, 3–8 and 1–3, 6–9).
- Both versions read it as one employee doing neither. **The question as frozen does not support the gold's "all
  nine".**

## Answers to the interpretation criteria
1. **1336:** 9b_e works at leaf level. `9b_e → OUTCOME_DISMISSAL_PERMITTED` did **not** complete, because 9b_b came
   out unknown. The correct outcome cannot be attributed to the marker path (2329/2532 was in the draft's context).
2. **822:** the exception path works at element level (9 = met, no dismissal outcome). The #20 guard was not exercised
   (element 3 = not_met). The final outcome is affected by the question-construction defect.
3. **No claim that staging is better than production.** Both cases give diagnostic evidence only. Production matched
   staging on both final outcomes.

## Open items (no change made)
- (a) 9b_b is order-shaped; work-rule breaches need a fitting leaf or a rule for "the breached norm *is* the work
  rule". This is a taxonomy question; not changed.
- (b) Expected-state construction: derived expectations should hold across all accepted leaf variants, or the accept
  lists should be narrowed. This affects p1720 10251 and both cases here; nothing re-frozen.
- (c) 822 question defect: the group overlap is missing. Fix the question and re-freeze only with approval.
- (d) #20 positive firing: still no observation.
