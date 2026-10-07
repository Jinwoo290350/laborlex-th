# Local legal audit L1 / L2 (2026-10-07) — statute (DB) + rulings in the Legal Index, full judgments read

Local only. No Gemini, and no change to code, issues.yaml, expected JSON or manifests.
Search (scratchpad `l12_hits.json`): every ruling whose full text cites the LRA together with s.123(3)/s.31(3) → 13;
s.31 + transfer + demand → 10. All 23 were read in full, plus 3043/2541, 8311/2559 and 768/2533. The 2/2554 Q4
question and model answer were read in memory only (A in v2).
Statute (DB): s.123 bars **dismissal** of covered persons while a CBA/award is in force, except (1)–(5).
s.31 bars **dismissal or transfer** of involved persons while a s.13 demand is in negotiation/mediation/arbitration,
except (1)–(4).

## 1. L1 — meaning of the s.123 outcome after a dismissal
**Conclusion.** s.123 is a prohibition with exceptions. When the employer's ground for dismissal is the employee's
misconduct and no exception applies, the dismissal violates s.123 and is a ULP: the employee is protected.
- No exception means: a non-serious breach without a valid prior written warning, an expired or unrelated warning, or a
  serious-breach claim that fails.
- No ruling found calls the employee "not protected" in that situation.
- The 2/2554 key's label ("ไม่ได้รับการคุ้มครอง … แต่ให้ออกทันทีไม่ได้") is **not supported** by the case law. Its
  operative result (the immediate dismissal is not allowed) is.

| ruling | facts → holding | supports |
|---|---|---|
| 768/2533 (ฎีกา) | lawful order breached, not serious, no written warning, CBA in force → ULP under s.123; LRC may reinstate | PROHIBITED = protected |
| ร 1559/2563 (อุทธรณ์ชำนัญพิเศษ) | rule breach not serious, no written warning → "ไม่เข้าข้อยกเว้น ม.123(3) … การเลิกจ้าง … เป็นการฝ่าฝืน ม.123 … การกระทำอันไม่เป็นธรรม" | same |
| ร 142/2566 | the last absence was illness, so not a repeat of the warned misconduct → not within 123(3) → ULP | warning must cover the same kind of breach |
| 4168/2530 | written warnings 7+ years old have lapsed → ULP | a warning can expire |
| 2747/2525 | remanded to decide whether a written warning was given | the warning is decisive |
| 2329/2532 | written warning given before the CBA still counts; repeat breach → dismissal allowed | PERMITTED |
| 3631/2529, 2211/2523 | repeat breach after written warning → 123(3), not a ULP | PERMITTED |
| 5596/2534, 1818/2527, 2691-2694/2523 | serious breach → no warning needed, not a ULP | PERMITTED (serious) |
| 3943/2557 | no CBA in force → s.123 not engaged | element 8 = coverage |
| 3043/2541 | s.123 does not bar a dismissal for an **unavoidable business necessity** outside (1)–(5); here the necessity was not shown → ULP | non-misconduct route |
| 8311/2559 | a s.123 violation requires a motive to obstruct union activity / CBA benefits; probation failure → no ULP | non-misconduct route (see tension) |

**Tension (stated, not forced).**
- 8311/2559 says, in general terms, that a s.123 violation requires an obstructive motive.
- 768/2533, ร 1559/2563 and ร 142/2566 find a ULP for misconduct dismissals without examining motive.
- The rulings separate by the ground of dismissal:
  - misconduct ground → the (1)–(5) exceptions are applied strictly;
  - business-necessity or probation ground → necessity/motive test (3043, 8311).
- No ruling in the DB states this split expressly, so it is an inference.

**Derivation (s.123):**
- `9b_dismissed` (fact): the employer has dismissed. A s.52 permission request counts as not dismissed.
- **new** `9b_ground_misconduct` (fact): the employer's stated ground is the employee's own conduct, not business necessity or probation.
- `9b_e` question to state: a **valid** written warning (same kind of breach, not stale: 2329, 4168, ร 142) or a serious breach.
- `9b` (exception (3)) = all[9b_lawful, 9b_e].
- `9b_warning_required` = all[8, 9b_lawful, ¬9b_e].
  - Meaning: dismissal **on this ground** needs a valid written warning and a repeat breach first, unless serious.
  - It does not decide a dismissal that already happened.
- `9b_dismissal_prohibited` = all[8, 9b_dismissed, 9b_ground_misconduct, ¬9b, ¬9].
  - Text: "การเลิกจ้างไม่เข้าข้อยกเว้นตาม ม.123 จึงต้องห้าม เป็นการกระทำอันไม่เป็นธรรม ลูกจ้างได้รับความคุ้มครอง".
  - Definitive.
- `9b_dismissal_permitted` = all[8, 9b_dismissed, any[9b, 9]].
  - Text: "เข้าข้อยกเว้นตาม ม.123 ไม่เป็นการกระทำอันไม่เป็นธรรม".
  - s.52 permission for committee members and LPA severance are separate questions.
- Ground = necessity/probation (`9b_ground_misconduct` = not_met): prohibited = not_met, permitted = not_met.
  - Render the unmodelled test as a condition: "ต้องเป็นความจำเป็นที่ไม่อาจหลีกเลี่ยงและไม่ใช่การกลั่นแกล้ง (3043/2541, 8311/2559)".

Simulated with the frozen leaves (`9b_ground_misconduct` = met where the ground is the breach):
| case | prohibited / permitted |
|---|---|
| 768 | met / not_met |
| 2/2554 | met / not_met |
| 3211 | U / U |
| 2563-65 | U / U |
| 10251, 2911, 2222 | not_met / not_met (not dismissed) |

## 2. L2 — s.31 and transfers; is `5_lawful` variant A right?
**Conclusion.** Variant A ("agreement authority does not make the barred transfer a lawful order; consent does") is
**not correct as a general rule**. The case law on transfers during negotiation **conflicts**:

| line | rulings | holding |
|---|---|---|
| strict | 2490/2526 (dismissal), 3822/2528 (transfer) | during negotiation the employer may not dismiss/transfer **for any reason** outside (1)–(4), even one unrelated to the demand. A CBA clause authorising the dismissal (2490) or a statute authorising restructuring (3822) does not override s.31. |
| flexible | 8137-8138/2543 (transfer), 2476/2544 (dismissal) | s.31 does not bar a transfer/dismissal for another **necessary and proper** reason that is **not harassment**. Examples: a transfer to prevent violence or routine rotation (8137); a dismissal for losses with s.52 permission sought before the demand (2476). |

Other rulings:
- **Scope of "transfer":** a promotion is not a s.31 transfer, including one the employee competed for (2392/2526, 2234/2528).
- **Demand status:**
  - a demand that has lapsed by conduct → no s.31 protection (3815/2529);
  - a transfer ordered before the demand → not barred (2222/2538);
  - forum: s.31 = court directly, s.121 = LRC; one route only (10293/2546).
- **Consent:** no ruling in the DB decides a transfer *with* the employee's consent during negotiation. 2392 (a promotion he applied for) is only indirect. → unknown.
- **s.123 vs s.31:**
  - s.123 bars only dismissal, so under s.123 a transfer can be a lawful order whose refusal feeds exception (3). Examples: the 2/2554 key; the work-rule transfer in 2911 (s.52).
  - Under s.31 the transfer is itself the regulated act. Its lawfulness is decided by s.31 itself: strict line → only (1)–(4); flexible line → necessity and no harassment. CBA authority (5_b) is not the test in either line.

Variant A against the two lines:
- It matches the strict line on agreement authority (2490).
- It misses the flexible line's test (necessity + no harassment).
- Its consent rule has no authority in the DB.

**Recommended derivation:** when `5_order_is_act` = met, set `5_lawful` = **unknown**. Do not derive it from 5_b. The
rendered condition names both lines: strict, transfer barred unless (1)–(4); flexible, allowed only if necessary and not
harassment.
`5_act_prohibited` stays conditional. Its unmodelled prerequisites are demand validity/status and, for transfers, the
strict/flexible line.

## 3. What is still UNKNOWN
| # | open point | why |
|---|---|---|
| U1 | s.31: strict vs flexible line | rulings conflict (2490, 3822 vs 8137, 2476); no reconciling ruling in the DB |
| U2 | s.31: effect of employee consent to a transfer | no ruling in the DB |
| U3 | s.123: exact boundary of the necessity/motive route | 8311's general motive statement vs 768 / ร 1559 / ร 142; reconciled by ground type only by inference |
| U4 | s.31(3): whether the warning requirement applies before a **transfer** | no ruling in the set |
| U5 | per-employee element evaluation (S-2558-q4) | design scope |

## 4. Recommendation: lock design v2 as follows
1. **s.123 — lock.** L1 is answered by consistent case law:
   - markers;
   - `9b_dismissed` and the new `9b_ground_misconduct`;
   - the derivations in §1;
   - PROHIBITED text = "ต้องห้าม … การกระทำอันไม่เป็นธรรม … ได้รับความคุ้มครอง", definitive;
   - no phrase guard.
   2/2554 stays development/regression. Score it on the operative result ("immediate dismissal not allowed"), not on
   the key's label, and record the label as contrary to the case law.
2. **768/2533** can return to the PASS denominator after the redesign is implemented and the expected states are
   re-frozen (new leaves `9b_dismissed` = met, `9b_ground_misconduct` = met, `9` = not_met). L1 no longer blocks it.
3. **s.31 — lock the structure, not the doctrine.**
   - `5_order_is_act` = met ⇒ `5_lawful` = unknown (replaces variant A).
   - `5_act_prohibited` stays conditional with U1 and demand status named.
   - No guards.
   - 1-2551-q3 stays the known adversarial case.
4. **Fixtures for the new tests** come from the rulings above (ids and statuses only):
   - L1 rulings → prohibited / permitted / necessity-unknown;
   - strict and flexible s.31 rulings → conditional;
   - promotion rulings → element 3 not_met.
5. **Decisions:** #21 cites these rulings and records U1–U5 as open; #20 (2)/(3) superseded.
