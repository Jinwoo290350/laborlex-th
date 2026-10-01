"""Convert the client's dev sheet (xlsx export) → data/eval/dev100.csv.

Only the tab holding the 100 DEV rows is read, and only rows with split == DEV.
Other tabs/rows may contain held-out questions and are never opened (see CLAUDE.md §4.3).

Columns in the sheet:
  F คำถาม                         → question
  G "ผลเฉลย … ตาม ref ที่อัพ"      → draft_answer (draft with known errors — never gold)
  H "มาตราเเละคำตอบที่ถูกสั้นๆ"    → gold_answer (correction of G) + g_verdict on G
Only Sheet2 has this meaning for H (in Sheet1, H is a Random column).
"""

import argparse
import csv
import re
from pathlib import Path

import openpyxl
import yaml

FIELDS = ["id", "question", "gold_answer", "gold_issues", "gold_citations", "event_date",
          "source", "notes", "category", "question_type", "difficulty",
          "draft_answer", "g_verdict", "h_raw"]

# H often opens with a verdict on the draft in G ("ถูกต้อง", "ไม่ถูกต้อง", "ถูกบางส่วน …").
VERDICTS = [  # longest first; (phrase, verdict)
    ("ไม่ถูกต้องบางส่วน", "partial"), ("ถูกบางส่วน", "partial"),
    ("คำตอบถูก แต่มาตราไม่ถูก", "partial"), ("ไม่ถูกต้อง", "incorrect"),
    ("คำตอบและการคำนวณถูกต้อง", "correct"), ("คำตอบและมาตราถูกต้อง", "correct"),
    ("มาตราคำตอบถูกต้อง", "correct"), ("อ้างมาตราถูกต้อง", "correct"), ("มาตราถูกต้อง", "correct"),
    ("คำตอบถูกต้อง", "correct"), ("ถูกต้องทั้งหมด", "correct"), ("ถูกต้อง", "correct"),
    ("คำตอบถูก", "correct"),
]
ENUM_RE = re.compile(r"^\s*(\(?[0-9ก-ฮ]\)|\d+\.)\s*")


def split_verdict(h: str) -> tuple[str, str]:
    """"ไม่ถูกต้อง มาตรา 23/12 ไม่มี…" → ("incorrect", "มาตรา 23/12 ไม่มี…").
    A verdict followed soon by "แต่" is partial. H without a leading verdict is a standalone
    answer (verdict "")."""
    body = ENUM_RE.sub("", h.strip())
    for phrase, verdict in VERDICTS:
        if body.startswith(phrase):
            rest = body[len(phrase):].lstrip(" ,:")
            if verdict == "correct" and "แต่" in rest[:40]:
                verdict = "partial"
            return verdict, rest
    head = body[:120]                      # verdict inside the text: "มาตรา 5, 61 … ถูกต้องทั้งหมด แต่ขาด …"
    if re.search(r"ไม่ถูก|ถูกต้อง|ขาดมาตรา|ถูกบางส่วน", head):
        partial = re.search(r"ไม่ถูก|แต่|ขาด", head)
        return ("partial" if partial else "correct"), h.strip()
    return "", h.strip()
SECTION_RE = re.compile(r"มาตรา\s*(\d+(?:/\d+)?)((?:\s*(?:,|และ|หรือ)\s*(?:มาตรา\s*)?\d+(?:/\d+)?(?!\d))*)")
# "มาตรา 41/2 … ไม่มีอยู่ในกฎหมาย" = gold says the section does not exist; plain "ไม่มีอำนาจ" is not
NONEXISTENT_RE = re.compile(r"ไม่มี(อยู่|ใน(กฎหมาย|พ\.?ร\.?บ)|จริง|บทบัญญัติ)")
LAW_NAMES = [("คุ้มครองแรงงาน", "LPA2541"), ("กฎหมายแรงงาน", "LPA2541"), ("แรงงานสัมพันธ์", "LRA2518"),
             ("ป.พ.พ", "CCC"), ("แพ่งและพาณิชย์", "CCC"), ("ศาลแรงงาน", "LCA2522")]


def _law_near(before: str, after: str, default: str = "LPA2541") -> str:
    """Law named last before the mention on the same line, else first after it, else default."""
    line_before = before.split("\n")[-1]
    hits = [(line_before.rfind(n), code) for n, code in LAW_NAMES if n in line_before]
    if hits:
        return max(hits)[1]
    clause = re.split(r"มาตรา|\n", after, maxsplit=1)[0]
    if re.match(r"\s*(และ|หรือ|,)", clause):      # "มาตรา 118 และ ป.พ.พ. …" names the next item
        return default
    return next((code for n, code in LAW_NAMES if n in clause), default)


def first_law(text: str) -> str | None:
    hits = [(text.find(n), code) for n, code in LAW_NAMES if n in text]
    return min(hits)[1] if hits else None


def resolve_citations(gold: str, default: str = "LPA2541") -> list[str]:
    """"มาตรา 118" → "LPA2541:118" (section level); "มาตรา 123 และ 124" gives both.
    Mentions whose clause says it does not exist ("… ไม่มีอยู่ในกฎหมาย") are skipped.
    `default` = law for mentions with no law named nearby."""
    out = []
    for m in SECTION_RE.finditer(gold):
        clause = re.split(r"มาตรา|\n", gold[m.end():m.end() + 120], maxsplit=1)[0]
        if NONEXISTENT_RE.search(clause):
            continue
        law = _law_near(gold[:m.start()], gold[m.end():m.end() + 60], default)
        nums = [m.group(1), *re.findall(r"\d+(?:/\d+)?", m.group(2) or "")]
        out += [f"{law}:{n}" for n in nums]
    return list(dict.fromkeys(out))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default="data/raw/eval/dev100_sheet.xlsx")
    ap.add_argument("--sheet", default="Sheet2")
    ap.add_argument("--out", default="data/eval/dev100.csv")
    a = ap.parse_args()

    ws = openpyxl.load_workbook(a.xlsx, read_only=True)[a.sheet]
    rows = ws.iter_rows(values_only=True)
    header = [str(h).split("\n")[0].strip() if h else "" for h in next(rows)]
    col = {name: header.index(name) for name in header if name}
    split = col["Dataset Split"]
    gold = col["มาตราเเละคำตอบที่ถูกสั้นๆ"]
    draft = col["ผลเฉลย (ระบุเฉพาะมาตราหลักเเละระบุคำตอบสั้นๆ)"]      # G: draft, has errors

    overrides = yaml.safe_load(Path("config/gold_overrides.yaml").read_text(encoding="utf-8")) or {}
    out = []
    for r in rows:
        if r[split] != "DEV":
            continue
        h = str(r[gold] or "").strip()
        g_draft = str(r[draft] or "").strip()
        verdict, answer = split_verdict(h)
        if not answer:                     # H is only "ถูกต้อง": the draft is confirmed
            answer = g_draft
        # H reviewing G ("มาตรา 22 ถูกต้อง …") without naming a law means G's law
        default = (first_law(answer) or (first_law(g_draft) if verdict else None) or "LPA2541")
        cites = resolve_citations(answer, default)
        if not cites and verdict in ("correct", "partial"):
            cites = resolve_citations(g_draft)
        qid = f"dev{int(float(r[col['Items']])):03d}"
        cites = [c for c in cites if c not in overrides.get(qid, {}).get("remove", [])]
        out.append({
            "id": qid,
            "question": str(r[col["คำถาม"]]).strip(),
            "gold_answer": answer,
            "gold_issues": "",
            "gold_citations": ";".join(cites),
            "event_date": "",
            "source": "client_dev_sheet",
            "notes": "",
            "category": r[col["Question Category"]],
            "question_type": r[col["Question Type"]],
            "difficulty": r[col["Difficulty"]],
            "draft_answer": g_draft,
            "g_verdict": verdict,
            "h_raw": h,
        })
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} DEV rows → {a.out}")


if __name__ == "__main__":
    main()
