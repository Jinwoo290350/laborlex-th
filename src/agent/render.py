"""AnswerJSON → markdown in the client's layout (prompts/answer_template.md)."""

from src.agent.answer import AnswerJSON


def _b(s: str) -> str:
    """Bold once: the LLM sometimes wraps headlines in ** itself."""
    return f"**{s.strip().strip('*').strip()}**"


_LABELS: dict[str, str] = {}


def _chips(keys: list[str]) -> str:
    return " " + " ".join(f"`[{_LABELS.get(k, k)}]`" for k in keys) if keys else ""


def render(a: AnswerJSON, labels: dict[str, str] | None = None) -> str:
    """labels: citation_key → short reader-facing reference (built from the DB at ⑩)."""
    _LABELS.clear()
    _LABELS.update(labels or {})
    out = ["# คำตอบทางกฎหมาย", "## คำตอบเบื้องต้น", "จากข้อเท็จจริงที่ปรากฏ", ""]
    out += [f"- {_b(p.headline)} {p.detail}{_chips(p.citations)}".rstrip() for p in a.preliminary]
    if a.payments:
        out += ["", "## สรุปจำนวนเงินที่นายจ้างต้องจ่าย",
                "| ลูกจ้าง | ค่าชดเชย | สินจ้างแทนการบอกกล่าวล่วงหน้า | ค่าจ้างงวดสุดท้าย | รวม | หมายเหตุ |",
                "|---|---:|---:|---:|---:|---|"]
        out += [f"| {r.name} | {r.severance} | {r.notice_pay} | {r.final_wage} | **{r.total}** | {r.note} |"
                for r in a.payments]
        out += ["", f"**รวมทั้งสิ้น {a.payments_total} บาท**", "", "วิธีคำนวณ (ต่อลูกจ้างหนึ่งคน)"]
        out += [f"- {s}" for s in a.payments_steps]
        if a.payments_citations:
            out += [f"- บทบัญญัติที่ใช้ในการคำนวณ:{_chips(a.payments_citations)}"]
    out += ["", "เพื่อให้ได้ข้อสรุปโดยละเอียด จำเป็นต้องพิจารณาข้อกฎหมายและข้อเท็จจริงเป็นรายประเด็น",
            "", "## ประเด็นทางกฎหมายที่ต้องพิจารณา"]
    out += [f"{n}. {i.question}" for n, i in enumerate(a.issues, 1)]

    for n, i in enumerate(a.issues, 1):
        out += ["", f"## {n}. {i.question}", "### สิ่งที่ต้องพิจารณา", i.consider,
                "", "### กฎหมายที่เกี่ยวข้อง"]
        for law in i.laws:
            out += [f"- **{law.label}**",
                    f"  {law.explanation} (**{law.topic}**){_chips([law.citation_key])}"]
        out += ["", "### การปรับบทกฎหมายกับข้อเท็จจริง"]
        for ap in i.application:
            out += [f"**{ap.heading}**"]
            out += [f"- {st.fact} → {st.result}" for st in ap.steps]
            if ap.citations:
                out[-1] += _chips(ap.citations)
        if i.calculation:
            out += ["", "### การคำนวณ"] + [f"- {s}" for s in i.calculation]
            if i.calculation_citations:
                out += [f"- บทบัญญัติที่ใช้ในการคำนวณ:{_chips(i.calculation_citations)}"]
        out += ["", "### ข้อสรุปประเด็นนี้"]
        out += [f"- {_b(p.headline)} {p.detail}{_chips(p.citations)}".rstrip() for p in i.conclusion]

    out += ["", "## ความเห็นทางกฎหมาย", "| ประเด็น | ข้อสรุป | ฐานกฎหมาย |", "|---|---|---|"]
    out += [f"| {i.question} | {i.opinion} | {i.basis} |" for i in a.issues]
    if a.version_notes:
        out += ["", "## หมายเหตุฉบับกฎหมาย"] + [f"- {n}" for n in a.version_notes]
    if a.follow_up_questions:
        out += ["", "## ข้อเท็จจริงที่ต้องถามเพิ่ม"] + [f"- {q}" for q in a.follow_up_questions]
    return "\n".join(out) + "\n"
