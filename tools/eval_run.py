"""Fresh, budget-guarded eval runs (docs/design/2026-10-11_dev100_accuracy_plan.md §4).

Wraps `src.eval.run_eval.main` in-process with three guards, without changing the eval code:
- run-local LLM cache: every call is fresh and the shared cache (data/processed/llm_cache) is never written;
- a cost cap: the next call is refused once the fresh spend exceeds --cap USD;
- the first 402 / 429 (credit or spending cap) stops the whole run at once, with no retries.

    python tools/eval_run.py --out data/processed/runs/<dir> --cap 16 -- --set dev100 --leave-one-out --split holdout
    python tools/eval_run.py --out ... --cap 0 --cache-only -- ...   # plumbing check, Gemini 0

Arguments after `--` go to run_eval unchanged. `harness_state.json` in --out records the spend and any stop.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

LOCK = threading.Lock()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cap", type=float, required=True, help="USD cap on fresh Gemini spend")
    ap.add_argument("--cache-only", action="store_true", help="no API calls at all (LLM_CACHE_ONLY=1)")
    ap.add_argument("--reuse", help="copy this run-local cache in first (resume an interrupted stage)")
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.cache_only:
        os.environ["LLM_CACHE_ONLY"] = "1"

    import src.llm as L
    from src.config import settings
    L.CACHE = out / "llm_cache"
    if a.reuse:
        import shutil
        shutil.copytree(a.reuse, L.CACHE, dirs_exist_ok=True)
    state: dict = {"cap": a.cap, "events": [], "started": time.strftime("%Y-%m-%d %H:%M:%S")}

    def spent() -> float:
        fresh = [c for c in L.USAGE.log if not c["cached"]]
        return sum(c["in"] * settings.gemini_price_in + c["out"] * settings.gemini_price_out for c in fresh) / 1e6

    def save() -> None:
        state.update(spent_usd=round(spent(), 4), calls=len(L.USAGE.log),
                     fresh_calls=sum(not c["cached"] for c in L.USAGE.log))
        (out / "harness_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    def stop(code: int, why: str) -> None:
        with LOCK:
            state["events"].append({"stop": why, "at": time.strftime("%H:%M:%S")})
            save()
        print(f"[eval_run] STOP: {why}", flush=True)
        os._exit(code)

    orig = L.client

    class _Models:
        def __init__(self, m):
            self.m = m

        def generate_content(self, *args, **kw):
            if spent() > a.cap:
                stop(5, f"cost cap ${a.cap} reached (${spent():.4f})")
            try:
                return self.m.generate_content(*args, **kw)
            except Exception as e:
                msg = str(e)
                if getattr(e, "code", None) in (402, 429) or "RESOURCE_EXHAUSTED" in msg or msg[:40].count("429"):
                    stop(3, f"API refused (credit / spending cap): {msg[:200]}")
                raise

    class _Client:
        def __init__(self, c):
            self.models = _Models(c.models)

    L.client = lambda: _Client(orig())
    rest = a.rest[1:] if a.rest[:1] == ["--"] else a.rest
    sys.argv = ["run_eval", *rest]
    from src.eval import run_eval
    try:
        run_eval.main()
    finally:
        save()
        print(f"[eval_run] spent ${state['spent_usd']} in {state['fresh_calls']} fresh calls "
              f"({state['calls']} total); state → {out / 'harness_state.json'}", flush=True)


if __name__ == "__main__":
    main()
