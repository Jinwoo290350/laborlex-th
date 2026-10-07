# Re-freeze v2 — field-level diff (2026-10-08)

Spec re-freeze only: rule B (deterministic decisive leaves) + 9b_b R1 wording (taxonomy commit b768725) + 822 question revision.
No Gemini run; historical run outputs and result documents are not modified (checksum recorded below).

## docs/benchmarks/p1720_expected_DRAFT_2026-10-07.json
- previous: `git 3bd6b18:docs/benchmarks/p1720_expected_DRAFT_2026-10-07.json` sha256 178b29d7c1f25caa → new sha256 **76228c320590534e**

- **p1720-768-2533**: employ/9b_b: accept ['unknown'] → []; employ/9: accept ['unknown'] → []; scored_derived = {'employee_committee_and_union_protection': ['9b_lawful', '9b', '9b_warning_required', '9b_dismissal_prohibited', '9b_dismissal_permitted']}
- **p1720-10251-2551**: employ/9b_b: accept ['unknown'] → []; employ/9b_d: accept ['unknown'] → []; scored_derived = {'employee_committee_and_union_protection': ['9b_lawful', '9b', '9b_warning_required', '9b_dismissal_prohibited', '9b_dismissal_permitted']}
- **p1720-3211-2545**: employ/8: accept ['unknown'] → []; employ/9b_b: accept ['not_met'] → []; employ/9b_c: accept ['unknown'] → []; employ/9b_c: scored False → True; employ/9b_d: accept ['unknown'] → []; employ/9: accept ['unknown'] → []; disput/5_b: accept ['not_met'] → []; disput/5_c: accept ['unknown'] → []; disput/5_c: scored False → True; disput/5_d: accept ['unknown'] → []; scored_derived = {'employee_committee_and_union_protection': ['9b_lawful', '9b', '9b_warning_required', '9b_dismissal_prohibited', '9b_dismissal_permitted'], 'dispute_protection_s31': ['5_lawful', '5', '5_outcome']}
- **p1720-2911-2528**: employ/8: accept ['not_met'] → []; employ/9b_d: accept ['not_met'] → []; employ/9b_e: accept ['not_met'] → []; employ/9b_e: scored False → True; scored_derived = {'employee_committee_and_union_protection': ['9b_lawful', '9b', '9b_warning_required', '9b_dismissal_prohibited', '9b_dismissal_permitted']}
- **p1720-2222-2538**: employ/9b_b: accept ['not_met'] → []; employ/9b_c: accept ['unknown'] → []; employ/9b_c: scored False → True; employ/9b_d: accept ['unknown'] → []; disput/5_b: accept ['not_met'] → []; disput/5_c: accept ['unknown'] → []; disput/5_c: scored False → True; disput/5_d: accept ['unknown'] → []; scored_derived = {'employee_committee_and_union_protection': ['9b_lawful', '9b', '9b_warning_required', '9b_dismissal_prohibited', '9b_dismissal_permitted'], 'dispute_protection_s31': ['5_lawful', '5', '5_outcome']}
- **p1720-2563-2565-2552**: employ/8: accept ['unknown'] → []; employ/9b_b: accept ['unknown'] → []; employ/9: accept ['unknown'] → []; scored_derived = {'employee_committee_and_union_protection': ['9b_lawful', '9b', '9b_warning_required', '9b_dismissal_prohibited', '9b_dismissal_permitted']}

## docs/benchmarks/s123pos_freeze_2026-10-08.json
- previous: `docs/benchmarks/s123pos_freeze_2026-10-08_v1.json` sha256 1b34e96fa20f09a0 → new sha256 **d6a255671fb27b05**

- **s123pos-1336-2527**: employ/8: accept ['unknown'] → []; employ/9b_b: accept ['unknown'] → []; employ/9b_d: accept ['unknown'] → []; scored_derived = {'employee_committee_and_union_protection': ['9b_lawful', '9b', '9b_warning_required', '9b_dismissal_prohibited', '9b_dismissal_permitted']}
- **s123pos-822-2536**: `question` changed; `question_sha256` changed; `gold` changed; `source_facts` changed; `provenance_note` changed; `leakage` changed; employ/3: scored True → False; employ/8: scored True → False; employ/9b_ground_misconduct: scored True → False; scored_derived = {'employee_committee_and_union_protection': []}
- **s123pos-1159-2531**: employ/8: accept ['met'] → []; employ/9b_b: accept ['unknown'] → []; employ/9b_d: accept ['unknown'] → []; scored_derived = {'employee_committee_and_union_protection': ['9b_lawful', '9b', '9b_warning_required', '9b_dismissal_prohibited', '9b_dismissal_permitted']}

