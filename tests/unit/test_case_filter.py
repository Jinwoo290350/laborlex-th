import pytest

from src.index.tools import _mentions


def test_mentions_matches_section_number_only_as_a_whole_number():
    secs = {"LPA2541:119", "LPA2541:17", "LPA2541:17/1"}
    assert _mentions("ตามมาตรา 119 (2) และมาตรา 17 วรรคสอง", secs) == ["LPA2541:119", "LPA2541:17"]
    assert _mentions("มาตรา 1190 และมาตรา 17/1", secs) == ["LPA2541:17/1"]
    assert _mentions("", secs) == []


def _db_ok() -> bool:
    try:
        from src.index.db import connect
        with connect() as c:
            return c.execute("SELECT count(*) FROM cases").fetchone()[0] > 0
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _db_ok(), reason="Legal Index not loaded")
def test_search_cases_excludes_used_and_repeated_headnotes():
    from src.index.tools import search_cases
    q, secs = "ลูกจ้างถูกเลิกจ้างโดยไม่ได้รับค่าชดเชย", {"LPA2541:118", "LPA2541:119"}
    first = search_cases(q, secs, k=5)
    assert first and all(h["overlap"] or h["mentions"] for h in first)
    heads = [h["holding"][:400] for h in first]
    assert len(heads) == len(set(heads))
    again = search_cases(q, secs, k=5, exclude={first[0]["key"]})
    assert first[0]["key"] not in {h["key"] for h in again}
