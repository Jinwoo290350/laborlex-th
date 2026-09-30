"""OpenThai-SystemOne backend (iApp). Contract: https://iapp.co.th/docs/llm/openthai-systemone

Hosted:  POST https://api.iapp.co.th/v3/store/openthai/systemone  (header apikey)
         free preview: 100 req/min, 1,000 decisions/day per key
Local:   set OPENTHAI_URL=http://127.0.0.1:8000/v1/systemone  (open weights, no quota)
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx

from src.agent.state import Decision
from src.config import settings
from src.decision.base import QuestionSpec

HOSTED = "https://api.iapp.co.th/v3/store/openthai/systemone"
CACHE = Path("data/processed/decision_cache")


class OpenThaiDecider:
    name = "openthai"

    def __init__(self, url: str | None = None):
        self.url = url or os.environ.get("OPENTHAI_URL") or HOSTED
        self.headers = {"apikey": settings.iapp_api_key} if self.url == HOSTED else {}

    def _post(self, body: dict) -> dict:
        key = hashlib.sha256((self.url + json.dumps(body, ensure_ascii=False, sort_keys=True))
                             .encode()).hexdigest()
        path = CACHE / key[:2] / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        last = None
        for attempt in range(4):
            r = httpx.post(self.url, headers=self.headers, json=body, timeout=120)
            if r.status_code == 429:                       # per-minute limit
                last = r.text
                time.sleep(15 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        raise RuntimeError(f"openthai rate-limited: {last}")

    def decide(self, state: str | dict, questions: dict[str, QuestionSpec]) -> dict[str, Decision]:
        data = self._post({"state": state, "questions": {k: q.to_api() for k, q in questions.items()}})
        out = {}
        for name, a in data["answers"].items():
            if a["type"] == "noul":
                p = float(a["noul"])
                out[name] = Decision(p=p, confidence=abs(2 * p - 1), raw=a)
            elif a["type"] == "choice":
                out[name] = Decision(p=float(a["probabilities"][a["choice"]]),
                                     confidence=float(a.get("confidence", 0)), choice=a["choice"], raw=a)
            else:
                levels = len(a["probabilities"])
                out[name] = Decision(p=float(a["score"]) / max(levels - 1, 1),
                                     confidence=float(a.get("confidence", 0)), raw=a)
        return out
