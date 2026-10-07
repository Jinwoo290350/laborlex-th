# 2026-10-06: Fix plan from the Ram pilot (before any code change)

Regression spec: `docs/benchmarks/exam_regression_spec_2026-10-06.yaml` (4 cases + unit tests).
Fail-first measurements: local only (bge-m3 + DB), no Gemini.
Nothing changed: no code, no production, no merge.

## 1. Retrieval / representation: what the fail-first test showed

Rank of **10293/2546** (the ruling with the s.31 court route vs s.121 committee route rule), using production's whole-question query:

| Variant | 2/2558 Q4 | 2/2560 Q4 |
|---|---:|---:|
| Current (one vector per ruling, sorted by similarity, the issue's sections as filter) | 4–5 | 4–11 |
| **Best headnote paragraph (V2-F2)** | **12** (worse) | **15** (worse) |
| Pipeline's own `facts.asked` / issue-reason queries | 22–96 (best-para 23–139) | 2–338 |
| Link-overlap first (rulings linked to more of the issue's selected sections), broad issue sections as today | 10 | 2 |
| **Link-overlap first + issue narrowed to {LRA:31, LRA:121}** (what the taxonomy split would produce) | **1** | **1** |

**Findings:**
- **Best-paragraph representation doesn't help production's query** (the whole question). It helped V2 because V2 uses element / principle queries.
- **10293/2546 is found when the issue's sections are narrow and rulings linked to several of them come first.** So the retrieval fix depends on the taxonomy fix, not the other way round.
- **The old targets don't move with this fix** (11096/2556 rank 91; 4554/2540 filtered out because it isn't linked to s.119). They need the V2 element-query track and a reviewed link. Tracked in R3, not a gate.

**Recommendation:** reorder the plan.
1. **Taxonomy split first.**
2. **Then link-overlap ranking in `search_cases`.**

Paragraph-level representation stays in the V2 track (it needs element queries).

## 2. What each fix would change (proposals)

| Fix | Where | Behaviour change | Covered by |
|---|---|---|---|
| **A. Split the s.31 issue** | `data/processed/issues.yaml`: new issue (e.g. `dispute_protection_s31`) with primary sections LRA s.31 (+ s.13/s.121 as related); `unfair_labor_practices_and_disputes` keeps s.121/123/124 | The s.31 dismissal / transfer protection gets its own elements, with no committee-complaint element. The "committee first" route only applies to s.121/124 | T1; e2e 2558, 2560 |
| **B. Lawful / agreed transfer order element** | elements of the s.31 and s.123 issues | The exception under s.123(3) / s.31(3) gets checked against the facts (transfer under an agreement or at the employee's request, a written warning) instead of a generic "exception" left `unknown` | T2; e2e 2554 |
| **C. Entitlement coverage** | issue spotting: when the event is termination / retirement, also offer `annual_leave` (s.67 + s.30) as a candidate. Either a deterministic rule from the taxonomy, or a reviewed list in issues.yaml | Questions asking "what rights do they have" get annual-leave pay alongside severance | T3; e2e 2563 |
| **D. Link-overlap ranking for rulings** | `src/index/tools.py search_cases`: within the existing section filter, order by the number of the issue's sections a ruling is linked to, then similarity | Rulings that tie the issue's sections together (10293/2546 links s.31 + s.121) come before rulings that merely share one section | R1, R2; e2e 2558, 2560 |

All four change answers. Per CLAUDE.md:
- record them in `docs/decisions.md`
- run `make eval-dev` before any merge
- production stays frozen at the demo commit until the client gives feedback

## 3. Tests

- **Unit (local, no Gemini):**
  - R1: 10293/2546 rank 1 for the s.31 issue (fail-first today: rank 4–5)
  - R2: no 5061/2533 for the s.31 issue
  - R3: old targets tracked
  - T1–T3: taxonomy / element checks
- **e2e (Gemini):** the 4 spec cases with the C2 runner, ≈ $0.80, using the existing guards (`--live` + `EXAM_ALLOW_GEMINI=1`).
- **`make eval-dev`:**
  - On dev100 C2 costs ≈ $0.78 per question → the full 100 ≈ $78; subset 30 ≈ $23.
  - **Both exceed the remaining credit (≈ 220 baht ≈ $6).**
  - Needs a budget decision, or a smaller agreed regression set: the 4 Ram cases + the dev100 questions that touch s.31/121/123/67 (≈ 10–15 questions, ≈ $8–12).

## 4. Unchanged

- Production
- `src/`
- the V2-F1 freeze
- the Ministry corpus (not merged)
- C2 not expanded to 12
