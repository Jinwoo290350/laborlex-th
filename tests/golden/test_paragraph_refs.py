"""Self-consistency check on real statutes: when a section refers to its own
"วรรคN" (not "มาตรา X วรรคN"), the parser must have found at least N paragraphs,
and the reference must come from a later paragraph. Catches paragraph mis-splits
without relying on the parser's own output as ground truth."""
import re
from pathlib import Path

import pytest

from src.ingest.parse_statute import parse

ORD = {"หนึ่ง": 1, "สอง": 2, "สาม": 3, "สี่": 4, "ห้า": 5, "หก": 6, "เจ็ด": 7, "แปด": 8}
# "วรรคสาม" not preceded by "มาตรา <n>" / "แห่ง…" within a few chars
SELF_REF = re.compile(r"(?<!\d )(?<!\d/\d )(?:ตาม|ใน|ของ|แห่ง)?วรรค(หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด)")
OTHER_SECTION = re.compile(
    r"\d+(?:/\d+)?\s*(?:วรรค\S*?(?:\s*(?:และ|หรือ|,)\s*วรรค\S*?)*)?\s*(?:และ|หรือ|,)?\s*$")
LAWS = {"LPA2541": "มาตรา", "LRA2518": "มาตรา"}


@pytest.mark.parametrize("law", LAWS)
def test_self_paragraph_refs(law):
    src = Path(f"data/interim/laws/{law}.txt")
    if not src.exists():
        pytest.skip("run make ingest first")
    problems = []
    for s in parse(src.read_text(encoding="utf-8"), unit=LAWS[law], normalized=True):
        for pi, p in enumerate(s.paragraphs, 1):
            for m in SELF_REF.finditer(p.full_text()):
                before = p.full_text()[max(0, m.start() - 60):m.start()]
                if OTHER_SECTION.search(before):
                    continue                      # "มาตรา 25 วรรคสองและวรรคสาม" → another section
                n = ORD[m.group(1)]
                if n > len(s.paragraphs):
                    problems.append(f"{law}:{s.section_no} para {pi} cites วรรค{m.group(1)} "
                                    f"but has {len(s.paragraphs)} paragraphs")
    assert not problems, "\n".join(problems)
