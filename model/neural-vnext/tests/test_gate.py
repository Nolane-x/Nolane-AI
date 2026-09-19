from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
VNEXT_ROOT = HERE.parents[1]
if str(VNEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(VNEXT_ROOT))

from nvnext.gate import EXPECTED_FAMILIES, evaluate_frozen_fresh_gate  # noqa: E402


def _lock() -> dict[str, object]:
    return {
        "candidate": "Neural-vNext-MultiDepth-Recursive",
        "parent": {"version": "Neural-R2.3-Ultra-Recursive-DAgger-Gated"},
        "confirmatory_fresh": {
            "block_1_indices": [1120, 1139],
            "block_2_indices": [1140, 1159],
            "episodes_expected": 160,
        },
        "promotion_gates": {
            "candidate_solved_minimum_gain_over_parent": 8,
            "family_regressions_allowed": 0,
        },
    }


def _manifest() -> dict[str, object]:
    return {
        "status": "FROZEN_BEFORE_FRESH",
        "state_dict_sha256": "a" * 64,
        "bundle_sha256": "b" * 64,
        "predev_lock_sha256": "c" * 64,
    }


def _parent_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(1120, 1160):
        for family_index, family in enumerate(EXPECTED_FAMILIES):
            rows.append(
                {
                    "index": index,
                    "family": family,
                    "solved": (index + family_index) % 3 == 0,
                    "steps": 20 + family_index,
                }
            )
    return rows


def _candidate_with_eight_clean_gains(parent: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = [dict(row) for row in parent]
    gains = 0
    for row in rows:
        if not row["solved"] and gains < 8:
            row["solved"] = True
            gains += 1
    assert gains == 8
    return rows


def test_frozen_fresh_gate_passes_exact_plus_eight_without_family_regression() -> None:
    parent = _parent_rows()
    candidate = _candidate_with_eight_clean_gains(parent)

    result = evaluate_frozen_fresh_gate(
        parent,
        candidate,
        predev_lock=_lock(),
        candidate_manifest=_manifest(),
    )

    assert result["status"] == "PASS_FROZEN_CONFIRMATORY_FRESH"
    assert result["candidate_solved_gain"] == 8
    assert result["family_regressions"] == []
    assert result["promotion_gate"]["passed"] is True
    assert [block["episodes"] for block in result["blocks"]] == [80, 80]


def test_frozen_fresh_gate_fails_closed_on_any_family_regression() -> None:
    parent = _parent_rows()
    candidate = _candidate_with_eight_clean_gains(parent)
    victim = next(
        row
        for row in candidate
        if row["family"] == "causal_prerequisites"
        and next(
            original["solved"]
            for original in parent
            if original["index"] == row["index"] and original["family"] == row["family"]
        )
    )
    victim["solved"] = False

    result = evaluate_frozen_fresh_gate(
        parent,
        candidate,
        predev_lock=_lock(),
        candidate_manifest=_manifest(),
    )

    assert "causal_prerequisites" in result["family_regressions"]
    assert result["promotion_gate"]["passed"] is False
    assert result["status"] == "FAIL_FROZEN_CONFIRMATORY_FRESH"


def test_fresh_gate_requires_the_exact_160_registered_episode_identities() -> None:
    parent = _parent_rows()
    candidate = _candidate_with_eight_clean_gains(parent)
    candidate[-1]["index"] = 1160

    try:
        evaluate_frozen_fresh_gate(
            parent,
            candidate,
            predev_lock=_lock(),
            candidate_manifest=_manifest(),
        )
    except ValueError as exc:
        assert "unregistered fresh episode" in str(exc)
    else:
        raise AssertionError("fresh gate must reject identities outside the preregistered blocks")
