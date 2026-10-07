# DRAFT — Decision #21 (not yet in docs/decisions.md; for Frank's audit)

## Row text proposed for `docs/decisions.md`
| 21 | **Outcome elements v2 for s.123 (L1); s.31 outcome pending (L2)** (staging) |
**Decision.** s.123 outcomes are separated by meaning. Each carries a structured marker. The phrase-based outcome guard
of #20 is removed.

New and changed elements (issue `employee_committee_and_union_protection`):
- **Element 8:** asks protection only (CBA/award in force + covered person); no longer "employer has dismissed".
- **`9b_e`:** a *valid* written warning (same kind of breach, still in effect, repeated) or a serious breach.
- **New factual leaves:**
  - `9b_dismissed`: dismissal already happened; a s.52 permission request = not_met.
  - `9b_ground_misconduct`: ground = the employee's own conduct, not business necessity or probation.
- **Derived outcomes** (all `certainty: definitive`, `guard: none`):

  | element | derive | marker |
  |---|---|---|
  | `9b_warning_required` | all[8, 9b_lawful, ¬9b_e] | OUTCOME_WARNING_REQUIRED |
  | `9b_dismissal_prohibited` | all[8, 9b_dismissed, 9b_ground_misconduct, ¬9b, ¬9] | OUTCOME_DISMISSAL_PROHIBITED |
  | `9b_dismissal_permitted` | all[8, 9b_dismissed, any[9b, 9]] | OUTCOME_DISMISSAL_PERMITTED |

  The prohibited statement reads: ต้องห้าม, การกระทำอันไม่เป็นธรรม, ลูกจ้างได้รับความคุ้มครอง.
- **Removed:** `9b_outcome`.

Code:
- The renderer selects outcomes by marker.
- `_says` and `outcome_contradicted` are removed.
- #20 `defeated_by` and the forbidden-citation guard are unchanged.

**s.31.** No semantic change in this round:
- `5_outcome` stays with the same derive and the same display (shown only when met), tagged `legacy_outcome: pending_L2`.
- Its phrase guard is gone with the global removal.

**Basis — L1** comes from a local full-judgment audit of the Legal Index rulings
(`docs/design/2026-10-07_legal_audit_L1_L2.md`):
- **Misconduct dismissal during a CBA with no exception → violates s.123, ULP, employee protected:**
  - 768/2533
  - ร 1559/2563
  - ร 142/2566 (the warned breach must be the same kind)
  - 4168/2530 (a stale warning lapses)
  - 2747/2525
- **Valid warning or serious breach → permitted:** 2329/2532, 3631/2529, 2211/2523, 5596/2534, 1818/2527, 2691-2694/2523.
- **Coverage requires a CBA in force:** 3943/2557.
- **Business necessity / probation is a separate, unmodelled route:** 3043/2541, 8311/2559.
  - Tension recorded: 8311 states a general motive requirement, while 768 and ร 1559 find a ULP without examining motive.
  - The split by ground is an inference.

**2/2554 Q4 (development case).**
- The model answer's label "นายอุทิศไม่ได้รับการคุ้มครอง" (while also holding that the immediate termination is not
  allowed without a written warning) departs from the case law above.
- The system follows the legal outcome of the case law (dismissal prohibited / employee protected), not the gold's
  wording. The wording is recorded as a source/gold discrepancy.
- Regression tests score 2/2554 on the operative result.

**Open (L2, not decided).** s.31 transfers during negotiation have conflicting lines:
- strict: 2490/2526, 3822/2528;
- flexible: 8137-8138/2543, 2476/2544.

Also open:
- consent has no authority in the DB;
- whether the s.31(3) warning applies before a transfer;
- per-employee evaluation.

`5_order_is_act`, the s.31 markers and `unknown_if` are not implemented. The s.31 fail-first tests are kept as
`xfail(strict=True)`.

**Supersedes.** #20 parts (2) and (3), i.e. the outcome element text and the phrase guard. #20 parts (1) and (4)
(`defeated_by`, strip forbidden keys) stay.

**Evidence.**
- `tests/unit/test_outcome_v2.py`
- rewritten `tests/regression/test_2554_consistency.py`
- `tests/regression/test_pilot_guards.py` (unchanged assertions)
- `pytest tests tools`: 201 passed, 8 skipped, 7 xfailed
- no Gemini run

**Cost note.** The s.123 check_elements questions changed (8, 9b_e, 2 new leaves), so cached runs of s.123 cases
miss. | reviewed_by: draft (Frank) |

## Not part of #21 (separate approvals)
- Re-freezing `docs/benchmarks/p1720_expected_DRAFT_2026-10-07.json`. Proposal:
  `scratchpad/p1720_expected_PROPOSED.json`, diff `scratchpad/p1720_refreeze.diff`; the file itself is unchanged.
- Any Gemini run, manifest, L2 implementation, merge/push.
