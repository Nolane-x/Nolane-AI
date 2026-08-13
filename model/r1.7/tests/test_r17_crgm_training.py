from pathlib import Path

import pytest
import torch

from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r17_crgm_training import (
    collect_crgm_episode,
    crgm_internal_gate,
    crgm_trainable_parameter_names,
    evaluate_crgm_episodes,
)


def _root():
    return Path(__file__).resolve().parents[1]


def _load_goal():
    root = _root()
    return load_r17_checkpoint(
        root / "checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt",
        expected_r1_2_checkpoint=root / "checkpoints/Nolane-Rebuild-R1.2-ACE.pt",
        expected_r1_6_parent_checkpoint=root / "checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt",
    )[0]


def test_crgm_optimizer_scope_excludes_policy_scale_and_all_parent_paths():
    model = _load_goal()
    names = crgm_trainable_parameter_names(model, include_policy_scale=False)
    assert names
    assert all(name.startswith("causal_role_goal_") for name in names)
    assert "causal_role_goal_policy_scale" not in names
    assert all(not name.startswith("causal_law_") for name in names)
    assert all(not name.startswith("goal_difference_") for name in names)


def test_crgm_collector_rejects_dev_and_fresh():
    model = _load_goal()
    with pytest.raises(ValueError, match="train split"):
        collect_crgm_episode(model, make_r17_task("causal_laws", "dev", 170))
    with pytest.raises(ValueError, match="train split"):
        collect_crgm_episode(model, make_r17_task("causal_switch", "fresh", 170))


def test_crgm_collector_emits_role_law_targets_and_goal_difference_baseline():
    model = _load_goal(); model.eval()
    ep = collect_crgm_episode(model, make_r17_task("causal_laws", "train", 170), exploration_steps=6, max_steps=14)
    assert ep.steps
    row = ep.steps[0]
    actions = row.retrieved_law.shape[0]
    assert row.need_sketch.shape == (64,)
    assert float(row.role_confidence) > 0
    assert row.retrieved_law.shape == (actions, model.causal_law_dim)
    assert row.law_confidence.shape == (actions,)
    assert row.target_progress.shape == (actions,)
    assert row.baseline_progress.shape == (actions,)
    assert row.predict_mask.shape == (actions,)
    assert row.predict_mask.dtype == torch.bool
    assert bool(row.predict_mask.any())


def test_crgm_evaluator_reports_mse_and_top_action_ranking_against_baseline():
    model = _load_goal(); model.eval()
    ep = collect_crgm_episode(model, make_r17_task("causal_switch", "train", 186), exploration_steps=4, max_steps=10)
    metrics = evaluate_crgm_episodes(model, [ep])
    assert metrics["elements"] > 0
    assert metrics["candidate_mse"] >= 0
    assert metrics["baseline_mse"] >= 0
    assert 0 <= metrics["candidate_rank_accuracy"] <= 1
    assert 0 <= metrics["baseline_rank_accuracy"] <= 1
    assert "causal_switch" in metrics["families"]


def test_crgm_gate_requires_both_mse_and_ranking_gain_with_family_preservation():
    passing = {
        "candidate_mse": 0.10,
        "baseline_mse": 0.20,
        "candidate_rank_accuracy": 0.60,
        "baseline_rank_accuracy": 0.40,
        "families": {
            "causal_laws": {"candidate_rank_accuracy": 0.60, "baseline_rank_accuracy": 0.50},
            "causal_switch": {"candidate_rank_accuracy": 0.55, "baseline_rank_accuracy": 0.55},
        },
    }
    assert crgm_internal_gate(passing)
    assert not crgm_internal_gate(dict(passing, candidate_rank_accuracy=0.40))
    bad_family = dict(passing)
    bad_family["families"] = dict(passing["families"])
    bad_family["families"]["causal_switch"] = {"candidate_rank_accuracy": 0.40, "baseline_rank_accuracy": 0.55}
    assert not crgm_internal_gate(bad_family)
