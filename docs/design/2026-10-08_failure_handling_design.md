# Failure handling design — fail-closed with status NEEDS_REVIEW (2026-10-08)

**Status:** approved 2026-10-08 with 4 locks; implemented in staging 2026-10-09 (see *As implemented* at the end). Sections 1–8 are the approved proposal as written.

Scope (round 1): `extract_facts`, `check_elements`, `verify_select`. `retrieve_cases` / `select_citations` keep their
current fallbacks. No change to taxonomy, retrieval, expected states or benchmarks. Finding: decisions #22; audit:
`2026-10-08_node_fallback_audit.md`.

## Principle
For the three critical nodes, a failure means **no legal conclusion is delivered**:
- the run ends early;
- the result carries an explicit status, `needs_review`, with the reasons;
- every consumer (API, renderer, UI, eval, harnesses) must see the status, and none may present or grade the result as
  a normal answer.

Combining fail-closed with NEEDS_REVIEW: the run is fail-closed (no draft is produced and no further Gemini spend),
and what is returned is an explicit review status, not an HTTP 500 or a crash.

## 1. State (`src/agent/state.py`)
- `status: Literal["ok", "needs_review"] = "ok"`.
- `degraded: Annotated[list[dict], operator.add] = []`. Each entry has the form
  `{"node", "issue" (optional), "error", "kind": "exception" | "partial"}`.
- No other field changes. `markdown` and `answer` keep their meaning: `answer = None` when `needs_review`.

## 2. Nodes
**`common.py::traced`.** New option `on_fail="review"`, used instead of `fallback=`. On an exception:
- record `entry["error"]` (as now);
- return `{"status": "needs_review", "degraded": [{"node": name, "error": repr(e), "kind": "exception"}]}`.

**`extract_facts`.** `traced("extract_facts", on_fail="review")`; `_facts_fallback` is removed.

**`check_elements`.** Per-issue isolation inside the node:
- `one(code)` returns `(code, checks)` or `(code, error)`. A failing issue no longer aborts the others.
- Successful issues are **kept** in `state.elements`, resolved as usual; they stay visible in the state and the trace.
- Each failed issue becomes a degraded entry: `{"node": "check_elements", "issue": code, "kind": "exception"}`.
  If any issue failed, `status = needs_review`.
- **Partial output** (the LLM omits some asked element ids) is recorded as `{"kind": "partial", "issue", "missing":
  [ids]}` in the trace summary only. It does **not** change the status in round 1, because the LLM sometimes omits
  non-decisive leaves; whether it should is a later decision.

**`verify_select`.** `traced("verify_select", on_fail="review")`; `_verify_fallback` is removed. A failing *revise*
call (inside the node) therefore also yields `needs_review`; the unrevised draft is never shipped silently.

## 3. Graph (`src/agent/graph.py`)
After each of the three nodes, add a conditional edge: `status == "needs_review"` routes to a new terminal node
`review_stop`, otherwise to the next step.
- `review_stop` is deterministic and makes no LLM call. It sets:
  - `answer = None`;
  - `markdown` = the review notice (§4);
  - a `trace` entry `{"node": "review_stop", "summary": {"reasons": degraded}}`.
- No draft, verify or validate runs after a critical failure, so a degraded answer cannot be produced and nothing more
  is spent.
- The other nodes and edges are unchanged.

## 4. Renderer
`review_stop` writes a fixed Thai notice (no legal content). For example:

> ⚠️ **ระบบยังไม่สามารถให้คำตอบทางกฎหมายสำหรับคำถามนี้ได้** — ขั้นตอน *{node(s)}* ทำงานไม่สำเร็จ ({short reason})
> จึงไม่ได้สรุปผลทางกฎหมาย เพื่อป้องกันคำตอบที่ไม่ครบถ้วน · โปรดลองใหม่อีกครั้ง หรือส่งให้ผู้เชี่ยวชาญตรวจ (สถานะ: NEEDS_REVIEW)

`render()` for normal answers is unchanged.

## 5. API (`src/api/main.py`)
- `AskOut` gains `status: str` ("ok" or "needs_review") and `review_reasons: list[dict]` (`degraded`).
- On `needs_review`: HTTP **200** with `answer = None`, `citations = []`, `markdown` = the notice, and `trace` as now.
  HTTP 200 is used so the UI can show the notice; a 5xx would look like an outage.
- The current behaviour stays for nodes without a fallback (exception → 500).

## 6. UI (`src/ui/app.py`)
- If `status != "ok"`: show `st.warning(notice)` at the top and no answer or sources panel.
- The trace expander also prints `t["error"]` when present, for every status.
- The status-to-banner text logic sits in a small pure helper so that it can be unit-tested.

## 7. Eval and harnesses
**`src/eval/run_eval.py::run_one`:**
- records `status` and `degraded`;
- when `status != "ok"` **or any trace entry has `error`** (this also catches the remaining round-1 fallbacks in
  `retrieve_cases` / `select_citations`), it does **not** call the judge and sets `score = None`, `pass = False`,
  `invalid = True`.

**Report:**
- PASS = pass / n, where invalid cases count as not passing (conservative);
- plus a separate line "invalid (degraded/review): k, ids…";
- PASS / n_valid is shown as secondary information only.

**`tools/exam/run.py` and the benchmark analysers:** store `status`; any `needs_review` case or trace `error` is
reported as INVALID, never scored. This makes the earlier manual INVALID / NOT_RUN markers automatic.

## 8. Fail-first tests (written before the implementation, local, no Gemini)
1. **`extract_facts` raises.** `answer()` returns `status = needs_review`; `answer is None`; the markdown contains
   "NEEDS_REVIEW"; the draft LLM is never called (spy).
2. **`check_elements` partial.** Two issues; issue A returns checks and issue B raises.
   - A's elements are present in `state.elements`;
   - `degraded` names issue B;
   - `status = needs_review`;
   - no draft is called.
3. **`check_elements` all fail.** Same `needs_review` result; `elements` is empty, but this is now explicit.
4. **`verify_select` raises** (verifier error) and **revise raises.** Both give `needs_review`, `answer = None`, and
   the unverified draft is not in the markdown.
5. **Normal path.** With the existing stubs, `status = ok` and the output is unchanged. The existing suite still
   passes.
6. **API.** FastAPI `TestClient` with `answer` patched to return a `needs_review` state: HTTP 200, `status =
   "needs_review"`, `answer is None`, `review_reasons` present.
7. **UI helper.** The status-to-banner text for `needs_review` contains the warning; the trace helper shows `error`.
8. **Eval.**
   - `run_one` with a `needs_review` state: the judge is not called, `pass = False`, `invalid = True`.
   - A state with `status = ok` but a trace entry with `error` (a `retrieve_cases` fallback) is also invalid.
   - The report lists the invalid ids.
9. **Unchanged in round 1:** the `retrieve_cases` and `select_citations` fallbacks still return their fallback values
   (now flagged invalid by eval through test 8).

## Trade-offs to note
- **Availability.** A transient error now yields no answer. That is acceptable for a legal product, but the UI should
  offer "ลองใหม่". Retries inside `generate_json` stay as they are (3 attempts).
- **Partial `check_elements` results are kept but not used for an answer.** The alternative, answering with the
  successful issues and marking the failed ones, is more useful but reintroduces partial legal content; not
  recommended in round 1.
- **Old runs are not rescored.** The one historical fallback (HK, fix20) stays as recorded in decisions #22.

## Implementation footprint (after approval)
`state.py` (2 fields) · `common.py` (`on_fail`) · `understand.py`, `decide.py` (check_elements isolation),
`draft.py` (verify) · `graph.py` (conditional edges, `review_stop`) · `api/main.py` · `ui/app.py` (+ helper) ·
`eval/run_eval.py` · `tools/exam/run.py` · new tests. No prompt or taxonomy change, so the LLM cache is unaffected.

## As implemented (2026-10-09) — differences from the proposal
Locks added at approval:
1. `status != ok` → never draft; the run stops before any legal answer.
2. `status` stops the current run; `trace.error` is the safety net for eval and historical audit; a fallback must never make
   a run with a trace error look `ok`.
3. Partial `check_elements` results are kept for diagnosis only, never used for a legal conclusion in this round.
4. No new retry, recovery or LLM call.

Differences:
- **Status has three values**, `ok < degraded < needs_review`, with a worst-of reducer (it never improves). `degraded` is set
  when a round-1 fallback is used (`retrieve_cases`, `select_citations`). The fallback values are unchanged and so is the
  markdown (no notice is added); the status, the API field and the UI banner carry the flag (lock 2).
- **`effective_status(state)`** (`src/agent/status.py`) is what consumers check: `needs_review`, otherwise `degraded` if the
  status says so or any trace entry has `error`, otherwise `ok`.
- **`answer()` rejects** `trace`, `status` and `degraded` arguments, so the status always comes from the current run. The
  graph has no checkpointer, and `traced()` and `review_stop` are the only trace writers.
- **`check_elements`** reports isolated issue failures through a `_error` return key, so the trace entry carries `error`
  even though the node itself did not raise.
- **`draft_answers` refuses** to run when `status == needs_review` (defence in depth; the graph already routes to
  `review_stop`).
- **Exam runner:** a C2 record whose status is not ok gets `failure = INVALID_<STATUS>`; `c2_state` stores `status` and
  `degraded`.
- **UI:** a warning banner (`src/ui/status.py::status_banner`) shows above the message; the sources panel is empty for
  `needs_review` because the API returns `citations = []`.

Verification (Gemini 0):
- 32 tests in `tests/unit/test_failure_handling.py`:
  - tests 1–9 above;
  - no status leak between runs;
  - injected run state is refused;
  - every pair of statuses for the reducer;
  - graph transitions `ok → degraded → needs_review`;
  - the API contract for `ok`, `degraded` (status-only and trace-only) and `needs_review`.
- Full suite: 233 passed, 8 skipped, 7 xfailed.
- Cache-only replay: p1720-3211 is identical to the historical staging run; p1720-2563 hits a real CacheMiss on the s.123
  issue → `needs_review`, no draft.
