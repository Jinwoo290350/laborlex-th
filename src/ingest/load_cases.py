"""Load court decisions into `cases` and link them to provisions (`case_links`).

Source (for now): data/raw/legacy/cases.jsonl — 886 labour-division rulings of the
ศาลอุทธรณ์คดีชำนัญพิเศษ scraped by a previous contractor from sjapsc.coj.go.th, with
data/raw/legacy/case_section_links.jsonl. These are NOT Supreme Court (ฎีกา) decisions and
are always labelled with their court.

Usage: python -m src.ingest.load_cases   (then python -m src.index.embed --cases)
"""

from __future__ import annotations

import json
from pathlib import Path

from src.index.db import connect

RAW = Path("data/raw/legacy")
LAW_CODES = {"LPA_2541": "LPA2541", "LRA_2518": "LRA2518", "LCA_2522": "LCA2522", "CCC": "CCC"}


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
            cur.execute(
                "INSERT INTO case_links (case_id, provision_id)"
                " SELECT %s, p.id FROM provisions p JOIN laws l ON l.id=p.law_id"
                " WHERE l.short_name=%s AND p.section_no=%s AND p.sub_no IS NULL"
                " ON CONFLICT DO NOTHING",
                (ids[lk["case_no"]], law, str(lk["section"]).replace(" ", "")))
            n += cur.rowcount
        print(f"{len(ids)} cases · {n} case→provision links · {skipped} link rows for other laws")


if __name__ == "__main__":
    main()
