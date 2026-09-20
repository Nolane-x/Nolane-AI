from __future__ import annotations

import random

import torch

from rescue_aligned_proposal_core import (
    BOTH_FAIL_CLASS,
    BOTH_SOLVE_CLASS,
    HARM_CLASS,
    JOINT_OUTCOME_CLASS_COUNT,
    PAIR_FEATURE_DIM,
    RESCUE_CLASS,
    NativeR40RescueAlignedProposalEnsemble,
)
from rescue_aligned_proposal_training import (
    _round_robin_stratified_order,
    _select_action_row,
    _training_stratum,
)


def _group(task_index: int) -> list[dict[str, object]]:
    return [
        {
            "task_index": task_index,
            "step": 0,
            "class_id": BOTH_SOLVE_CLASS,
            "features": torch.zeros(PAIR_FEATURE_DIM),
        }
    ]


def test_parameter_count_is_identical_to_r39() -> None:
    model = NativeR40RescueAlignedProposalEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        set_hidden_dim=64,
    )
    assert model.goal_parameter_count() == 107799
    assert model.set_parameter_count() == 313365
    assert model.parameter_count() == 421164


def test_runtime_set_model_still_has_null_option() -> None:
    model = NativeR40RescueAlignedProposalEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        set_hidden_dim=16,
    )
    output = model.decision_set_outputs(torch.zeros(3, PAIR_FEATURE_DIM))
    assert output["outcome_probabilities"].shape == (3, 3, JOINT_OUTCOME_CLASS_COUNT)
    assert output["selection_probabilities"].shape == (3, 4)
    assert output["rescue_probabilities"].shape == (3, 3)
    assert torch.all((output["rescue_probabilities"] >= 0.0) & (output["rescue_probabilities"] <= 1.0))
    assert torch.allclose(
        output["selection_probabilities"].sum(dim=-1),
        torch.ones(3),
        atol=1e-6,
    )


def test_eight_training_strata_cover_contiguous_range() -> None:
    minimum = 24704
    maximum = 25087
    values = [
        _training_stratum(
            _group(index),
            minimum_index=minimum,
            maximum_index=maximum,
            stratum_count=8,
        )
        for index in range(minimum, maximum + 1)
    ]
    assert min(values) == 0
    assert max(values) == 7
    counts = [values.count(index) for index in range(8)]
    assert counts == [48] * 8


def test_round_robin_order_interleaves_strata_deterministically() -> None:
    groups = [_group(index) for index in range(24704, 24704 + 8 * 2)]
    order, strata = _round_robin_stratified_order(
        groups,
        stratum_count=8,
        rng=random.Random(123),
    )
    assert sorted(order) == list(range(len(groups)))
    observed = [strata[index] for index in order[:8]]
    assert observed == list(range(8))


def test_joint_classes_are_unchanged() -> None:
    assert (BOTH_FAIL_CLASS, RESCUE_CLASS, HARM_CLASS, BOTH_SOLVE_CLASS) == (0, 1, 2, 3)
    assert JOINT_OUTCOME_CLASS_COUNT == 4


class _FakeSetModel:
    ensemble_size = 3

    def decision_set_outputs(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        selection = torch.tensor([
            [0.10, 0.60, 0.30],
            [0.10, 0.58, 0.32],
            [0.10, 0.62, 0.28],
        ])
        outcome = torch.zeros(3, 2, 4)
        outcome[:, 0, :] = torch.tensor([0.55, 0.10, 0.03, 0.32])
        outcome[:, 1, :] = torch.tensor([0.20, 0.20, 0.02, 0.58])
        rescue = torch.tensor([
            [0.20, 0.95],
            [0.18, 0.93],
            [0.22, 0.94],
        ])
        return {
            "selection_probabilities": selection,
            "selection_logits": selection.log(),
            "outcome_probabilities": outcome,
            "rescue_probabilities": rescue,
        }


def test_joint_proposal_can_choose_rescue_aligned_candidate_not_selection_argmax() -> None:
    rows = [
        {"features": torch.zeros(PAIR_FEATURE_DIM), "candidate_action": 1},
        {"features": torch.ones(PAIR_FEATURE_DIM), "candidate_action": 2},
    ]
    selected, score = _select_action_row(
        _FakeSetModel(),
        rows,
        selection_threshold=0.20,
        rescue_threshold=0.80,
        harm_ceiling=0.05,
    )
    assert selected is not None
    assert int(selected["candidate_action"]) == 2
    assert score is not None
    assert score["joint_proposal_heads"] == 3
    assert score["selection_preferred_heads"] == 0
    assert score["min_rescue"] >= 0.92
    assert score["max_harm"] <= 0.02
    assert score["selection_margin_vs_null"] > 0.0


class _DisagreeingJointModel(_FakeSetModel):
    def decision_set_outputs(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        output = super().decision_set_outputs(features)
        rescue = output["rescue_probabilities"].clone()
        rescue[2] = torch.tensor([0.95, 0.20])
        output["rescue_probabilities"] = rescue
        return output


def test_joint_proposal_requires_ensemble_consensus() -> None:
    rows = [
        {"features": torch.zeros(PAIR_FEATURE_DIM), "candidate_action": 1},
        {"features": torch.ones(PAIR_FEATURE_DIM), "candidate_action": 2},
    ]
    selected, score = _select_action_row(
        _DisagreeingJointModel(),
        rows,
        selection_threshold=0.20,
        rescue_threshold=0.50,
        harm_ceiling=0.05,
    )
    assert selected is None
    assert score is not None
    assert score["joint_proposal_heads"] < 3
