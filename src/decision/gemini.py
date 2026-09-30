"""Gemini fallback decider: the same typed questions answered by one JSON call,
self-consistency over n samples."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from src.agent.state import Decision
from src.decision.base import QuestionSpec
from src.llm import generate_json


class _Ans(BaseModel):
    name: str
    p_yes: float | None = Field(None, ge=0, le=1, description="noul: P(yes)")
    choice: str | None = Field(None, description="choice: chosen option name")
    level: int | None = Field(None, description="score: chosen level index (0-based)")


class _Answers(BaseModel):
    answers: list[_Ans]


class GeminiDecider:
    name = "gemini"

    def __init__(self, n: int = 1):
        self.n = n

    def decide(self, state: str | dict, questions: dict[str, QuestionSpec]) -> dict[str, Decision]:
        spec = {k: q.to_api() for k, q in questions.items()}
        prompt = (f"สถานะ (state):\n{json.dumps(state, ensure_ascii=False)}\n\n"
                  f"ตอบทุกคำถามต่อไปนี้ (noul → p_yes, choice → choice จาก criteria เท่านั้น, "
                  f"score → level):\n{json.dumps(spec, ensure_ascii=False, indent=1)}")
        runs = [generate_json(prompt, _Answers, name="decide", temperature=0.0 if i == 0 else 0.7, seed=i)
                for i in range(self.n)]
        out = {}
        for k, q in questions.items():
            got = [a for r in runs for a in r.answers if a.name == k]
            if q.type == "noul":
                ps = [a.p_yes for a in got if a.p_yes is not None] or [0.5]
                p = sum(ps) / len(ps)
                out[k] = Decision(p=p, confidence=abs(2 * p - 1), raw={"samples": ps})
            elif q.type == "choice":
                opts = list(q.criteria or {})
                votes = [a.choice for a in got if a.choice in opts]
                best = max(set(votes), key=votes.count) if votes else None
                p = votes.count(best) / len(votes) if votes else 0.0
                out[k] = Decision(p=p, confidence=p, choice=best, raw={"votes": votes})
            else:
                lv = [a.level for a in got if a.level is not None] or [0]
                n_levels = len(q.criteria or []) or 2
                out[k] = Decision(p=sum(lv) / len(lv) / max(n_levels - 1, 1), confidence=1.0,
                                  raw={"levels": lv})
        return out
