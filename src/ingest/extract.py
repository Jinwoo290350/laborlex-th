"""Raw law files (.pdf from krisdika, .docx) → parser-ready text.

Output conventions (consumed by parse_statute.parse):
  * a line starting with two spaces begins a new unit (section / paragraph / sub-item)
  * a line without indent continues the previous line (PDF line wrap)
  * " [^n]" appended to a line = krisdika footnote n (amendment history)

krisdika PDFs lay out body text with line starts at a larger x than wrapped lines,
put footnote markers "[n]" as separate floating spans, and list footnote bodies
("[n] มาตรา … แก้ไขเพิ่มเติมโดย …") on the last pages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import docx
import pymupdf

MARKER_RE = re.compile(r"^\[(\d+)\]$")
BODY_END_RE = re.compile(r"^(หมายเหตุ\s*:-|อัตราค่าธรรมเนียม)")
FURNITURE_RE = re.compile(r"(สำนักงานคณะกรรมการกฤษฎีกา|about:blank|^\d+/\d+$|^\d{1,2}/\d{1,2}/\d{2} \d{1,2}:\d{2}$|/ Checker|/ Authorizer)")


@dataclass
class Line:
    page: int
    x: float
    y: float
    text: str
    lead_ws: int = 0     # leading spaces/NBSPs: some krisdika lines indent with NBSP runs


@dataclass
class Extracted:
    text: str                       # parser-ready body
    footnotes: dict[str, str]       # "63" -> "มาตรา 118 (5) เพิ่มโดย ..."
    tail: str                       # text after the body (notes, fee appendix, amending acts)


def _pdf_lines(path: Path) -> list[Line]:
    out: list[Line] = []
    with pymupdf.open(path) as doc:
        for pno, page in enumerate(doc):
            h = page.rect.height
            raw: list[Line] = []
            for b in page.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    x0, y0 = ln["bbox"][0], ln["bbox"][1]
                    full = "".join(s["text"] for s in ln["spans"])
                    t = full.strip()
                    if not t or y0 < 40 or y0 > h - 40 or FURNITURE_RE.search(t):
                        continue
                    raw.append(Line(pno, x0, y0, t, len(full) - len(full.lstrip())))
            # markers stay separate; text spans on the same baseline merge left→right
            # (e.g. "(๕)" + "ลูกจ้างซึ่ง…")
            markers = [r for r in raw if MARKER_RE.match(r.text)]
            texts = sorted((r for r in raw if not MARKER_RE.match(r.text)), key=lambda r: (r.y, r.x))
            merged: list[Line] = []
            for r in texts:
                if merged and abs(merged[-1].y - r.y) <= 1.5:
                    merged[-1].text += " " + r.text
                else:
                    merged.append(r)
            out += sorted(merged + markers, key=lambda r: r.y)
    return out


def _indent_threshold(lines: list[Line]) -> float:
    """Midpoint between the wrap margin (most common x) and the line-start indent."""
    xs = sorted(round(ln.x) for ln in lines if not MARKER_RE.match(ln.text.strip()))
    margin = max(set(xs), key=xs.count)
    starts = [x for x in xs if x > margin + 20]
    indent = max(set(starts), key=starts.count) if starts else margin + 72
    return (margin + indent) / 2


def extract_pdf(path: str | Path) -> Extracted:
    lines = _pdf_lines(Path(path))
    end = next((i for i, ln in enumerate(lines) if BODY_END_RE.match(ln.text.strip())), len(lines))
    body, tail = lines[:end], lines[end:]
    thr = _indent_threshold(body)

    # footnote bodies: "[n]" at the left margin in the tail, text on the same row onward
    footnotes: dict[str, str] = {}
    cur: str | None = None
    tail_text = []
    for ln in tail:
        t = ln.text.strip()
        m = MARKER_RE.match(t.split(" ")[0]) if t.startswith("[") else None
        if m and ln.x < thr:
            cur = m.group(1)
            footnotes[cur] = t[len(m.group(0)):].strip()
        elif cur is not None:
            footnotes[cur] = (footnotes[cur] + " " + t).strip()
        else:
            tail_text.append(t)

    # body: markers attach to the nearest text line on the same page
    out: list[Line] = []
    markers: list[Line] = []
    for ln in body:
        (markers if MARKER_RE.match(ln.text.strip()) else out).append(ln)
    notes: dict[int, list[str]] = {}
    for mk in markers:
        cands = [i for i, ln in enumerate(out) if ln.page == mk.page]
        if cands:
            i = min(cands, key=lambda i: abs(out[i].y - mk.y))
            notes.setdefault(i, []).append(MARKER_RE.match(mk.text.strip()).group(1))  # type: ignore[union-attr]

    text_lines = []
    for i, ln in enumerate(out):
        t = ln.text.strip() + "".join(f" [^{n}]" for n in notes.get(i, []))
        indented = ln.x >= thr or ln.lead_ws >= 3
        text_lines.append(("  " if indented else "") + t)
    return Extracted("\n".join(text_lines), footnotes, "\n".join(tail_text))


def extract_docx(path: str | Path) -> Extracted:
    lines = []
    for p in docx.Document(str(path)).paragraphs:
        t = p.text.strip()
        if not t:
            lines.append("")
            continue
        # every docx paragraph is a logical line; only indented/heading/sub lines start units,
        # plain lines are broken-off fragments that continue the previous one
        pf = p.paragraph_format
        indented = bool(pf.first_line_indent) or bool(pf.left_indent)
        starts = re.match(r"(มาตรา|ข้อ)\s*[\d๐-๙]|\([\d๐-๙]+\)|หมวด|ส่วนที่|บทเฉพาะกาล", t)
        lines.append(("  " if indented or starts else "") + t)
    text, tail = cut_tail("\n".join(lines))
    return Extracted(text, {}, tail)


TAIL_RE = re.compile(r"^\s*(ผู้รับสนองพระบรมราชโองการ|หมายเหตุ\s*:?-?|ให้ไว้\s*ณ\s*วันที่)")
FIRST_UNIT_RE = re.compile(r"^\s*(มาตรา|ข้อ)\s*[\d๐-๙]")


def cut_tail(text: str) -> tuple[str, str]:
    """Split off what follows the operative text: signature block, "หมายเหตุ :-" and the
    amending acts that consolidated texts append. Markers before the first section
    (e.g. "ให้ไว้ ณ วันที่" in an act's preamble) are ignored."""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if FIRST_UNIT_RE.match(ln)), 0)
    end = next((i for i in range(start + 1, len(lines)) if TAIL_RE.match(lines[i])), len(lines))
    return "\n".join(lines[:end]), "\n".join(lines[end:])


INLINE_FN_RE = re.compile(r"(?<=[\u0e00-\u0e7f\d)])\[\d+\]")   # "มาตรา ๒[1]" superscript refs


def extract_ocs_txt(path: str | Path) -> Extracted:
    """Text saved from searchlaw.ocs.go.th (ฉบับปรับปรุงล่าสุด): one unit per line, indented,
    footnote refs as " [^n]", endnotes after "=====FOOTNOTES=====". A first line
    "#INFO …" carries the page's metadata."""
    raw = Path(path).read_text(encoding="utf-8")
    body, _, notes = raw.partition("=====FOOTNOTES=====")
    lines = [ln for ln in body.split("\n") if not ln.startswith("#INFO")]
    text, tail = cut_tail("\n".join(INLINE_FN_RE.sub("", ln) for ln in lines))
    footnotes = {}
    for ln in notes.strip().split("\n"):
        m = re.match(r"\[(\d+)\]\s*(.*)", ln)
        if m:
            footnotes[m.group(1)] = m.group(2)
    return Extracted(text, footnotes, tail)


def extract(path: str | Path) -> Extracted:
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return extract_pdf(p)
    if p.suffix.lower() == ".txt":
        return extract_ocs_txt(p)
    return extract_docx(p)
