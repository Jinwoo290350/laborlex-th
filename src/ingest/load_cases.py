"""Load court decisions into `cases` and link them to provisions (`case_links`).

Sources:
- data/raw/deka/labour_deka.jsonl — Supreme Court decisions (ศาลฎีกา) collected from
  deka.supremecourt.or.th by src/ingest/scrape_deka.py (labour-related only)
- data/raw/legacy/cases.jsonl — 886 labour-division rulings of the ศาลอุทธรณ์คดีชำนัญพิเศษ
  scraped by a previous contractor from sjapsc.coj.go.th (+ case_section_links.jsonl).
  These are NOT ฎีกา and are always labelled with their court.

Usage: python -m src.ingest.load_cases   (then python -m src.index.embed --cases)
"""

from __future__ import annotations

import json
from pathlib import Path

from src.index.db import connect

RAW = Path("data/raw/legacy")
DEKA = Path("data/raw/deka/labour_deka.jsonl")
LAW_CODES = {"LPA_2541": "LPA2541", "LRA_2518": "LRA2518", "LCA_2522": "LCA2522", "CCC": "CCC"}
# law names as printed by deka.supremecourt.or.th → our short names
DEKA_LAWS = {"พระราชบัญญัติคุ้มครองแรงงาน": "LPA2541", "พระราชบัญญัติแรงงานสัมพันธ์": "LRA2518",
             "พระราชบัญญัติจัดตั้งศาลแรงงาน": "LCA2522", "ประมวลกฎหมายแพ่งและพาณิชย์": "CCC"}


def _link(cur, case_id: int, law: str, section: str) -> int:
    cur.execute(
        "INSERT INTO case_links (case_id, provision_id)"
        " SELECT %s, p.id FROM provisions p JOIN laws l ON l.id=p.law_id"
        " WHERE l.short_name=%s AND p.section_no=%s AND p.sub_no IS NULL"
        " ON CONFLICT DO NOTHING", (case_id, law, section.replace(" ", "")))
    return cur.rowcount


def load_deka(cur) -> tuple[int, int]:
    if not DEKA.exists():
        return 0, 0
    n_cases = n_links = 0
    for line in DEKA.open(encoding="utf-8"):
        d = json.loads(line)
        if not d.get("labour"):
            continue
        tail = d["deka_no"].rsplit("/", 1)[-1] if "/" in d["deka_no"] else ""
        year = int(tail) if tail.isdigit() and 2400 <= int(tail) <= 2700 else None
        cur.execute(
            "INSERT INTO cases (deka_no, court, doc_type, year, holding, full_text, source,"
            " source_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (deka_no) DO NOTHING"
            " RETURNING id",
            (d["deka_no"], "ศาลฎีกา", "คำพิพากษา", year,
             d["short_text"], d["long_text"], "deka.supremecourt.or.th", d["source_url"]))
        row = cur.fetchone()
        if not row:
            continue
        n_cases += 1
        for law in d["laws"]:
            short = next((v for k, v in DEKA_LAWS.items() if law.get("law_name", "").startswith(k)), None)
            if short and law.get("section"):
                n_links += _link(cur, row[0], short, law["section"])
    return n_cases, n_links


def main() -> None:
    cases = [json.loads(line) for line in (RAW / "cases.jsonl").open(encoding="utf-8")]
    links = [json.loads(line) for line in (RAW / "case_section_links.jsonl").open(encoding="utf-8")]
    with connect() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE case_links, cases RESTART IDENTITY CASCADE")
        ids: dict[str, int] = {}
        for c in cases:
            cur.execute(
                "INSERT INTO cases (deka_no, court, doc_type, year, holding, full_text, source,"
                " source_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (c["case_no"], c["court"], c.get("doc_type"), c.get("case_no_year"),
                 (c.get("holding_short") or "").strip(), (c.get("holding_long") or "").strip(),
                 "legacy:sjapsc", c.get("source_url")))
            ids[c["case_no"]] = cur.fetchone()[0]

        n = skipped = 0
        for lk in links:
            law = LAW_CODES.get(lk["law_code"])
            if not law or lk["case_no"] not in ids:
                skipped += 1
                continue
            n += _link(cur, ids[lk["case_no"]], law, str(lk["section"]))
        print(f"appeal court: {len(ids)} cases · {n} links · {skipped} link rows for other laws")
        d_cases, d_links = load_deka(cur)
        print(f"supreme court: {d_cases} labour decisions · {d_links} links")


if __name__ == "__main__":
    main()
