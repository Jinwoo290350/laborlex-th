# s.123 positive-path discovery (2026-10-08) — local only, no Gemini, nothing frozen

**Goal.** Find 2–3 clean cases for the exception / permitted side of s.123 (#21), plus a contrast case.

**Independence rule.** Every ruling read in the L1 legal audit (`docs/design/2026-10-07_legal_audit_L1_L2.md`) informed
the #21 design, so it is *design-informing*, not independent evidence. Excluded on that ground:
2329/2532, 3631/2529, 2211/2523, 5596/2534, 1818/2527, 2691-2694/2523, 768/2533, ร 1559/2563, ร 142/2566, 4168/2530,
2747/2525, 3943/2557, 7564/2544, 3043/2541, 8311/2559. The p1720 sources are excluded too.

**Search.** All 3,591 rulings; filter = LRA cited + s.123 cited + CBA-in-force wording + warning or "serious" wording,
minus the excluded set → 9 rulings. Full text read for all 9 (822/2536 had been read earlier).
- ร 2503/2565 is excluded: it is the same dismissal (same parties and amounts) as ร 142/2566, which is in the design set.
- 3771/2529 is excluded: a procedural point only.

**Near-duplicates.** Max cosine against dev100 ≤ 0.745 and against p1720 ≤ 0.727; none appears in dev100 or p1720.
**Leakage.** Every candidate is in the Legal Index. The rank must be measured on the frozen question, so it is not
measured yet. The linked sections decide whether `retrieve_cases` (k = 1, section filter) can return the ruling.

## Recommended clean candidates
| | **1336/2527** (ฎีกา) | **822/2536** (ฎีกา) | **1159/2531** (ฎีกา) |
|---|---|---|---|
| path | valid written warning (+ serious) → **dismissal permitted** (post-dismissal) | serious misconduct / exceptions (2), (5) → **permission to dismiss granted** (pre-dismissal, s.52) | no written warning, not serious → **permission refused; warning required first** (contrast) |
| facts (court's findings) | employer dismissed the employee during a CBA; earlier written letter, not on the usual form but clearly warning and saying the employee would be punished if it happened again; repeated breach of the work rules; wilful damage | employee-committee members (union president, vice-president, officers) while a CBA is in force; wrote and circulated a statement accusing the employer of bad faith and union-busting; some also led a stoppage during the CBA without a demand or notice | employee-committee member; CBA with the union in force; 28 days' sick leave in a year without being sick (false sick reports); the work rules classify false sick reports as category "ค": 1st offence = final written warning, 2nd = dismissal; no prior written warning |
| legal ground | s.123(3): a letter that clearly warns counts as a written warning whatever its form; repeat after warning + wilful damage (serious) → dismissal fair, not a ULP | s.123(2) wilful damage (serious under the CBA-based rules) and (5) inciting a stoppage in breach of the CBA → s.52 permission granted | the work rules (a CBA term) require a written warning first, so dismissal is not allowed |
| expected outcome | dismissal permitted; not a ULP | employer may dismiss with the court's permission (granted) | permission refused: warn first |
| relevant elements (draft) | 8 met (U accepted) · 9 met ((2)) · 9b_a met · 9b_b met (work rules) · 9b_d not_met · **9b_e met** · 9b_dismissed met · 9b_ground_misconduct met → 9b met, **OUTCOME_DISMISSAL_PERMITTED** | 8 met · **9 met** ((2), (5)) · 9b_e met (serious) · 9b_dismissed **not_met** (permission request) · ground_misconduct met → exception met; no post-dismissal outcome (only exception status + s.52) | 8 met · 9 not_met · 9b_a met · 9b_b met (rule) · 9b_d not_met · **9b_e not_met** · 9b_dismissed not_met · ground_misconduct met → **OUTCOME_WARNING_REQUIRED** |
| linked sections (leakage) | LRA 123, so it can surface for the s.123 issue | LRA 123, 52, so it can surface | **LCA 52 only** (link looks wrong: the ruling is about LRA s.52). A section filter on LRA sections may not return it, so the leakage risk is lower; measure it |
| why clean | the court decides the s.123 exception itself; the warning point is explicit; no allegation-only element | the court finds the facts (wilful damage, inciting) and grants permission under s.123/52; rich facts | the court finds the false sick reports and the missing warning; the result follows directly |
| caveats | **thin facts**: the judgment does not describe the breach itself, so the question must not invent it; serious + warning both present (two routes to "permitted") | the outcome comes through element 9, not the lawful-order path; also touches s.99 (no immunity) | the court reasons through s.52 + the work rules, not s.123(3) by name. The LC framed it as incapacity; the SC treated it as misconduct |

## Diagnostic (not clean; listed for audit)
| ruling | why diagnostic |
|---|---|
| 7043-7047/2543 | serious misconduct + wilful damage during a CBA → the exception is met, **but permission is refused out of mercy** (the employer breached the CBA first); wages cut instead. Tests that "exception met" is not read as "dismissal granted"; the system has no discretion element |
| 172/2533, 9049/2559 | dismissal for "incapacity" because of frequent *approved* leave → ULP. The court says this is not a necessity outside (1)–(5). Our `9b_ground_misconduct` may come out not_met → prohibited = not_met, against the court. **Exposes the U3 boundary** (misconduct vs necessity) |
| 3101-3102/2523 | dismissal for leaving the sales round; the court says it is not dishonesty (1), only abandonment (4) needing 3 days → ULP; warning/seriousness facts missing |

## Not done (needs approval)
- Freezing facts-only questions.
- Pre-registering expected states.
- Measuring the source-ruling rank on the frozen questions.
- Any Gemini run.
