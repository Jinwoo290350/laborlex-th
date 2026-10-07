"""Parse saved LAW4004/LAW4104 exam pages (mjsheetramfree.com HTML) into the exam-framework intake format.

Works OFFLINE on HTML files that Frank / the client supply once the right to use the set is confirmed
(data/raw/exams/ram/html/*.html). It does not fetch anything. Rules were checked on a 5-set pilot
(1/2551, 1/2554, S/2557, 1/2559, 1/2567: 20/20 question↔answer pairs) using page structure only.

Page structure seen in the pilot:
  body       div.td-post-content
  question   line-start "ข้อ N." (a full stop); older sets use "ข้อ N" without one. Lines like "ข้อ 1 ให้ยกเลิก…"
             inside an answer are quoted regulation clauses, not questions.
  answer     line-start ธงคำตอบ / แนวคำตอบ, or a line ending in "ตอบ" followed by a "หลักกฎหมาย" line
  parts      หลักกฎหมาย (rule) → วินิจฉัย (application) → สรุป (conclusion); older sets are free text
  quirk      "ํา" (nikhahit + sara aa) instead of "ำ" in some sets → normalised

Section roles (DRAFT, a person confirms; never bucket from the raw citation count):
  Scope (2026-10-05): only LPA 2541 + LRA 2518. sections_needed_draft keeps LPA/LRA only; another law's
  needed sections go to sections_needed_other_draft; in_scope yes / review / no + scope_reason.
  needed_draft      sections cited in the application / conclusion part (after วินิจฉัย / ตามปัญหา /
                    จากข้อเท็จจริง / ดังนั้น / สรุป): what the decision actually rests on
  supporting_draft  sections cited only in the rule part (quoted or background)

  python -m tools.exam.parse_mjsheet data/raw/exams/ram/html --out data/staging/exams/ram_law4004.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from html.parser import HTMLParser
from pathlib import Path

LAWS = [("คุ้มครองแรงงาน", "LPA2541"), ("แรงงานรัฐวิสาหกิจ", "SELRA2543"), ("แรงงานสัมพันธ์", "LRA2518"),
        ("ประกันสังคม", "SSA2533"), ("เงินทดแทน", "WCA2537"), ("จัดตั้งศาลแรงงาน", "LCA2522"),
        ("ป.พ.พ", "CCC"), ("แพ่งและพาณิชย์", "CCC")]
BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "table", "blockquote"}
HEAD_DOT = re.compile(r"(?:^|\n)[ \t]*ข้อ\s*(\d+)\s*\.")
HEAD_ANY = re.compile(r"(?:^|\n)[ \t]*ข้อ\s*(\d+)")
ANSWER = re.compile(r"(?:^|\n)[ \t]*(?:ธงคำตอบ|แนวคำตอบ|แนวตอบ)|ตอบ[ \t]*\n\s*หลักกฎหมาย")
APPLY = re.compile(r"(?:^|\n)[ \t]*(?:วินิจฉัย|สรุป)|กรณีตามปัญหา|ตามปัญหา|จากข้อเท็จจริง|ดังนั้น")
SECTION = re.compile(r"มาตรา\s*(\d+(?:/\d+)?)((?:\s*(?:,|และ|หรือ)\s*(?:มาตรา\s*)?\d+(?:/\d+)?)*)")
TERM = re.compile(r"(?:(ซ่อม)\s*)?\b([12sS])\s*/\s*(25\d\d)|ภาค(ฤดูร้อน|\s*[12])\s*ปีการศึกษา\s*(25\d\d)")


def normalise(s: str) -> str:
    s = s.translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789"))
    s = s.replace("ํา", "ำ")
    return re.sub(r"[\u200b-\u200d\ufeff]", "", s)


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Body(HTMLParser):
    """Text of div.td-post-content with a newline at block boundaries; scripts and ad containers dropped.
    A real tag stack (void tags ignored, a closing tag pops back to its match) so unclosed <p> or <input>
    inside the post can't keep the capture open into the sidebar / footer."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool, bool]] = []      # (tag, is_root, starts_skip)
        self.done, self.out, self.title, self._in_h1 = False, [], "", False

    def _skipping(self) -> bool:
        return any(sk for _, _, sk in self.stack)

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        if tag == "h1":
            self._in_h1 = True
        if self.done or tag in VOID:
            if self.stack and tag == "br":
                self.out.append("\n")
            return
        if not self.stack:
            if tag == "div" and "td-post-content" in cls:
                self.stack.append((tag, True, False))
            return
        self.stack.append((tag, False, tag in {"script", "style"} or "apMainContainer" in cls))
        if tag in BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_h1 = False
        if not self.stack or tag in VOID or all(t != tag for t, _, _ in self.stack):
            return
        while self.stack:
            t, root, _ = self.stack.pop()
            if t == tag:
                if root:
                    self.done = True
                break
        if tag in BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_h1:
            self.title += data
        if self.stack and not self.done and not self._skipping():
            self.out.append(data)


def body_text(html: str) -> tuple[str, str]:
    p = _Body()
    p.feed(html)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", "".join(p.out))
    return normalise(p.title.strip()), normalise(text).strip()


def term_year(title: str) -> tuple[str, str]:
    m = TERM.search(title)
    if not m:
        return "", ""
    if m.group(3):
        term = m.group(2).upper()
        return ("R" + term if m.group(1) else term), m.group(3)
    t = m.group(4).strip()
    return ("S" if t == "ฤดูร้อน" else t), m.group(5)


def questions(text: str) -> list[tuple[int, int]]:
    """(question_no, start offset). Prefer 'ข้อ N.' headings; fall back to 'ข้อ N' when they don't cover all."""
    best: list[tuple[int, int]] = []
    for rx in (HEAD_DOT, HEAD_ANY):
        seq: list[tuple[int, int]] = []
        for m in rx.finditer(text):
            if int(m.group(1)) == len(seq) + 1:
                seq.append((len(seq) + 1, m.start()))
        if len(seq) > len(best):
            best = seq
    return best


def cites(text: str, default: str) -> list[str]:
    out, sticky = [], default
    for m in SECTION.finditer(text):
        before, after = text[max(0, m.start() - 60):m.start()], text[m.start():m.start() + 60]
        hits = [(before.rfind(n), code) for n, code in LAWS if n in before]
        law = max(hits)[1] if hits else next((code for n, code in LAWS if n in after), sticky)
        sticky = law
        out += [f"{law}:{n}" for n in [m.group(1), *re.findall(r"\d+(?:/\d+)?", m.group(2) or "")]]
    return list(dict.fromkeys(out))


SCOPE_LAWS = ("LPA2541", "LRA2518")      # what the system supports today; everything else is out of scope


def scope(needed: list[str]) -> tuple[str, str, list[str], list[str]]:
    """(in_scope, scope_reason, needed LPA/LRA sections, needed sections of other laws).
    in_scope: yes = decided on LPA/LRA alone · review = LPA/LRA plus another law's needed section (a person
    checks whether LPA+LRA alone decides it) · no = no needed LPA/LRA section (another law is the basis)."""
    inside = [s for s in needed if s.split(":")[0] in SCOPE_LAWS]
    other = [s for s in needed if s.split(":")[0] not in SCOPE_LAWS]
    laws = sorted({s.split(":")[0] for s in other})
    if not needed:
        return "review", "no needed section detected (parse) — check by hand", inside, other
    if not inside:
        return "no", "decided on " + "+".join(laws) + " (outside LPA 2541 / LRA 2518)", inside, other
    if other:
        return "review", "LPA/LRA plus " + "+".join(laws) + " — check LPA/LRA alone decides it", inside, other
    return "yes", "needed sections all in LPA 2541 / LRA 2518", inside, other


CCC_KEEP = {"150", "151"}                  # CCC general-part sections the answers really rely on


def answer_family(ans: str) -> str:
    """The law the answer mainly discusses = the law named most often (ties → LPA). Used as the default
    for a bare "มาตรา N" with no law named nearby."""
    counts = {code: 0 for _, code in LAWS}
    for name, code in LAWS:
        counts[code] += ans.count(name)
    best = max(counts.values())
    return "LPA2541" if best == 0 or counts["LPA2541"] == best else max(counts, key=counts.get)


def fix_ccc_bleed(keys: list[str], family: str) -> list[str]:
    """After a "ป.พ.พ. มาตรา 150" mention, bare LPA/LRA numbers get labelled CCC ("CCC:17/1" — the Civil Code
    has no 17/1). CCC sections 1–160 other than 150/151 are relabelled to the answer's family; the CCC
    employment chapter (575–586) and 150/151 stay CCC."""
    target = family if family in ("LPA2541", "LRA2518") else "LPA2541" if family == "CCC" else None
    out = []
    for k in keys:
        law, n = k.split(":", 1)
        if target and law == "CCC" and n not in CCC_KEEP and int(n.split("/")[0]) <= 160:
            k = f"{target}:{n}"        # CCC-dominant answers: 1–160 bleed is LPA (e.g. 17, 118, 119)
        out.append(k)
    return list(dict.fromkeys(out))


def parse_page(html: str, url: str) -> list[dict]:
    title, text = body_text(html)
    term, year = term_year(title)
    heads = questions(text)
    rows = []
    for k, (n, start) in enumerate(heads):
        block = text[start:heads[k + 1][1] if k + 1 < len(heads) else len(text)]
        a = ANSWER.search(block)
        q, ans = (block[:a.start()], block[a.start():]) if a else (block, "")
        flags = [] if a else ["NO_ANSWER"]
        family = answer_family(ans)
        p = APPLY.search(ans)
        applied = ans[p.start():] if p else ans
        all_secs, needed = fix_ccc_bleed(cites(ans, family), family), fix_ccc_bleed(cites(applied, family), family)
        if not p:
            flags.append("NO_APPLICATION_PART")
        in_scope, reason, needed_in, needed_other = scope(needed)
        rows.append({
            "exam_id": f"ram-law4004-{term or 'X'}-{year or 'X'}-q{n}", "source": "ram", "exam_year": year,
            "semester": term, "question_no": n, "question": re.sub(r"^\s*ข้อ\s*\d+\s*\.?\s*", "", q).strip(),
            "model_answer": ans.strip(), "source_url": url,
            "sections_all": ";".join(all_secs), "sections_needed_draft": ";".join(needed_in),
            "sections_needed_other_draft": ";".join(needed_other),
            "sections_supporting_draft": ";".join(s for s in all_secs if s not in needed),
            "in_scope": in_scope, "scope_reason": reason, "parse_flags": ";".join(flags)})
    return rows


COLS = ["exam_id", "source", "exam_year", "semester", "question_no", "question", "model_answer", "source_url",
        "sections_all", "sections_needed_draft", "sections_needed_other_draft", "sections_supporting_draft",
        "in_scope", "scope_reason", "parse_flags"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("html_dir")
    ap.add_argument("--out", default="data/staging/exams/ram_law4004.csv")
    ap.add_argument("--base-url", default="https://mjsheetramfree.com/")
    a = ap.parse_args()
    rows = []
    for f in sorted(Path(a.html_dir).glob("*.html")):
        rows += parse_page(f.read_text(encoding="utf-8", errors="ignore"), a.base_url + f.stem + "/")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f"{len(rows)} questions → {out}  flagged {sum(bool(r['parse_flags']) for r in rows)}  "
          f"in_scope {dict(Counter(r['in_scope'] for r in rows))}")


if __name__ == "__main__":
    main()
