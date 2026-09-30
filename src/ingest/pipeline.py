"""raw law files → data/interim (parser-ready text) → provisions in Postgres.

Usage: python -m src.ingest.pipeline [--dry-run]
Rebuilds laws/provisions/links from scratch (the index is derived data).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from src.ingest.extract import extract
from src.ingest.parse_statute import (
    ProvisionRow,
    Section,
    normalize,
    parse,
    reconcile_footnotes,
    section_sort_key,
    to_rows,
)

RAW = Path("data/raw/laws")
INTERIM = Path("data/interim/laws")
REGISTRY = Path("data/processed/laws.yaml")
AUTH_RE = re.compile(r"อาศัยอำนาจตามความใน(.{0,200}?)แห่ง(พระราชบัญญัติ[^\s]+(?:\s*พ\.ศ\.\s*\d{4})?)")
SEC_REF_RE = re.compile(r"มาตรา\s*(\d+(?:/\d+)?)")


def load_law(entry: dict) -> tuple[list[Section], dict[str, str], str, list[str]]:
    ex = extract(RAW / entry["file"])
    text = normalize(ex.text)
    secs = parse(text, unit=entry["unit"], normalized=True)
    if not secs:
        # instruments without numbered clauses (e.g. a list of "(1) …" items):
        # keep the body as one pseudo-clause "0" under the title line
        lines = text.split("\n")
        body = "\n".join(lines[1:]) if len(lines) > 1 else text
        secs = parse(f"  {entry['unit']} 0\n{body}", unit=entry["unit"], normalized=True)
    log = reconcile_footnotes(secs, ex.footnotes)
    if entry.get("include_sections"):
        # large codes: keep only the ranges relevant to labour cases
        ranges = entry["include_sections"]
        secs = [s for s in secs
                if any(lo <= section_sort_key(s.section_no)[0] <= hi for lo, hi in ranges)]
    return secs, ex.footnotes, text, log


def issued_under(text: str) -> list[str]:
    """Section numbers named in the enabling clause ("อาศัยอำนาจตามความในมาตรา …")."""
    m = AUTH_RE.search(text)
    return SEC_REF_RE.findall(m.group(1)) if m else []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    INTERIM.mkdir(parents=True, exist_ok=True)
    parsed: dict[str, tuple[dict, list[ProvisionRow], list[Section], dict[str, str], list[str]]] = {}
    report = []
    for e in registry:
        secs, fns, text, log = load_law(e)
        rows = to_rows(secs, e["short_name"])
        (INTERIM / f"{e['short_name']}.txt").write_text(text, encoding="utf-8")
        parsed[e["short_name"]] = (e, rows, secs, fns, issued_under(text))
        report.append(f"{e['short_name']:24} units={len(secs):4} rows={len(rows):4} "
                      f"fn={len(fns):3} moved={len(log)} auth={parsed[e['short_name']][4]}")
    print("\n".join(report))
    if a.dry_run:
        return

    from src.index.db import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE links, case_links, issue_links, provisions, laws RESTART IDENTITY CASCADE")
        law_id: dict[str, int] = {}
        for e in registry:
            cur.execute(
                "INSERT INTO laws (name, short_name, type, level, source_file, quality, note) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (e["name"], e["short_name"], e["type"], e["level"], e["file"],
                 e.get("quality"), e.get("note")),
            )
            law_id[e["short_name"]] = cur.fetchone()[0]
        for e in registry:
            if e.get("parent"):
                cur.execute("UPDATE laws SET parent_law_id=%s WHERE id=%s",
                            (law_id[e["parent"]], law_id[e["short_name"]]))

        for short, (e, rows, secs, fns, _) in parsed.items():
            titles = {s.section_no: s.chapter_title for s in secs}
            for r in rows:
                cur.execute(
                    "INSERT INTO provisions (law_id, chapter, chapter_title, section_no, paragraph_no,"
                    " sub_no, text, repealed, amendment_notes, citation_key)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (law_id[short], r.chapter, titles.get(r.section_no), r.section_no,
                     r.paragraph_no, r.sub_no, r.text, r.repealed,
                     [fns[f] for f in r.footnotes if f in fns], r.citation_key),
                )

        # ISSUED_UNDER: every provision of a child → the enabling sections of its parent
        n_links = 0
        for short, (e, rows, _, _, auth) in parsed.items():
            parent = e.get("parent")
            if not parent or not auth:
                continue
            for sec in auth:
                cur.execute(
                    "INSERT INTO links (from_id, to_id, type, evidence)"
                    " SELECT c.id, p.id, 'ISSUED_UNDER', %s FROM provisions c, provisions p"
                    " WHERE c.law_id=%s AND c.paragraph_no=1 AND c.sub_no IS NULL"
                    "   AND p.law_id=%s AND p.section_no=%s AND p.paragraph_no=1 AND p.sub_no IS NULL"
                    " ON CONFLICT DO NOTHING",
                    (json.dumps({"enabling_sections": auth}, ensure_ascii=False),
                     law_id[short], law_id[parent], sec),
                )
                n_links += cur.rowcount
        # REFERS_TO: a subordinate provision naming "มาตรา N" of its parent act
        n_refs = 0
        for short, (e, rows, _, _, _) in parsed.items():
            parent = e.get("parent")
            if not parent:
                continue
            for r in rows:
                if r.sub_no:
                    continue
                for sec in dict.fromkeys(SEC_REF_RE.findall(r.text)):
                    cur.execute(
                        "INSERT INTO links (from_id, to_id, type, evidence)"
                        " SELECT c.id, p.id, 'REFERS_TO', %s FROM provisions c, provisions p"
                        " WHERE c.citation_key=%s AND p.law_id=%s AND p.section_no=%s"
                        "   AND p.paragraph_no=1 AND p.sub_no IS NULL ON CONFLICT DO NOTHING",
                        (r.text[:200], r.citation_key, law_id[parent], sec))
                    n_refs += cur.rowcount
        print(f"{n_refs} REFERS_TO links")
        cur.execute("SELECT count(*) FROM provisions")
        print(f"loaded {cur.fetchone()[0]} provisions, {n_links} ISSUED_UNDER links")


if __name__ == "__main__":
    main()
