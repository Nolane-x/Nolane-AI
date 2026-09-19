from __future__ import annotations

import copy
from pathlib import Path
import sys

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_fresh import (  # noqa: E402
    expected_identities,
    git_blob_sha,
    promotion_gate,
    verify_court_rows,
)


LOCK = {
    "fresh_court": {
        "families": [
            "conditional_regimes",
            "regime_switch",
            "implicit_goal_regimes",
            "causal_prerequisites",
        ],
        "index_start": 0,
        "index_end": 1,
        "episodes_expected": 8,
    },
    "promotion_gate": {
        "minimum_total_solved": 6,
        "minimum_total_solve_rate": 0.75,
        "minimum_solved_per_family": 1,
    },
}


def _rows() -> list[dict[str, object]]:
    return [
        {"family": family, "split": "fresh", "index": index, "solved": True, "steps": 1}
        for family, index in sorted(expected_identities(LOCK))
    ]


def test_git_blob_sha_matches_git_object_formula(tmp_path: Path) -> None:
    path = tmp_path / "x.txt"
    path.write_bytes(b"hello\n")
    assert git_blob_sha(path) == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_fresh_identity_gate_accepts_exact_cartesian_product() -> None:
    verify_court_rows(LOCK, _rows())


def test_fresh_identity_gate_rejects_duplicate_and_missing_identity() -> None:
    rows = _rows()
    rows[-1] = copy.deepcopy(rows[0])
    try:
        verify_court_rows(LOCK, rows)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate fresh identities must fail closed")


def test_promotion_gate_requires_total_rate_and_every_family() -> None:
    result = {
        "solved": 6,
        "solve_rate": 0.75,
        "families": {
            "conditional_regimes": {"solved": 2},
            "regime_switch": {"solved": 1},
            "implicit_goal_regimes": {"solved": 2},
            "causal_prerequisites": {"solved": 1},
        },
    }
    gate = promotion_gate(LOCK, result)
    assert gate["accepted"] is True

    failed = copy.deepcopy(result)
    failed["families"]["regime_switch"]["solved"] = 0
    gate = promotion_gate(LOCK, failed)
    assert gate["accepted"] is False
    assert gate["all_families_pass"] is False
