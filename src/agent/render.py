"""AnswerJSON → markdown in the client's layout (prompts/answer_template.md)."""

from src.agent.answer import AnswerJSON


def _b(s: str) -> str:
    """Bold once: the LLM sometimes wraps headlines in ** itself."""
    return f"**{s.strip().strip('*').strip()}**"


def _chips(keys: list[str]) -> str:
    return " " + " ".join(f"`[{k}]`" for k in keys) if keys else ""


def render(a: AnswerJSON) -> str:
    out = ["# คำตอบทางกฎหมาย", "## คำตอบเบื้องต้น", "จากข้อเท็จจริงที่ปรากฏ", ""]
    out += [f"- {_b(p.headline)} {p.detail}{_chips(p.citations)}".rstrip() for p in a.preliminary]
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
        out += ["", "### ข้อสรุปประเด็นนี้"]
        out += [f"- {_b(p.headline)} {p.detail}{_chips(p.citations)}".rstrip() for p in i.conclusion]

    out += ["", "## ความเห็นทางกฎหมาย", "| ประเด็น | ข้อสรุป | ฐานกฎหมาย |", "|---|---|---|"]
    out += [f"| {i.question} | {i.opinion} | {i.basis} |" for i in a.issues]
    if a.version_notes:
        out += ["", "## หมายเหตุฉบับกฎหมาย"] + [f"- {n}" for n in a.version_notes]
    if a.follow_up_questions:
        out += ["", "## ข้อเท็จจริงที่ต้องถามเพิ่ม"] + [f"- {q}" for q in a.follow_up_questions]
    return "\n".join(out) + "\n"
