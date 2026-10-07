# Merge / production plan — staging `feat/taxonomy-s31-split` (PLAN ONLY, not executed)

Status 2026-10-06: nothing committed, merged, pushed or deployed. Production stays at `f50f467` (demo freeze).
Needs Frank's approval at each gate below.

## What would be merged (decisions #13–#20)
| # | Change | Files | Runtime effect |
|---|---|---|---|
| 13–14 | s.31 issue split from s.121/124; lawful-order element | `data/processed/issues.yaml`, `data/processed/dev100_issues.json`* | spot_issues sees one more issue; s.31 has no committee-first element |
| 15 | open "what rights" + end of employment → annual_leave | `src/agent/rules/entitlements.py`, `understand.py` | fires 0/100 on dev100 |
| 16 | case ranking by support-weighted section links, s.31 only | `src/index/tools.py`, `retrieve.py`, `config/params.yaml` | changes the offered ruling only for the s.31 issue |
| 17 | lawful-order exception from factual sub-elements | `issues.yaml`, `src/agent/rules/elements.py`, `decide.py` | check_elements prompt changes for s.123 / s.31 issues |
| 18 | per-employee calculation when figures differ | `state.py`, `prompts/extract_facts.md` v7, `decide.py`, `draft.py` | **extract_facts schema/prompt change → every cached question re-runs extract_facts and everything after it** |
| 20 | cross-issue consistency, outcome element, conflict guard (forced revise), ⑩ never keeps excluded keys | `elements.py`, `issues.yaml`, `draft.py` | +1 revise call when a draft contradicts the system |
| — | `LLM_CACHE_ONLY=1` replay flag | `src/llm.py` | none unless set |
\* `dev100_issues.json` is gitignored but read at runtime (few-shot picking in `draft.py`) — must be shipped by hand.

Not for production: `tools/exam/*`, `prompts/exam_c*.md` (exam benchmark tooling, separate PR) · `tools/corpus`, `tools/kb`,
`docs/benchmarks/adjudication_*` (research; check for copied ruling/exam text before committing anything) · everything under `data/`.

## Gates before merge
1. **Legal review** of the interpretations taken from one model answer: #17 (d) "conflict alone ≠ obstruction",
   #20 outcome wording and the s.121(1) exclusion. Until reviewed, `reviewed_by: draft` stays in issues.yaml.
2. **Evidence beyond the 4 pilot cases** (no cache for anything else, because of #18): recommended targeted Gemini run —
   the 10 dev questions on s.121/123/31 + the Huay Khwang demo question ≈ 11 × ~$0.20 ≈ $2.2–2.5 — instead of
   `make eval-dev` (~$78) or the 30-question subset (~$23). Compare against the 2026-10-01 dev runs where they exist.
3. **Demo freeze**: production is frozen for the client demo until client feedback (memory, 2026-10-02). Merging
   to main does not have to deploy; deploying needs that freeze lifted.

## Commit plan (small commits on the branch, then one PR)
1. taxonomy s.31 split + T1/T2 (#13, #14) · 2. entitlements companion + T3 (#15) · 3. case ranking + R1/R2 + qvec
fixture (#16) · 4. derived elements (#17) · 5. per-employee calc + extract_facts v7 + guards (#18) · 6. consistency +
guard + regression fixtures (#20) · 7. LLM_CACHE_ONLY · 8. decisions.md + design docs · (separate PR) exam tooling (#19).
Gate per commit: `pytest tests tools/exam`, ruff, mypy (no new errors vs the 24 pre-existing).

## Deploy steps (only after gates 1–3)
1. VM: `git pull` (main) · copy `data/processed/issues.yaml` (tracked) and `data/processed/dev100_issues.json` (scp).
2. `docker compose build api ui && docker compose up -d`.
3. Smoke (Gemini, ≈ $0.5): Huay Khwang demo question → payment table 5,250 / 42,000, total 47,250 must be unchanged;
   one Ram case (2/2554 Q4). Re-warm the demo question's cache before any client demo.
4. Rollback: `git checkout f50f467` + previous `issues.yaml` / `dev100_issues.json` + `docker compose up -d --build`.
