"""Gemini client: structured JSON output, disk cache, retry with backoff, usage accounting.

Cache key = sha256(model + system + prompt + schema + params) → data/processed/llm_cache/.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from src.config import settings

CACHE = Path("data/processed/llm_cache")
T = TypeVar("T", bound=BaseModel)


@dataclass
class Usage:
    calls: int = 0
    cached: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    log: list[dict] = field(default_factory=list)

    def add(self, name: str, inp: int, out: int, ms: int, cached: bool) -> None:
        self.calls += 1
        self.cached += cached
        self.input_tokens += inp
        self.output_tokens += out
        self.log.append({"name": name, "in": inp, "out": out, "ms": ms, "cached": cached})


USAGE = Usage()
_client = None


def client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def generate_json(prompt: str, schema: type[T], *, system: str = "", name: str = "llm",
                  temperature: float = 0.0, model: str | None = None, seed: int = 0,
                  use_cache: bool = True, thinking: str | None = None) -> T:
    """Call Gemini with a response schema and return a validated model instance.

    thinking: None = model default, or "low"/"medium"/"high" (Gemini 3 thinking_level).
    Thinking tokens are billed as output, so simple classification steps pass "low"."""
    from google.genai import types

    model = model or settings.gemini_model
    params = json.dumps({"t": temperature, "seed": seed, **({"thinking": thinking} if thinking else {})})
    key = _key(model, system, prompt, json.dumps(schema.model_json_schema(), sort_keys=True), params)
    path = CACHE / key[:2] / f"{key}.json"
    if use_cache and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        USAGE.add(name, data["usage"]["in"], data["usage"]["out"], 0, True)
        return schema.model_validate(data["output"])

    cfg = types.GenerateContentConfig(
        system_instruction=system or None,
        temperature=temperature,
        seed=seed,
        response_mime_type="application/json",
        response_schema=schema,
        thinking_config=types.ThinkingConfig(thinking_level=thinking.upper()) if thinking else None,
    )
    last: Exception | None = None
    for attempt in range(3):
        t0 = time.monotonic()
        try:
            if attempt:                       # a deterministic retry would repeat a parse failure
                cfg.seed, cfg.temperature = seed + attempt, max(temperature, 0.3)
            r = client().models.generate_content(model=model, contents=prompt, config=cfg)
            out = r.parsed if isinstance(r.parsed, schema) else schema.model_validate_json(r.text)
            um = r.usage_metadata
            # billed output = answer tokens + thinking tokens
            inp = um.prompt_token_count or 0
            outp = (um.candidates_token_count or 0) + (um.thoughts_token_count or 0)
            ms = int((time.monotonic() - t0) * 1000)
            USAGE.add(name, inp, outp, ms, False)
            if use_cache:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"output": out.model_dump(mode="json"),
                                            "usage": {"in": inp, "out": outp}},
                                           ensure_ascii=False), encoding="utf-8")
            return out
        except Exception as e:  # retry any API/parse failure
            code = getattr(e, "code", None)
            if isinstance(code, int) and 400 <= code < 500 and code != 429:
                raise RuntimeError(f"{name}: Gemini {code} (not retried): {e}") from e
            last = e
            if attempt < 2:
                time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"{name}: Gemini failed after 3 attempts: {last}") from last
