"""DecisionModel protocol (CLAUDE.md §5.4): System-1 yes/no judgements, swappable via DECIDER."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from src.agent.state import Decision


class QuestionSpec(BaseModel):
    text: str                  # "บทนี้ใช้กับข้อเท็จจริงนี้ไหม"
    context: str               # short: facts + one candidate


class DecisionModel(Protocol):
    def decide(self, questions: dict[str, QuestionSpec]) -> dict[str, Decision]: ...


def get_decider(name: str | None = None) -> DecisionModel:
    from src.config import settings
    name = name or settings.decider
    if name == "gemini":
        from src.decision.gemini import GeminiDecider
        return GeminiDecider()
    raise NotImplementedError(f"DECIDER={name} not implemented yet (openthai/jev: Day 10)")
