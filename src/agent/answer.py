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
    calculation: list[str] = Field(default_factory=list)   # CalcResult.steps (set by ⑩ from the calculator)
    calculation_citations: list[str] = Field(default_factory=list)  # provisions the calculator used (⑩)
    conclusion: list[Point]
    opinion: str                     # short text for the summary table
    basis: str                       # e.g. "ม.13 พ.ร.บ.คุ้มครองแรงงาน, ม.577 ป.พ.พ."


class EmployeeOutcome(BaseModel):
    """Drafted by the LLM: only the legal judgement, never an amount."""
    name: str
    m119_applies: bool | None = None          # None = facts not enough to decide
    m119_ground: str = ""                     # e.g. "(2) จงใจทำให้นายจ้างได้รับความเสียหาย"


class PaymentRow(BaseModel):
    """Set by ⑩ from the calculator (never by the LLM)."""
    name: str
    m119_applies: bool | None
    severance: str
    notice_pay: str
    final_wage: str
    total: str
    note: str = ""


class AnswerJSON(BaseModel):
    preliminary: list[Point]
    issues: list[Issue]
    follow_up_questions: list[str] = Field(default_factory=list)
    # set by the system in ⑩ from the DB's amendment footnotes (anything the LLM puts here is replaced)
    version_notes: list[str] = Field(default_factory=list)
    # each dismissed employee and whether ม.119 applies (LLM); amounts per employee (⑩, calculator)
    employees: list[EmployeeOutcome] = Field(default_factory=list)
    payments: list[PaymentRow] = Field(default_factory=list)
    payments_total: str = ""
    payments_steps: list[str] = Field(default_factory=list)
    payments_citations: list[str] = Field(default_factory=list)

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
            keys.update(i.calculation_citations)
        keys.update(self.payments_citations)
        return keys
