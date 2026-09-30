"""Every tunable value must come from config/params.yaml with provenance, and the code
must not hide numeric tuning constants of its own."""
import re
from pathlib import Path

from src.params import KINDS, registry

REQUIRED = ("value", "kind", "source", "rule", "evidence", "status")


def test_every_parameter_has_provenance():
    bad = []
    for name, e in registry().items():
        missing = [k for k in REQUIRED if k not in e or e[k] in (None, "")]
        if missing:
            bad.append(f"{name}: missing {missing}")
        elif e["kind"] not in KINDS:
            bad.append(f"{name}: kind {e['kind']!r}")
        elif e["status"] not in ("final", "provisional"):
            bad.append(f"{name}: status {e['status']!r}")
        elif "pending derive" in str(e["evidence"]):
            bad.append(f"{name}: run python -m src.params_derive")
    assert not bad, "\n".join(bad)


def test_every_P_name_exists():
    used = set()
    for f in Path("src").rglob("*.py"):
        if f.name == "params.py":
            continue
        used |= set(re.findall(r'P\("([a-z_.]+)"\)', f.read_text(encoding="utf-8")))
    assert used <= set(registry()), sorted(used - set(registry()))


def test_no_hidden_tuning_constants_in_the_flow():
    """Module-level ALL_CAPS numeric constants in the agent/retrieval code must move to the
    registry (identifiers, URLs and model names are fine)."""
    offenders = []
    for f in [*Path("src/agent").rglob("*.py"), Path("src/index/tools.py"), Path("src/api/main.py")]:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^[A-Z][A-Z0-9_]+\s*=\s*[0-9.]+\s*(#.*)?$", line):
                offenders.append(f"{f}:{i}: {line.strip()}")
    assert not offenders, "\n".join(offenders)
