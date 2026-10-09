"""Pure helpers for the UI's run-status display (#22); kept out of app.py so they can be unit-tested."""

from __future__ import annotations


def status_banner(resp: dict) -> str | None:
    """Warning text for a non-ok /ask response, None for a normal answer."""
    status = resp.get("status") or "ok"
    if status == "ok" and not any(t.get("error") for t in resp.get("trace") or []):
        return None
    nodes = ", ".join(dict.fromkeys(r.get("node", "?") for r in resp.get("review_reasons") or [])) or "-"
    if status == "needs_review":
        return f"NEEDS_REVIEW — ระบบไม่ได้ให้คำตอบทางกฎหมาย เพราะขั้นตอน {nodes} ทำงานไม่สำเร็จ · โปรดลองใหม่"
    return (f"คำตอบนี้ไม่สมบูรณ์ (degraded): ขั้นตอน {nodes} ใช้ค่าสำรองแทนผลจริง "
            "· ตรวจสอบแหล่งที่มาก่อนใช้")


def trace_line(t: dict) -> str:
    line = f"**{t['node']}** · {t.get('ms', 0)} ms · LLM {t.get('llm_calls', 0)}"
    return line + (f" · ❌ error: `{t['error'][:300]}`" if t.get("error") else "")
