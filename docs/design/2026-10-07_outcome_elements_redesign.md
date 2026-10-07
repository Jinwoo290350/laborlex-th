# Design audit: `9b_outcome` / `5_outcome` → separate outcome elements (2026-10-07) — PROPOSAL, nothing changed

> Superseded in part by `2026-10-07_outcome_elements_redesign_v2.md` (2/2554 dismissal fact corrected, s.31 audit, final schema). §1 usage inventory still valid.

Local only: no Gemini, no code/config/taxonomy/expected-JSON/manifest change. Simulation: scratchpad
`design_outcome.py` (staging `combine()` on fixture / frozen / paired8-run leaves).

## 1. Every use of the current outcome elements
| place | what it depends on |
|---|---|
| `data/processed/issues.yaml` 9b_outcome (l.1345), 5_outcome (l.1631) | derive `all[8, 9b_lawful, ¬9b_e]` / `all[2, 3, 5_lawful, ¬5_e]`; text "ไม่ได้รับความคุ้มครอง … แต่เลิกจ้างทันทีไม่ได้ ต้องตักเตือน…"; `forbid_phrases: [ได้รับความคุ้มครอง]` |
| `src/agent/nodes/draft.py:109–118` `_elements_block` | "outcome element" = has `forbid_phrases`; shown to the draft only when met |
| `src/agent/rules/elements.py:96–102, 133–143` `_fired`, `answer_conflicts` | outcome met + non-negated phrase in that issue's conclusions/preliminary → `outcome_contradicted` → ⑨ forced revise (`draft.py:228–232`) |
| `tests/regression/test_2554_consistency.py` l.36–41, 51, 61–68, 70–74, 141 | asserts the wording ("ไม่ได้รับความคุ้มครอง" + "ตักเตือนเป็นหนังสือ"), that "ได้รับความคุ้มครอง และนายจ้างเลิกจ้างทันทีไม่ได้" is flagged, that the "not protected but warn first" answer passes |
| `tests/regression/test_pilot_guards.py` l.41, 74 | 5_outcome ≠ met on 2/2560 and the dev102 pattern |
| `docs/decisions.md` #20 | wording taken from the 2/2554 Q4 answer key, "รอ Frank/ผู้เชี่ยวชาญตรวจ" |
| `docs/design/2026-10-06_fix_123_trace.md`, `docs/results/2026-10-06_targeted_fix20.md` | historical records (unchanged) |
`prompts/` does not name the elements. Huay Khwang: no s.123/s.31 element in its test or gold → not affected.

## 2. What each use case actually needs
| case | situation | needs |
|---|---|---|
| 2/2554 Q4 (development) | per our spec: may the employer dismiss? lawful order (CBA + own preference), no warning | **warning requirement** (advisory); "the refusal itself is not protected" scoped to the refusal, not to a dismissal |
| 768/2533 | dismissal already done, no warning, not serious | **post-dismissal outcome**: prohibited → protected / ULP |
| 2-2553-q4 (paired8 guard) | dismissal done, no lawful-order breach | post-dismissal outcome: prohibited (gold: protected / ULP) |
| 3211/2545, 2563-2565/2552 | dismissal done after warnings; lawfulness / purpose unresolved | exception status (unknown) → conditional outcome |
| 10251/2551, 2911/2528, 2222/2538 | s.52 permission requested; no dismissal yet | exception status (+ s.52); no post-dismissal outcome |
| s.31: 2/2560, dev102, 1-2551-q3, 2-2555-q4, S-2558-q4 | act = dismissal **or transfer** during negotiation | exception status; post-act outcome must cover transfers too |
The current single element derives "exception (3) fails for lack of warning". Its text labels that "not protected",
which is the opposite of what the derivation means once a dismissal has happened. `5_outcome` has the same text,
derivation and guard → **the same conflation**. In s.31 it is worse, because the protected act may be a transfer, not a
dismissal.

## 3. Proposed design (s.123; the s.31 version is analogous)
New factual leaf `9b_dismissed`: "นายจ้างได้เลิกจ้างแล้วตามข้อเท็จจริงหรือไม่ (ไม่ใช่ถามว่าจะเลิกจ้างได้หรือไม่)". Element 8
should then ask coverage only (CBA in force + covered person); today it also says "นายจ้างได้เลิกจ้าง…".
| element | derive | meaning | text shown when met | guard (proposal) |
|---|---|---|---|---|
| 9b_exception (= today's 9b) | all[9b_lawful, 9b_e] | exception (3) applies | "เข้าข้อยกเว้น ม.123(3)" | — |
| 9b_warning_required | all[8, 9b_lawful, ¬9b_e] | a lawful-order breach, not serious, not yet warned: a written warning must come before dismissal on this ground | "การฝ่าฝืนคำสั่งนี้ไม่ใช่การกระทำที่กฎหมายคุ้มครอง แต่ ม.123(3) ยังห้ามเลิกจ้างด้วยเหตุนี้จนกว่าจะตักเตือนเป็นหนังสือ (เว้นแต่ร้ายแรง)" | forbid "เลิกจ้างได้ทันที" (non-negated) |
| 9b_dismissal_prohibited | all[8, 9b_dismissed, ¬9b_exception, ¬9] | the dismissal that happened falls under the s.123 prohibition → protected | "การเลิกจ้างที่เกิดขึ้นต้องห้ามตาม ม.123 ลูกจ้างได้รับความคุ้มครอง" | none at first (see risk 1) |
| 9b_dismissal_permitted | all[8, 9b_dismissed, any[9b_exception, 9]] | an exception applies → not prohibited by s.123 | "การเลิกจ้างเข้าข้อยกเว้นตาม ม.123" | forbid a non-negated ULP claim (needs fixtures) |
s.31: `5_exception = all[5_lawful, 5_e]` · `5_warning_required = all[2, 5_lawful, ¬5_e]` ·
`5_act_prohibited = all[1, 2, 3, ¬5_exception, ¬4]` · `5_act_permitted = all[1, 2, 3, any[5_exception, 4]]`
(element 3 = dismissal or transfer during negotiation; the text must say "เลิกจ้างหรือโยกย้าย").
The "outcome" marker should be an explicit `outcome: true` instead of "has `forbid_phrases`".

## 4. Mapping: case → old → new (simulated with `combine()`; (P) = leaf proposed, not yet approved)
| case | leaves used | old: 9b / 9b_outcome | new: exception / warning_required / prohibited / permitted | vs gold |
|---|---|---|---|---|
| 2/2554 Q4 | fixture fix123; dismissed = not_met (P, from our spec; exam text not re-read) | not_met / **met** ("not protected") | not_met / **met** / not_met / not_met | same advice, no "not protected" label on a dismissal ✔ (if dismissed = met: prohibited = met, still consistent with "cannot dismiss at once") |
| 768/2533 | frozen; 9 = not_met (P), dismissed = met (P) | not_met / **met** | not_met / met / **met** / not_met | protected / ULP ✔ |
| 768/2533, 9b_b = U | as above | not_met / U | not_met / U / **met** / not_met | ✔ robust to the 9b_b caveat (no warning ∧ not serious ⇒ exception fails whatever the order's basis) |
| 3211/2545 | frozen; 9 = not_met (P) | U / not_met | U / not_met / U / U | conditional (LIMITATION stays in 9b_b, where it belongs) |
| 2911/2528 | frozen; 9 = met (P); permission sought | U / U | U / U / not_met / not_met | outcome via s.52 + exception (4); no post-dismissal claim ✔ |
| 10251/2551 | frozen; permission sought | met / not_met | **met** / not_met / not_met / not_met | exception applies ✔ |
| 2563-2565/2552 | frozen; 9 = not_met (P) | U / not_met | U / not_met / U / U | conditional on purpose ✔ |
| 2222/2538 | frozen (s.123 side); permission sought | U / not_met | U / not_met / not_met / not_met | s.52 decides ✔ |
| 2-2553-q4 (paired8 run) | staging run; dismissed = met (P) | not_met / not_met | not_met / not_met / **met** / not_met | protected / ULP ✔ (new: an outcome is now stated) |
| Huay Khwang | — | — | — | not affected |
| s.31 2/2560 Q4 | fixture fix20 | U / U | U / U / U / U | unchanged (gold: protected — still left to the draft) |
| s.31 dev102 pattern | test fixture | not_met / not_met | not_met / not_met / **met** / not_met | transfer barred ✔ (dev gold s.31 + 121(1)) |
| s.31 1-2551-q3 | staging run | not_met / U | not_met / U / **met** / not_met | ✘ **gold: demand invalid (s.15) → no breach** — upstream element 1 error amplified |
| s.31 2-2555-q4 | staging run | U / U | U / U / U / U | unchanged |
| s.31 S-2558-q4 | staging run | not_met / U | not_met / U / U / not_met | unchanged |
| s.31 3211, 2222 sides | frozen | U / not_met | U / not_met / U / U · U / not_met / not_met / not_met | ✔ (2222: element 3 = not_met, transfer before the demand) |

## 5. Risks and open legal questions (for Frank / an expert)
1. **The prohibited outcome amplifies upstream errors** (1-2551-q3): it asserts protection whenever elements 1–3 are
   met, but demand validity (s.13/s.15) is not an element. Do not guard it, and possibly show it as conditional
   ("ถ้าข้อเรียกร้องชอบด้วยกฎหมาย …"), until elements 1–3 cover validity.
2. s.31: the refused order may itself be the transfer that s.31 forbids (S-2558-q4). "Lawful order" should then be
   not_met, but 5_b/5_d do not capture this.
3. The 2/2554 Q4 key's "not protected" must be scoped to the refusal (warning_required text). Whether the exam key
   intends more needs a check against the key (not re-fetched now).
4. Phrase guards are fragile (negation is only checked as "ไม่" directly before the phrase). Each new guard needs
   fail-first fixtures, including the court-correct wording from 768.
5. Change footprint once approved: issues.yaml (9b/5 groups + element 8 wording), `_elements_block`/`_fired`
   outcome marker, two regression test files, decisions.md #20 (new row), and the p1720 expected JSON (new leaves 9 and
   9b_dismissed for each case). Then re-freeze the expected states before any run.
