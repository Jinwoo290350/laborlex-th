"""Collect labour-related Supreme Court decisions (คำพิพากษาศาลฎีกา) from
deka.supremecourt.or.th, the official public search.

Query: basic search, doctype = คำพิพากษาศาลฎีกา, word "ศาลแรงงาน" (decisions whose lower court
was a Labour Court or that discuss one) — 5,899 hits on 2026-10-01. Result pages already
embed ย่อสั้น, ย่อยาว and cited sections, so one request per 20 decisions is enough.

Politeness: ≥ 2 s between requests, identifying User-Agent, every page cached on disk
(re-runs and resumes never re-fetch), stops on HTTP errors. The site has no robots.txt
rules for /search. Judgments are not copyright works (Copyright Act B.E. 2537 s.7(4));
we keep the source and the deka number for every record. Litigant and judge names are not
stored (not needed for legal reasoning).

  python -m src.ingest.scrape_deka fetch   # pages → data/raw/deka/pages/
  python -m src.ingest.scrape_deka parse   # pages → data/raw/deka/labour_deka.jsonl
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

BASE = "https://deka.supremecourt.or.th"
QUERY = {"search_form_type": "basic", "start": "true", "search_doctype": "1", "search_word": "ศาลแรงงาน"}
OUT = Path("data/raw/deka")
PAGES = OUT / "pages"
DELAY_S = 2.0
UA = "Mozilla/5.0 (compatible; laborlex-research/0.1; academic labour-law QA)"
LABOUR_LAWS = ("คุ้มครองแรงงาน", "แรงงานสัมพันธ์", "ศาลแรงงาน", "เงินทดแทน", "ประกันสังคม")


def fetch() -> None:
    PAGES.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": UA}, timeout=90, follow_redirects=True,
                      verify=False) as c:            # the site's TLS chain does not verify
        first = c.post(f"{BASE}/search", data=QUERY)
        first.raise_for_status()
        total = int(re.search(r'id="total_page" name="total_page" value="(\d+)"',
                              first.text).group(1))
        (PAGES / "0001.html").write_text(first.text, encoding="utf-8")
        (OUT / "query.json").write_text(json.dumps(
            {"query": QUERY, "total_pages": total,
             "started": datetime.now().astimezone().isoformat(),
             "count": re.search(r'name="count_result" value="(\d+)"', first.text).group(1)},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{total} pages")
        for n in range(2, total + 1):
            path = PAGES / f"{n:04d}.html"
            if path.exists():
                continue
            time.sleep(DELAY_S)
            r = c.get(f"{BASE}/search/index/{n}")
            r.raise_for_status()
            if "item_deka_no" not in r.text:            # session expired → stop, re-run resumes
                raise SystemExit(f"page {n}: no results (session?) — re-run to resume")
            path.write_text(r.text, encoding="utf-8")
            if n % 20 == 0:
                print(f"  page {n}/{total}")


def _text(fragment: str) -> str:
    t = re.sub(r"</p>\s*<p[^>]*>", "\n", fragment)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"[ \t]+", " ", html.unescape(t)).strip()


def parse_page(page: str) -> list[dict]:
    out = []
    for block in re.split(r'<li class="clear result">', page)[1:]:
        no = re.search(r"คำพิพากษาศาลฎีกาที่\s*(\d+(?:\s*[-–]\s*\d+)?/\d{4}|\d+)", block)
        docid = re.search(r'id="short_text_docid_(\d+)"', block)
        if not (no and docid):
            continue
        short = re.search(r'id="short_text_docid_\d+"[^>]*>(.*?)</li>', block, re.DOTALL)
        long_ = re.search(r'id="long_text_docid_\d+"[^>]*>(.*?)</li>', block, re.DOTALL)
        laws = [dict(zip(("law_code", "law_name", "law_short", "section", "paragraph", "sub", "other"),
                         [a.strip().strip("'") for a in re.findall(r"'([^']*)'", args)]))
                for args in re.findall(r"sectionView\(([^)]*)\)", block)]
        prim = re.search(r'print_item_primarycourt[^>]*>(.*?)</ul>', block, re.DOTALL)
        dept = re.search(r'print_item_department[^>]*>.*?<span[^>]*>(.*?)</span>', block, re.DOTALL)
        src = re.search(r'print_item_source[^>]*>.*?<span class="content-detail">(.*?)</span>',
                        block, re.DOTALL)
        courts = ([re.sub(r"\s*-\s*.*$", "", _text(x))
                   for x in re.findall(r"<li>(.*?)</li>", prim.group(1), re.DOTALL)] if prim else [])
        out.append({
            "docid": docid.group(1), "deka_no": re.sub(r"\s*[-–]\s*", "-", no.group(1)),
            "short_text": _text(short.group(1)) if short else "",
            "long_text": _text(long_.group(1)) if long_ else "",
            "laws": list({json.dumps(x, sort_keys=True, ensure_ascii=False): x for x in laws}.values()),
            "lower_courts": courts,                      # court names only (no judges)
            "department": _text(dept.group(1)) if dept else "",
            "source": _text(src.group(1)) if src else "",
        })
    return out


def parse() -> None:
    best: dict[str, dict] = {}                  # one record per deka number: the fullest text
    for p in sorted(PAGES.glob("*.html")):
        for r in parse_page(p.read_text(encoding="utf-8")):
            old = best.get(r["deka_no"])
            if old is None or len(r["long_text"]) > len(old["long_text"]):
                best[r["deka_no"]] = r
    rows = []
    for r in best.values():
            r["labour"] = (any("แรงงาน" in c for c in r["lower_courts"]) or "แรงงาน" in r["department"]
                           or any(any(k in x.get("law_name", "") for k in LABOUR_LAWS) for x in r["laws"]))
            r["source_url"] = f"{BASE}/search (เลขที่ {r['deka_no']})"
            rows.append(r)
    path = OUT / "labour_deka.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    lab = sum(r["labour"] for r in rows)
    print(f"{len(rows)} distinct decisions · {lab} labour · → {path}")


if __name__ == "__main__":
    {"fetch": fetch, "parse": parse}[sys.argv[1] if len(sys.argv) > 1 else "fetch"]()
