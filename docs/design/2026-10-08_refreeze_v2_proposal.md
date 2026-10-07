# Re-freeze v2 proposal — 9b_b R1 wording + rule B + 822 question revision (2026-10-08) — NOT APPLIED

No Gemini, no production change. The frozen p1720 and s123pos files are untouched. Proposed files are in the
scratchpad: `p1720_PROPOSED_v2.json`, `s123pos_PROPOSED_v2.json`; the 822 entry alone is in `s123pos_822_PROPOSED.json`.

## 1. `9b_b` wording (R1) — applied to staging `issues.yaml` (uncommitted), derive unchanged
Old: "คำสั่งนั้นเป็นไปตามที่ข้อตกลงเกี่ยวกับสภาพการจ้าง สัญญาจ้าง หรือข้อบังคับเกี่ยวกับการทำงาน ให้นายจ้างทำได้หรือไม่ (ตามข้อเท็จจริงในโจทย์)"

New: "สิ่งที่ลูกจ้างไม่ปฏิบัติตาม (คำสั่งของนายจ้าง ข้อบังคับ ระเบียบ หรือข้อตกลง/เงื่อนไขที่ลูกจ้างต้องปฏิบัติตาม) เป็นไปตามที่ข้อตกลงฯ
สัญญาจ้าง หรือข้อบังคับฯ ให้นายจ้างกำหนดหรือสั่งได้หรือไม่ — ถ้าเป็นคำสั่ง ให้ดูว่าข้อตกลง สัญญาจ้าง หรือข้อบังคับให้นายจ้างสั่งเรื่องนั้นได้หรือไม่
ถ้าสิ่งที่ฝ่าฝืนคือข้อบังคับเกี่ยวกับการทำงาน ระเบียบ หรือข้อตกลง/เงื่อนไขนั้นเอง ให้ตอบ met เว้นแต่ข้อเท็จจริงแสดงว่าขัดต่อกฎหมายหรือข้อตกลงฯ (ตามข้อเท็จจริงในโจทย์)"

Notes:
- The order case keeps its original test, and the wording adds only the rule/regulation/agreement branch.
- `5_b` (s.31, L2 pending) is not changed.

Local regression:
- Taxonomy diff = exactly one field (`9b_b.question`); element ids and derive expressions are unchanged.
- `resolve_elements` gives identical results with the old and new taxonomy on all 18 stored leaf sets (p1720,
  s123pos, paired8 runs, regression fixtures).
- `pytest tests tools`: 201 passed, 8 skipped, 7 xfailed; ruff clean.

**Not shown:** whether the LLM still answers *order* cases the same way. The prompt text changed, so that needs a
Gemini replay of 768, 2911, 2222, 3211, 2563 and 2/2554 (cache will miss).

## 2. Rule B applied (expected derived states unchanged in every case)
Rule:
- A leaf that can change a scored derived element (tested over all three statuses with the other leaves at their
  expected values) has exactly **one** expected value and is scored.
- Non-decisive leaves keep their accept lists.
- 822 scores the leaves `9` and `9b_dismissed` only; no 9b-derived element is scored there.

| case | accept lists removed (expected value kept) | scored flag changes |
|---|---|---|
| p1720 768 | 9b_b (met), 9 (not_met) | — |
| p1720 10251 | 9b_b (met), 9b_d (not_met) | — |
| p1720 3211 | s.123: 8 (met), 9b_b (U), 9b_c (not_met), 9b_d (not_met), 9 (not_met); s.31: 5_b (U), 5_c (not_met), 5_d (not_met) | 9b_c, 5_c → scored (decisive, because b = U) |
| p1720 2911 | 8 (U), 9b_d (U), 9b_e (U) | 9b_e → scored |
| p1720 2222 | s.123: 9b_b (U), 9b_c (not_met), 9b_d (not_met); s.31: 5_b (U), 5_c (not_met), 5_d (not_met) | 9b_c, 5_c → scored |
| p1720 2563 | 8 (met), 9b_b (met), 9 (not_met) | — |
| s123pos 1336 | 8 (met), 9b_b (met), 9b_d (not_met) | — |
| s123pos 822 | — | 3, 8, 9b_ground_misconduct → not scored (only 9 and 9b_dismissed are scored) |
| s123pos 1159 (not_run) | 8 (U), 9b_b (met), 9b_d (not_met) | — |

New field per case: `scored_derived` (all s.123 derived elements, and for 3211/2222 also 5_lawful, 5, 5_outcome;
822: none). Each leaf also gets a `decisive` flag and a `spec_rule` note.

## 3. 822 question revision (in `s123pos_PROPOSED_v2.json`)
- **Groups as found by the court:** statement = employees 1 and 3–8 (the frozen "eight" was the employer's pleading);
  stoppage = employees 1–3 and 6–9; together all nine. The roles are numbered.
- **sha:** 4606882e… → 0661543c….
- **gold:** "ทั้งเก้าคน".
- **leakage:** rank 5 of 3,591. Top-1 by section: LRA 123 → 1062/2525, 52 → 5211/2531, 121 → 3985-3987/2529,
  31 → 4398/2536, LPA 119 → ร 2834/2563. The source is not top-1 anywhere.
- **near-duplicates (facts-only):** dev100 0.715, p1720 0.673.
- **Unchanged:** leaves and derived states.

## 4. What B would change in metrics — display only; stored results are not changed (historical diagnostics)
| run (staging) | v1 scoring | v2 scoring |
|---|---|---|
| p1720 10251 | leaves 8/8 matched; derived 9b_lawful/9b U ≠ met | **leaf mismatch 9b_b (U ≠ met)** + the same derived mismatch → the failure is located at 9b_b |
| s123pos 1336 | leaves 8/8; derived lawful/9b/permitted U ≠ met | **leaf mismatch 9b_b (U ≠ met)** + derived mismatch (PERMITTED U ≠ met) |
| p1720 2222 | leaf mismatches 8, s31/3 | + **s31/5_c (U ≠ not_met)** (consent leaf now decisive) |
| p1720 768, 2911 | all match | all match |
| p1720 2563 | 3 leaf + 4 derived mismatches | unchanged |
| p1720 3211 | s.123 leaves absent | unchanged (absent) |
| s123pos 822 | leaves 5/5; derived U ≠ met | 2/2 scored leaves; no scored derived. **Not comparable:** the stored run used the old question |

#20 remains untested; nothing was added for it.

## To approve
1. Commit the `9b_b` wording (staging).
2. Apply `p1720_PROPOSED_v2.json` and `s123pos_PROPOSED_v2.json` as the new freezes, with their status set to FROZEN
   v2.
3. Whether to run the Gemini replay of the order cases (§1) before or with the next run.
