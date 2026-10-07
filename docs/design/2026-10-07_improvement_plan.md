# Improvement plan after fix20 — technical + research-backed (2026-10-07)

PLAN ONLY. No code change, no Gemini, nothing merged. Huay Khwang (HK) is the gold case for *diagnosis*; every proposal
below must also hold on questions it was not designed on (see §6 overfitting guard).

## 1. Pipeline audit on the HK gold case (staging v8b run vs `tests/regression/huaykhwang.yaml`)
| Stage | Right now | Still at risk | Failure mode | Layer to fix | Helps other questions? |
|---|---|---|---|---|---|
| extract_facts | dates, pay days, 4 pay items with purpose/basis correct; rent read as 1,000 (v7 run read 10,000) | extractor ignores "same wage → no workers" (2 runs of 2) | instruction drift on schema fields | **code guard** (done: `worker_views` collapse + fill) — not more prompt text | yes: every multi-employee question |
| issue spotting | wages, s.119, notice, employer liability | `severance_pay` not spotted (cap 4 reached); answer still has severance via the termination table | **fixed cap of 4** fitted to dev tags (max 4); real exams need more | spot_issues: asked-item → issue coverage + cap by coverage | yes: S/2563 (annual leave), dev152 (maternity leave), every >2-section exam question |
| element analysis | — | s.119 grounds chosen as one free-form list per employee | compound decision (like 9b before #17) | **per-ground factual sub-elements + system combination** (Chain-of-Logic pattern) | yes: `dismissal_for_cause` is the largest dev issue (19 questions) |
| retrieval (statute) | right sections for wages, s.17, s.118, s.119 | — | — | — | — |
| retrieval (rulings) | offers 4 rulings, cites 3 | **0 of the 6 gold authorities that are in the DB** offered (9096/2546, 2967/2555, 7402-7403/2544, 3934/2557, 11096/2556, 4554/2540) — same in production | whole-question dense query (#11); reranker saturation; no element query | **V2 element/principle query + section-link path** (designed #12; offline D+guard selected 4/8 HK targets) — blocked on expert labels | yes: every rule-from-case-law question (2/2558 Q4 class) |
| legal reasoning | ม.119 applies to แพรวพราว, not ซื่อบื้อ (right) | found grounds (1)+(2); **gold: (2) only** (prod and staging) | LLM over-attributes grounds the facts don't establish | same as element row | yes |
| calculator | base 10,000 + 500 = 10,500; 31,500 / 5,250 / 5,250; table 5,250 / 42,000 / 47,250 | none seen after #18 fixes | — | — | — |
| draft | answers the 4 asked parts; amounts equal the calculator | — | — | — | — |
| citation / verification | invalid keys removed (`LPA2541:5:2` ×4); verify 1.0 | verifier scored 1.0 on drafts later shown wrong (2/2554 fix123) | intrinsic LLM verification is uninformative | deterministic checks (done for #20); extend to amounts / prose citations | yes |

## 2. Inventory of existing evals and failure classes (no new tests added)
| Eval | Status | Failures → class |
|---|---|---|
| Pilot 12, C0 | 4/12 all-4 | law knowledge 5 · issue spotting 1 · fact application 1 · legal reasoning 1 |
| Pilot 12, C1 (statute text given) | **9/12** | fact application (2/2554) · case-law rule (2/2558) · issue spotting (S/2563) |
| Pilot C2 original (4) | 0/4 | case-law retrieval 2 · fact application 1 · issue spotting 1 |
| 4 regression cases, fix20 v8 | 3 right + 1 partly | **rendering/drafting**: 2/2554 residual "ได้รับความคุ้มครอง" after one revise |
| Targeted 10 (v7) | 7 pass strict / 8 in substance | **retrieval** dev099 s.125 · **drafting/citation** dev120 s.124, dev152 s.41 · **selection** dev152 s.59 · **issue spotting** dev152 maternity leave · gold-vs-output dev099 s.123 |
| HK v8b | table right | **retrieval** (rulings 0/6) · **legal reasoning** (s.119 grounds) · **issue spotting** (cap) |
| **Not measured** | — | C2 on the 8 pilot questions where C1 was right (do-no-harm) · any held-out real exam question |

Failure counts by class across all of the above (one per miss): issue spotting 5 · case-law retrieval 3 (+HK) · statute
retrieval/selection 2 · fact→element 2 · citation completeness 3 · legal reasoning (grounds) 1 (HK, both runs) ·
rendering 1 · calculation 0 after #18 · extraction 0 after guards.

## 3. Systemic problems (fix the class, not the case)
1. **Issue coverage** — fixed cap 4 + no check that every asked sub-question has an issue. Seen in C0, C1, C2, dev, HK.
2. **Compound elements** — one LLM verdict over several conditions (9b before #17; s.119 grounds now). Seen 2/2554, HK.
3. **Case-law retrieval query** — whole question as the query; principle never formulated. Seen 2/2558, 2/2560, HK.
4. **Verifier without external signal** — LLM verifier 1.0 on wrong drafts; one revise not enough (2/2554 v8).
5. **Citation completeness** — sections discussed in prose but not attached (dev120, S/2563 s.30, dev152 s.41).
6. **Conditional answers** — a core element unknown → issue dropped instead of answered conditionally (dev099 s.123;
   CLAUDE.md requirement 7).
7. Not systemic now: wage classification (deterministic, correct), calculation routing (after #18), cross-issue
   consistency (one rule; generalise only with evidence).

## 4. What the research says and what we can actually use
| Paper | Proposes / finds | Use in LaborLex |
|---|---|---|
| NitiBench (Akarajaradwong et al., EMNLP 2025) — Thai legal QA | RAG beats long-context LLMs on Thai law; hierarchy-aware (section) chunking clearly better; NitiLink cross-reference expansion **did not** improve end-to-end; retriever is the bottleneck; human-finetuned BGE-M3 best; metrics: coverage, contradiction, citation P/R/F1, multi-hit | keep RAG + section/วรรค chunking (already); don't invest in reference-expansion tuning; measure retrieval with multi-hit recall vs column H; fine-tuning is out of contract scope |
| Magesh et al., *Hallucination-Free?* (JELS 2025) | commercial legal RAG tools still hallucinate; typology: incorrect vs **misgrounded** (citation doesn't support the claim) | add a "misgrounded ruling" count to eval (5061/2533 in 2/2560 was exactly this) |
| Dahl et al., *Large Legal Fictions* (JLA 2024) | LLMs hallucinate on legal facts ≥58% and cannot predict their own hallucinations | never use LLM self-confidence as a gate; keep DB-grounded checks |
| Huang et al., *LLMs Cannot Self-Correct Reasoning Yet* (ICLR 2024) | intrinsic self-correction does not improve and can degrade reasoning | revise only on external, deterministic feedback (as #20); no extra LLM-only critique loops |
| Gou et al., CRITIC (ICLR 2024) | self-correction works when the critique comes from tools | extend tool checks: calculator amounts vs draft text, DB text vs cited claim, element outcomes vs conclusions |
| Servantez et al., Chain of Logic (Findings ACL 2024) | decompose compositional rules into elements, solve independently, recompose the logical expression; beats CoT on LegalBench rule tasks | exactly #17; extend to s.119 grounds, s.118/1 retirement, s.17 notice conditions |
| Jiang & Yang, Legal Syllogism Prompting (ICAIL 2023) | law = major premise, facts = minor premise → conclusion | our answer template already follows it; no change |
| Guha et al., LegalBench (NeurIPS 2023) | 162 expert-built tasks by reasoning type (IRAC) | label our failures by IRAC stage (done in §2) |
| Gao et al., ALCE (EMNLP 2023) | citation recall / precision metrics for generated text | eval: every claimed section cited (recall) and every citation supporting its claim (precision) |
| Min et al., FActScore (EMNLP 2023) | split output into atomic facts, check each against a source | later (P2): per-claim support check against DB text |
| Gao et al., HyDE (ACL 2023) | generate a hypothetical document, embed it, retrieve real neighbours | V2 ruling retrieval: generate the *legal principle* for an element, embed, retrieve headnotes (#12) |
| Sun et al., RankGPT (EMNLP 2023) | listwise LLM reranking competitive with supervised rerankers | option for bge-reranker saturation on rulings (costs Gemini per issue — measure first) |
| Li et al., SAILER (SIGIR 2023) | case relevance hinges on key legal elements and document structure | element-level rerank against the holding span / headnote paragraph (V2-F2 rep) |
| COLIEE (statute retrieval + entailment on bar exams) | retrieve statutes, then decide entailment | our C1/C2 framing; "does the selected section entail the conclusion" = citation-support check |
| Louis et al., LLeQA (AAAI 2024) | retrieve-then-read long-form statutory QA with expert-labelled provisions | evaluate retrieval against labelled provisions (our column H), separately from answer quality |

## 5. Prioritised changes
Cost per E2E question measured on staging: ~$0.24 average, ~$0.50 with a revise round.

### P0 — before test160
**P0-1 Do-no-harm + held-out measurement** (measurement, first)
- Root cause: every fix so far was designed on the same 4 cases + HK; C2 was never run where C1 is right.
- Change: none. Run C2 (staging) on the 8 pilot questions C1 got right + C1/C2 on 12 *new* in-scope Ram questions stratified by bucket (1 / 2 / >2), manual 4-point review.
- Regression: the 20 become the held-out exam set (frozen, never used for design).
- Benefit: tells whether the system loses what Gemini gets right and where the real gap is. Overfitting risk: none (measurement).
- Gemini: 8 × ~$0.25 + 12 × ~$0.28 ≈ **$5–6**; review ~3–4 h.

**P0-2 Issue coverage** (largest failure class)
- Root cause: fixed cap 4 (from dev tags) and no link between `facts.asked` and issues.
- Change: spot_issues returns, per asked item, the issue codes that answer it (schema field, same call); system check: every asked item covered; cap = max(4, issues needed to cover asked items) with a hard upper bound; open entitlement checklist (#15) widened from "annual_leave only" to the taxonomy's entitlement issues, still gated by asked-item coverage.
- Regression: S/2563 (annual leave), dev152 (maternity leave), HK (severance_pay), dev120 (3 asked parts); held-out set.
- Benefit: issue spotting appears in C0, C1, C2, dev and HK. Overfitting risk: medium (over-spotting costs B0 "เกิน") → the held-out set must show no B0 loss.
- Gemini: 4 cases + HK ≈ $1.5; held-out re-run ≈ $3.

**P0-3 s.119 per-ground decomposition** (Chain-of-Logic, same mechanism as #17)
- Root cause: `found_ground_keys` chosen freely per employee → over-attribution ((1)+(2) vs gold (2)).
- Change: per employee × per s.119 ground, factual sub-elements written from the DB text of LPA2541:119:1 (1)–(6) (not from HK facts); system derives each ground; `found_ground_keys` = derived met grounds only; the LLM keeps writing the reasons.
- Regression: HK fixture (แพรวพราว (2) only, ซื่อบื้อ none), dev150 (dismissal for cause + s.121), dismissal_for_cause dev questions (19).
- Benefit: B1/B2 on the most frequent dev issue. Overfitting risk: medium — the ground texts must be the statute's, reviewed (legal gate).
- Gemini: HK + 5 dev ≈ $1.5–2.

**P0-4 Statute-retrieval recall audit** (local, no Gemini)
- Root cause unknown at scale (dev099 s.125 is one sign).
- Change: offline run of retrieve_law with the *gold* issue tags over dev100 → section recall@k vs column H; list systematic misses (taxonomy primary sections, query terms).
- Regression: the audit itself becomes a stored benchmark (`docs/results/`). Benefit: finds misses for free. Gemini: 0.

### P1 — accuracy gains
**P1-1 Deterministic outcome headline** — for a met outcome element (#20) the system writes the issue's conclusion headline; the LLM writes the detail. Root cause: one revise doesn't guarantee framing (2/2554 v8). Test: 2/2554 fixture + guard. Risk: low (only when an outcome element is met). Gemini: 2/2554 ≈ $0.3.
**P1-2 Citation completeness** — a section number written in prose that is in the allowed set (selected / calculator) gets its key attached in ⑩; report prose sections that are *not* allowed. Root cause: dev120 s.124, dev152 s.41, S/2563 s.30. Test: those three answers re-rendered locally. Risk: low. Gemini: 0 (re-render from stored answers).
**P1-3 Conditional answers for unknown core elements** — guard: an issue whose core element is `unknown` must have a conditional conclusion ("หาก…") rather than be dropped (requirement 7). Test: dev099 (s.123). Risk: medium (more hedging can hurt A1/B3) → held-out check. Gemini: ≈ $1.
**P1-4 Case-law retrieval V2** — element/principle query (HyDE-style) + section-link path + element rerank (SAILER); ruling cited only when linked to the issue's own sections (precision, against misgrounded citations). Blocked on the 49-pair expert labels. Test: adjudicated pairs + HK authorities + 2/2558, 2/2560. Risk: medium-high without labels. Gemini: principle query adds ~1 call per issue (~$0.02); E2E ≈ $3.
**P1-5 Amount-consistency check** — every baht amount in the draft must equal a calculator output or a question fact (CRITIC-style tool check). Test: HK, S/2563, dev120. Gemini: 0 (stored answers).

### P2 — later
Annual-leave day counting (`unused_leave_pay` routing) · per-claim support check (FActScore-style) · LLM listwise reranking for rulings (RankGPT) if P1-4 still saturates · generalising cross-issue rules · Ministry corpus merge · hierarchy/child-law conflict handling. Not in scope: fine-tuning (contract).

## 6. Overfitting guard (applies to every item)
- Design set (allowed for fixes): HK, the 4 regression cases, dev100. Held-out set (never used for design): the 20 questions of P0-1, frozen before any fix.
- A fix is accepted only if the held-out set shows no loss on any of the 4 review points; legal texts in elements come from DB provisions; interpretations from one model answer stay `reviewed_by: draft` until expert review.

## 7. Roadmap (ordered by expected accuracy gain per baht and per day)
| Step | What | Gemini | Why this order |
|---|---|---|---|
| 1 | P0-4 statute-recall audit + P1-2 citation completeness + P1-5 amount check | $0 | free, finds and fixes measurable misses |
| 2 | P0-1 do-no-harm + held-out 20 (freeze before step 3) | ~$5–6 | every later decision depends on it |
| 3 | P0-2 issue coverage | ~$1.5 + held-out ~$3 | largest failure class across all evals |
| 4 | P0-3 s.119 per-ground decomposition | ~$2 | most frequent dev issue; HK's remaining legal error |
| 5 | P1-1 outcome headline + P1-3 conditional answers | ~$1.3 | closes the known residuals with low risk |
| 6 | expert labels on the 49 pairs (no Gemini), then P1-4 V2 rulings | ~$3 | biggest retrieval gap, but only measurable with labels |
| 7 | re-run held-out 20 + 10 targeted + HK, then decide `make eval-dev` subset | ~$8 | acceptance before test160 |
Total Gemini ≈ $20–25 over the plan; legal review needed at steps 4, 5 (P1-3) and 6.
