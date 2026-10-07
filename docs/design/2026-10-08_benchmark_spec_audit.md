# Benchmark specification audit (2026-10-08) — local only, nothing changed

No Gemini, no taxonomy/code/production change, no re-freeze. The frozen s123pos 822 entry is untouched. Proposals are
in the scratchpad (`s123pos_822_PROPOSED.json` vs `s123pos_822_FROZEN.json`).

## 1. 822/2536 — question revision (proposed, not applied)
Re-reading the judgment found **two** construction defects in the frozen question, not one:

| | frozen | judgment | proposed |
|---|---|---|---|
| who made the statement | "ลูกจ้างแปดคนในจำนวนนี้" | **the employer's pleading** said respondents 1–8; the **Labour Court found** respondents 1 and 3–8 (seven) | "ลูกจ้างคนที่ 1 และคนที่ 3 ถึงคนที่ 8" |
| who joined the stoppage | "ลูกจ้างเจ็ดคนในจำนวนนี้" (no identities) | respondents 1–3 and 6–9 (LC finding) | "ลูกจ้างคนที่ 1 ถึงคนที่ 3 และคนที่ 6 ถึงคนที่ 9" |
| roles | "คนหนึ่งเป็นประธาน …" | 1 = president, 3 = vice-president, 4 = secretary, 2 and 5–9 = committee | numbered the same way |

The two groups together cover all nine (2 and 9 by the stoppage only; 4 and 5 by the statement only). No conclusion was
added.

Diff (fields):
- **Changed:** `source_facts` (facts 1, 2, 4), `question`, `question_sha256` (4606882e… → 0661543c…),
  `provenance_note` (revision appended), `gold`, `leakage` (recomputed).
  - `gold`: "(1) เลิกจ้างได้ทั้งเก้าคนเมื่อได้รับอนุญาต…", i.e. "ทั้งเก้าคน" added, matching the LC order affirmed by the SC.
  - `leakage`: rank 4 → 5. Top-1 for LRA 52 is now 5211/2531 (the source is no longer top-1); LRA 123 → 1062/2525.
    LRA 31 and LPA 119 were not recomputed in this proposal.
- **Unchanged:** expected leaves, derived states (verified with `derive_checks` against the current taxonomy), role,
  near-duplicate status (facts-only max: dev100 0.715, p1720 0.673).
- **Open:** issue-level elements cannot express that each employee fits a *different* exception (2 and 9 via (5);
  4 and 5 via (2)). That is U5 (per-employee evaluation). The expected `9 = met` stays issue-level.

## 2. `9b_b` semantics — where it was used
`9b_b` / `5_b` asks: "คำสั่งนั้นเป็นไปตามที่ข้อตกลงเกี่ยวกับสภาพการจ้าง สัญญาจ้าง หรือข้อบังคับเกี่ยวกับการทำงาน ให้นายจ้างทำได้หรือไม่".
The s.123(3) / s.31(3) text covers three norm types: ข้อบังคับ, ระเบียบ, คำสั่ง (each "อันชอบด้วยกฎหมาย").

| norm breached | cases (LLM status) | does the current question fit? |
|---|---|---|
| **Order with stated authority** | 768 (met), 2911 (met), 2/2554 fixture (met) | **yes**, works |
| **Order without stated authority** | 2222 (U), 3211 s.31 (U), S-2558-q4 s.31 (U), 2563 (not_met) | fits; U is the known **L2/LIMITATION** (authority = management power or reasonableness). Not a 9b_b wording problem |
| **Work rule / CBA breached directly** | 1336 (U), 822 (U, evidence even talks about "the transfer order") | **no**: the LLM looks for an authority *for the rule itself*, which the question presupposes is an order |
| **Employer regulation (ระเบียบ) as a standing instruction** | 10251 (U, also 5_b U) | **no**: same misfit |
| no breach / no refusal | 2-2553-q4, 1-2551-q3, 2-2555-q4 (U) | irrelevant (9b_a = not_met decides) |

**Finding.** `9b_b` works for orders. It systematically returns U for breaches of rules or regulations, because the
question is order-shaped. This is not a 1336-specific problem (822 and 10251 show the same).

Options (none applied):
- **R1 (minimal):** reword `9b_b` to cover the three norm types. For example: "สิ่งที่ลูกจ้างฝ่าฝืน (ข้อบังคับ ระเบียบ หรือคำสั่ง)
  นายจ้างมีอำนาจกำหนดตามข้อตกลง สัญญาจ้าง หรือข้อบังคับเกี่ยวกับการทำงาน — ถ้าสิ่งที่ฝ่าฝืนคือข้อบังคับเกี่ยวกับการทำงาน/ระเบียบ/ข้อตกลงเอง
  ให้ตอบ met เว้นแต่ข้อเท็จจริงแสดงว่าขัดต่อกฎหมายหรือข้อตกลง".
  - The derive is unchanged and order cases keep their meaning.
  - Risk: still depends on the LLM classifying the norm type correctly.
- **R2 (structural):** add a factual leaf `9b_rule_breach` (the breached norm is a work rule / regulation / CBA term
  itself) and set `9b_lawful = all[9b_a, any[9b_rule_breach, 9b_b, 9b_c], ¬9b_d]`.
  - It is cleaner, but it adds a leaf and changes the derive.
  - A rule can itself be unlawful (contrary to the CBA or the law). R2 would then also need a guard, which is overfit
    risk.

Simulated effect (current run leaves plus my reading of the norm type):
- R1/R2 would complete 1336 (→ PERMITTED) and 10251 (→ 9b met).
- 822 still needs `9b_a`; it came out U from the same confusion.
- Order cases (768, 2911, 2222, 3211, 2563, 2/2554) are unchanged.
- 2563 stays prohibited because `9b_d = met` (the allegation-as-fact problem is independent).

Overfit guard for later:
- Fail-first fixtures from every row above, not from 1336 alone.
- Any wording change misses the check_elements cache, so it would need a Gemini replay of the order cases to show
  they are unchanged.

## 3. Accept lists vs expected derived
All frozen cases were enumerated over every accepted leaf combination (scratchpad output; `derive_checks` with the
current taxonomy).

| case | non-deterministic derived elements | single-leaf culprits (accepted alternative) | observed in a run |
|---|---|---|---|
| p1720 768 | 9b_lawful, warning_required, **prohibited**, permitted | 9:U, 9b_b:U | no (LLM gave the primaries) |
| **p1720 10251** | 9b_lawful, 9b | 9b_b:U, 9b_d:U | **yes** (9b_b = U) |
| p1720 3211 (s.123 + s.31) | lawful, 9b/5, prohibited, permitted | 9b_b:not_met, 5_b:not_met | no (s.123 issue absent) |
| p1720 2911 | 9b_lawful, 9b, warning_required | 8:not_met, 9b_d:not_met, 9b_e:not_met (ns) | no |
| p1720 2222 (s.123 + s.31) | lawful, 9b/5 | 9b_b:not_met, 5_b:not_met | no |
| p1720 2563 | deterministic | — | (its mismatch is outside the accept lists) |
| **s123pos 1336** | 9b_lawful, 9b, prohibited, **permitted** | 8:U, 9b_b:U, 9b_d:U | **yes** (9b_b = U) |
| **s123pos 822** | 9b_lawful, 9b, warning_required | 9b_a:U, 9b_b:U, 9b_d:U, 9b_e:U — **all non-scored** | **yes** |
| s123pos 1159 (not run) | 9b_lawful, warning_required | 8:met, 9b_b:U, 9b_d:U | — |

Two flaws in my construction:
- (i) Accept lists on leaves that feed derived elements make the expected derived state non-deterministic. This
  affects 8 of 9 cases.
- (ii) Some leaves were marked "not scored" but still decide a derived element (822). A non-scored leaf must not be
  able to change a scored derived element.

**Options:**
- **A — derived scored against the set:** compare the actual derived state with the set of values reachable through
  accepted leaves.
  - It never fails on accepted variants, but it also lets the key outcome be "unknown": 1336's PERMITTED would pass as
    U, so the positive path could never fail.
- **B — deterministic derived (your preference):** every leaf that can change a scored derived element gets **one**
  expected value. Multi-accept is allowed only on leaves that cannot change any scored derived element. If the facts
  genuinely leave a decisive leaf open, the single expected value is `unknown`, and the derived outcome is expected U
  (explicit).
  - Re-scoring the existing runs under B (no rerun):
    - 1336: 9b_b → met only, so the staging run becomes a C1 **mismatch at 9b_b**. The failure is located exactly.
    - 10251: 9b_b → met, 9b_d → not_met; the staging run mismatches at 9b_b.
    - 822: 9b_a, 9b_b, 9b_d, 9b_e become scored decisive leaves (or the 9b-derived elements are marked non-scored,
      because 9 is the decisive route).
    - 768, 2911, 2222 and 3211: pick the single value already set as primary; the observed runs still match.

**Recommendation: B.**
- Per case, mark which derived elements are scored. The 822 option above is the main choice (score 9 and
  9b_dismissed, not the 9b_* derived states).
- Apply it in one re-freeze of p1720 + s123pos together with the 822 question revision, after your approval.
- Rule for building expected states from now on: "a decisive leaf has exactly one expected value; a non-scored leaf
  cannot feed a scored derived element".

#20 remains untested; no attempt was made to build a firing case.
