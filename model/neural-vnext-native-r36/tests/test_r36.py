from __future__ import annotations

import torch

from decision_set_ranker_core import (
    BOTH_FAIL_CLASS,
    BOTH_SOLVE_CLASS,
    HARM_CLASS,
    JOINT_OUTCOME_CLASS_COUNT,
    PAIR_FEATURE_DIM,
    RESCUE_CLASS,
    NativeR36DecisionSetRankerEnsemble,
)
from decision_set_ranker_training import _select_action_row


def test_parameter_count_is_preregistered() -> None:
    model = NativeR36DecisionSetRankerEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        set_hidden_dim=64,
    )
    assert model.goal_parameter_count() == 107799
    assert model.set_parameter_count() == 275730
    assert model.parameter_count() == 383529


def test_decision_set_has_explicit_null_option() -> None:
    model = NativeR36DecisionSetRankerEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        set_hidden_dim=16,
    )
    features = torch.zeros(3, PAIR_FEATURE_DIM)
    output = model.decision_set_outputs(features)
    assert output["outcome_probabilities"].shape == (3, 3, JOINT_OUTCOME_CLASS_COUNT)
    assert output["selection_probabilities"].shape == (3, 4)
    assert output["selection_logits"].shape == (3, 4)
    assert torch.allclose(
        output["selection_probabilities"].sum(dim=-1),
        torch.ones(3),
        atol=1e-6,
    )


def test_set_model_is_permutation_equivariant_and_null_invariant() -> None:
    torch.manual_seed(7)
    model = NativeR36DecisionSetRankerEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        set_hidden_dim=16,
    )
    features = torch.randn(4, PAIR_FEATURE_DIM)
    permutation = torch.tensor([2, 0, 3, 1])
    first = model.decision_set_outputs(features)
    second = model.decision_set_outputs(features[permutation])

    assert torch.allclose(
        first["selection_probabilities"][:, 0],
        second["selection_probabilities"][:, 0],
        atol=1e-6,
    )
    assert torch.allclose(
        first["outcome_probabilities"][:, permutation],
        second["outcome_probabilities"],
        atol=1e-6,
    )
    assert torch.allclose(
        first["selection_probabilities"][:, 1:][:, permutation],
        second["selection_probabilities"][:, 1:],
        atol=1e-6,
    )


def test_joint_classes_are_unchanged() -> None:
    assert (BOTH_FAIL_CLASS, RESCUE_CLASS, HARM_CLASS, BOTH_SOLVE_CLASS) == (0, 1, 2, 3)
    assert JOINT_OUTCOME_CLASS_COUNT == 4


class _FakeSetModel:
    ensemble_size = 3

    def decision_set_outputs(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        assert features.shape[0] == 2
        selection = torch.tensor([
            [0.10, 0.80, 0.10],
            [0.12, 0.78, 0.10],
            [0.11, 0.79, 0.10],
        ])
        outcome = torch.zeros(3, 2, 4)
        outcome[:, 0, :] = torch.tensor([0.03, 0.92, 0.02, 0.03])
        outcome[:, 1, :] = torch.tensor([0.10, 0.15, 0.65, 0.10])
        return {
            "selection_probabilities": selection,
            "selection_logits": selection.log(),
            "outcome_probabilities": outcome,
        }


def test_selector_uses_set_consensus_and_harm_ceiling() -> None:
    rows = [
        {"features": torch.zeros(PAIR_FEATURE_DIM), "candidate_action": 1},
        {"features": torch.ones(PAIR_FEATURE_DIM), "candidate_action": 2},
    ]
    selected, score = _select_action_row(
        _FakeSetModel(),
        rows,
        rescue_threshold=0.70,
        harm_ceiling=0.05,
    )
    assert selected is not None
    assert int(selected["candidate_action"]) == 1
    assert score is not None
    assert score["min_selection"] >= 0.779
    assert score["max_harm"] <= 0.02


class _FakeNullModel:
    ensemble_size = 3

    def decision_set_outputs(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        selection = torch.tensor([
            [0.80, 0.10, 0.10],
            [0.75, 0.15, 0.10],
            [0.78, 0.12, 0.10],
        ])
        outcome = torch.full((3, 2, 4), 0.25)
        return {
            "selection_probabilities": selection,
            "selection_logits": selection.log(),
            "outcome_probabilities": outcome,
        }


def test_null_choice_fails_closed() -> None:
    rows = [
        {"features": torch.zeros(PAIR_FEATURE_DIM), "candidate_action": 1},
        {"features": torch.ones(PAIR_FEATURE_DIM), "candidate_action": 2},
    ]
    selected, score = _select_action_row(
        _FakeNullModel(),
        rows,
        rescue_threshold=0.35,
        harm_ceiling=0.30,
    )
    assert selected is None
    assert score is not None
    assert score["selected_index"] == 0
