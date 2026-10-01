"""Run the full ①–⑩ flow with a fake LLM against the real Legal Index.

Checks wiring, system controls (taxonomy-only issues, candidate-only citations,
DB-validated labels) and that every node writes a trace entry. Skips without the DB."""
import re

import pytest

from src.agent.answer import AnswerJSON
from src.agent.state import Facts

psycopg = pytest.importorskip("psycopg")


def _db_ok() -> bool:
    try:
        from src.index.db import connect
        with connect() as c:
            return c.execute("SELECT count(*) FROM provisions").fetchone()[0] > 0
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _db_ok(), reason="Legal Index not loaded")


def fake_generate_json(prompt, schema, **kw):
    name = schema.__name__
    if schema is Facts:
        return Facts(key_facts=["ลูกจ้างถูกเลิกจ้าง"], asked=["ได้ค่าชดเชยหรือไม่"])
    if name == "_Issues":
        return schema.model_validate({"issues": [
            {"code": "severance_pay", "reason": "ถามเรื่องค่าชดเชย"},
            {"code": "not_a_real_code", "reason": "ต้องถูกตัดทิ้ง"}]})
    if name == "Scores":   # one required score per listed candidate "[cN] <key> | …"
        keys = dict(re.findall(r"^\[(c\d+)\] (\S+)", prompt, re.MULTILINE))
        return schema.model_validate({i: 0.9 if k == "LPA2541:118:1" else 0.1 for i, k in keys.items()})
    if name == "_Checks":
        return schema.model_validate({"checks": []})
    if schema is AnswerJSON:
        return AnswerJSON.model_validate({
            "preliminary": [{"headline": "ได้ค่าชดเชย", "citations": ["LPA2541:118:1", "LPA2541:999:1"]}],
            "issues": [{"code": "severance_pay", "question": "ได้ค่าชดเชยหรือไม่", "consider": "-",
                        "laws": [{"citation_key": "LPA2541:118:1", "label": "มาตรา 999 ผิด",
                                  "explanation": "-", "topic": "ค่าชดเชย"}],
                        "application": [], "conclusion": [{"headline": "ได้"}],
                        "opinion": "ได้", "basis": "ม.118"}]})
    if name == "Verdict":
        return schema.model_validate({"complete": 1, "supported": 1, "consistent": 1,
                                      "focused": 1, "feedback": ""})
    raise AssertionError(f"unexpected schema {name}")


def test_flow(monkeypatch):
    import src.agent.nodes.decide as d
    import src.agent.nodes.draft as dr
    import src.agent.nodes.understand as u
    for m in (u, d, dr):
        monkeypatch.setattr(m, "generate_json", fake_generate_json)
    from src.agent.graph import STEPS, answer

    s = answer("ลูกจ้างถูกเลิกจ้าง ได้ค่าชดเชยหรือไม่")
    assert [i.code for i in s.issues] == ["severance_pay"]                   # taxonomy only
    assert s.selected["severance_pay"] == ["LPA2541:118:1"] or \
        "LPA2541:999:1" not in s.selected["severance_pay"]                  # candidates only
    assert "LPA2541:999:1" in s.removed_citations                           # ⑩ removed it
    assert s.answer.issues[0].laws[0].label.startswith("มาตรา 118 ")        # label from DB
    assert [t["node"] for t in s.trace] == [n for n, _ in STEPS]
    assert "# คำตอบทางกฎหมาย" in s.markdown
