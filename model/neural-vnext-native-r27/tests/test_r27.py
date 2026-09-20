from __future__ import annotations

import torch

from public_planner import GOAL_HYPOTHESIS_COUNT
from action_mass_core import (
    NativeR27GoalBeliefEnsemble,
    PUBLIC_GOAL_FEATURE_DIM,
    encode_public_goal_features,
)
from action_mass_training import _action_mass_decision


def test_parameter_count_is_preregistered() -> None:
    model = NativeR27GoalBeliefEnsemble(ensemble_size=3, hidden_dim=96)
    assert model.parameter_count() == 107799


def test_public_goal_features_have_locked_shape() -> None:
    support = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.bool)
    support[5] = True
    support[17] = True
    features = encode_public_goal_features(
        support_mask=support,
        observation={
            "state": [1, 2, 3],
            "progress_signal": 0.25,
            "budget_remaining": 24,
            "step": 4,
        },
        previous_feedback=[0.1, 0.2, 0.0],
    )
    assert features.shape == (PUBLIC_GOAL_FEATURE_DIM,)
    assert torch.isfinite(features).all()


def test_probabilities_are_hard_masked() -> None:
    model = NativeR27GoalBeliefEnsemble(ensemble_size=3, hidden_dim=16)
    support = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.bool)
    support[4] = True
    support[19] = True
    features = encode_public_goal_features(
        support_mask=support,
        observation={
            "state": [0, 1, 2],
            "progress_signal": 0.5,
            "budget_remaining": 20,
            "step": 3,
        },
        previous_feedback=[0.0, 0.0, 0.0],
    )
    probs = model.per_head_probabilities(
        features=features,
        support_mask=support,
        temperature=1.0,
    )
    assert probs.shape == (3, GOAL_HYPOTHESIS_COUNT)
    assert float(probs[:, ~support].abs().sum().item()) == 0.0
    assert torch.allclose(probs.sum(dim=-1), torch.ones(3), atol=1e-6)


def test_action_mass_requires_head_consensus() -> None:
    probs = torch.zeros(3, GOAL_HYPOTHESIS_COUNT)
    probs[:, 1] = 0.6
    probs[:, 2] = 0.4
    action, minimum_mass, masses = _action_mass_decision(
        per_head_goal_probabilities=probs,
        goal_actions={1: 2, 2: 3},
        action_count=5,
    )
    assert action == 2
    assert abs(minimum_mass - 0.6) < 1e-6
    assert masses.shape == (3, 5)

    disagree = probs.clone()
    disagree[2, 1] = 0.2
    disagree[2, 2] = 0.8
    action2, _, _ = _action_mass_decision(
        per_head_goal_probabilities=disagree,
        goal_actions={1: 2, 2: 3},
        action_count=5,
    )
    assert action2 is None
