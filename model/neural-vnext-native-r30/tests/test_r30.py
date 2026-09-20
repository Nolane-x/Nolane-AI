from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM
from public_planner import GOAL_HYPOTHESIS_COUNT
from action_conditioned_rescue_core import (
    ACTION_RESCUE_FEATURE_DIM,
    PUBLIC_GOAL_FEATURE_DIM,
    RESCUE_CLASS_COUNT,
    NativeR30ActionConditionedRescueEnsemble,
    encode_action_rescue_features,
    encode_public_goal_features,
)
from action_conditioned_rescue_training import _action_masses, _select_action_row


def test_parameter_count_is_preregistered() -> None:
    model = NativeR30ActionConditionedRescueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        rescue_hidden_dim=64,
    )
    assert model.goal_parameter_count() == 107799
    assert model.rescue_parameter_count() == 61257
    assert model.parameter_count() == 169056


def test_uncertified_action_feature_is_retained() -> None:
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
    features = encode_action_rescue_features(
        public_goal_features=public,
        r11_action_features=torch.zeros(ACTION_FEATURE_DIM),
        candidate_action_features=torch.ones(ACTION_FEATURE_DIM),
        r11_next_state=None,
        candidate_next_state=None,
        support_count=2,
        candidate_min_mass=0.05,
        candidate_mean_mass=0.1,
        r11_mean_mass=0.7,
        mass_margin=-0.6,
        candidate_mass_spread=0.08,
        r11_mass_spread=0.1,
        parent_logit_margin=-0.3,
        r11_certified=False,
        candidate_certified=False,
        r11_rule_count=0,
        candidate_rule_count=0,
        current_expected_distance=5.0,
        r11_expected_distance=5.0,
        candidate_expected_distance=5.0,
        distance_advantage=0.0,
        rule_count_advantage=0.0,
        candidate_seen_in_context=0,
        r11_seen_in_context=1,
    )
    assert public.shape == (PUBLIC_GOAL_FEATURE_DIM,)
    assert features.shape == (ACTION_RESCUE_FEATURE_DIM,)
    assert ACTION_RESCUE_FEATURE_DIM == 246
    assert torch.isfinite(features).all()


def test_goal_probabilities_respect_public_support() -> None:
    model = NativeR30ActionConditionedRescueEnsemble(
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


def test_rescue_probabilities_are_three_class_distributions() -> None:
    model = NativeR30ActionConditionedRescueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        rescue_hidden_dim=16,
    )
    probs = model.rescue_class_probabilities(torch.zeros(ACTION_RESCUE_FEATURE_DIM))
    assert probs.shape == (3, RESCUE_CLASS_COUNT)
    assert RESCUE_CLASS_COUNT == 3
    assert torch.allclose(probs.sum(dim=-1), torch.ones(3), atol=1e-6)


def test_action_masses_keep_disagreement_instead_of_rejecting_candidate_generation() -> None:
    probs = torch.zeros(3, GOAL_HYPOTHESIS_COUNT)
    probs[0, 1] = 0.8
    probs[0, 2] = 0.2
    probs[1, 1] = 0.2
    probs[1, 2] = 0.8
    probs[2, 1] = 0.5
    probs[2, 2] = 0.5
    masses = _action_masses(
        per_head_goal_probabilities=probs,
        goal_actions={1: 2, 2: 3},
        action_count=5,
    )
    assert masses.shape == (3, 5)
    assert int(masses[0].argmax().item()) == 2
    assert int(masses[1].argmax().item()) == 3
    assert float(masses[:, 2].sum().item()) > 0.0
    assert float(masses[:, 3].sum().item()) > 0.0


class _FakeRescueModel:
    def rescue_class_probabilities(self, features: torch.Tensor) -> torch.Tensor:
        marker = int(features[0].item())
        if marker == 1:
            return torch.tensor(
                [[0.05, 0.90, 0.05], [0.05, 0.88, 0.07], [0.06, 0.89, 0.05]]
            )
        return torch.tensor(
            [[0.10, 0.80, 0.10], [0.08, 0.82, 0.10], [0.10, 0.81, 0.09]]
        )


def test_selector_compares_all_eligible_alternative_actions() -> None:
    first = torch.zeros(ACTION_RESCUE_FEATURE_DIM)
    second = torch.zeros(ACTION_RESCUE_FEATURE_DIM)
    first[0] = 1.0
    second[0] = 2.0
    selected, score = _select_action_row(
        _FakeRescueModel(),
        [
            {"features": second, "candidate_action": 3, "candidate_mean_mass": 0.4},
            {"features": first, "candidate_action": 1, "candidate_mean_mass": 0.2},
        ],
        rescue_threshold=0.75,
        harm_ceiling=0.10,
    )
    assert selected is not None
    assert score is not None
    assert int(selected["candidate_action"]) == 1
    assert score["min_rescue"] >= 0.879
