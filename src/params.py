"""Parameter registry: every tunable value lives in config/params.yaml with its provenance.

kind:     statute | requirement | data | measured | design
source:   where the value comes from (file, section, rule)
evidence: numbers/run ids that justify the current value
status:   final | provisional (measured value not yet re-derived on the tune split)
rule:     for measured/data values, the pre-registered selection rule

Code reads values with P("name"); tests fail if an entry lacks provenance.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

PATH = Path("config/params.yaml")
KINDS = {"statute", "requirement", "data", "measured", "design"}


@cache
def registry() -> dict[str, dict[str, Any]]:
    return yaml.safe_load(PATH.read_text(encoding="utf-8"))


def P(name: str) -> Any:
    return registry()[name]["value"]
