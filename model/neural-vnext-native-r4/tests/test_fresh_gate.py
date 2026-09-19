from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_fresh.py"

spec = importlib.util.spec_from_file_location(
    "r4_evaluate_fresh",
    SCRIPT,
)
assert spec is not None and spec.loader is not None
evaluate_fresh = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evaluate_fresh
spec.loader.exec_module(evaluate_fresh)


def _lock() -> dict:
    return {
        "schema_version": 1,
        "status": "FROZEN_FRESH_UNOPENED",
        "candidate": "Neural-vNext-Native-R4-LatentGoalBelief",
        "frozen_candidate": {
            "checkpoint_sha256": "candidate-file",
            "state_dict_sha256": "candidate-state",
            "selected_candidate": "latent_goal_guarded",
            "fresh_opened": False,
        },
        "candidate_authority": {
            "mode": "frozen_workflow_artifact",
            "status": "VERIFIED",
            "workflow_run_id": 1,
            "artifact_id": 2,
            "checkpoint_sha256": "candidate-file",
            "state_dict_sha256": "candidate-state",
            "selected_candidate": "latent_goal_guarded",
        },
        "source_training_reproducibility": {
            "status": "NON_BITWISE_REPRODUCIBLE_DISCLOSED",
            "cross_run_bitwise_reproducible": False,
            "behavioral_dev_metrics_reproduced": True,
            "canonical_selection_rule": (
                "first completed successful dev run at locked source head"
            ),
            "canonical_workflow_run_id": 1,
            "attempts": [{"workflow_run_id": 1}, {"workflow_run_id": 3}],
        },
        "fresh_court": {
            "opened": False,
            "families": [
                "conditional_regimes",
                "regime_switch",
                "implicit_goal_regimes",
                "causal_prerequisites",
            ],
            "index_start": 120,
            "index_end": 159,
            "episodes_expected": 160,
        },
        "promotion_gate": {
            "minimum_total_solved_delta_vs_parent": 1,
            "target_family": "implicit_goal_regimes",
            "minimum_target_family_solved_delta": 1,
            "visible_target_families": [
                "conditional_regimes",
                "regime_switch",
                "causal_prerequisites",
            ],
            "required_visible_family_solved_delta": 0,
            "all_requirements_must_pass": True,
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
        "conditional_regimes": {
            "solved": conditional,
            "episodes": 40,
        },
        "regime_switch": {"solved": regime, "episodes": 40},
        "implicit_goal_regimes": {
            "solved": implicit,
            "episodes": 40,
        },
        "causal_prerequisites": {
            "solved": causal,
            "episodes": 40,
        },
    }
    solved = sum(row["solved"] for row in families.values())
    return {"solved": solved, "episodes": 160, "families": families}


def test_gate_accepts_hidden_gain_with_exact_visible_families() -> None:
    parent = _result(
        conditional=35,
        regime=30,
        implicit=25,
        causal=35,
    )
    candidate = _result(
        conditional=35,
        regime=30,
        implicit=27,
        causal=35,
    )
    gate = evaluate_fresh.promotion_gate(
        _lock(),
        parent=parent,
        candidate=candidate,
    )
    assert gate["accepted"] is True
    assert gate["total_solved_delta_vs_parent"] == 2
    assert gate["target_family_solved_delta_vs_parent"] == 2
    assert gate["all_visible_target_families_exact"] is True


def test_gate_rejects_visible_drift_even_with_hidden_gain() -> None:
    parent = _result(
        conditional=35,
        regime=30,
        implicit=25,
        causal=35,
    )
    candidate = _result(
        conditional=36,
        regime=30,
        implicit=27,
        causal=35,
    )
    gate = evaluate_fresh.promotion_gate(
        _lock(),
        parent=parent,
        candidate=candidate,
    )
    assert gate["accepted"] is False
    assert (
        gate["visible_target_family_pass"][
            "conditional_regimes"
        ]
        is False
    )


def test_expected_identities_are_exact_new_fresh_block() -> None:
    identities = evaluate_fresh.expected_identities(_lock())
    assert len(identities) == 160
    assert ("implicit_goal_regimes", 120) in identities
    assert ("implicit_goal_regimes", 159) in identities
    assert ("implicit_goal_regimes", 119) not in identities


def test_expected_identities_reject_bool_integer_coercion() -> None:
    lock = _lock()
    lock["fresh_court"]["index_start"] = True
    with pytest.raises(ValueError, match="exact integer"):
        evaluate_fresh.expected_identities(lock)


def test_verify_rows_rejects_duplicate_or_nonfresh() -> None:
    lock = _lock()
    rows = [
        {
            "family": family,
            "split": "fresh",
            "index": index,
        }
        for family, index in sorted(
            evaluate_fresh.expected_identities(lock)
        )
    ]
    evaluate_fresh.verify_rows(
        lock,
        rows,
        label="candidate",
    )
    duplicate = list(rows)
    duplicate[-1] = duplicate[0]
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_fresh.verify_rows(
            lock,
            duplicate,
            label="candidate",
        )


def test_load_lock_requires_negative_repro_disclosure(
    tmp_path: Path,
) -> None:
    path = tmp_path / "PRE_FRESH_LOCK.json"
    lock = _lock()
    path.write_text(json.dumps(lock))
    assert evaluate_fresh.load_lock(path)["fresh_court"]["opened"] is False

    bad = _lock()
    bad["source_training_reproducibility"][
        "cross_run_bitwise_reproducible"
    ] = True
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="must not claim"):
        evaluate_fresh.load_lock(path)

    bad = _lock()
    bad["source_training_reproducibility"][
        "canonical_selection_rule"
    ] = "best hash"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="canonical artifact rule"):
        evaluate_fresh.load_lock(path)

    bad = _lock()
    bad["fresh_court"]["opened"] = True
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="opened=false"):
        evaluate_fresh.load_lock(path)
