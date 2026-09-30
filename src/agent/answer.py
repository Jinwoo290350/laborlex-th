"""AnswerJSON: the structured answer drafted by the LLM, validated, then rendered."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Cited(BaseModel):
    text: str
    citations: list[str] = Field(default_factory=list)  # citation_key or "DEKA:<no>"


class Point(BaseModel):
    headline: str                    # rendered bold
    detail: str = ""
    citations: list[str] = Field(default_factory=list)


class LawRef(BaseModel):
    citation_key: str
    label: str                       # e.g. "มาตรา 13 พระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541"
    explanation: str
    topic: str                       # bold principle name


class Step(BaseModel):
    fact: str
    result: str                      # legal consequence of the fact


class Application(BaseModel):
    heading: str                     # e.g. "มาตรา 118 (ค่าชดเชย)"
    steps: list[Step]
    citations: list[str] = Field(default_factory=list)


class Issue(BaseModel):
    code: str = ""                   # taxonomy code
    question: str
    consider: str
    laws: list[LawRef]
    application: list[Application]
    calculation: list[str] = Field(default_factory=list)   # CalcResult.steps
    conclusion: list[Point]
    opinion: str                     # short text for the summary table
    basis: str                       # e.g. "ม.13 พ.ร.บ.คุ้มครองแรงงาน, ม.577 ป.พ.พ."


class AnswerJSON(BaseModel):
    preliminary: list[Point]
    issues: list[Issue]
    follow_up_questions: list[str] = Field(default_factory=list)

    def all_citations(self) -> set[str]:
        keys: set[str] = set()
        for p in self.preliminary:
            keys.update(p.citations)
        for i in self.issues:
            keys.update(law.citation_key for law in i.laws)
            for a in i.application:
                keys.update(a.citations)
            for p in i.conclusion:
                keys.update(p.citations)
        return keys
