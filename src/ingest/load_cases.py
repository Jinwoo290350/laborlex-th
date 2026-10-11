"""Load court decisions into `cases` and link them to provisions (`case_links`).

Sources:
- data/raw/deka/labour_deka.jsonl — Supreme Court decisions (ศาลฎีกา) collected from
  deka.supremecourt.or.th by src/ingest/scrape_deka.py (labour-related only)
- data/raw/legacy/cases.jsonl — 886 labour-division rulings of the ศาลอุทธรณ์คดีชำนัญพิเศษ
  scraped by a previous contractor from sjapsc.coj.go.th (+ case_section_links.jsonl).
  These are NOT ฎีกา and are always labelled with their court.
- data/raw/deka/extra/*.html — deka.supremecourt.or.th result pages saved for specific decisions that the
  labour query does not return (e.g. partnership liability decided in tort cases, P6). Only the named decisions
  are loaded, additively.

Usage: python -m src.ingest.load_cases   (then python -m src.index.embed --cases)
       python -m src.ingest.load_cases --relink   (additive: links of loaded decisions to newly appended provisions)
       python -m src.ingest.load_cases --extra PAGE.html --only 15199-15200/2558,2066/2545
           additive: inserts the named decisions if missing, links them to provisions; never truncates
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
        case_id, links = _insert_deka(cur, d)
        n_cases += case_id is not None
        n_links += links
    return n_cases, n_links


def _insert_deka(cur, d: dict) -> tuple[int | None, int]:
    """One Supreme Court decision (scrape_deka record) and its provision links; (None, 0) if already loaded."""
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
        return None, 0
    n_links = 0
    for law in d["laws"]:
        short = next((v for k, v in DEKA_LAWS.items() if (law.get("law_name") or "").startswith(k)), None)
        if short and law.get("section"):
            n_links += _link(cur, row[0], short, law["section"])
    return row[0], n_links


def extra_records(page: Path, only: list[str]) -> list[dict]:
    """The named decisions from a saved result page (fullest text per number); a missing number is an error."""
    from src.ingest.scrape_deka import BASE, parse_page
    best: dict[str, dict] = {}
    for r in parse_page(page.read_text(encoding="utf-8")):
        if r["deka_no"] in only and len(r["long_text"]) > len(best.get(r["deka_no"], {}).get("long_text", "")):
            best[r["deka_no"]] = {**r, "source_url": f"{BASE}/search (เลขที่ {r['deka_no']})"}
    missing = [n for n in only if n not in best]
    if missing:
        raise SystemExit(f"not on {page}: {missing}")
    return [best[n] for n in only]


def load_extra(page: Path, only: list[str]) -> None:
    with connect() as conn, conn.cursor() as cur:
        for d in extra_records(page, only):
            case_id, links = _insert_deka(cur, d)
            print(f"{d['deka_no']}: " + (f"case id {case_id}, {links} links" if case_id else "already loaded"))


def relink() -> None:
    """Additive: re-create the provision links of loaded decisions (after provisions were appended, e.g. the
    CCC partnership sections). Existing links are kept; only missing ones are inserted."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT deka_no, id FROM cases")
        ids = dict(cur.fetchall())
        n = 0
        for line in (RAW / "case_section_links.jsonl").open(encoding="utf-8"):
            lk = json.loads(line)
            law = LAW_CODES.get(lk["law_code"])
            if law and lk["case_no"] in ids:
                n += _link(cur, ids[lk["case_no"]], law, str(lk["section"]))
        for line in DEKA.open(encoding="utf-8") if DEKA.exists() else []:
            d = json.loads(line)
            for law in d["laws"] if d["deka_no"] in ids else []:
                short = next((v for k, v in DEKA_LAWS.items() if (law.get("law_name") or "").startswith(k)), None)
                if short and law.get("section"):
                    n += _link(cur, ids[d["deka_no"]], short, law["section"])
        print(f"{n} new case links")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", type=Path, help="saved deka result page (additive load)")
    ap.add_argument("--only", default="", help="comma-separated deka numbers to load from --extra")
    ap.add_argument("--relink", action="store_true", help="additive: insert missing links of loaded decisions")
    a = ap.parse_args()
    if a.extra:
        load_extra(a.extra, [n.strip() for n in a.only.split(",") if n.strip()])
        return
    if a.relink:
        relink()
        return
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
