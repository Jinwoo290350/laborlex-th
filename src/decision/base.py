"""DecisionModel (CLAUDE.md §5.4): System-1 typed decisions, swappable via DECIDER.

The question format mirrors the System One contract (POST /v1/systemone) used by
OpenThai-SystemOne and Jev: a state plus named questions of type
  noul   — yes/no, answered as P(yes)
  choice — one of up to 255 named options
  score  — 2..10 ordered levels
so every backend (including the Gemini fallback) takes the same request.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel

from src.agent.state import Decision


class QuestionSpec(BaseModel):
    type: Literal["noul", "choice", "score"]
    instructions: str
    criteria: dict[str, str | None] | list[str] | None = None   # choice: options; score: levels

    def to_api(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type, "instructions": self.instructions}
        if self.criteria is not None:
            d["criteria"] = self.criteria
        return d


class DecisionModel(Protocol):
    name: str

    def decide(self, state: str | dict, questions: dict[str, QuestionSpec]) -> dict[str, Decision]:
        """Decision.p = P(yes) for noul, P(chosen) for choice, normalised score for score;
        Decision.choice = chosen option (choice) or None; raw = backend answer."""
        ...


def get_decider(name: str | None = None) -> DecisionModel:
    from src.config import settings
    name = name or settings.decider
    if name == "openthai":
        from src.decision.openthai import OpenThaiDecider
        return OpenThaiDecider()
    if name == "gemini":
        from src.decision.gemini import GeminiDecider
        return GeminiDecider()
    raise NotImplementedError(f"DECIDER={name} not implemented (jev: waiting for API access)")
