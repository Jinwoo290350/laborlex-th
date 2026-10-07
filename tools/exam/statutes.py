"""Statute extraction for exam answers (C0/C1 JSON text and C2 markdown) — the exam tool's automatic checks.

Separate from `src.eval.import_dev100.resolve_citations`, which builds the dev100 gold and stays unchanged.
Fixes two mislabels found in the C2 pilot answers (docs/design/2026-10-06_fix_ABCD_e2e.md):
  1. "ศาลแรงงาน" (the court) was read as the Labour Court Act → "ฟ้องศาลแรงงาน … ฝ่าฝืนมาตรา 31" became LCA2522:31.
     Only the Act's own name ("จัดตั้งศาลแรงงาน", "วิธีพิจารณาคดีแรงงาน") names that law now.
  2. A bare "มาตรา N" defaulted to LPA even in an answer about the LRA. The default is now the law the answer
     names most often; rendered citations "[ม.31 พระราชบัญญัติแรงงานสัมพันธ์ …]" are read with their own law.
Law for one mention: the law named immediately before it ("พ.ร.บ.คุ้มครองแรงงาน พ.ศ. 2541 มาตรา 76") → else the law
named right after it ("มาตรา 31 พ.ร.บ.แรงงานสัมพันธ์") → else the nearest law named before it on the same line within
WINDOW characters → else the answer's family.
"""

from __future__ import annotations

import re

from src.eval.import_dev100 import NONEXISTENT_RE, SECTION_RE

# longest / most specific first (the full LCA title is one mention, not two); "ศาลแรงงาน" alone is the court
LAWS = [("จัดตั้งศาลแรงงานและวิธีพิจารณาคดีแรงงาน", "LCA2522"), ("จัดตั้งศาลแรงงาน", "LCA2522"), ("วิธีพิจารณาคดีแรงงาน", "LCA2522"),
        ("แรงงานรัฐวิสาหกิจ", "SELRA2543"), ("คุ้มครองแรงงาน", "LPA2541"), ("แรงงานสัมพันธ์", "LRA2518"),
        ("ประกันสังคม", "SSA2533"), ("เงินทดแทน", "WCA2537"), ("ป.พ.พ", "CCC"), ("แพ่งและพาณิชย์", "CCC")]
_LAW_RE = re.compile("|".join(re.escape(n) for n, _ in LAWS))
_CODE = dict(LAWS)
WINDOW = 80
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_SHORT_M = re.compile(r"(?<![ก-๙])ม\.\s*(?=\d)")             # "ม.31" → "มาตรา 31" (not "ม.ค.")
# a law named immediately after the section and its own qualifiers: "มาตรา 31 วรรคหนึ่ง (1) แห่งพระราชบัญญัติ…"
# a conjunction joins numbers only ("มาตรา 31 และ 121 แห่ง…"); "มาตรา 118 และ ป.พ.พ. มาตรา 583" names the next item
_TAIL = re.compile(r"\s*(?:วรรค\S*?\s*|\(\d+\)\s*|(?:และ|หรือ|,)\s*\d+(?:/\d+)?\s*)*(?:แห่ง\s*)?"
                   r"(?:พ\.?\s*ร\.?\s*บ\.?|พระราชบัญญัติ|ประมวลกฎหมาย|ป\.พ\.พ)")


def normalise(text: str) -> str:
    return _SHORT_M.sub("มาตรา ", (text or "").translate(_THAI_DIGITS))


def family(text: str) -> str:
    """The law the answer names most often (ties and no name → LPA2541)."""
    counts: dict[str, int] = {}
    for m in _LAW_RE.finditer(text):
        counts[_CODE[m.group(0)]] = counts.get(_CODE[m.group(0)], 0) + 1
    if not counts:
        return "LPA2541"
    best = max(counts.values())
    return "LPA2541" if counts.get("LPA2541") == best else max(counts, key=counts.get)


# a law named immediately before: "พระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541 มาตรา 76", "ป.พ.พ. มาตรา 583"
# no comma: in "…พ.ศ. 2518, มาตรา 8 (2) พ.ร.บ.จัดตั้งศาลแรงงานฯ" the law before belongs to the previous item
_ADJ = re.compile(r"[.\sฯ]*(?:พ\.\s*ศ\.\s*\d{4})?\s*(?:มาตรา\s*)?$")


def _law_for(text: str, start: int, end: int, default: str) -> str:
    before = text[max(0, start - WINDOW):start]
    names = list(_LAW_RE.finditer(before.split("\n")[-1]))
    line = before.split("\n")[-1]
    if names and _ADJ.fullmatch(line[names[-1].end():]):
        return _CODE[names[-1].group(0)]
    after = text[end:end + 120]
    if (t := _TAIL.match(after)) and (m := _LAW_RE.search(after[:t.end() + 60])):
        return _CODE[m.group(0)]
    return _CODE[names[-1].group(0)] if names else default


def statutes(text: str, default: str | None = None) -> list[str]:
    """Section-level keys named in an answer, in order of first mention: "LRA2518:31", "LPA2541:17/1"."""
    text = normalise(text)
    fam = default or family(text)
    out = []
    for m in SECTION_RE.finditer(text):
        clause = re.split(r"มาตรา|\n", text[m.end():m.end() + 120], maxsplit=1)[0]
        if NONEXISTENT_RE.search(clause):
            continue
        # each number at its own position: "มาตรา 118 และมาตรา 575 แห่ง ป.พ.พ." → LPA:118, CCC:575
        for n in re.finditer(r"\d+(?:/\d+)?", m.group(0)):
            law = _law_for(text, m.start() + n.start(), m.start() + n.end(), fam)
            out.append(f"{law}:{n.group(0)}")
    return list(dict.fromkeys(out))


# laws the Legal Index holds in full (CCC holds only selected sections, so a missing CCC section proves nothing)
COMPLETE = ("LPA2541", "LRA2518", "LCA2522")


def unknown(keys: list[str]) -> list[str]:
    """Keys naming a section that a fully-held law does not have (e.g. LCA2522:121). Needs the DB; [] without it."""
    try:
        from src.index.db import connect
        with connect() as c:
            have = {f"{law}:{s}" for law, s in c.execute(
                "SELECT DISTINCT l.short_name, p.section_no FROM provisions p JOIN laws l ON l.id = p.law_id")}
    except Exception:  # noqa: BLE001 — offline: cannot check
        return []
    return [k for k in keys if k.split(":")[0] in COMPLETE and k not in have]
