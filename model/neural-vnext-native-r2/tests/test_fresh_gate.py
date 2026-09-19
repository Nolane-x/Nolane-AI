from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_fresh.py"

spec = importlib.util.spec_from_file_location("r2_evaluate_fresh", SCRIPT)
assert spec is not None and spec.loader is not None
evaluate_fresh = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evaluate_fresh
spec.loader.exec_module(evaluate_fresh)


def _lock() -> dict:
    return {
        "schema_version": 1,
        "status": "FROZEN_FRESH_UNOPENED",
        "candidate": "Neural-vNext-Native-R2-TransitionTrace",
        "frozen_candidate": {
            "fresh_opened": False,
        },
        "fresh_court": {
            "opened": False,
            "families": [
                "conditional_regimes",
                "regime_switch",
                "implicit_goal_regimes",
                "causal_prerequisites",
            ],
            "index_start": 40,
            "index_end": 79,
            "episodes_expected": 160,
        },
        "promotion_gate": {
            "minimum_total_solved_delta_vs_parent": 1,
            "maximum_family_solved_regression": 0,
            "target_family": "implicit_goal_regimes",
            "minimum_target_family_solved_delta": 1,
        },
    }


def _result(
    *,
    conditional: int,
    regime: int,
    implicit: int,
    causal: int,
) -> dict:
    families = {
        "conditional_regimes": {"solved": conditional, "episodes": 40},
        "regime_switch": {"solved": regime, "episodes": 40},
        "implicit_goal_regimes": {"solved": implicit, "episodes": 40},
        "causal_prerequisites": {"solved": causal, "episodes": 40},
    }
    solved = sum(row["solved"] for row in families.values())
    return {
        "solved": solved,
        "episodes": 160,
        "solve_rate": solved / 160,
        "families": families,
    }


def test_parent_relative_gate_accepts_only_strict_targeted_successor_gain() -> None:
    parent = _result(conditional=25, regime=25, implicit=25, causal=25)
    candidate = _result(conditional=25, regime=26, implicit=26, causal=25)

    gate = evaluate_fresh.promotion_gate(
        _lock(),
        parent=parent,
        candidate=candidate,
    )

    assert gate["accepted"] is True
    assert gate["total_solved_delta_vs_parent"] == 2
    assert gate["target_family_solved_delta_vs_parent"] == 1
    assert gate["all_family_regressions_pass"] is True


def test_parent_relative_gate_rejects_total_gain_without_hidden_goal_gain() -> None:
    parent = _result(conditional=25, regime=25, implicit=25, causal=25)
    candidate = _result(conditional=26, regime=26, implicit=25, causal=25)

    gate = evaluate_fresh.promotion_gate(
        _lock(),
        parent=parent,
        candidate=candidate,
    )

    assert gate["accepted"] is False
    assert gate["total_delta_pass"] is True
    assert gate["target_family_delta_pass"] is False


def test_parent_relative_gate_rejects_family_regression_even_when_total_improves() -> None:
    parent = _result(conditional=25, regime=25, implicit=25, causal=25)
    candidate = _result(conditional=27, regime=26, implicit=26, causal=24)

    gate = evaluate_fresh.promotion_gate(
        _lock(),
        parent=parent,
        candidate=candidate,
    )

    assert gate["accepted"] is False
    assert gate["total_delta_pass"] is True
    assert gate["target_family_delta_pass"] is True
    assert gate["family_regression_pass"]["causal_prerequisites"] is False


def test_expected_identities_is_exact_cartesian_fresh_block() -> None:
    identities = evaluate_fresh.expected_identities(_lock())

    assert len(identities) == 160
    assert ("conditional_regimes", 40) in identities
    assert ("implicit_goal_regimes", 79) in identities
    assert ("implicit_goal_regimes", 39) not in identities


def test_expected_identities_rejects_boolean_integer_coercion() -> None:
    lock = _lock()
    lock["fresh_court"]["index_start"] = True

    with pytest.raises(ValueError, match="exact integer"):
        evaluate_fresh.expected_identities(lock)


def test_verify_court_rows_rejects_duplicates_and_cross_split_rows() -> None:
    lock = _lock()
    rows = [
        {
            "family": family,
            "split": "fresh",
            "index": index,
        }
        for family, index in sorted(evaluate_fresh.expected_identities(lock))
    ]
    evaluate_fresh.verify_court_rows(lock, rows, label="candidate")

    duplicate = list(rows)
    duplicate[-1] = duplicate[0]
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_fresh.verify_court_rows(lock, duplicate, label="candidate")

    wrong_split = [dict(row) for row in rows]
    wrong_split[0]["split"] = "dev"
    with pytest.raises(ValueError, match="non-fresh"):
        evaluate_fresh.verify_court_rows(lock, wrong_split, label="candidate")


def test_load_fresh_lock_is_fail_closed(tmp_path: Path) -> None:
    lock = _lock()
    path = tmp_path / "PRE_FRESH_LOCK.json"
    path.write_text(json.dumps(lock), encoding="utf-8")
    loaded = evaluate_fresh.load_fresh_lock(path)
    assert loaded["fresh_court"]["opened"] is False

    lock["fresh_court"]["opened"] = True
    path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="opened=false"):
        evaluate_fresh.load_fresh_lock(path)

    lock = _lock()
    lock["candidate"] = "wrong"
    path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate identity"):
        evaluate_fresh.load_fresh_lock(path)
