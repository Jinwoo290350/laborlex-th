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
SECTION_RE = re.compile(r"มาตรา\s*(\d+(?:/\d+)?)")


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
            # section numbers only; law prefix is resolved after the Legal Index exists
            "gold_citations": ";".join(dict.fromkeys(SECTION_RE.findall(g))),
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
