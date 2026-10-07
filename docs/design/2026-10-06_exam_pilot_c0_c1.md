# 2026-10-06: Ram LAW4004 pilot, C0 vs C1 (12 questions, LPA 2541 + LRA 2518)

**Question:** does giving the AI the correct statute text (C1) improve performance over the question alone (C0)?

- **Setup:**
  - 12 reviewed questions, 4 per bucket; buckets come from `sections_confirmed`
  - prompts `exam_c0` / `exam_c1` v2; model `gemini-3.5-flash`
  - text fetched from the source at run time, not stored
- **Not done:** C2, no Gemini judge, no commit.
- **Review:** compared against the source's model answer on 4 points, one main cause per wrong answer.
  - **Done by Claude, provisional. Frank or a lawyer should confirm.**
  - File: `data/eval/exams/ram_law4004/review_provisional_c0c1.csv` (labels only, no exam text)
- **Caveat:** n = 12, so this shows direction only and isn't statistically conclusive.

## 1. Results by bucket

| Bucket | Condition | Conclusion correct | Correct on all 4 points | Cites every needed section (auto) |
|---|---|---:|---:|---:|
| 1 section | C0 | 2/4 | 1/4 | 3/4 |
| 1 section | C1 | 3/4 | 3/4 | 4/4 |
| 2 sections | C0 | 3/4 | 3/4 | 2/4 |
| 2 sections | C1 | 3/4 | 3/4 | 4/4 |
| >2 sections | C0 | 1/4 | 0/4 | 1/4 |
| >2 sections | C1 | 3/4 | 3/4 | 2/4 |
| **All** | **C0** | **6/12** | **4/12** | 6/12 |
| **All** | **C1** | **9/12** | **9/12** | 10/12 |

## 2. C0 → C1: what changed

| Change | Questions |
|---|---|
| C0 wrong or partly right → **C1 correct** (5) | 1/2566 Q1 (legal reasoning), 2/2557 Q4 (wrong section), 2/2552 Q1 (wrong section), 2/2560 Q4 (wrong procedure), 1/2556 Q4 (wrong authority and threshold) |
| **Both wrong in the same way** (3) | 2/2554 Q4 (fact application), 2/2558 Q4 (rule from case law, not in the statute), S/2563 Q1 (missed issue: annual-leave pay) |
| Both correct (4) | S/2562 Q1, 1/2567 Q1, S/2559 Q2, S/2551 Q4 |
| C1 worse than C0 | none |

## 3. Failure reasons (one main cause per answer that isn't correct on all 4 points)

| Cause | C0 | C1 |
|---|---:|---:|
| Issue spotting | 1 | 1 |
| Doesn't know / misremembers the law | 5 | 1 |
| Legal reasoning | 1 | 0 |
| Fact application | 1 | 1 |
| Calculation | 0 | 0 |
| Conclusion (contradicts the analysis) | 0 | 0 |

**Reading:**
- **The statute text fixes "doesn't know / misremembers the law" errors** (5 → 1).
- **It doesn't fix:**
  - fact application
  - issue spotting (C1 had the text of s.67/30 and still didn't use them)
  - rules that come from case law rather than statute text
- **Calculations were right in both conditions** (15,000 / 3,200 / 800,000 / 150-120-120).
- **The effect is largest on >2-section questions** (conclusion correct: 1/4 → 3/4).

## 4. Actual cost

| | Calls | Input tokens | Output tokens | Cost |
|---|---:|---:|---:|---:|
| C0 | 12 | 4,436 | 39,859 | $0.365 |
| C1 | 12 | 13,008 | 35,223 | $0.337 |
| **Total** | 24 | 17,444 | 75,082 | **$0.702** (≈ 25 baht) |

- Latency: about 12–21 s per call.
- 18 of the calls were billed during the earlier, interrupted run and served from cache on the rerun. This total counts all 24.
- Credit after this round: about 273.89 − 25 ≈ 249 baht (about $7). Check the actual balance in AI Studio.

## 5. Next step: C2 (not run)

| C2 option | Estimate (avg $0.78/question, max $1.46) | Fits the remaining ~$7? |
|---|---:|---|
| All 12 | ~$9.4 (max ~$17.5) | **No** |
| 4 questions (the 3 where C1 failed + 1 where C1 was right) | ~$3.1 (max ~$5.8) | Yes, tight in the worst case |

For a smaller C2 run, choose the questions that answer the C2 question:
- the 3 where C1 failed. Would retrieval + elements + the verify step help?
- 1–2 where C1 was right, to check whether the full system keeps them right.
