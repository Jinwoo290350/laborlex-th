"""M3 calculator: tenure under ป.พ.พ. 193/3 and 193/5, minimum wage, ม.9 interest and surcharge.

Unit logic uses a synthetic RateBook (numbers are fixtures, not law). The tests marked `needs_db` load the real
data/processed/rates.yaml and verify every row against the provision text in the Legal Index."""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from src.calc import labor
from src.calc.labor import RateBook, Tenure

RATES = Path("data/processed/rates.yaml")


def _db_ok() -> bool:
    try:
        from src.index.db import connect
        with connect() as c:
            return c.execute("SELECT count(*) FROM provisions").fetchone()[0] > 0
    except Exception:  # noqa: BLE001
        return False


needs_db = pytest.mark.skipif(not _db_ok() or not RATES.exists(), reason="Legal Index or rate book not available")


def _texts(keys: set[str]) -> dict[str, str]:
    from src.index.db import connect
    with connect() as c:
        rows = c.execute("SELECT citation_key, text FROM provisions WHERE citation_key = ANY(%s)", (list(keys),))
        return {k: t for k, t in rows}


def _book() -> RateBook:
    return RateBook.load(RATES)


# synthetic tiers mirroring the shape of ม.118 (fixture values)
T = lambda mn, mx, v, k: {"min": mn, "max": mx, "value": v, "citation_key": k}
SYN = RateBook(rates=[
    {"key": "days_per_month", "citation_key": "X:68:1", "value": "30"},
    {"key": "severance_tiers", "citation_key": "X:118:1", "tiers": [
        T({"amount": 120, "unit": "day"}, {"amount": 1, "unit": "year"}, "30", "X:118:1:(1)"),
        T({"amount": 1, "unit": "year"}, {"amount": 3, "unit": "year"}, "90", "X:118:1:(2)")]},
    {"key": "min_wage_daily", "citation_key": "W:2:1", "locality_citation_key": "W:2:1:(3)",
     "localities": ["กรุงเทพมหานคร"], "valid_from": "2025-07-01", "value": "400"},
    {"key": "min_wage_daily", "citation_key": "W:4:1", "localities": ["นครปฐม", "นนทบุรี"],
     "valid_from": "2025-07-01", "value": "372"},
    {"key": "interest_rate_pa", "citation_key": "X:9:1", "value": "15"},
    {"key": "surcharge_rate", "citation_key": "X:9:2", "value": "15"},
    {"key": "surcharge_grace_days", "citation_key": "X:9:2", "value": "7"},
    {"key": "surcharge_period_days", "citation_key": "X:9:2", "value": "7"},
])


# ---------------------------------------------------------------- 1. tenure (ป.พ.พ. 193/3, 193/5)

def test_service_full_calendar_year():
    t = Tenure.from_service(date(2026, 1, 1), date(2026, 12, 31))
    assert (t.years, t.months, t.days) == (1, 0, 365)
    assert {"CCC:193/3:2", "CCC:193/5:1", "CCC:193/5:2"} <= set(t.citations)
    assert any("193/3" in s for s in t.steps) and any("193/5" in s for s in t.steps)


def test_service_one_day_short_is_364_days_tier_1():
    t = Tenure.from_service(date(2026, 1, 1), date(2026, 12, 30))
    assert (t.years, t.months, t.days) == (0, 11, 364)
    r = labor.severance(D(100), t, date(2026, 12, 30), SYN)
    assert r.citations == ["X:118:1:(1)"] and r.amount == D(3000)


def test_service_appeal_case_pattern_17_dec_to_16_dec():
    t = Tenure.from_service(date(2018, 12, 17), date(2019, 12, 16))
    assert t.years == 1 and t.months == 0
    assert Tenure.from_service(date(2018, 12, 17), date(2019, 12, 15)).years == 0


def test_service_leap_day_start_ends_on_last_day_of_february():
    # no corresponding day (29 Feb) in the last month → the period ends on the month's last day (193/5 ว.2)
    assert Tenure.from_service(date(2024, 2, 29), date(2025, 2, 28)).years == 1
    assert Tenure.from_service(date(2024, 2, 29), date(2025, 2, 27)).years == 0
    # relativedelta (from_dates) already counts 27 Feb 2025 as one year: the CCC rule differs here
    assert Tenure.from_dates(date(2024, 2, 29), date(2025, 2, 27)).years == 1


def test_service_across_leap_year_counts_366_days():
    t = Tenure.from_service(date(2024, 1, 1), date(2024, 12, 31))
    assert (t.years, t.days) == (1, 366)
    t = Tenure.from_service(date(2023, 3, 1), date(2024, 2, 29))
    assert (t.years, t.days) == (1, 366)
    assert Tenure.from_service(date(2023, 3, 1), date(2024, 2, 28)).years == 0


def test_service_month_end_start_counts_months_by_calendar():
    # 31 Jan: 1-month period has no 31 Feb → ends 28 Feb (2025 not leap)
    assert Tenure.from_service(date(2025, 1, 31), date(2025, 2, 28)).months == 1
    assert Tenure.from_service(date(2025, 1, 31), date(2025, 2, 27)).months == 0


def test_service_rejects_end_before_start():
    with pytest.raises(ValueError):
        Tenure.from_service(date(2026, 1, 2), date(2026, 1, 1))


def test_from_dates_unchanged():
    t = Tenure.from_dates(date(2020, 1, 1), date(2020, 12, 31))
    assert (t.days, t.years) == (366, 1) and t.steps == [] and t.citations == []


def test_severance_branches_when_last_day_unknown():
    br = labor.severance_branches(D(100), date(2026, 1, 1), date(2026, 12, 30), date(2026, 12, 31), SYN)
    assert [b.result.amount for b in br] == [D(3000), D(9000)]
    assert "30 ธ.ค. 2569" in br[0].condition and "31 ธ.ค. 2569" in br[1].condition
    assert br[0].tenure.days == 364 and br[1].tenure.years == 1
    assert "CCC:193/5:2" in br[1].result.citations


def test_severance_branches_single_branch_when_tier_does_not_change():
    br = labor.severance_branches(D(100), date(2026, 1, 1), date(2026, 6, 1), date(2026, 6, 30), SYN)
    assert len(br) == 1 and br[0].result.amount == D(3000)


@needs_db
def test_ccc_rule_text_in_db():
    t = _texts({"CCC:193/3:2", "CCC:193/5:1", "CCC:193/5:2"})
    assert "เว้นแต่จะเริ่มการในวันนั้นเอง" in t["CCC:193/3:2"]
    assert "ปีปฏิทิน" in t["CCC:193/5:1"]
    assert "วันก่อนหน้าจะถึง" in t["CCC:193/5:2"] and "วันสุดท้ายแห่งเดือนนั้น" in t["CCC:193/5:2"]


# ---------------------------------------------------------------- 2. minimum wage

def test_get_local_and_get_unchanged():
    assert SYN.get_local("min_wage_daily", "กรุงเทพมหานคร", date(2026, 1, 1)).value == D(400)
    assert SYN.get_local("min_wage_daily", "นนทบุรี", date(2026, 1, 1)).value == D(372)
    with pytest.raises(LookupError):
        SYN.get_local("min_wage_daily", "เชียงราย", date(2026, 1, 1))
    with pytest.raises(LookupError):                       # not yet in force
        SYN.get_local("min_wage_daily", "กรุงเทพมหานคร", date(2025, 6, 30))
    assert SYN.get("days_per_month", date(2026, 1, 1)).value == D(30)


def test_verify_checks_localities_and_thai_number_words():
    texts = {"W:2:1": "ให้กำหนดอัตราค่าจ้างขั้นต่ำเป็นเงินวันละสี่ร้อยบาท ดังนี้",
             "W:2:1:(3)": "ในท้องที่กรุงเทพมหานคร จังหวัดฉะเชิงเทรา",
             "W:4:1": "วันละสามร้อยเจ็ดสิบสองบาท ในท้องที่จังหวัดนครปฐม",   # นนทบุรี missing
             "X:68:1": "สามสิบ", "X:118:1": "", "X:118:1:(1)": "ครบ 120 วัน 1 ปี 30",
             "X:118:1:(2)": "1 3 90", "X:9:1": "ร้อยละสิบห้าต่อปี", "X:9:2": "เจ็ดวัน ร้อยละสิบห้า"}
    assert SYN.verify(texts) == ["min_wage_daily: locality 'นนทบุรี' not found in W:4:1"]
    texts["W:2:1"] = "วันละสามร้อยบาท"
    assert "min_wage_daily: 400 not found in W:2:1" in SYN.verify(texts)


def test_min_wage_check_below_bangkok():
    r = labor.min_wage_check(D(11500), "กรุงเทพมหานคร", date(2026, 1, 1), SYN)
    assert r.below and r.minimum == D(400) and r.amount == D("383.33")
    assert {"W:2:1", "W:2:1:(3)", "X:68:1"} <= set(r.citations)
    assert any("สมมติ" in s or "ข้อสันนิษฐาน" in s for s in r.steps)


def test_min_wage_check_not_below_nakhon_pathom():
    r = labor.min_wage_check(D(11500), "นครปฐม", date(2026, 1, 1), SYN)
    assert not r.below and r.minimum == D(372)


def test_min_wage_check_exactly_at_minimum_is_not_below():
    assert not labor.min_wage_check(D(12000), "กรุงเทพมหานคร", date(2026, 1, 1), SYN).below


def _months(y: int, paid: D) -> list[tuple[date, date, D]]:
    import calendar
    return [(date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1]), paid) for m in range(1, 13)]


def _halves(y: int, paid: D) -> list[tuple[date, date, D]]:
    import calendar
    out = []
    for m in range(1, 13):
        out += [(date(y, m, 1), date(y, m, 15), paid), (date(y, m, 16), date(y, m, calendar.monthrange(y, m)[1]), paid)]
    return out


@pytest.mark.parametrize("base,per_month,per_year", [(10500, 1500, 18000), (11500, 500, 6000)])
def test_min_wage_shortfall_bangkok_monthly(base, per_month, per_year):
    r = labor.min_wage_shortfall(_months(2026, D(base)), "กรุงเทพมหานคร", SYN)
    assert r.amount == D(per_year)
    assert sum(1 for s in r.steps if f"ขาด {per_month:,} บาท" in s) == 12
    assert "W:2:1" in r.citations


def test_min_wage_shortfall_half_month_pay_periods_no_double_count():
    r = labor.min_wage_shortfall(_halves(2026, D(5250)), "กรุงเทพมหานคร", SYN)
    assert r.amount == D(18000)
    assert sum(1 for s in r.steps if "ขาด 750 บาท" in s) == 24


def test_min_wage_shortfall_zero_when_not_below():
    assert labor.min_wage_shortfall(_months(2026, D(11500)), "นครปฐม", SYN).amount == 0
    assert labor.min_wage_shortfall(_months(2026, D(12000)), "กรุงเทพมหานคร", SYN).amount == 0
    assert labor.min_wage_shortfall(_months(2026, D(15000)), "กรุงเทพมหานคร", SYN).amount == 0


def test_min_wage_shortfall_rejects_unsupported_period():
    with pytest.raises(ValueError):
        labor.min_wage_shortfall([(date(2026, 1, 5), date(2026, 1, 20), D(5000))], "กรุงเทพมหานคร", SYN)


def test_min_wage_shortfall_rejects_overlapping_periods():
    p = _months(2026, D(10500))[:2]
    with pytest.raises(ValueError):
        labor.min_wage_shortfall(p + p[:1], "กรุงเทพมหานคร", SYN)


# ---------------------------------------------------------------- 3. ม.9 interest and surcharge

def test_interest_15_pa():
    r = labor.interest(D(36500), 365, date(2026, 1, 1), SYN)
    assert r.amount == D("5475.00") and r.citations == ["X:9:1"]


def test_surcharge_counts_completed_seven_day_periods_after_grace():
    due = date(2026, 1, 1)
    assert labor.surcharge(D(10000), due, date(2026, 1, 8), SYN).amount == 0      # grace still running
    r = labor.surcharge(D(10000), due, date(2026, 1, 15), SYN)                   # one full period after grace
    assert r.amount == D(1500) and r.citations == ["X:9:2"]
    assert labor.surcharge(D(10000), due, date(2026, 1, 22), SYN).amount == D(3000)
    assert labor.surcharge(D(10000), due, date(2026, 1, 21), SYN).amount == D(1500)
    assert "จงใจ" in (labor.surcharge.__doc__ or "") and "ปราศจากเหตุผลอันสมควร" in (labor.surcharge.__doc__ or "")


# ---------------------------------------------------------------- real rate book vs DB

@needs_db
def test_real_rate_book_verifies_against_db():
    book = _book()
    keys = {r.citation_key for r in book.rates} | {t.citation_key for r in book.rates for t in r.tiers}
    keys |= {r.locality_citation_key for r in book.rates if r.locality_citation_key}
    keys |= {r.valid_from_citation_key for r in book.rates if r.valid_from_citation_key}
    assert book.verify(_texts(keys)) == []


@needs_db
def test_real_minimum_wage_rows():
    book = _book()
    bkk = book.get_local("min_wage_daily", "กรุงเทพมหานคร", date(2026, 1, 1))
    assert bkk.citation_key == "ANN-WAGE14-2568:2:1" and bkk.locality_citation_key == "ANN-WAGE14-2568:2:1:(3)"
    assert bkk.valid_from == date(2025, 7, 1) and bkk.valid_from_citation_key == "ANN-WAGE14-2568:21:1"
    np_ = book.get_local("min_wage_daily", "นครปฐม", date(2026, 1, 1))
    assert np_.citation_key == "ANN-WAGE14-2568:4:1"
    assert labor.min_wage_shortfall(_months(2026, D(10500)), "กรุงเทพมหานคร", book).amount == D(18000)
    assert labor.min_wage_shortfall(_months(2026, D(11500)), "กรุงเทพมหานคร", book).amount == D(6000)
    assert labor.min_wage_shortfall(_months(2026, D(11500)), "นครปฐม", book).amount == 0


@needs_db
def test_real_interest_and_surcharge_rows():
    book = _book()
    assert book.get("interest_rate_pa", date(2026, 1, 1)).citation_key == "LPA2541:9:1"
    for k in ("surcharge_rate", "surcharge_grace_days", "surcharge_period_days"):
        assert book.get(k, date(2026, 1, 1)).citation_key == "LPA2541:9:2"
    assert labor.interest(D(36500), 365, date(2026, 1, 1), book).amount == D("5475.00")
