"""Shared helpers for nodes: prompt loading, tracing, provision formatting."""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import cache, lru_cache, wraps
from pathlib import Path
from typing import Any

import yaml

from src.agent.state import AgentState
from src.llm import USAGE

PROMPTS = Path("prompts")


@cache
def prompt(name: str) -> tuple[str, str]:
    """Return (version, body) of prompts/<name>.md."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    _, header, body = text.split("---", 2)
    version = yaml.safe_load(header).get("version", "?")
    return str(version), body.strip()


@lru_cache(maxsize=1)
def taxonomy() -> dict[str, dict]:
    items = yaml.safe_load(Path("data/processed/issues.yaml").read_text(encoding="utf-8"))
    return {i["code"]: i for i in items}


def traced(name: str, fallback: Callable[[AgentState, Exception], dict] | None = None):
    """Wrap a node: record latency/tokens in state.trace; on failure use a safe fallback."""
    def deco(fn: Callable[[AgentState], dict]):
        @wraps(fn)
        def run(state: AgentState) -> dict[str, Any]:
            t0, n0 = time.monotonic(), len(USAGE.log)
            err = None
            try:
                out = fn(state)
            except Exception as e:  # node failure must not crash the run
                if fallback is None:
                    raise
                err = repr(e)
                out = fallback(state, e)
            calls = USAGE.log[n0:]
            entry = {"node": name, "ms": int((time.monotonic() - t0) * 1000),
                     "llm_calls": len(calls), "cached": sum(c["cached"] for c in calls),
                     "in_tokens": sum(c["in"] for c in calls),
                     "out_tokens": sum(c["out"] for c in calls),
                     "summary": out.pop("_summary", None)}
            if err:
                entry["error"] = err
            return {**out, "trace": [entry]}
        return run
    return deco


def fmt_provision(r: dict, max_len: int = 1500) -> str:
    from src.agent.rules.hierarchy import tag
    note = f" [หมายเหตุแก้ไข: {'; '.join(r['amendment_notes'])}]" if r.get("amendment_notes") else ""
    return f"{r['citation_key']} | {r['law_name']} [{tag(r)}] | {r['text'][:max_len]}{note}"


def fmt_facts(state: AgentState) -> str:
    f = state.facts
    if f is None:
        return state.question
    lines = [f"- {x}" for x in f.key_facts]
    nums = {k: v for k, v in f.model_dump(exclude={"key_facts", "asked", "missing", "parties"}).items()
            if v is not None}
    if nums:
        lines.append(f"- ข้อมูลตัวเลข: {nums}")
    if f.missing:
        lines.append(f"- ข้อเท็จจริงที่ไม่ทราบ: {', '.join(f.missing)}")
    return "\n".join(lines)
