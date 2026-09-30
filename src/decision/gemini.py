"""Gemini decider: one JSON call per question, self-consistency over n seeds."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field

from src.agent.state import Decision
from src.decision.base import QuestionSpec
from src.llm import generate_json


class _Answer(BaseModel):
    applies: bool
    p: float = Field(ge=0, le=1)
    reason: str


class GeminiDecider:
    def __init__(self, n: int = 1):
        self.n = n

    def _one(self, q: QuestionSpec) -> Decision:
        outs = [generate_json(f"{q.context}\n\nคำถาม: {q.text}\nตอบ applies (จริง/เท็จ), "
                              f"p = ความน่าจะเป็นที่ใช่ และเหตุผลสั้น ๆ", _Answer,
                              name="decide", temperature=0.0 if i == 0 else 0.7, seed=i)
                for i in range(self.n)]
        p = sum(o.p for o in outs) / len(outs)
        agree = sum(o.applies for o in outs) / len(outs)
        return Decision(p=p, confidence=max(agree, 1 - agree),
                        raw={"reasons": [o.reason for o in outs]})

    def decide(self, questions: dict[str, QuestionSpec]) -> dict[str, Decision]:
        with ThreadPoolExecutor(8) as ex:
            return dict(zip(questions, ex.map(self._one, questions.values())))
