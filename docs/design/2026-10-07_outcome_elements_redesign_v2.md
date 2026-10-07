# Outcome-element redesign v2 — design audit only (2026-10-07)

Supersedes the proposal part of `2026-10-07_outcome_elements_redesign.md`; §1 there (usage inventory) still holds.
Nothing changed: no code, issues.yaml, expected JSON or manifest edits, and no Gemini. Simulation: scratchpad
`design_outcome2.py` (staging `combine()`).
Frank's decisions applied: no validity-of-demand element this round · no keyword guard for `*_prohibited` · an outcome
whose prerequisites are not all modelled is conditional/UNKNOWN, never definitive · `9b_dismissed` added as a factual
leaf · markers instead of phrase guards.

## A. Source check: 2/2554 Q4 — **UNRESOLVED**
The exam question and model answer were fetched in memory and not stored.
- Correction to my earlier note: the employer **had already** terminated him with immediate effect. It was not an
  advisory question, so `9b_dismissed = met`. The fact pattern is the same as 768: dismissed, lawful order refused, no
  written warning.
- The model answer:
  - sets out the s.123 frame: the employee is protected, and dismissal during the agreement is a ULP unless (1)–(5);
  - says the refusal of the lawful transfer order makes him "not protected under s.123(3)";
  - also says the immediate termination is not allowed and a written warning is required first.
- It does not separate "the refusal is not protected" from "the dismissal is not protected". It uses one label ("not
  protected") for a result that its own frame and the Supreme Court in 768 call a prohibited dismissal.
→ **UNRESOLVED** for the legal reviewer. Expected states for 2/2554 are not changed. The fixture leaves are unchanged;
only the derived outcome would differ.

## B. s.31 audit
| question | finding |
|---|---|
| protected act | s.31 (DB text) bars **dismissal or transfer** of an involved employee while a s.13 demand is in negotiation/mediation/arbitration; exceptions (1)–(4) are about the employee's conduct. s.123 bars **dismissal only**, so a transfer can be a lawful order under s.123 (2/2554), but under s.31 the transfer may itself be the barred act. |
| do 5_b / 5_d cover both? | No. 5_b asks whether the order is authorised by agreement/rules, and 5_d whether it was issued to obstruct. Neither asks whether **the refused order is itself the transfer s.31 bars** (issued during the negotiation). Today a CBA-authorised transfer ordered mid-negotiation would derive 5_lawful = met. |
| S-2558-q4 | Two employees. For the involved employee, the transfer during the demand is barred by s.31, so the refusal is not a breach of a lawful order. The other employee is outside s.31 (not involved), so the transfer is allowed and the refusal is disobedience. It needs a new factual leaf `5_order_is_act` (met for the involved employee), and **per-employee element evaluation**, which the element layer does not have (#18 splits calculations only) → out of scope; noted. |
| dev102 vs 1-2551-q3 | Both: transfer during negotiation, no refusal, elements 1–3 met. dev102: the demand is valid, so the transfer is barred (gold s.31 + 121(1)). 1-2551-q3: the union lacked members (s.15), so the demand is invalid and s.31 is not engaged. The only difference is **demand validity, which is not modelled** → `5_act_prohibited` can never be definitive; it is always rendered conditional. 1-2551-q3 stays a known adversarial regression case. |
| timing (2222/2538) | Order issued before the demand → `5_order_is_act = not_met` and element 3 not_met; s.31 not engaged. |

## C. Proposed final schema
New element field (replaces `forbid_phrases`):
```yaml
outcome:
  marker: OUTCOME_WARNING_REQUIRED | OUTCOME_DISMISSAL_PROHIBITED | OUTCOME_DISMISSAL_PERMITTED | OUTCOME_ACT_PROHIBITED | OUTCOME_ACT_PERMITTED
  certainty: definitive | conditional        # conditional when a prerequisite is not modelled
  unmodelled_prerequisites: [<Thai condition>] # rendered as "ถ้า …" before the statement
  statement: <Thai text shown to the draft when met>
  guard: none | marker                      # v1: none for every *_PROHIBITED (Frank)
```
- Renderer (`_elements_block`): selects outcome elements by `outcome.marker`, not by "has forbid_phrases". It prints
  `[MARKER | certainty | ถ้า …] statement`, only when met.
- Guard: no Thai-substring check. If a guard is ever enabled, the draft echoes markers in a structured field
  (`Issue.outcome_markers`) and the system compares markers; v1 only records mismatches in the trace (diagnostic, no
  forced revise). The #20 `forbidden_citation` guard is unchanged.

### s.123 (`employee_committee_and_union_protection`)
| id | kind | derive / question | exact meaning |
|---|---|---|---|
| 8 | leaf (reworded) | "ขณะเกิดเหตุ ข้อตกลงเกี่ยวกับสภาพการจ้างหรือคำชี้ขาดมีผลใช้บังคับ และลูกจ้างเป็นบุคคลตาม ม.123 ซึ่งเกี่ยวข้องกับข้อเรียกร้อง" | coverage only; it no longer contains "นายจ้างได้เลิกจ้าง" |
| 9 | leaf (unchanged) | exceptions (1)(2)(4)(5) | another exception applies |
| 9b_dismissed | **new leaf** | "นายจ้างได้เลิกจ้างแล้วตามข้อเท็จจริงหรือไม่ (ไม่ใช่ถามว่าจะเลิกจ้างได้หรือไม่)" | fact only; permission requested under s.52 = not_met |
| 9b_a–9b_e, 9b_lawful | unchanged | — | as today |
| 9b | derived (unchanged, labelled "exception") | all[9b_lawful, 9b_e] | exception (3) applies |
| 9b_warning_required | derived, OUTCOME_WARNING_REQUIRED, definitive | all[8, 9b_lawful, ¬9b_e] | a lawful-order breach, not serious and not yet warned in writing: dismissal on **this ground** needs a written warning first. It says nothing about whether a dismissal that already happened is lawful. |
| 9b_dismissal_prohibited | derived, OUTCOME_DISMISSAL_PROHIBITED, definitive (all prerequisites modelled), guard none | all[8, 9b_dismissed, ¬9b, ¬9] | the dismissal that happened is barred by s.123 → protected |
| 9b_dismissal_permitted | derived, OUTCOME_DISMISSAL_PERMITTED, definitive, guard none (v1) | all[8, 9b_dismissed, any[9b, 9]] | an exception applies → s.123 does not bar this dismissal |
| 9b_outcome | **removed** | — | — |

### s.31 (`dispute_protection_s31`)
| id | kind | derive / question | exact meaning |
|---|---|---|---|
| 1, 2, 4 | leaves (unchanged) | — | demand notified (validity **not** modelled) · still in negotiation · exceptions (1)(2)(4) |
| 3 | leaf (reworded) | "นายจ้างได้เลิกจ้างหรือโยกย้ายบุคคลซึ่งเกี่ยวข้องกับข้อเรียกร้อง ในระหว่างนั้นแล้วหรือไม่ (ระบุว่าเลิกจ้างหรือโยกย้าย)" | the act occurred (fact) |
| 5_order_is_act | **new leaf** | "คำสั่งที่ลูกจ้างไม่ปฏิบัติตามคือคำสั่งโยกย้ายที่ออกในระหว่างข้อเรียกร้องยังอยู่ในการเจรจาเองหรือไม่" | fact only |
| 5_lawful | derived (changed) | all[5_a, ¬5_d, any[5_c, all[5_b, ¬5_order_is_act]]] — **variant A, legal question L2** | lawful-order breach; agreement authority does not cover the barred transfer itself; consent does |
| 5 | derived ("exception") | all[5_lawful, 5_e] | exception (3) applies |
| 5_warning_required | derived, OUTCOME_WARNING_REQUIRED | all[2, 5_lawful, ¬5_e] | as 9b_warning_required |
| 5_act_prohibited | derived, OUTCOME_ACT_PROHIBITED, **conditional**, guard none | all[1, 2, 3, ¬5, ¬4]; unmodelled_prerequisites: ["ข้อเรียกร้องเป็นข้อเรียกร้องที่ชอบตาม ม.13 (รวมถึงสัดส่วน/สมาชิกตามที่กฎหมายกำหนด)"] | "ถ้าข้อเรียกร้องชอบด้วยกฎหมาย การเลิกจ้าง/โยกย้ายนี้ต้องห้ามตาม ม.31" — never definitive |
| 5_act_permitted | derived, OUTCOME_ACT_PERMITTED, definitive, guard none | all[1, 2, 3, any[5, 4]] | an exception applies → s.31 does not bar the act |
| 5_outcome | **removed** | — | — |

## D. Mappings (simulated; (P) = proposed leaf value, needs approval)
s.123: exception (9b) / warning_required / dismissal_prohibited / dismissal_permitted
| case | key leaves | old 9b / 9b_outcome | new | vs gold |
|---|---|---|---|---|
| 2/2554 Q4 | fixture; dismissed = met (source) | not_met / met ("not protected") | not_met / met / **met** / not_met | operative result = key (immediate dismissal not allowed); label ≠ key's "not protected" → **UNRESOLVED (A)** |
| 768/2533 | frozen; 9 = not_met (P), dismissed = met (P) | not_met / met | not_met / met / **met** / not_met | = court (ULP, protected) |
| 768, 9b_b = U | | not_met / U | not_met / U / **met** / not_met | robust to the caveat |
| 10251/2551 | frozen; dismissed = not_met (s.52 request) | met / not_met | **met** / not_met / not_met / not_met | exception applies; s.52 decides |
| 2911/2528 | frozen; 9 = met (P), dismissed = not_met | U / U | U / U / not_met / not_met | s.52 + abandonment |
| 3211/2545 | frozen; 9 = not_met (P) | U / not_met | U / not_met / U / U | conditional (LIMITATION stays in 9b_b) |
| 2222/2538 | frozen; dismissed = not_met | U / not_met | U / not_met / not_met / not_met | s.52 decides |
| 2563-2565/2552 | frozen; 9 = not_met (P) | U / not_met | U / not_met / U / U | conditional on purpose |
| 2-2553-q4 | paired8 staging run; dismissed = met (P) | not_met / not_met | not_met / not_met / **met** / not_met | = gold (protected / ULP); new outcome stated |

s.31 (former `5_outcome` cases): exception (5) / warning_required / act_prohibited (conditional) / act_permitted
| case | key leaves | old 5 / 5_outcome | new | vs gold |
|---|---|---|---|---|
| dev102 pattern | test fixture; no refusal | not_met / not_met | not_met / not_met / **met (cond.)** / not_met | gold s.31 + 121(1) ✔ (conditional) |
| 1-2551-q3 | paired8 run; no refusal | not_met / U | not_met / U / **met (cond.)** / not_met | gold: demand invalid → no breach. A conditional statement is compatible; it stays a known adversarial case |
| S-2558-q4, involved | paired8 run (2 = U); order_is_act = met (P) | not_met / U | not_met / not_met / U / not_met | with 2 = met: act_prohibited met (cond.) ✔ — but per-employee evaluation is missing |
| 2/2560 Q4 | fixture fix20 | U / U | U / U / U / U | unchanged; protection left to the draft |
| 2-2555-q4 | paired8 run | U / U | U / U / U / U | unchanged |
| 3211 s.31 side | frozen; order_is_act = not_met (P) | U / not_met | U / not_met / U / U | ✔ |
| 2222 s.31 side | frozen; element 3 = not_met | U / not_met | U / not_met / not_met / not_met | ✔ s.31 not engaged |
Huay Khwang: no s.123/s.31 elements → n/a.

## E. Unresolved legal questions (for the legal reviewer)
- **L1** 2/2554 key vs 768: after a dismissal without the required warning, is the employee "protected" (768, s.123
  frame) or "not protected but cannot be dismissed at once" (key)? This decides the wording of
  OUTCOME_DISMISSAL_PROHIBITED and whether 2/2554 is scored against the label or the operative result.
- **L2** s.31: is a transfer authorised by a CBA but ordered during the negotiation a "lawful order" whose refusal is
  exception (3)? Does employee consent change it? (variant A assumes: agreement no, consent yes)
- **L3** s.31 exceptions apply to transfers too; does exception (3)'s warning requirement apply before a *transfer*,
  or only before dismissal? (affects 5_warning_required)
- **L4** S-2558-q4: should element evaluation be per employee? (design scope, not purely legal)
- **L5** 768-type cases: is "not serious" (9b_e) for the court alone? The frozen leaf follows the court; an exam may
  not state it.

## F. Tests to add (fail-first, before implementation)
1. **Schema:** every element with `outcome` has a marker from the allowed set; certainty is set; every `*_PROHIBITED` has `guard: none`; `OUTCOME_ACT_PROHIBITED` is `conditional` with ≥ 1 unmodelled prerequisite.
2. **Derivation table:** each row in §D as a parametrised test, using fixture / frozen leaves only.
3. **768 robustness:** with `9b_b = U`, `9b_dismissal_prohibited` is still met.
4. **Renderer:**
   - outcome lines are selected by marker;
   - a conditional outcome is printed with "ถ้า …";
   - an outcome that is not met is not printed;
   - the 2/2560 fixture still shows no outcome.
5. **No phrase guard:** the 768 court wording ("ได้รับความคุ้มครอง … การกระทำอันไม่เป็นธรรม") produces no conflict; the old `outcome_contradicted` kind is gone.
6. **#20 unchanged:** `forbidden_citation` for the 2/2554 fixture still fires; 2/2560 and dev102 keep LRA2518:121:1:(1).
7. **1-2551-q3 (adversarial):** act_prohibited is met but conditional; the rendered line contains the demand-validity condition.
8. **Existing tests to rewrite (not delete):**
   - `test_2554_consistency.py`:
     - l.36–41: wording;
     - l.51: `9b_outcome` → new ids;
     - l.61–74: the guard-shape tests become marker/diagnostic tests;
     - l.141.
   - `test_pilot_guards.py`: l.41, l.74.
   - Outcome assertions for 2/2554 stay pending L1.

## G. Decisions to update (after approval)
- **New row #21** "outcome elements v2":
  - markers, certainty, `9b_dismissed`, `5_order_is_act`;
  - element 8 and element 3 rewording;
  - `9b_outcome` / `5_outcome` removed;
  - no phrase guard;
  - source of each choice (768, 2/2554 source check, s.31 audit) and the open points L1–L5.
- **#20:** mark parts (2) and (3) (outcome element text and phrase guard) as superseded by #21; parts (1) and (4) stay.
- **#17:** note `5_lawful` variant A (pending L2).
- **p1720 methodology:**
  - expected JSON gets new leaves (9, 9b_dismissed, 5_order_is_act) and the `defeated_by` precision fix;
  - re-freeze before any run;
  - 768 returns to the PASS denominator only after L1 is resolved;
  - 2/2554 stays development / regression only.
