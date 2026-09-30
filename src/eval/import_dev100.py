"""Convert the client's dev sheet (xlsx export) → data/eval/dev100.csv.

Only the tab holding the 100 DEV rows is read, and only rows with split == DEV.
Other tabs/rows may contain held-out questions and are never opened (see CLAUDE.md §4.3).

Columns in the sheet:
  G "ผลเฉลย ... ตาม ref ที่อัพ"   → ref_answer (answer per the uploaded reference; may be wrong)
  H "มาตราเเละคำตอบที่ถูกสั้นๆ"    → gold_answer (reviewed correct section + short answer)
"""

import argparse
import csv
import re
from pathlib import Path

import openpyxl

FIELDS = ["id", "question", "gold_answer", "gold_issues", "gold_citations", "event_date",
          "source", "notes", "category", "question_type", "difficulty", "ref_answer"]
SECTION_RE = re.compile(r"มาตรา\s*(\d+(?:/\d+)?)((?:\s*(?:,|และ|หรือ)\s*(?:มาตรา\s*)?\d+(?:/\d+)?(?!\d))*)")
# "มาตรา 41/2 … ไม่มีอยู่ในกฎหมาย" = gold says the section does not exist; plain "ไม่มีอำนาจ" is not
NONEXISTENT_RE = re.compile(r"ไม่มี(อยู่|ใน(กฎหมาย|พ\.?ร\.?บ)|จริง|บทบัญญัติ)")
LAW_NAMES = [("คุ้มครองแรงงาน", "LPA2541"), ("กฎหมายแรงงาน", "LPA2541"), ("แรงงานสัมพันธ์", "LRA2518"),
             ("ป.พ.พ", "CCC"), ("แพ่งและพาณิชย์", "CCC"), ("ศาลแรงงาน", "LCA2522")]


def _law_near(before: str, after: str) -> str:
    """Law named last before the mention on the same line, else first after it, else LPA."""
    line_before = before.split("\n")[-1]
    hits = [(line_before.rfind(n), code) for n, code in LAW_NAMES if n in line_before]
    if hits:
        return max(hits)[1]
    clause = re.split(r"มาตรา|\n", after, maxsplit=1)[0]
    if re.match(r"\s*(และ|หรือ|,)", clause):      # "มาตรา 118 และ ป.พ.พ. …" names the next item
        return "LPA2541"
    return next((code for n, code in LAW_NAMES if n in clause), "LPA2541")


def resolve_citations(gold: str) -> list[str]:
    """"มาตรา 118" → "LPA2541:118" (section level); "มาตรา 123 และ 124" gives both.
    Mentions whose clause says it does not exist ("… ไม่มีอยู่ในกฎหมาย") are skipped."""
    out = []
    for m in SECTION_RE.finditer(gold):
        clause = re.split(r"มาตรา|\n", gold[m.end():m.end() + 120], maxsplit=1)[0]
        if NONEXISTENT_RE.search(clause):
            continue
        law = _law_near(gold[:m.start()], gold[m.end():m.end() + 60])
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
    ref = col["ผลเฉลย (ระบุเฉพาะมาตราหลักเเละระบุคำตอบสั้นๆ)"]

    out = []
    for r in rows:
        if r[split] != "DEV":
            continue
        g = str(r[gold] or "").strip()
        out.append({
            "id": f"dev{int(float(r[col['Items']])):03d}",
            "question": str(r[col["คำถาม"]]).strip(),
            "gold_answer": g,
            "gold_issues": "",
            "gold_citations": ";".join(resolve_citations(g)),
            "event_date": "",
            "source": "client_dev_sheet",
            "notes": "",
            "category": r[col["Question Category"]],
            "question_type": r[col["Question Type"]],
            "difficulty": r[col["Difficulty"]],
            "ref_answer": str(r[ref] or "").strip(),
        })
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} DEV rows → {a.out}")


if __name__ == "__main__":
    main()
