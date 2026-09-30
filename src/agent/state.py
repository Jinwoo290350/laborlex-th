"""Agent state passed between LangGraph nodes (CLAUDE.md §5.3)."""

from __future__ import annotations

import operator
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.agent.answer import AnswerJSON
from src.calc.labor import CalcResult


class Facts(BaseModel):
    event_date: date | None = Field(None, description="วันเกิดเหตุ ถ้าโจทย์ระบุ")
    wage_amount: float | None = Field(None, description="ค่าจ้างเป็นตัวเลข ถ้าระบุ")
    wage_period: Literal["day", "month", "hour", "piece"] | None = None
    start_date: date | None = Field(None, description="วันเริ่มทำงาน ถ้าโจทย์ระบุ (ค.ศ.)")
    end_date: date | None = Field(None, description="วันเลิกจ้าง/สิ้นสุดการจ้าง ถ้าโจทย์ระบุ (ค.ศ.)")
    service_years: int | None = Field(None, description="อายุงานส่วนปี ตามที่โจทย์เขียนไว้ตรง ๆ")
    service_months: int | None = Field(None, description="อายุงานส่วนเดือน ตามที่โจทย์เขียนไว้ตรง ๆ")
    service_days: int | None = Field(None, description="อายุงานส่วนวัน ตามที่โจทย์เขียนไว้ตรง ๆ")
    parties: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list,
                                 description="ข้อเท็จจริงสำคัญ ทีละข้อ ตามที่โจทย์ให้มา ไม่ตีความ")
    asked: list[str] = Field(default_factory=list, description="สิ่งที่คำถามต้องการให้ตอบ ทีละข้อ")
    missing: list[str] = Field(default_factory=list,
                               description="ข้อเท็จจริงที่จำเป็นแต่โจทย์ไม่ได้ให้")


class IssueSel(BaseModel):
    code: str
    reason: str


class ElementCheck(BaseModel):
    id: str
    status: Literal["met", "not_met", "unknown"]
    evidence: str = Field(description="ข้อเท็จจริงในโจทย์ที่ใช้ตัดสิน หรือเหตุที่ไม่ทราบ")


class Decision(BaseModel):
    p: float                      # probability the candidate applies
    confidence: float
    choice: str | None = None
    raw: dict = Field(default_factory=dict)


class AgentState(BaseModel):
    question: str
    question_id: str | None = None
    exclude_example_ids: list[str] = Field(default_factory=list)   # leave-one-out
    event_date: date | None = None

    facts: Facts | None = None
    issues: list[IssueSel] = Field(default_factory=list)
    candidates: dict[str, list[dict]] = Field(default_factory=dict)   # issue → provisions
    cases: dict[str, list[dict]] = Field(default_factory=dict)
    selected: dict[str, list[str]] = Field(default_factory=dict)      # issue → citation keys
    elements: dict[str, list[ElementCheck]] = Field(default_factory=dict)
    calcs: dict[str, CalcResult] = Field(default_factory=dict)
    drafts: list[AnswerJSON] = Field(default_factory=list)
    draft_scores: list[dict] = Field(default_factory=list)
    answer: AnswerJSON | None = None
    removed_citations: list[str] = Field(default_factory=list)
    markdown: str = ""

    trace: Annotated[list[dict], operator.add] = Field(default_factory=list)
