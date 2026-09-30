"""LLM judge for the 6-criterion rubric (CLAUDE.md §3). Calibrate against professor
scores (Cohen's κ) before trusting it."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.agent.nodes.common import prompt
from src.llm import generate_json

CRITERIA = ["A1", "A2", "B0", "B1", "B2", "B3"]


class Score(BaseModel):
    A1: int = Field(ge=0, le=2)
    A2: int = Field(ge=0, le=2)
    B0: int = Field(ge=0, le=2)
    B1: int = Field(ge=0, le=2)
    B2: int = Field(ge=0, le=2)
    B3: int = Field(ge=0, le=2)
    reasons: str

    @property
    def passed(self) -> bool:
        return all(getattr(self, c) == 2 for c in CRITERIA)


def judge(question: str, gold: str, answer_md: str) -> Score:
    version, body = prompt("judge")
    return generate_json(body.format(question=question, gold=gold, answer=answer_md), Score,
                         name=f"judge_v{version}")
