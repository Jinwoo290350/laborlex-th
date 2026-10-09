# Node-fallback audit (2026-10-08) — local only, nothing changed

Trigger: in the invalid v2 run, `check_elements` failed (429) and the pipeline continued with `elements = {}`. It
stopped only because `draft` also failed. No code, expected state or taxonomy was changed, no Gemini call was made,
nothing was pushed.

## 1. Exact code path
- `src/agent/nodes/common.py::traced(name, fallback)`:
  - wraps every node;
  - on **any** exception, if a fallback is given it records `entry["error"] = repr(e)` in the trace and returns
    `fallback(state, e)`;
  - with no fallback it re-raises.
- `src/agent/nodes/decide.py:104`: `@traced("check_elements", fallback=lambda state, e: {"elements": {}})`.
- `src/llm.py::generate_json`:
  - retries any API/parse error 3 times (4xx other than 429 are not retried);
  - then raises `RuntimeError("…: Gemini failed after 3 attempts")`;
  - `check_elements` runs its per-issue calls in a `ThreadPoolExecutor`, so one failing issue raises through
    `ex.map` and the whole node falls back. **The successful issues are discarded too.**

## 2. Production or harness only? → **production path**
The same decorator and fallback exist in production f50f467 (`decide.py:102`) and staging (`decide.py:104`). The
harness is not involved. The only harness link: in the cache-only dry run, `CacheMiss` was swallowed by this same
fallback, which is how it was noticed. The production behaviour is identical for a real API failure (429, 5xx,
timeout, connection reset).

## 3. Downstream with `elements = {}` (staging)
| step | what happens | detected? |
|---|---|---|
| `calculate` | does not read elements | — |
| `draft_answers` (`draft.py::_elements_block`) | returns `"-"`; the draft prompt shows "## ผลตรวจองค์ประกอบ -" and the LLM drafts from facts + provisions + rulings alone | **no** |
| `verify_select` → `system_conflicts` | no elements, so no conflicts; the #20 guard is effectively off. The LLM verifier never sees elements | **no** |
| `validate_cites` | `forbidden_citations` is empty, so LRA2518:121:1:(1) can never be removed (#20 off) | **no** |
| `markdown` (render) | normal answer; no warning | **no** |
| API `/ask` (`src/api/main.py`) | returns `trace` including `entry["error"]`; no top-level flag | only if a client reads the trace |
| UI (`src/ui/app.py:76`) | trace expander shows node, ms and LLM calls only; **`error` is not displayed** | **no** |
| `src/eval/run_eval.py::run_one` | `error` is set only when `answer()` itself raises. Node fallbacks are **graded as normal answers** | **no** |
| `tools/exam/run.py` | keeps `error` per trace entry (visible in the record); no gate | partly |

## 4. The same pattern in other nodes
| node | fallback | effect | risk |
|---|---|---|---|
| `extract_facts` (`understand.py:14`) | `Facts(key_facts=[question], asked=[question])` | no structured facts: workers, wages, dates and amounts are gone. Calculations are skipped or wrong, issue spotting is weaker | high, silent |
| `retrieve_cases` (`retrieve.py:101`) | `{"cases": {}}` | no rulings; the answer cites no case law | low–medium, silent |
| `select_citations` (`decide.py:57`) | top-5 retrieved candidates per issue, not validated by the decider | possibly irrelevant provisions are shown to the draft; `validate_cites` still checks they exist and are in force | medium, silent |
| `check_elements` (`decide.py:104`) | `{"elements": {}}` | §3: no system reasoning, no outcome markers, #20 off | **high, silent** |
| `verify_select` (`draft.py:226`) | `answer = drafts[0]` | unverified first draft; **no `system_conflicts`, no forced revise**. A failing *revise* call also lands here, dropping the revision | high, silent |
| `spot_issues`, `retrieve_law`, `calculate`, `draft_answers`, `validate_cites` | none | the exception propagates; `answer()` fails (API 500 / eval error) | fail-closed already |

**Historical occurrence.** One silent fallback was found in 122 stored traces:
`2026-10-06_targeted_fix20/huaykhwang.json` → `select_citations` fell back after "Connection reset by peer" (top-5
candidates). That run's Huay Khwang result (in `docs/results/2026-10-06_targeted_fix20.md`) was therefore produced
with unvalidated citations. No other stored run (p1720, s123pos, paired8 and others) has a node fallback.

## 5. Can production answer a legal question without elements? → **yes**
If the check_elements call fails while `draft` succeeds (a transient 5xx, timeout or connection reset on one call),
the user gets a normal-looking legal answer:
- no element reasoning and no outcome markers;
- the #20 citation guard is off;
- no warning in the answer or the UI.

The dry run shows the pipeline really continues past the failed `check_elements` to `draft`. The same holds for
`verify_select` (an unverified answer) and `extract_facts` (an answer without structured facts).

## 6. Options
| option | behaviour | pros | cons |
|---|---|---|---|
| **A. fail-closed** | the node re-raises (no fallback); `/ask` returns an error and eval records an error | never shows a degraded legal answer; simplest; honest metrics | availability: one transient error loses the whole answer; the demo UX shows errors; more retries / cost on the client side |
| **B. propagate error (degraded flag)** | keep the fallback, but carry `state.degraded = [node, error]`; the markdown shows a visible warning; `/ask` returns `degraded: true`; eval counts the case as degraded | the user still gets an answer and is told it is incomplete; no lost availability | a degraded answer can still be read as authoritative if the warning is ignored; the draft must be told the elements are missing |
| **C. NEEDS_REVIEW** | like B, but the result status is `NEEDS_REVIEW`: no definitive conclusions, the answer is framed as preliminary, the UI shows a banner, eval treats it as not passing | safest middle ground for a legal product; nothing degraded is presented as final | more work (status field, renderer, UI, eval); answers become less useful during outages |

**Recommendation (per node, by legal impact):**
- **check_elements, verify_select, extract_facts → C (or A for the API until C exists).** These carry the system's
  legal reasoning, its consistency guard and the facts.
- **retrieve_cases, select_citations → B.** An answer without rulings, or with unvalidated top-5 provisions, can
  still be correct, but must say so.
- **Eval and benchmark (independent of A/B/C, recommended first):**
  - `run_eval` and the benchmark harnesses must treat any trace `error` as an invalid case, never a graded answer;
  - the UI trace expander should show `error`.
  - These two changes are small and make silent degradation visible in our own evidence.

Not done: any code change.
