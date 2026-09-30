"""Parse Thai statute text into หมวด → ส่วน → มาตรา → วรรค → อนุมาตรา.

Input is plain text (from a text PDF, OCR output, or krisdika copy).
Output is a list of Section objects, which flatten into provision rows
(one row per paragraph, plus one row per sub-item) with a unique citation_key.

Paragraph detection: a new paragraph starts on a line that is indented or follows
a blank line. Non-indented lines are wrap-continuations of the previous line.
Sub-items are lines starting with "(n)" and belong to the preceding paragraph.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
THAI_CHAR = re.compile("[\u0e00-\u0e7f]")

# Page furniture commonly left by PDF extraction. Extend per source as needed.
DEFAULT_NOISE = [
    re.compile(r"^\s*-\s*\d+\s*-\s*$"),                 # "- 12 -"
    re.compile(r"^\s*(หน้า|page)\s*\d+(\s*/\s*\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),                          # bare page number
    re.compile(r"^\s*เล่ม\s*\d+.*ราชกิจจานุเบกษา.*$"),
]

CHAPTER_RE = re.compile(r"^\s*หมวด\s*(\d+)\s*(.*)$")
PART_RE = re.compile(r"^\s*ส่วนที่\s*(\d+)\s*(.*)$")
SUB_RE = re.compile(r"^\s*\((\d+)\)\s*(.*)$")
NOTE_RE = re.compile(r"^\s*\[.*\]\s*$")               # krisdika amendment notes
REPEALED_RE = re.compile(r"^\(?ยกเลิก\)?$")
INDENT_RE = re.compile(r"^(\t| {2,})")


def normalize(text: str, noise: list[re.Pattern[str]] | None = None) -> str:
    """Thai digits → Arabic, drop zero-width chars, NBSP → space, strip page furniture.

    Leading indentation is preserved (it is the paragraph signal)."""
    noise = DEFAULT_NOISE if noise is None else noise
    text = ZERO_WIDTH.sub("", text.translate(THAI_DIGITS)).replace(" ", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in text.split("\n"):
        line = line.rstrip()
        if any(p.match(line) for p in noise):
            continue
        # collapse inner runs of spaces but keep leading indent
        lead = INDENT_RE.match(line)
        body = re.sub(r"[ \t]+", " ", line.strip())
        out.append(("  " if lead else "") + body)
    return "\n".join(out)


def _join(a: str, b: str) -> str:
    """Join a wrapped line; Thai-to-Thai wraps get no space."""
    if not a:
        return b
    if THAI_CHAR.match(a[-1]) and THAI_CHAR.match(b[:1] or " "):
        return a + b
    return a + " " + b


def section_sort_key(no: str) -> tuple[int, int]:
    main, _, sub = no.partition("/")
    return int(main), int(sub or 0)


@dataclass
class Paragraph:
    text: str = ""
    subs: list[tuple[str, str]] = field(default_factory=list)  # [("(1)", text), ...]

    def full_text(self) -> str:
        return "\n".join([self.text, *(f"{n} {t}" for n, t in self.subs)]).strip()


@dataclass
class Section:
    section_no: str
    chapter: str | None = None
    part: str | None = None
    paragraphs: list[Paragraph] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    repealed: bool = False

    def full_text(self) -> str:
        return "\n".join(p.full_text() for p in self.paragraphs)


@dataclass
class ProvisionRow:
    citation_key: str
    section_no: str
    paragraph_no: int
    sub_no: str | None
    text: str
    chapter: str | None
    repealed: bool


def parse(text: str, unit: str = "มาตรา", normalized: bool = False) -> list[Section]:
    """unit: "มาตรา" for acts/decrees, "ข้อ" for ministerial regulations/announcements."""
    if not normalized:
        text = normalize(text)
    head_re = re.compile(rf"^\s*{unit}\s*(\d+(?:/\d+)?)\s*(.*)$")

    sections: list[Section] = []
    chapter = part = None
    cur: Section | None = None
    new_para = True      # next text line starts a new paragraph
    in_sub = False       # last text went into a sub-item

    for line in text.split("\n"):
        if not line.strip():
            new_para = True
            continue
        stripped = line.strip()

        if m := CHAPTER_RE.match(stripped):
            chapter = f"หมวด {m.group(1)}"
            part, cur = None, None
            continue
        if m := PART_RE.match(stripped):
            part = f"ส่วนที่ {m.group(1)}"
            cur = None
            continue

        m = head_re.match(stripped)
        # A section heading must advance the numbering; otherwise it is a wrapped
        # cross-reference such as "...ตาม\nมาตรา 17 ..." and is treated as body text.
        if m and (cur is None or section_sort_key(m.group(1)) > section_sort_key(cur.section_no)):
            cur = Section(section_no=m.group(1), chapter=chapter, part=part)
            sections.append(cur)
            rest = m.group(2).strip()
            if REPEALED_RE.match(rest):
                cur.repealed = True
                cur.paragraphs.append(Paragraph(text="(ยกเลิก)"))
                new_para = True
                continue
            if rest:
                cur.paragraphs.append(Paragraph(text=rest))
            new_para, in_sub = not rest, False
            continue

        if cur is None:          # preamble / title text before the first section
            continue
        if NOTE_RE.match(stripped):
            cur.notes.append(stripped.strip("[] "))
            new_para = True
            continue

        if m := SUB_RE.match(stripped):
            if not cur.paragraphs:
                cur.paragraphs.append(Paragraph())
            cur.paragraphs[-1].subs.append((f"({m.group(1)})", m.group(2)))
            new_para, in_sub = False, True
            continue

        indented = line.startswith("  ")
        if new_para or indented or not cur.paragraphs:
            cur.paragraphs.append(Paragraph(text=stripped))
            in_sub = False
        elif in_sub:
            p = cur.paragraphs[-1]
            n, t = p.subs[-1]
            p.subs[-1] = (n, _join(t, stripped))
        else:
            p = cur.paragraphs[-1]
            p.text = _join(p.text, stripped)
        new_para = False

    return sections


def to_rows(sections: list[Section], law: str) -> list[ProvisionRow]:
    """Flatten to DB rows. Key: "<LAW>:<section>:<paragraph>" or "<LAW>:<section>:<para>:(n)"."""
    rows: list[ProvisionRow] = []
    for s in sections:
        for i, p in enumerate(s.paragraphs, start=1):
            base = f"{law}:{s.section_no}:{i}"
            rows.append(ProvisionRow(base, s.section_no, i, None, p.full_text(), s.chapter, s.repealed))
            for n, t in p.subs:
                rows.append(ProvisionRow(f"{base}:{n}", s.section_no, i, n, t, s.chapter, s.repealed))
    dupes = [k for k, c in Counter(r.citation_key for r in rows).items() if c > 1]
    if dupes:
        raise ValueError(f"duplicate citation keys in {law}: {sorted(dupes)[:10]}")
    return rows
