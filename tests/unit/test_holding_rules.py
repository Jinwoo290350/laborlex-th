"""Verified holding rules (config/holding_rules.yaml): every quote is a verbatim span of the cited decision in the DB,
and determine_grounds shows the rules for the provisions it judges."""

from __future__ import annotations

import pytest

from src.agent.rules.holding_rules import load_rules, rules_block, verify_rules


def _db_ok() -> bool:
    try:
        from src.index.db import connect
        with connect() as c:
            c.execute("select 1")
        return True
    except Exception:  # noqa: BLE001
        return False


def test_rules_load_and_have_quotes():
    rules = load_rules()
    assert rules and all(r.cases and all(c.quote for c in r.cases) for r in rules)


@pytest.mark.skipif(not _db_ok(), reason="Legal Index not loaded")
def test_every_quote_is_verbatim_in_the_db():
    assert verify_rules() == []


def test_rules_block_filters_by_provision():
    block = rules_block(["CCC:583:1"])
    assert "2512/2545" in block and "239/2545" not in block
    assert "239/2545" in rules_block(["LPA2541:119:1:(2)"])
