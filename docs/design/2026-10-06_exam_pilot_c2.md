# 2026-10-06: Ram LAW4004 pilot, C2 on 4 questions (C0 → C1 → C2)

**Setup:**
- **Questions:** the 3 that C1 still got wrong, plus 1 regression check that C1 got right (2/2560 Q4).
- **C2:** the current system (HEAD `be2a3e5`, `src/` unchanged).
- **Trace recorded:** issues, candidate provisions, rulings retrieved, selected sections, element checks.
- **Same 4 review points as before.** No Gemini judge.
  - The review is provisional (by Claude): `data/eval/exams/ram_law4004/review_provisional_c2.csv`
- **Nothing committed or merged, no production change.**

## 1. C0 → C1 → C2 (conclusion verdict, with main cause)

| Question | Bucket | C0 | C1 | C2 | Main cause in C2 |
|---|---|---|---|---|---|
| 2/2554 Q4 | 1 (LRA s.123) | ✗ | ✗ (partly right) | ✗ | **fact application**: element "s.123(3) lawful order" = unknown even though the facts are stated |
| 2/2558 Q4 | 2 (LRA s.31 + 121) | ✗ | ✗ | ✗ | **case-law retrieval**: the deciding ruling 10293/2546 is in the DB but wasn't retrieved |
| S/2563 Q1 | >2 (LPA s.118/1, 118, 67, 30) | partly right | partly right | partly right | **issue spotting**: the `annual_leave` issue exists but wasn't selected |
| 2/2560 Q4 (regression) | >2 (LRA s.22, 31, 34) | partly right | **✓** | **partly right (regressed)** | **case-law retrieval + element design**: an off-point ruling (5061/2533) was used to support a wrong rule |

**C2 fixed 0 of 3, and regressed 1 of 1** compared with C1.

## 2. The three questions

| Does C2 help…? | Answer | Evidence from the trace |
|---|---|---|
| **1. fact application** | **No** | 2/2554 Q4: retrieved s.123, but the element checker returned `unknown` for the s.123(3) exception although the facts say the employee refused a transfer he had asked for himself |
| **2. case-law retrieval** | **No, and it can make things worse** | 2/2558 Q4: 10293/2546 is in the DB, linked to LRA s.31/121, and its headnote **states the rule** (s.31 breach → Labour Court directly; s.121 → committee; must choose one route). But the rule is in **headnote paragraph 2**, after an unrelated paragraph, so it wasn't retrieved (the same representation problem the V2-F2 staging work addresses). 2/2560 Q4 and 2/2554 Q4 retrieved off-point rulings (5061/2533 on mediation, 8491/2559 on food allowance) |
| **3. issue spotting** | **No** | S/2563 Q1 "what rights do they have": spot_issues picked `retirement` + `severance_pay` only and missed `annual_leave` (s.67), which is in the taxonomy |

**Root cause found in the taxonomy:** `unfair_labor_practices_and_disputes` merges s.31 (protection during a dispute; direct court route) with s.121/124 (unfair practice; committee route).
- Its element 8 is "a complaint filed with the Labour Relations Committee within the time limit".
- So the pipeline steers every s.31 dismissal towards "must go to the committee first". This caused the wrong answer on 2/2558 and the regression on 2/2560.
- There's also no element for "refusing a lawful or agreed transfer order (s.123(3))".

## 3. Cost and latency

| | Questions | Calls | Input / output | Cost | Latency |
|---|---:|---:|---|---:|---|
| C2 | 4 | 30 | 133,425 / 64,884 | **$0.784** ($0.20 per question, far below the $0.78 estimate) | 64–131 s |
| Whole pilot so far (C0 + C1 on 12, C2 on 4) | | | | **$1.49** (≈ 53 baht) | |

## 4. Recommendation

**Don't move on to a full C2 / full-pipeline run yet.** On these questions the full system adds nothing over C1 (statute text) and can make things worse. Fix these first (proposals only, not done):

1. **Case-law retrieval, representation.** Score rulings by their best headnote paragraph (V2-F2, built in staging): 10293/2546 is exactly that case. Then re-check against this pilot.
2. **Issue taxonomy and elements.**
   - Split s.31 (court route) from s.121/124 (committee route), and drop the committee-complaint element from s.31 cases.
   - Add an element for the s.123(3) / s.31(3) "lawful order" exception.
   - These are rule changes, so they need review: they go in `docs/decisions.md` and through `make eval-dev` (Gemini).
3. **Issue spotting for open questions** ("what rights do they have"). Check the entitlements that come with the event: severance, annual leave, notice, etc.
4. **For the client report:** C1 shows that giving the AI the correct statute text clearly helps (conclusion correct 6/12 → 9/12). The remaining errors are fact application, case law, and issue spotting. That's where the system has to add value, and today it doesn't.

Caveat: n = 4 for C2 and the review is provisional, so treat this as diagnosis, not a final score.
