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

CHAPTER_RE = re.compile(r"^\s*(หมวด\s*\d+|บทเฉพาะกาล)\s*(.*)$")
PART_RE = re.compile(r"^\s*ส่วนที่\s*(\d+)\s*(.*)$")
SUB_RE = re.compile(r"^\s*\((\d+)\)\s*(.*)$")
LETTER_SUB_RE = re.compile(r"^\s*\([ก-ฮ]\)\s*")       # (ก) items nest inside the current (n)
NOTE_RE = re.compile(r"^\s*\[.*\]\s*$")               # krisdika amendment notes
REPEALED_RE = re.compile(r"^\(?ยกเลิก\)?$")
FN_RE = re.compile(r"\s*\[\^(\d+)\]")             # footnote refs from extract.py
SLASH_PAREN_RE = re.compile(r"(มาตรา\s*\d+)/\((\d+)\)")  # docx typo "มาตรา 4/(1)"
INDENT_RE = re.compile(r"^(\t| {2,})")


def normalize(text: str, noise: list[re.Pattern[str]] | None = None) -> str:
    """Thai digits → Arabic, drop zero-width chars, NBSP → space, strip page furniture.

    Leading indentation is preserved (it is the paragraph signal)."""
    noise = DEFAULT_NOISE if noise is None else noise
    text = ZERO_WIDTH.sub("", text.translate(THAI_DIGITS)).replace("\u00a0", " ")
    text = SLASH_PAREN_RE.sub(r"\1/\2", text)
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


LATIN_SUFFIX = ["ทวิ", "ตรี", "จัตวา", "เบญจ", "ฉ", "สัตต", "อัฏฐ", "นว", "ทศ"]
SUFFIX_RE = "|".join(LATIN_SUFFIX)


def section_sort_key(no: str) -> tuple[int, int, int]:
    """"118" < "118/1" ; "17" < "17ทวิ" < "17ตรี" (older acts use Latin ordinals)."""
    m = re.match(rf"(\d+)(?:/(\d+))?({SUFFIX_RE})?$", no)
    if not m:
        raise ValueError(f"bad section number {no!r}")
    suffix = LATIN_SUFFIX.index(m.group(3)) + 1 if m.group(3) else 0
    return int(m.group(1)), int(m.group(2) or 0), suffix


@dataclass
class Paragraph:
    text: str = ""
    subs: list[tuple[str, str]] = field(default_factory=list)  # [("(1)", text), ...]
    fns: list[str] = field(default_factory=list)                # footnotes on the lead text
    sub_fns: dict[str, list[str]] = field(default_factory=dict)

    def full_text(self) -> str:
        return "\n".join([self.text, *(f"{n} {t}" for n, t in self.subs)]).strip()

    def all_fns(self) -> list[str]:
        return list(dict.fromkeys(self.fns + [f for v in self.sub_fns.values() for f in v]))


@dataclass
class Section:
    section_no: str
    chapter: str | None = None
    part: str | None = None
    paragraphs: list[Paragraph] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    repealed: bool = False
    chapter_title: str | None = None

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
    footnotes: list[str] = field(default_factory=list)


def parse(text: str, unit: str = "มาตรา", normalized: bool = False) -> list[Section]:
    """unit: "มาตรา" for acts/decrees, "ข้อ" for ministerial regulations/announcements.

    If the text carries indentation (output of extract.py), headings, sub-items and
    chapters are only recognised on indented lines; unindented lines are wraps. This
    stops a wrapped cross-reference ("…ตาม\nมาตรา 17/1 หรือ…") from opening a section."""
    if not normalized:
        text = normalize(text)
    head_re = re.compile(rf"^\s*{unit}\s*(\d+(?:/\d+)?(?:\s*(?:{SUFFIX_RE})(?=\s|\[|$))?)\s*(.*)$")
    lines = text.split("\n")
    indent_mode = any(ln.startswith("  ") for ln in lines)

    sections: list[Section] = []
    chapter = part = chapter_title = None
    await_title = False
    cur: Section | None = None
    new_para = True      # next text line starts a new paragraph
    in_sub = False       # last text went into a sub-item

    def next_unit(i: int) -> str | None:
        """Stripped text of the next line that starts a unit, after line i."""
        for ln in lines[i + 1:]:
            if ln.strip() and (ln.startswith("  ") or not indent_mode):
                return FN_RE.sub("", ln).strip()
        return None

    for i, line in enumerate(lines):
        if not line.strip():
            new_para = True
            continue
        fns = FN_RE.findall(line)
        stripped = FN_RE.sub("", line).strip()
        if not stripped:
            continue
        starts_unit = line.startswith("  ") or not indent_mode

        if starts_unit and (m := CHAPTER_RE.match(stripped)) and not head_re.match(stripped):
            chapter = re.sub(r"\s+", " ", m.group(1))
            chapter_title = m.group(2).strip() or None
            await_title = chapter_title is None
            part, cur = None, None
            continue
        if await_title and cur is None and not head_re.match(stripped):
            chapter_title, await_title = stripped, False
            continue
        if starts_unit and (m := PART_RE.match(stripped)):
            part = f"ส่วนที่ {m.group(1)}"
            cur = None
            continue

        m = head_re.match(stripped) if starts_unit else None
        # A heading must also advance the numbering (guards non-indented sources).
        if m and (cur is None or section_sort_key(re.sub(r"\s+", "", m.group(1)))
                  > section_sort_key(cur.section_no)):
            cur = Section(section_no=re.sub(r"\s+", "", m.group(1)), chapter=chapter, part=part,
                          chapter_title=chapter_title)
            sections.append(cur)
            await_title = False
            rest = m.group(2).strip()
            cur.repealed = bool(REPEALED_RE.match(rest))
            cur.paragraphs.append(Paragraph(text=rest, fns=fns))
            new_para, in_sub = not rest, False
            continue

        if cur is None:          # preamble / title text before the first section
            continue
        if NOTE_RE.match(stripped):
            cur.notes.append(stripped.strip("[] "))
            new_para = True
            continue

        para = cur.paragraphs[-1] if cur.paragraphs else None
        if starts_unit and (m := SUB_RE.match(stripped)):
            if para is None:
                para = Paragraph()
                cur.paragraphs.append(para)
            n = f"({m.group(1)})"
            if any(k == n for k, _ in para.subs):     # numbering restarts → a new list
                para = Paragraph()
                cur.paragraphs.append(para)
            para.subs.append((n, m.group(2)))
            para.sub_fns.setdefault(n, []).extend(fns)
            new_para, in_sub = False, True
            continue

        if starts_unit and in_sub and para is not None and LETTER_SUB_RE.match(stripped):
            n, t = para.subs[-1]
            para.subs[-1] = (n, f"{t}\n{stripped}")
            para.sub_fns.setdefault(n, []).extend(fns)
            continue

        # An indented plain line inside a sub-item list stays in the current sub-item when
        # the list continues with the next number, e.g. ม.119 (4) … "หนังสือเตือน…" (5) …
        if starts_unit and indent_mode and in_sub and para is not None and para.subs:
            nxt = next_unit(i)
            m_next = SUB_RE.match(nxt) if nxt else None
            last = int(para.subs[-1][0].strip("()"))
            if m_next and int(m_next.group(1)) == last + 1:
                n, t = para.subs[-1]
                para.subs[-1] = (n, f"{t}\n{stripped}")
                para.sub_fns.setdefault(n, []).extend(fns)
                continue

        if para is not None and not para.text and not para.subs:
            para.text = stripped                       # heading line had no body text
            para.fns.extend(fns)
        elif new_para or starts_unit and indent_mode or para is None:
            cur.paragraphs.append(Paragraph(text=stripped, fns=fns))
            in_sub = False
        elif in_sub:
            n, t = para.subs[-1]
            para.subs[-1] = (n, _join(t, stripped))
            para.sub_fns.setdefault(n, []).extend(fns)
        else:
            para.text = _join(para.text, stripped)
            para.fns.extend(fns)
        new_para = False

    for sec in sections:     # drop an empty lead paragraph left by a bare heading
        sec.paragraphs = [p for p in sec.paragraphs if p.text or p.subs] or [Paragraph()]
    return sections


def _row(key: str, s: Section, para: int, sub: str | None, text: str,
         fns: list[str]) -> ProvisionRow:
    return ProvisionRow(key, s.section_no, para, sub, text, s.chapter, s.repealed,
                        list(dict.fromkeys(fns)))


def to_rows(sections: list[Section], law: str) -> list[ProvisionRow]:
    """Flatten to DB rows. Key: "<LAW>:<section>:<paragraph>" or "<LAW>:<section>:<para>:(n)"."""
    rows: list[ProvisionRow] = []
    for s in sections:
        for i, p in enumerate(s.paragraphs, start=1):
            base = f"{law}:{s.section_no}:{i}"
            rows.append(_row(base, s, i, None, p.full_text(), p.all_fns()))
            for n, t in p.subs:
                rows.append(_row(f"{base}:{n}", s, i, n, t, p.sub_fns.get(n, [])))
    dupes = [k for k, c in Counter(r.citation_key for r in rows).items() if c > 1]
    if dupes:
        raise ValueError(f"duplicate citation keys in {law}: {sorted(dupes)[:10]}")
    return rows


FN_TARGET_RE = re.compile(r"^มาตรา\s*(\d+(?:/\d+)?)(?:\s*(\(\d+\)))?")


def reconcile_footnotes(sections: list[Section], footnotes: dict[str, str]) -> list[str]:
    """Move a footnote to the section its text names ("[17] มาตรา 23/1 เพิ่มโดย …").

    Markers are placed by page position, so one next to a section boundary can land on
    the neighbour. Returns log lines for every move."""
    by_no = {s.section_no: s for s in sections}
    log = []
    for sec in sections:
        for pi, para in enumerate(sec.paragraphs):
            holders = [("", para.fns)] + [(n, v) for n, v in para.sub_fns.items()]
            for where, lst in holders:
                for f in list(lst):
                    m = FN_TARGET_RE.match(normalize(footnotes.get(f, "")))
                    if not m or m.group(1) == sec.section_no or m.group(1) not in by_no:
                        continue
                    lst.remove(f)
                    target = by_no[m.group(1)].paragraphs[0]
                    sub = m.group(2)
                    (target.sub_fns.setdefault(sub, []) if sub else target.fns).append(f)
                    log.append(f"fn {f}: {sec.section_no}:{pi + 1}{where} → {m.group(1)}{sub or ''}")
    return log
