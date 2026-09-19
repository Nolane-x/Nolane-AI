from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_fresh.py"

spec = importlib.util.spec_from_file_location("r3_evaluate_fresh", SCRIPT)
assert spec is not None and spec.loader is not None
evaluate_fresh = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evaluate_fresh
spec.loader.exec_module(evaluate_fresh)


def _lock() -> dict:
    return {
        "schema_version": 1,
        "status": "FROZEN_FRESH_UNOPENED",
        "candidate": "Neural-vNext-Native-R3-AttributedBelief",
        "frozen_candidate": {
            "checkpoint_sha256": "candidate-file",
            "state_dict_sha256": "candidate-state",
            "selected_candidate": "attributed_broad",
            "fresh_opened": False,
        },
        "candidate_authority": {
            "mode": "frozen_workflow_artifact",
            "status": "VERIFIED",
            "workflow_run_id": 1,
            "artifact_id": 2,
            "checkpoint_sha256": "candidate-file",
            "state_dict_sha256": "candidate-state",
            "selected_candidate": "attributed_broad",
        },
        "workflow_reproduction": {
            "status": "BITWISE_REPRODUCED_WORKFLOW_LEVEL",
            "workflow_run_ids": [1, 2],
            "cross_host_guarantee_claimed": False,
        },
        "phase2_negative_result": {
            "status": "FROZEN",
            "fresh_opened": False,
        },
        "secondary_development": {
            "supports_freeze": True,
            "claim_boundary": "POST_HOC_DEVELOPMENT_NOT_PROMOTION_COURT",
        },
        "fresh_court": {
            "opened": False,
            "families": [
                "conditional_regimes",
                "regime_switch",
                "implicit_goal_regimes",
                "causal_prerequisites",
            ],
            "index_start": 80,
            "index_end": 119,
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


def _result(*, conditional: int, regime: int, implicit: int, causal: int) -> dict:
    families = {
        "conditional_regimes": {"solved": conditional, "episodes": 40},
        "regime_switch": {"solved": regime, "episodes": 40},
        "implicit_goal_regimes": {"solved": implicit, "episodes": 40},
        "causal_prerequisites": {"solved": causal, "episodes": 40},
    }
    solved = sum(row["solved"] for row in families.values())
    return {"solved": solved, "episodes": 160, "families": families}


def test_gate_accepts_hidden_gain_with_exact_visible_families() -> None:
    parent = _result(conditional=35, regime=30, implicit=25, causal=35)
    candidate = _result(conditional=35, regime=30, implicit=27, causal=35)
    gate = evaluate_fresh.promotion_gate(_lock(), parent=parent, candidate=candidate)
    assert gate["accepted"] is True
    assert gate["total_solved_delta_vs_parent"] == 2
    assert gate["target_family_solved_delta_vs_parent"] == 2
    assert gate["all_visible_target_families_exact"] is True


def test_gate_rejects_visible_drift_even_if_total_and_hidden_improve() -> None:
    parent = _result(conditional=35, regime=30, implicit=25, causal=35)
    candidate = _result(conditional=36, regime=30, implicit=27, causal=35)
    gate = evaluate_fresh.promotion_gate(_lock(), parent=parent, candidate=candidate)
    assert gate["accepted"] is False
    assert gate["total_solved_delta_vs_parent"] > 0
    assert gate["target_family_solved_delta_vs_parent"] > 0
    assert gate["visible_target_family_pass"]["conditional_regimes"] is False


def test_gate_rejects_no_hidden_gain() -> None:
    parent = _result(conditional=35, regime=30, implicit=25, causal=35)
    candidate = _result(conditional=35, regime=30, implicit=25, causal=35)
    gate = evaluate_fresh.promotion_gate(_lock(), parent=parent, candidate=candidate)
    assert gate["accepted"] is False


def test_expected_identities_are_exact_fresh_cartesian_product() -> None:
    identities = evaluate_fresh.expected_identities(_lock())
    assert len(identities) == 160
    assert ("implicit_goal_regimes", 80) in identities
    assert ("implicit_goal_regimes", 119) in identities
    assert ("implicit_goal_regimes", 79) not in identities


def test_expected_identities_reject_bool_integer_coercion() -> None:
    lock = _lock()
    lock["fresh_court"]["index_start"] = True
    with pytest.raises(ValueError, match="exact integer"):
        evaluate_fresh.expected_identities(lock)


def test_verify_rows_rejects_duplicate_or_nonfresh() -> None:
    lock = _lock()
    rows = [
        {"family": family, "split": "fresh", "index": index}
        for family, index in sorted(evaluate_fresh.expected_identities(lock))
    ]
    evaluate_fresh.verify_rows(lock, rows, label="candidate")
    duplicate = list(rows)
    duplicate[-1] = duplicate[0]
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_fresh.verify_rows(lock, duplicate, label="candidate")
    wrong = [dict(row) for row in rows]
    wrong[0]["split"] = "dev"
    with pytest.raises(ValueError, match="non-fresh"):
        evaluate_fresh.verify_rows(lock, wrong, label="candidate")


def test_load_lock_is_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "PRE_FRESH_LOCK.json"
    lock = _lock()
    path.write_text(json.dumps(lock))
    loaded = evaluate_fresh.load_lock(path)
    assert loaded["fresh_court"]["opened"] is False

    bad = _lock()
    bad["fresh_court"]["opened"] = True
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="opened=false"):
        evaluate_fresh.load_lock(path)

    bad = _lock()
    bad["promotion_gate"]["required_visible_family_solved_delta"] = 1
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="promotion gate"):
        evaluate_fresh.load_lock(path)

    bad = _lock()
    bad["workflow_reproduction"]["cross_host_guarantee_claimed"] = True
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="cross-host"):
        evaluate_fresh.load_lock(path)

    bad = _lock()
    bad["phase2_negative_result"]["status"] = "IGNORED"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="negative result"):
        evaluate_fresh.load_lock(path)

    bad = _lock()
    bad["secondary_development"]["claim_boundary"] = "PROMOTION_COURT"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="boundary"):
        evaluate_fresh.load_lock(path)
