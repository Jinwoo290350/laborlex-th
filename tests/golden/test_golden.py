from pathlib import Path

import pytest
import yaml

from src.ingest.parse_statute import parse

CASES = yaml.safe_load(Path(__file__).with_name("provisions.yaml").read_text(encoding="utf-8"))
INTERIM = Path("data/interim/laws")


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['law']}:{c['section']}")
def test_golden(case):
    src = INTERIM / f"{case['law']}.txt"
    if case["paragraphs"] is None or not src.exists():
        pytest.skip("not verified yet / source not ingested")
    secs = {s.section_no: s for s in parse(src.read_text(encoding="utf-8"))}
    s = secs[case["section"]]
    assert len(s.paragraphs) == case["paragraphs"]
    if case["subs"] is not None:
        assert [len(p.subs) for p in s.paragraphs] == case["subs"]
