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
        "reproducibility_gate": {
            "status": "PASSED",
            "independent_attempts": [
                {"workflow_run_id": 1},
                {"workflow_run_id": 2},
            ],
            "checkpoint_sha256_equal": True,
            "state_dict_sha256_equal": True,
            "development_metrics_equal": True,
            "selected_candidate_equal": True,
            "fresh_unopened_equal": True,
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

    lock = _lock()
    lock["reproducibility_gate"]["status"] = "PENDING"
    path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="reproducibility_gate PASSED"):
        evaluate_fresh.load_fresh_lock(path)

    lock = _lock()
    lock["reproducibility_gate"]["independent_attempts"][1]["workflow_run_id"] = 1
    path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="distinct workflow runs"):
        evaluate_fresh.load_fresh_lock(path)


def test_r2_train_dev_fresh_seed_identities_are_disjoint() -> None:
    ranges = {
        "train": ((128, 511), (512, 1023)),
        "dev": ((32, 63), (64, 95)),
        "fresh": ((40, 79),),
    }
    families = (
        "conditional_regimes",
        "regime_switch",
        "implicit_goal_regimes",
        "causal_prerequisites",
    )
    seen: dict[int, tuple[str, str, int]] = {}
    for split, blocks in ranges.items():
        for start, end in blocks:
            for family in families:
                for index in range(start, end + 1):
                    task = evaluate_fresh.make_r18_task(family, split, index)
                    identity = (split, family, index)
                    assert task.split == split
                    assert f":{split}:" in task.task_id
                    assert task.seed not in seen, (
                        task.seed,
                        seen.get(task.seed),
                        identity,
                    )
                    seen[task.seed] = identity

    fresh_seeds = {
        seed
        for seed, (split, _family, _index) in seen.items()
        if split == "fresh"
    }
    nonfresh_seeds = set(seen) - fresh_seeds
    assert fresh_seeds
    assert fresh_seeds.isdisjoint(nonfresh_seeds)


def _checkpoint_authority_fixture() -> tuple[dict, dict]:
    development = {
        "split": "dev",
        "indices": [64, 95],
        "episodes": 128,
        "solved": 116,
        "solve_rate": 0.90625,
        "steps": 1700,
        "families": {
            "conditional_regimes": {"episodes": 32, "solved": 31, "steps": 290},
            "regime_switch": {"episodes": 32, "solved": 31, "steps": 472},
            "implicit_goal_regimes": {"episodes": 32, "solved": 22, "steps": 456},
            "causal_prerequisites": {"episodes": 32, "solved": 32, "steps": 482},
        },
    }
    eligibility = {
        "eligible": True,
        "total_improved": True,
        "implicit_goal_improved": True,
        "visible_target_families_exact": True,
        "regime_switch_non_regression": True,
        "family_solved_delta_vs_phase1": {
            "conditional_regimes": 0,
            "regime_switch": 0,
            "implicit_goal_regimes": 2,
            "causal_prerequisites": 0,
        },
    }
    phase1 = {"split": "dev", "indices": [64, 95], "solved": 114}
    parent = {"split": "dev", "indices": [64, 95], "solved": 101}
    frozen = {
        "checkpoint_sha256": "candidate-file",
        "state_dict_sha256": "candidate-state",
        "predev_lock_sha256": "predev",
        "parameters": 536085,
        "successor_parameters": 201986,
        "parent_checkpoint_sha256": "parent-file",
        "parent_state_dict_sha256": "parent-state",
        "selected_candidate": "hidden_trace_broad",
        "selected_rank": [116, 22, -1700],
        "selected_eligibility": eligibility,
        "development": development,
        "phase1_reference": phase1,
        "parent_reference": parent,
        "fresh_opened": False,
    }
    metadata = {
        key: frozen[key]
        for key in (
            "checkpoint_sha256",
            "state_dict_sha256",
            "predev_lock_sha256",
            "parameters",
            "successor_parameters",
            "parent_checkpoint_sha256",
            "parent_state_dict_sha256",
        )
    }
    metadata["training_summary"] = {
        "selected_candidate": "hidden_trace_broad",
        "selected_rank": [116, 22, -1700],
        "selected_eligibility": eligibility,
        "fresh_opened": False,
        "phase2_tournament": [
            {
                "name": "hidden_trace_broad",
                "development": development,
                "eligibility": eligibility,
            }
        ],
        "phase1_on_phase2_dev": phase1,
        "parent_phase2_dev": parent,
    }
    return {"frozen_candidate": frozen}, metadata


def test_verify_checkpoint_binds_full_development_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lock, metadata = _checkpoint_authority_fixture()
    model = object()
    monkeypatch.setattr(
        evaluate_fresh,
        "load_successor_checkpoint",
        lambda _path: (model, metadata),
    )
    restored, observed = evaluate_fresh.verify_checkpoint(
        lock,
        tmp_path / "successor.pt",
    )
    assert restored is model
    assert observed is metadata

    tampered = json.loads(json.dumps(metadata))
    tampered["training_summary"]["phase2_tournament"][0]["development"]["solved"] = 115
    monkeypatch.setattr(
        evaluate_fresh,
        "load_successor_checkpoint",
        lambda _path: (model, tampered),
    )
    with pytest.raises(ValueError, match="development evidence mismatch"):
        evaluate_fresh.verify_checkpoint(lock, tmp_path / "successor.pt")
