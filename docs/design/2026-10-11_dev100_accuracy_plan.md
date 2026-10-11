# dev100 accuracy run: plan (2026-10-11)

**Goal:** an accuracy figure for the client on all 100 dev questions that is defensible:
- measured the way their lawyers grade (rubric §3, PASS = all 6 criteria at 2);
- comparable with the lawyer-scored baselines on the same 100 questions: Gemini 55, ChatGPT 50, Claude 35
  (`data/raw/legacy/client-baseline-scores.jsonl`);
- honest about bias.

## 1. What will be reported
| metric | how | role |
|---|---|---|
| **PASS rate**, all 100 + holdout 40 | checklist judge (M1), only after calibration passes (κ ≥ 0.6 on A2 and B1, PASS agreement ≥ 80% on held-out lawyer rows) | headline (judge estimate) |
| % of answers scoring 2, per criterion | same | where answers lose points |
| **Gold sections cited** (column H) | code, no judge | criterion B1 and the client's "อ้างมาตราครบ" |
| Citation hallucination | code (`validate_cites`) | must be 0 |
| Run status | `ok` / `degraded` / `needs_review` (#22) | non-ok answers count as FAIL |
| Cost and latency per question | `harness_state.json` | budget |
| **Lawyer-graded PASS** (final number) | export of the 100 answers in the grading format (`export_for_grading`-style xlsx); the client's lawyers score them like the baselines | the only number directly comparable with the baselines |

Everything is broken down by difficulty (Easy 13 / Medium 38 / Hard 49) and by question type (Calculation 13, Legal
Analysis 38, …).

## 2. Honesty constraints
- **Leakage.** Leave-one-out is applied to the few-shot examples and to the section support (`exclude_example_ids`).
  The taxonomy and elements were drafted from all of dev100, so dev100 PASS is optimistic.
- **Holdout.** The holdout 40 (`config/dev100_split.json`) was not used for tuning. It is the headline, and the tune 60
  are reported separately.
- **Do not tune on the run.** After the run, fixes go into a new commit. The run is reported at its own commit hash and
  is never silently re-run over.
- **test160.** Not opened; it is only for `make export-160` in phase 2.
- **Caches.** Every question runs fresh, with a run-local LLM cache (as in the Huay Khwang harness): no reuse of
  answers cached under older code.
- **A judge figure is not a lawyer figure.** The report labels it "judge estimate" until the lawyers' scores are in.

## 3. Stages and gates
| # | stage | gate to continue | est. Gemini |
|---|---|---|---|
| 0 | Merge P6 (employer liability) and M1 (checklist judge). Freeze the commit. Check API credit and the spending cap. | suite green; credit ≥ the cost of the stages planned | $0 |
| 1 | **Judge calibration** on the 300 lawyer rows (calibrate/held-out split) | κ ≥ 0.6 on A2 and B1, PASS agreement ≥ 80% on the held-out rows. If not met, the judge is used only for error triage; the headline waits for the lawyers. | ≈ $3–5 |
| 2 | **Smoke run on 3 questions** (1 Easy, 1 Calculation, 1 Hard; from tune) | status ok; measured cost per question; 0 hallucinated citations | ≈ $1 |
| 3 | **Holdout 40** | all runs complete; no API errors | ≈ $12–16 |
| 4 | **Tune 60** | same | ≈ $18–24 |
| 5 | **Judge on 100** + report (`docs/results/2026-10-xx_dev100_<hash>.md`) | — | ≈ $3 |
| 6 | **Export for the lawyers** (xlsx: id, question, answer, A1..B3 blank, reasons) | sent to the client | $0 |
| 7 | **Error analysis**: label each FAIL as retrieval / selection / elements / calc / drafting / contradiction / format; fix the biggest group; re-run only the affected questions | — | depends on the fix |

**Estimated total for stages 1–5: ≈ $37–49.**
- Per question: Huay Khwang cost $0.41 (20 calls, two employees). A typical dev question has fewer determination calls,
  so ≈ $0.28–0.38 is estimated. Stage 2 gives the real number before committing to stages 3 and 4.
- Stage 3 can run alone first (≈ $15) if credit is short.

## 4. Mechanics
- `python -m src.eval.run_eval --set dev100 --leave-one-out --split holdout --judge checklist`, with a harness wrapper:
  - run-local LLM cache;
  - cost cap per stage;
  - stop on 429 / 402;
  - 4 workers.
- Records per question: answer JSON, markdown, trace, status, determinations, cost.
- The report states the config hash, the prompt versions and the commit.

## 5. Owner decisions needed
1. **Budget:** approve stages 1–2 (≈ $5); then stages 3–5 (≈ $35–45) after the smoke-run cost is known.
2. **Lawyer grading of our 100 answers** by the client's lawyers. This is required for a number the client can compare
   with their baselines.
3. **The client's answer key conflicts with case law** (config/client_rulings.yaml, CR-1 and CR-2). Under policy #27,
   case law is primary. If the lawyers grade by the key, those points may score lower; report this per point rather
   than tuning to the key.
