"""Legal hierarchy rule (CLAUDE.md §1 req. 12, §5.1).

พ.ร.บ./ประมวล (1) > พ.ร.ฎ. (2) > กฎกระทรวง (3) > ประกาศ (4). A subordinate instrument fills in
detail within the power its parent act grants. When both are cited, the answer must show
both and say which governs; if the subordinate text goes beyond the parent, the parent
prevails. (Principle pending the professors' confirmation — questions_for_professors #2.)
"""

from __future__ import annotations

LEVEL_NAME = {1: "พระราชบัญญัติ/ประมวลกฎหมาย", 2: "พระราชกฤษฎีกา", 3: "กฎกระทรวง", 4: "ประกาศ"}


def tag(r: dict) -> str:
    """Short hierarchy tag for a provision row, e.g. "กฎกระทรวง · ออกตาม พ.ร.บ.คุ้มครองแรงงาน"."""
    t = LEVEL_NAME.get(r.get("level") or 1, "")
    if r.get("parent_law_name"):
        t += f" · ออกตาม {r['parent_law_name']}"
    return t


def pair_notes(rows: list[dict]) -> list[str]:
    """Instructions for the drafter when a subordinate instrument and its parent act are
    both among the selected provisions."""
    laws = {r["law_name"]: r for r in rows}
    notes = []
    for r in rows:
        parent = r.get("parent_law_name")
        if parent and parent in laws and r["level"] > laws[parent]["level"]:
            notes.append(f"{r['law_name']} ({LEVEL_NAME.get(r['level'])}) ออกตาม {parent} — "
                         "อ้างทั้งสองฉบับ ระบุว่ากฎหมายลูกกำหนดรายละเอียดภายในกรอบกฎหมายแม่ "
                         "และถ้ากฎหมายลูกกำหนดเกินหรือขัดกรอบ ให้แจ้งว่าอาจขัดและยึดกฎหมายแม่")
    return list(dict.fromkeys(notes))
