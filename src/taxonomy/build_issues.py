"""Draft the issue taxonomy from dev100 (CLAUDE.md §5.6).

1. tag each dev question with 1–4 issues (Gemini, grounded on the gold answer)
2. consolidate labels into 20–40 canonical issues
3. primary_provisions = gold sections co-occurring with the issue (data, not memory)
4. elements/pitfalls drafted from the DB text of those provisions

Output: data/processed/issues.yaml with reviewed_by: null — professors must review.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from pydantic import BaseModel

from src.calc.labor import CALCULATORS
from src.llm import USAGE, generate_json

PROMPTS = Path("prompts")
OUT = Path("data/processed/issues.yaml")
TAGS = Path("data/processed/dev100_issue_tags.json")


def _prompt(name: str) -> str:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    return text.split("---", 2)[2].strip()          # drop version header


class Tag(BaseModel):
    code: str
    name: str
    reason: str


class Tags(BaseModel):
    issues: list[Tag]


class Canon(BaseModel):
    code: str
    name: str
    description: str
    merged_codes: list[str]


class Taxonomy(BaseModel):
    issues: list[Canon]


class Element(BaseModel):
    id: str
    question: str
    citation_keys: list[str]


class Elements(BaseModel):
    elements: list[Element]
    common_pitfalls: list[str]
    formula_key: str | None


def main() -> None:
    with open("data/eval/dev100.csv", encoding="utf-8") as f:
        qs = list(csv.DictReader(f))

    def tag(q):
        p = _prompt("tag_issues").format(question=q["question"], gold=q["gold_answer"],
                                         citations=q["gold_citations"] or "-")
        return q["id"], generate_json(p, Tags, name="tag_issues")

    with ThreadPoolExecutor(8) as ex:
        tagged = dict(ex.map(tag, qs))
    TAGS.write_text(json.dumps({k: v.model_dump() for k, v in tagged.items()},
                               ensure_ascii=False, indent=1), encoding="utf-8")

    labels = Counter((t.code, t.name) for v in tagged.values() for t in v.issues)
    listing = "\n".join(f"{c}: {n} ×{k}" for (c, n), k in labels.most_common())
    tax = generate_json(_prompt("consolidate_issues").format(min_n=20, max_n=40, labels=listing),
                        Taxonomy, name="consolidate")
    to_canon = {old: c.code for c in tax.issues for old in c.merged_codes}

    # issue → gold sections (co-occurrence over dev100)
    by_issue: dict[str, Counter] = defaultdict(Counter)
    q_issues: dict[str, list[str]] = {}
    for q in qs:
        codes = sorted({to_canon.get(t.code, t.code) for t in tagged[q["id"]].issues})
        q_issues[q["id"]] = codes
        for c in codes:
            by_issue[c].update(g for g in q["gold_citations"].split(";") if g)

    from src.index.tools import get_section

    def elements(c: Canon):
        prims = [s for s, n in by_issue[c.code].most_common(6) if n >= 1]
        texts = []
        for key in prims:
            law, sec = key.split(":", 1)
            for r in get_section(law, sec):
                texts.append(f"[{r['citation_key']}] {r['text']}")
        if not texts:
            return c, prims, None
        p = _prompt("issue_elements").format(name=c.name, description=c.description,
                                             provisions="\n".join(texts)[:12000],
                                             formulas=sorted(CALCULATORS))
        return c, prims, generate_json(p, Elements, name="issue_elements")

    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(elements, tax.issues))

    from src.index.db import connect
    with connect() as conn:
        valid = {r[0] for r in conn.execute("SELECT citation_key FROM provisions")}
    dropped = []

    def clean(keys: list[str]) -> list[str]:
        ks = [k.strip("[] ") for k in keys]
        dropped.extend(k for k in ks if k not in valid)
        return [k for k in ks if k in valid]

    out = []
    for c, prims, el in results:
        if el:
            for e in el.elements:
                e.citation_keys = clean(e.citation_keys)
                e.question = re.sub(r"\[([A-Za-z0-9\-]+:[^\]]+)\]", r"\1", e.question)
        out.append({
            "code": c.code, "name": c.name, "description": c.description,
            "primary_provisions": prims,
            "elements": [e.model_dump() for e in el.elements] if el else [],
            "common_pitfalls": el.common_pitfalls if el else [],
            "formula_key": el.formula_key if el else None,
            "dev_questions": sorted(k for k, v in q_issues.items() if c.code in v),
            "reviewed_by": None,
        })
    header = ("# DRAFT issue taxonomy generated from dev100 by src/taxonomy/build_issues.py\n"
              "# Elements are drafted from DB provision text. MUST be reviewed by the professors\n"
              "# (set reviewed_by) before production use.\n")
    OUT.write_text(header + yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120),
                   encoding="utf-8")
    Path("data/processed/dev100_issues.json").write_text(
        json.dumps(q_issues, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"dropped {len(dropped)} element citations not in DB: {sorted(set(dropped))}")
    print(f"{len(out)} issues → {OUT} · gemini calls={USAGE.calls} cached={USAGE.cached} "
          f"in={USAGE.input_tokens} out={USAGE.output_tokens}")


if __name__ == "__main__":
    main()
