"""Build data/processed/rates.yaml from provision text in the DB (never from memory).

Each entry keeps the citation_key it was read from; RateBook.verify() re-checks every
number against that text. Run after `make ingest`:  python -m src.calc.build_rates
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pythainlp.util import thaiword_to_num

from src.calc.labor import MULTIPLE_WORDS, RateBook
from src.index.db import connect

OUT = Path("data/processed/rates.yaml")
THAI_NUM = r"[ก-๙]+?"
TIER_RE = re.compile(rf"ครบ({THAI_NUM})(วัน|ปี)(?:\s*แต่ไม่ครบ({THAI_NUM})(วัน|ปี)|ขึ้นไป)")
PAY_RE = re.compile(rf"ค่าจ้างอัตราสุดท้าย({THAI_NUM})วัน")
WAGE_RE = re.compile(rf"วันละ({THAI_NUM})บาท")
INTEREST_RE = re.compile(rf"ร้อยละ({THAI_NUM})ต่อปี")
SURCHARGE_RE = re.compile(rf"พ้นกำหนดเวลา({THAI_NUM})วัน.*ร้อยละ({THAI_NUM})ของเงินที่ค้างจ่ายทุกระยะเวลา({THAI_NUM})วัน")
# Minimum-wage rows: (rate clause, clause naming the localities, localities). The localities are
# names, not legal numbers; each is verified as a substring of its clause. Clauses whose
# localities carry exceptions (e.g. "เฉพาะอำเภอ…", "ยกเว้น…") are left out until handled.
MIN_WAGE = "ANN-WAGE14-2568"
MIN_WAGE_ROWS = [
    (f"{MIN_WAGE}:2:1", f"{MIN_WAGE}:2:1:(3)", ["กรุงเทพมหานคร", "ฉะเชิงเทรา", "ชลบุรี", "ภูเก็ต", "ระยอง"]),
    (f"{MIN_WAGE}:4:1", f"{MIN_WAGE}:4:1", ["นครปฐม", "นนทบุรี", "ปทุมธานี", "สมุทรปราการ", "สมุทรสาคร"]),
]
MIN_WAGE_START = f"{MIN_WAGE}:21:1"     # commencement clause
MULT_RE = re.compile(r"ไม่น้อยกว่า(" + "|".join(sorted(MULTIPLE_WORDS, key=len, reverse=True)) + ")")


def text_of(conn, key: str) -> str:
    row = conn.execute("SELECT text FROM provisions WHERE citation_key=%s", (key,)).fetchone()
    if not row:
        raise LookupError(key)
    return row[0]


def duration(word: str, unit: str) -> dict:
    return {"amount": thaiword_to_num(word), "unit": "day" if unit == "วัน" else "year"}


def main() -> None:
    rates = []
    with connect() as conn:
        tiers = []
        subs = [r[0] for r in conn.execute(
            "SELECT citation_key FROM provisions WHERE citation_key LIKE 'LPA2541:118:1:(%' ORDER BY id")]
        for key in subs:
            t = text_of(conn, key)
            m, pay = TIER_RE.search(t), PAY_RE.search(t)
            if not (m and pay):
                raise ValueError(f"cannot read tier from {key}: {t[:80]}")
            tiers.append({"min": duration(m.group(1), m.group(2)),
                          "max": duration(m.group(3), m.group(4)) if m.group(3) else None,
                          "value": thaiword_to_num(pay.group(1)), "citation_key": key})
        rates.append({"key": "severance_tiers", "citation_key": "LPA2541:118:1", "tiers": tiers})

        for key, name in [("LPA2541:61:1", "ot_multiplier"),
                          ("LPA2541:62:1:(1)", "holiday_work_extra_multiplier"),
                          ("LPA2541:62:1:(2)", "holiday_work_multiplier"),
                          ("LPA2541:63:1", "holiday_ot_multiplier")]:
            m = MULT_RE.search(text_of(conn, key))
            rates.append({"key": name, "citation_key": key, "value": str(MULTIPLE_WORDS[m.group(1)])})

        t68 = text_of(conn, "LPA2541:68:1")
        if "หารด้วยผลคูณของสามสิบ" not in t68:
            raise ValueError("ม.68 wording changed; re-check days_per_month")
        rates.append({"key": "days_per_month", "citation_key": "LPA2541:68:1", "value": "30"})

        m = INTEREST_RE.search(text_of(conn, "LPA2541:9:1"))
        if not m:
            raise ValueError("ม.9 วรรคหนึ่ง wording changed; re-check interest_rate_pa")
        rates.append({"key": "interest_rate_pa", "citation_key": "LPA2541:9:1",
                      "value": str(thaiword_to_num(m.group(1)))})
        m = SURCHARGE_RE.search(text_of(conn, "LPA2541:9:2"))
        if not m:
            raise ValueError("ม.9 วรรคสอง wording changed; re-check surcharge rows")
        for name, grp in [("surcharge_grace_days", 1), ("surcharge_rate", 2), ("surcharge_period_days", 3)]:
            rates.append({"key": name, "citation_key": "LPA2541:9:2", "value": str(thaiword_to_num(m.group(grp)))})

        for key, loc_key, locs in MIN_WAGE_ROWS:
            row = conn.execute("SELECT text, valid_from, valid_to FROM provisions WHERE citation_key=%s",
                               (key,)).fetchone()
            if not row:
                raise LookupError(key)
            m = WAGE_RE.search(row[0])
            if not m:
                raise ValueError(f"cannot read minimum wage from {key}: {row[0][:80]}")
            rates.append({"key": "min_wage_daily", "citation_key": key, "locality_citation_key": loc_key,
                          "localities": locs, "valid_from": row[1], "valid_to": row[2],
                          "valid_from_citation_key": MIN_WAGE_START,
                          "value": str(thaiword_to_num(m.group(1)))})

        book = RateBook.model_validate({"rates": rates})
        keys = {r["citation_key"] for r in rates} | {t["citation_key"] for t in tiers}
        keys |= {r[k] for r in rates for k in ("locality_citation_key", "valid_from_citation_key") if r.get(k)}
        problems = book.verify({k: text_of(conn, k) for k in keys})
    if problems:
        raise SystemExit("rates do not match the statute:\n" + "\n".join(problems))
    header = ("# GENERATED by src/calc/build_rates.py from provision text in the DB — do not edit.\n"
              "# Every number is re-verified against its citation_key.\n")
    OUT.write_text(header + yaml.safe_dump(rates, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"{len(rates)} rates, {len(tiers)} severance tiers → {OUT}")


if __name__ == "__main__":
    main()
