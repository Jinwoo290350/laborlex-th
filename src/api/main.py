"""FastAPI: /ask runs the flow; /provision returns full text for a citation."""

from __future__ import annotations

import secrets
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from src.config import settings

app = FastAPI(title="LaborLex-TH")
security = HTTPBasic(auto_error=False)


def auth(cred: Annotated[HTTPBasicCredentials | None, Depends(security)]) -> None:
    if not settings.app_password:
        return
    if cred is None or not secrets.compare_digest(cred.password, settings.app_password):
        raise HTTPException(401, "unauthorized", headers={"WWW-Authenticate": "Basic"})


class AskIn(BaseModel):
    question: str
    event_date: date | None = None


class AskOut(BaseModel):
    markdown: str
    answer: dict | None
    citations: list[dict]
    follow_up_questions: list[str]
    trace: list[dict]


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/ask", response_model=AskOut, dependencies=[Depends(auth)])
def ask(body: AskIn) -> AskOut:
    from src.agent.graph import answer
    from src.index.tools import get_provision
    s = answer(body.question, event_date=body.event_date)
    keys = sorted(s.answer.all_citations()) if s.answer else []
    cites = [c for c in (get_provision(k, s.event_date) for k in keys) if c]
    return AskOut(markdown=s.markdown, answer=s.answer.model_dump() if s.answer else None,
                  citations=[_public(c) for c in cites],
                  follow_up_questions=s.answer.follow_up_questions if s.answer else [],
                  trace=s.trace)


@app.get("/provision/{citation_key:path}", dependencies=[Depends(auth)])
def provision(citation_key: str) -> dict:
    from src.index.tools import get_provision, get_section
    r = get_provision(citation_key)
    if r is None:
        raise HTTPException(404, "not found")
    return {**_public(r), "section": [_public(x) for x in get_section(r["law"], r["section_no"])]}


def _public(r: dict) -> dict:
    return {k: (str(v) if isinstance(v, date) else v) for k, v in r.items()
            if k in ("citation_key", "law", "law_name", "level", "section_no", "paragraph_no",
                     "sub_no", "chapter", "chapter_title", "text", "valid_from", "valid_to",
                     "amendment_notes")}
