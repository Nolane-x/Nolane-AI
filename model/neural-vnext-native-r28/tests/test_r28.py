from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM
from public_planner import GOAL_HYPOTHESIS_COUNT
from counterfactual_rescue_core import (
    NativeR28CounterfactualRescueEnsemble,
    PUBLIC_GOAL_FEATURE_DIM,
    RESCUE_FEATURE_DIM,
    encode_public_goal_features,
    encode_rescue_features,
)
from counterfactual_rescue_training import _action_mass_decision


def test_parameter_count_is_preregistered() -> None:
    model = NativeR28CounterfactualRescueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        rescue_hidden_dim=64,
    )
    assert model.goal_parameter_count() == 107799
    assert model.rescue_parameter_count() == 52035
    assert model.parameter_count() == 159834


def test_feature_shapes_are_locked() -> None:
    support = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.bool)
    support[5] = True
    support[17] = True
    public = encode_public_goal_features(
        support_mask=support,
        observation={
            "state": [1, 2, 3],
            "progress_signal": 0.25,
            "budget_remaining": 24,
            "step": 4,
        },
        previous_feedback=[0.1, 0.2, 0.0],
    )
    assert public.shape == (PUBLIC_GOAL_FEATURE_DIM,)
    r11 = torch.zeros(ACTION_FEATURE_DIM)
    candidate = torch.ones(ACTION_FEATURE_DIM)
    rescue = encode_rescue_features(
        public_goal_features=public,
        r11_action_features=r11,
        candidate_action_features=candidate,
        minimum_action_mass=0.8,
        mean_action_mass=0.85,
        mean_r11_action_mass=0.1,
        support_count=2,
    )
    assert rescue.shape == (RESCUE_FEATURE_DIM,)
    assert torch.isfinite(rescue).all()


def test_goal_probabilities_respect_public_support() -> None:
    model = NativeR28CounterfactualRescueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        rescue_hidden_dim=16,
    )
    support = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.bool)
    support[4] = True
    support[19] = True
    public = encode_public_goal_features(
        support_mask=support,
        observation={
            "state": [0, 1, 2],
            "progress_signal": 0.5,
            "budget_remaining": 20,
            "step": 3,
        },
        previous_feedback=[0.0, 0.0, 0.0],
    )
    probs = model.per_head_goal_probabilities(
        features=public,
        support_mask=support,
        temperature=1.0,
    )
    assert probs.shape == (3, GOAL_HYPOTHESIS_COUNT)
    assert float(probs[:, ~support].abs().sum().item()) == 0.0
    assert torch.allclose(probs.sum(dim=-1), torch.ones(3), atol=1e-6)


def test_action_mass_requires_consensus() -> None:
    probs = torch.zeros(3, GOAL_HYPOTHESIS_COUNT)
    probs[:, 1] = 0.7
    probs[:, 2] = 0.3
    action, minimum_mass, masses = _action_mass_decision(
        per_head_goal_probabilities=probs,
        goal_actions={1: 2, 2: 3},
        action_count=5,
    )
    assert action == 2
    assert abs(minimum_mass - 0.7) < 1e-6
    assert masses.shape == (3, 5)


def test_rescue_probabilities_are_bounded() -> None:
    model = NativeR28CounterfactualRescueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        rescue_hidden_dim=16,
    )
    probs = model.rescue_probabilities(torch.zeros(RESCUE_FEATURE_DIM))
    assert probs.shape == (3,)
    assert bool(torch.all((probs >= 0.0) & (probs <= 1.0)).item())
