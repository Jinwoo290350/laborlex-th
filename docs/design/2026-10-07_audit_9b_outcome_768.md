# Audit: `9b_outcome` on 768/2533 (2026-10-07) — local only, no Gemini, no code/JSON/manifest change

Script: scratchpad `audit768.py` (staging `resolve_elements` + `answer_conflicts` on the expected leaves from
`p1720_expected_DRAFT_2026-10-07.json`).

## 1. Input leaves (768, issue employee_committee_and_union_protection)
3 = not_met · 8 = met · 9b_a = met · 9b_b = met · 9b_c = not_met · 9b_d = not_met · 9b_e = not_met

## 2–3. Derived values and rules (`data/processed/issues.yaml`, `combine()` three-valued)
| element | rule | result |
|---|---|---|
| 9b_lawful | all[9b_a, any[9b_b, 9b_c], not 9b_d] | met |
| 9b | all[9b_lawful, 9b_e] | not_met |
| 9b_outcome | all[8, 9b_lawful, not 9b_e] | **met** |
`defeated_by` on element 3 changes a status only when the LLM has called element 3 **met** (`resolve_elements`:
`c.status == MET`). With the expected 3 = not_met nothing fires and no key is forbidden. The draft JSON's
`defeated_by_fires: true` for 768/10251 should read "only if element 3 is called met" (not edited, as instructed).

## 4. Downstream use
- ⑧ `draft.py::_elements_block`: an outcome element is shown to the draft only when met, as
  "- met: ผลตาม LRA2518:123:1:(3): ลูกจ้างไม่ได้รับความคุ้มครองตาม LRA2518:123:1 เพราะฝ่าฝืนคำสั่งอันชอบด้วยกฎหมายของนายจ้าง
  แต่นายจ้างจะเลิกจ้างทันทีไม่ได้ ต้องว่ากล่าวและตักเตือนเป็นหนังสือก่อน (เว้นแต่กรณีที่ร้ายแรง)".
- ⑨ `answer_conflicts`: when 9b_outcome is met, any non-negated "ได้รับความคุ้มครอง" in that issue's conclusions or the
  preliminary answer is a conflict, which forces one revision with that feedback.

Fail-first result (`answer_conflicts` on a one-point answer):
| leaves | conclusion text | conflicts |
|---|---|---|
| 768 | court's: "ได้รับความคุ้มครองตาม ม.123 … เลิกจ้างโดยไม่ได้ตักเตือน … เป็นการกระทำอันไม่เป็นธรรม" | **outcome_contradicted** → forced revise |
| 768 | 9b_outcome wording: "ไม่ได้รับความคุ้มครอง … แต่เลิกจ้างทันทีไม่ได้" | none |
| 768, 9b_b = U | court's | none (9b_outcome = unknown, hidden) |
The court-correct conclusion is flagged, and the revision is steered toward the opposite label.

## 5. Meaning of `9b_outcome = met`
- Its **derivation** means: a person covered by s.123 breached a lawful order, and the warning/serious condition of
  (3) is not satisfied, so **exception (3) does not apply**. Under s.123 in the DB ("ห้ามมิให้นายจ้างเลิกจ้าง … เว้นแต่
  … (3) … โดยนายจ้างได้ว่ากล่าวและตักเตือนเป็นหนังสือแล้ว เว้นแต่กรณีที่ร้ายแรง"), the prohibition then still stands:
  the employee is protected against this dismissal (the 768 court: ULP).
- Its **text** says both "ไม่ได้รับความคุ้มครอง" and "เลิกจ้างทันทีไม่ได้" (= still protected now).
- Its **guard** enforces only the first label.
Origin: decisions.md #20. The wording comes from the 2/2554 Q4 answer key (a development case), marked "รอ Frank/
ผู้เชี่ยวชาญตรวจ". There the operative point is advisory ("must warn first"); in 768 the dismissal has already
happened, so the operative point is that it is a ULP. The element does not distinguish the two. `5_outcome` (s.31)
carries the same text and guard.

## Conclusion: **B — `9b_outcome` is ambiguous; methodology must change before running.**
768/2533 is not usable as a PASS case until this is resolved:
- the counted case would mostly test this wording conflict, not #17;
- the staging result also splits on the caveat element (9b_b = met → guard fires; 9b_b = U → nothing shown).

Resolution belongs to Frank / an expert, because it touches the 2/2554 design-case gold and its regression tests
(`tests/regression/test_2554_consistency.py`). Options (not done):
(a) neutral wording: "ไม่เข้าข้อยกเว้น (3) … นายจ้างยังเลิกจ้างไม่ได้; ถ้าเลิกจ้างไปแล้วเป็นการกระทำอันไม่เป็นธรรม", and
    forbid the opposite claim ("เลิกจ้างได้") instead of "ได้รับความคุ้มครอง";
(b) split by whether the dismissal has already happened.
