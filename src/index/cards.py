"""Holding Cards: one rule-based card per court decision (M4, FIX_PLAN_v2 §B "Holding Card").

A card records what a decision can be cited for:
- `provisions`: current-style keys ("LPA2541:119") from the deka `laws` field, citations in the headnote, and the
  old-regime crosswalk (src/index/crosswalk.yaml: ประกาศกระทรวงมหาดไทย ข้อ 46 → LPA2541:118, ข้อ 47 → :119 ...).
- `regime`: "pre2541" when the decision applies the old ประกาศ, else by provisions/year (see `regime_of`).
- `segments`: the headnote split into paragraphs, each tagged with who decided it (`classify_span`).
- `decided_by` / `substantive`: card-level summaries of the segments (see `card_decided_by`, `is_substantive`).
- `ratio_quote`: a verbatim span of the headnote (the first segment the deciding court decided itself).
- `issue_codes`: taxonomy codes (data/processed/issues.yaml) whose primary_provisions meet `provisions`.

One card per decision for now. A decision with several holdings keeps them as tagged `segments` of a single card;
splitting it into one card per holding (and the LLM-filled `legal_question` / `fact_features`) is future work.

decided_by heuristic (`classify_span`), for a span of the headnote (or any span) against the full text:
1. The span itself refuses review ("ไม่รับวินิจฉัย", "ต้องห้าม…" next to อุทธรณ์/ฎีกา, "เป็นอุทธรณ์ในข้อเท็จจริง" ...)
   → procedural_refusal, unless it is a long mixed paragraph (≥ 400 chars, ≥ 30 % of it before the refused point
   or after the refusal phrase: `is_mixed`), which goes on to step 2.
2. Find where the deciding court's own reasoning starts (`own_start`): after "ศาลฎีกา…วินิจฉัยว่า" /
   "ศาลอุทธรณ์คดีชำนัญพิเศษ…วินิจฉัยว่า". When that header is followed by a restatement of the lower court
   ("ศาลแรงงานกลางฟังข้อเท็จจริงว่า … แล้ววินิจฉัยว่า …"), own reasoning starts at "(มี)ปัญหาต้องวินิจฉัย",
   else at the next paragraph.
3. Locate the span by overlapping 15-character n-grams (whitespace removed, Thai digits normalised). If most located
   n-grams also occur at or after `own_start`, the deciding court said it → own_holding, unless "ไม่รับวินิจฉัย"
   follows the located span within 80 characters of the same paragraph → procedural_refusal. If most of the span (≥ 50 % of its n-grams) is
   found only before → restated_lower_court.
4. No court header, too little text (own part < 300 chars: the full text was cut), or too few n-grams found
   → unknown.

substantive heuristic (`is_substantive`): False when every headnote segment is a procedural refusal, or when the
decision cites only procedural law: ป.วิ.พ., ป.วิ.อ., and the Labour Court Act (LCA2522) except ม.49 (unfair
dismissal, a substantive remedy). Decisions that cite nothing are substantive unless refused.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

CROSSWALK = Path(__file__).with_name("crosswalk.yaml")
ISSUES = Path("data/processed/issues.yaml")
SUPREME = "ศาลฎีกา"
APPEAL = "ศาลอุทธรณ์คดีชำนัญพิเศษ"
LPA_IN_FORCE_YEAR = 2541          # พ.ร.บ.คุ้มครองแรงงาน พ.ศ. 2541 (in force 19 Aug 2541)

DecidedBy = Literal["own_holding", "restated_lower_court", "procedural_refusal", "unknown"]


class Segment(BaseModel):
    text: str                      # verbatim headnote paragraph
    decided_by: DecidedBy


class HoldingCard(BaseModel):
    deka_no: str
    court: str
    doc_type: str = "คำพิพากษา"
    year: int | None = None
    regime: Literal["pre2541", "post2541"]
    provisions: list[str] = Field(default_factory=list)       # current keys "LAW:section"
    old_provisions: list[str] = Field(default_factory=list)   # old-regime keys "MOI2515:47" (before crosswalk)
    substantive: bool = True
    decided_by: DecidedBy = "unknown"
    ratio_quote: str = ""
    issue_codes: list[str] = Field(default_factory=list)
    legal_question: str = ""
    fact_features: dict = Field(default_factory=dict)
    segments: list[Segment] = Field(default_factory=list)
    source_url: str | None = None

    @property
    def text(self) -> str:
        """Searchable text: headnote segments the deciding court decided itself (or could not be placed)."""
        keep = [s.text for s in self.segments if s.decided_by in ("own_holding", "unknown")]
        return "\n".join(keep or [s.text for s in self.segments])

    @property
    def is_supreme(self) -> bool:
        return self.court == SUPREME


# ---------------------------------------------------------------- text helpers
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def normalize(text: str) -> str:
    """Thai digits → Arabic, decomposed sara am (ํ + า) → ำ, zero-width chars removed."""
    text = (text or "").translate(_THAI_DIGITS).replace("ํา", "ำ")
    return re.sub("[\u200b\u200c\u200d\ufeff]", "", text)


def squash(text: str) -> str:
    """normalize() with all whitespace removed; line/paragraph breaks kept as ¶ (full texts use either)."""
    text = re.sub(r"\s*\n\s*", "¶", normalize(text).strip())
    return re.sub(r"\s+", "", text)


def year_of(deka_no: str) -> int | None:
    tail = deka_no.rsplit("/", 1)[-1] if "/" in deka_no else ""
    return int(tail) if tail.isdigit() and 2400 <= int(tail) <= 2700 else None


# ---------------------------------------------------------------- provisions
# deka.supremecourt.or.th law codes → our short names (DB `laws.short_name` where the law is indexed)
LAW_CODES = {"ค77-03": "LPA2541", "ร27-06": "LRA2518", "จ07-05": "LCA2522", "ป03-05": "CCC",
             "ป04-01": "CPC", "ป05-01": "CrPC", "ป06-01": "PC", "ป11-01": "SSA2533", "ง04-01": "WCA2537",
             "พ13-04": "SELRA2543", "พ13-01": "SELRA2534"}
# legacy appeal-court link file codes (data/raw/legacy/case_section_links.jsonl)
LEGACY_CODES = {"LPA_2541": "LPA2541", "LRA_2518": "LRA2518", "LCA_2522": "LCA2522", "CCC": "CCC", "CPC": "CPC"}
# law names as written in headnotes → short names (citations found in the text)
_TEXT_LAWS = [
    (r"(?:พ\.\s*ร\.\s*บ\.|พระราชบัญญัติ)\s*คุ้มครองแรงงาน", "LPA2541"),
    (r"(?:พ\.\s*ร\.\s*บ\.|พระราชบัญญัติ)\s*แรงงานสัมพันธ์", "LRA2518"),
    (r"(?:พ\.\s*ร\.\s*บ\.|พระราชบัญญัติ)\s*จัดตั้งศาลแรงงาน(?:และวิธีพิจารณาคดีแรงงาน)?", "LCA2522"),
    (r"(?:ป\.\s*พ\.\s*พ\.|ประมวลกฎหมายแพ่งและพาณิชย์)", "CCC"),
    (r"(?:ป\.\s*วิ\.\s*พ\.|ประมวลกฎหมายวิธีพิจารณาความแพ่ง)", "CPC"),
]
_YEAR_TAIL = r"(?:\s*ฯ)?(?:\s*(?:พ\.\s*ศ\.)?\s*25\d\d)?(?:\s*ฯ)?"
_SECTION = r"\s*มาตรา\s*(\d+(?:/\d+)?)"
PROCEDURAL_LAWS = {"CPC", "CrPC"}
SUBSTANTIVE_LCA = {"49"}          # LCA2522 ม.49 = unfair dismissal remedy; every other LCA section is procedure


def section_no(raw: str | None) -> str | None:
    m = re.match(r"\s*(\d+(?:/\d+)?)", normalize(raw or ""))
    return m.group(1) if m else None


@lru_cache(maxsize=1)
def crosswalk() -> dict:
    return yaml.safe_load(CROSSWALK.read_text(encoding="utf-8"))


def old_instrument(law_code: str | None) -> str | None:
    for name, ins in crosswalk()["instruments"].items():
        if law_code in ins["law_codes"]:
            return name
    return None


def map_old(keys: list[str]) -> list[str]:
    clauses = crosswalk()["clauses"]
    return [t for k in keys for t in (clauses.get(k) or {}).get("to", [])]


def text_citations(text: str) -> tuple[list[str], list[str]]:
    """(current keys, old keys) cited in a headnote, e.g. "พ.ร.บ.คุ้มครองแรงงาน พ.ศ. 2541 มาตรา 5"."""
    t = normalize(text)
    cur = [f"{short}:{m.group(1)}" for pat, short in _TEXT_LAWS
           for m in re.finditer(pat + _YEAR_TAIL + _SECTION, t)]
    old = []
    for name, ins in crosswalk()["instruments"].items():
        for m in re.finditer(ins["text_pattern"] + r"[^ข]{0,40}?ข้อ\s*(\d+)", t):
            old.append(f"{name}:{m.group(1)}")
    return cur, old


def dedupe(xs: list[str]) -> list[str]:
    return list(dict.fromkeys(xs))


def deka_citations(laws: list[dict]) -> tuple[list[str], list[str], bool]:
    """(current keys, old keys, cites_only_procedure) from a deka `laws` field."""
    cur, old, kinds = [], [], []
    for law in laws:
        code, sec = law.get("law_code"), section_no(law.get("section"))
        if not code:
            continue
        ins = old_instrument(code)
        if ins:
            kinds.append(False)
            if sec:
                old.append(f"{ins}:{sec}")
            continue
        short = LAW_CODES.get(code)
        kinds.append(is_procedural(short, sec))
        if short and sec:
            cur.append(f"{short}:{sec}")
    return cur, old, bool(kinds) and all(kinds)


def is_procedural(short: str | None, sec: str | None) -> bool:
    if short in PROCEDURAL_LAWS:
        return True
    return short == "LCA2522" and sec not in SUBSTANTIVE_LCA


# ---------------------------------------------------------------- headnote segments
_HEADER_LINE = re.compile(r"^(?:คำ(?:พิพากษา|สั่ง|วินิจฉัย)|ป\.|พ\.ร\.|พระราช|ประมวล|ระเบียบ|ประกาศ|กฎกระทรวง|ข้อบังคับ)")


def headnote_segments(headnote: str, court: str) -> list[str]:
    """Verbatim headnote paragraphs. Appeal-court headnotes start with "คำพิพากษาศาล…ที่ n/yyyy" (or
    "คำวินิจฉัยของประธานศาล…") and the cited sections, which are dropped; some deka rows carry "++ … ++" banner
    fragments, and three legacy rows append the judgment after a "---" line; both are dropped too."""
    text = re.split(r"\n\s*-{3,}\s*\n", (headnote or "").strip())[0]   # 3 legacy rows append the judgment
    if "++" in text:
        text = "\n\n".join(p.strip() for p in text.split("++") if len(p.strip()) >= 80)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if court != SUPREME:
        while paras and len(paras) > 1 and len(paras[0]) < 300 and _HEADER_LINE.match(paras[0]):
            paras.pop(0)
    return paras


# ---------------------------------------------------------------- decided_by
_MARK = re.compile(r"ไม่\s*รับ\s*วินิจฉัย|ไม่\s*เห็น\s*สมควร\s*(?:ที่\s*จะ\s*)?ยก\s*ขึ้น\s*วินิจฉัย|ต้อง\s*ห้าม"
                   r"|(?<!ไม่)(?<!มิใช่)(?<!ไม่ใช่)เป็น\s*(?:อุทธรณ์|ฎีกา)\s*(?:ใน\s*(?:ปัญหา\s*)?ข้อ\s*เท็จ\s*จริง"
                   r"|ที่\s*ไม่\s*เป็น\s*สาระ)")
_APPEAL_WORD = re.compile(r"อุทธรณ์|ฎีกา")
# reasons courts give for refusing a point ("not pleaded", "disputes the weighing of evidence", "immaterial")
_REFUSAL_REASON = re.compile(r"(?:ไม่ได้|มิได้)\s*(?:ให้การ|ยกขึ้น|ต่อสู้|ว่ากล่าว)|โต้เถียงดุลพินิจ|ดุลพินิจในการรับฟัง"
                             r"|ไม่เป็นสาระ")
_COURT_HEADER = re.compile(r"ศาล(?:ฎีกา|อุทธรณ์คดีชำนัญพิเศษ)[^¶]{0,40}?วินิจฉัยว่า")
_COURT_HEADER_OLD = re.compile(r"ศาลฎีกา(?:แผนกคดีแรงงาน)?(?:โดยมติที่ประชุมใหญ่)?(?:ตรวจสำนวน|ประชุมปรึกษา|พิเคราะห์)")
_RESTATES_LOWER = re.compile(r"(?:ข้อเท็จจริง)?(?:ที่)?ศาล(?:แรงงาน|ชั้นต้น|อุทธรณ์(?!คดีชำนัญพิเศษ))")
_QUESTION = re.compile(r"(?:มี)?ปัญหา(?:ที่)?(?:ต้อง|จะต้อง)วินิจฉัย")
_GRAM, _STEP = 15, 5
_MIXED_MIN_CHARS, _MIXED_SHARE = 400, 0.3
_REFUSAL_WINDOW = 80              # "ไม่รับวินิจฉัย" this close after the span (same paragraph) = refused point
_MIN_OWN_CHARS = 300              # shorter "own part" = the full text was cut before the court's reasoning


def own_start(sq: str) -> int | None:
    """Offset in squash(full_text) where the deciding court's own reasoning starts (None = no structure)."""
    m = _COURT_HEADER.search(sq)
    if not m:
        m = _COURT_HEADER_OLD.search(sq)
        return m.end() if m else None
    if not _RESTATES_LOWER.match(sq, m.end()):
        return m.end()
    q = _QUESTION.search(sq, m.end())
    if q:
        return q.start()
    para = sq.find("¶", m.end())
    return para if para > 0 else m.end()


def classify_span(full_text: str, span: str) -> DecidedBy:
    """Who decided `span` in a decision whose full text is `full_text` (see module docstring)."""
    marks = refusal_marks(span)
    mixed = bool(marks) and is_mixed(span, marks)
    if marks and not mixed:
        return "procedural_refusal"
    sp = squash(span).replace("¶", "")
    sq = squash(full_text)
    start = own_start(sq) if len(sq) >= 200 else None
    if start is None or len(sp) < _GRAM or len(sq) - start < _MIN_OWN_CHARS:
        return "unknown"
    grams = [sp[i:i + _GRAM] for i in range(0, len(sp) - _GRAM + 1, _STEP)]
    located, own_pos = 0, []
    for g in grams:
        last = sq.rfind(g)
        if last < 0:
            continue
        located += 1
        if last >= start:
            own_pos.append(last)
    if located < max(3, 0.2 * len(grams)):
        return "unknown"
    if len(own_pos) * 2 < located:
        # restated only when the span is mostly found verbatim before the court's own part; a partial match
        # (headnote paraphrase, or a truncated full text) is not evidence either way
        return "restated_lower_court" if located >= 0.5 * len(grams) else "unknown"
    after = max(own_pos) + _GRAM            # where the located span ends
    stop = sq.find("¶", after)
    window = sq[after:min(after + _REFUSAL_WINDOW, stop if stop >= 0 else len(sq))]
    return "procedural_refusal" if "ไม่รับวินิจฉัย" in window and not mixed else "own_holding"


def refusal_marks(text: str) -> list[re.Match]:
    """Refusal phrases in `text`; a bare "ต้องห้าม" counts only next to "อุทธรณ์"/"ฎีกา" (an appeal barred),
    not e.g. "การกระทำที่ต้องห้ามตามมาตรา 121"."""
    t = normalize(text)
    return [m for m in _MARK.finditer(t)
            if not m.group().startswith("ต้อง") or _APPEAL_WORD.search(t[max(0, m.start() - 150):m.end() + 30])]


def is_mixed(text: str, marks: list[re.Match]) -> bool:
    """A long headnote paragraph that decides one point and refuses another: ≥ 30 % of it comes before the
    refused point is opened ("…อุทธรณ์ว่า", or a refusal reason such as "มิได้ให้การ") or after its refusal
    phrase."""
    t = normalize(text)
    if len(t) < _MIXED_MIN_CHARS:
        return False
    first = marks[0].start()
    opened = [m.start() for m in (_APPEAL_WORD.search(t, 0, first), _REFUSAL_REASON.search(t, 0, first)) if m]
    before = min(opened + [first])
    after = len(t) - min(len(t), marks[-1].end() + 80)      # + room for "ตาม … มาตรา 54"
    return max(before, after) >= _MIXED_SHARE * len(t)


def card_decided_by(segments: list[Segment]) -> DecidedBy:
    """Card-level label: own_holding if any headnote segment is the court's own holding; otherwise the refusal /
    restatement label of the segments; unknown when nothing could be placed."""
    labels = [s.decided_by for s in segments]
    for label in ("own_holding", "procedural_refusal", "restated_lower_court"):
        if label in labels:
            return label
    return "unknown"


def is_substantive(segments: list[Segment], only_procedural_cites: bool) -> bool:
    if segments and all(s.decided_by == "procedural_refusal" for s in segments):
        return False
    return not only_procedural_cites


# ---------------------------------------------------------------- regime, issues
def regime_of(year: int | None, provisions: list[str], old_provisions: list[str]) -> Literal["pre2541", "post2541"]:
    """pre2541 if the decision applies the old ประกาศ (cites it), post2541 if it cites LPA 2541 without it,
    else by decision year (decided after 2541 → post2541)."""
    if old_provisions:
        return "pre2541"
    if any(p.startswith("LPA2541:") for p in provisions):
        return "post2541"
    return "post2541" if (year or 0) > LPA_IN_FORCE_YEAR else "pre2541"


@lru_cache(maxsize=4)
def issue_index(path: str = str(ISSUES)) -> dict[str, list[str]]:
    """provision key → taxonomy codes whose primary_provisions list it."""
    out: dict[str, list[str]] = {}
    for issue in yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []:
        for p in issue.get("primary_provisions") or []:
            out.setdefault(p, []).append(issue["code"])
    return out


def issues_for(provisions: list[str], index: dict[str, list[str]] | None = None) -> list[str]:
    index = issue_index() if index is None else index
    return dedupe([c for p in provisions for c in index.get(p, [])])


# ---------------------------------------------------------------- builders
def _ratio(segments: list[Segment], limit: int = 600) -> str:
    seg = next((s for s in segments if s.decided_by == "own_holding"), segments[0] if segments else None)
    if seg is None:
        return ""
    t = seg.text
    if len(t) <= limit:
        return t
    cut = t.rfind(" ", 0, limit)
    return t[:cut if cut > limit // 2 else limit]


def make_card(*, deka_no: str, court: str, doc_type: str, year: int | None, headnote: str, full_text: str,
              cur: list[str], old: list[str], only_procedural: bool, source_url: str | None = None,
              issues: dict[str, list[str]] | None = None) -> HoldingCard:
    t_cur, t_old = text_citations("\n".join(headnote_segments(headnote, court)))
    old = dedupe(old + t_old)
    provisions = dedupe(cur + t_cur + map_old(old))
    if t_cur and not cur:                 # no laws field: judge "procedural only" from the headnote cites
        only_procedural = all(is_procedural(*k.split(":", 1)) for k in t_cur)
    segments = [Segment(text=p, decided_by=classify_span(full_text, p))
                for p in headnote_segments(headnote, court)]
    return HoldingCard(
        deka_no=deka_no, court=court, doc_type=doc_type or "คำพิพากษา", year=year,
        regime=regime_of(year, provisions, old), provisions=provisions, old_provisions=old,
        substantive=is_substantive(segments, only_procedural), decided_by=card_decided_by(segments),
        ratio_quote=_ratio(segments), issue_codes=issues_for(provisions, issues), segments=segments,
        source_url=source_url)


def card_from_deka(row: dict, issues: dict[str, list[str]] | None = None) -> HoldingCard:
    cur, old, only_proc = deka_citations(row.get("laws") or [])
    return make_card(deka_no=row["deka_no"], court=SUPREME, doc_type="คำพิพากษา", year=year_of(row["deka_no"]),
                     headnote=row.get("short_text") or "", full_text=row.get("long_text") or "",
                     cur=cur, old=old, only_procedural=only_proc, source_url=row.get("source_url"), issues=issues)


def card_from_appeal(row: dict, links: list[dict], issues: dict[str, list[str]] | None = None) -> HoldingCard:
    """Appeal-court (ศาลอุทธรณ์คดีชำนัญพิเศษ) decision; `links` = its rows of case_section_links.jsonl."""
    cur, kinds = [], []
    for lk in links:
        short, sec = LEGACY_CODES.get(str(lk.get("law_code"))), section_no(str(lk.get("section") or ""))
        kinds.append(is_procedural(short, sec))
        if short and sec:
            cur.append(f"{short}:{sec}")
    return make_card(deka_no=row["case_no"], court=row.get("court") or APPEAL, doc_type=row.get("doc_type") or "",
                     year=row.get("case_no_year"), headnote=row.get("holding_short") or "",
                     full_text=row.get("holding_long") or "", cur=dedupe(cur), old=[],
                     only_procedural=bool(kinds) and all(kinds), source_url=row.get("source_url"), issues=issues)


def load_cards(path: str | Path = "data/processed/holding_cards.jsonl") -> list[HoldingCard]:
    with Path(path).open(encoding="utf-8") as f:
        return [HoldingCard.model_validate_json(line) for line in f if line.strip()]
