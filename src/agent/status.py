"""Run status (#22): what every consumer (API, UI, eval, harnesses) must check before treating a run as an answer."""

from __future__ import annotations

from src.agent.state import AgentState, Status

NODE_TH = {"extract_facts": "สกัดข้อเท็จจริง", "check_elements": "ตรวจองค์ประกอบ", "verify_select": "ตรวจและเลือกคำตอบ"}


def effective_status(state: AgentState | dict) -> Status:
    """needs_review > degraded > ok. Any trace error makes the run at least degraded, so a fallback can
    never look ok (the trace is the safety net for eval and historical audit)."""
    s = state if isinstance(state, dict) else state.model_dump(include={"status", "trace"})
    status = s.get("status") or "ok"
    if status == "needs_review":
        return "needs_review"
    if status == "degraded" or any(t.get("error") for t in s.get("trace") or []):
        return "degraded"
    return "ok"


def review_notice(degraded: list[dict]) -> str:
    """Fixed notice for a needs_review run: no legal content."""
    nodes = list(dict.fromkeys(d["node"] for d in degraded)) or ["ไม่ทราบ"]
    issues = [d["issue"] for d in degraded if d.get("issue")]
    where = ", ".join(f"*{NODE_TH.get(n, n)}* ({n})" for n in nodes)
    extra = f" · ประเด็นที่ตรวจไม่สำเร็จ: {', '.join(issues)}" if issues else ""
    return ("⚠️ **ระบบยังไม่สามารถให้คำตอบทางกฎหมายสำหรับคำถามนี้ได้** — ขั้นตอน "
            f"{where} ทำงานไม่สำเร็จ{extra}\n\n"
            "จึงไม่ได้สรุปผลทางกฎหมาย เพื่อป้องกันคำตอบที่ไม่ครบถ้วน · โปรดลองใหม่อีกครั้ง "
            "หรือส่งให้ผู้เชี่ยวชาญตรวจ (สถานะ: NEEDS_REVIEW)")
