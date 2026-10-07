"""R1/R2 (docs/benchmarks/exam_regression_spec_2026-10-06.yaml): for the s.31 issue, the ruling that ties s.31 and
s.121 together (10293/2546) is the one offered; 5061/2533 (mediation of disputes) is not. Uses the DB and stored
question embeddings only (fixtures/ram_pilot_qvecs.npz: vectors, no exam text). No Gemini."""

from pathlib import Path

import numpy as np
import pytest

FIX = Path(__file__).parent / "fixtures" / "ram_pilot_qvecs.npz"


def _db_ok() -> bool:
    try:
        from src.index.db import connect
        with connect() as c:
            return c.execute("SELECT count(*) FROM cases").fetchone()[0] > 0
    except Exception:  # noqa: BLE001
        return False


needs_db = pytest.mark.skipif(not _db_ok() or not FIX.exists(), reason="Legal Index or fixture not available")


def _offered(qvec):
    from src.agent.nodes.retrieve import section_support
    from src.index.tools import search_cases
    from src.params import P
    prefer = section_support("dispute_protection_s31", set())
    # candidate sections as retrieve_law would give the issue: taxonomy sections plus typical search hits
    sections = set(prefer) | {"LRA2518:124", "LRA2518:22", "LRA2518:34", "LCA2522:8"}
    return [h["deka_no"] for h in search_cases("", sections, k=P("cases.per_issue"), query_vec=qvec, prefer=prefer)]


@needs_db
@pytest.mark.parametrize("idx", [0, 1])
def test_r1_s31_issue_offers_10293_2546(idx):
    data = np.load(FIX)
    assert _offered(data["vecs"][idx])[0] == "10293/2546", str(data["ids"][idx])


@needs_db
@pytest.mark.parametrize("idx", [0, 1])
def test_r2_s31_issue_does_not_offer_5061_2533(idx):
    data = np.load(FIX)
    assert "5061/2533" not in _offered(data["vecs"][idx])
