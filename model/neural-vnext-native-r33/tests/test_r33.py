from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM
from public_planner import GOAL_HYPOTHESIS_COUNT
from joint_terminal_outcome_core import (
    ATTRIBUTION_HIDDEN_DIM,
    BASE_ACTION_RESCUE_FEATURE_DIM,
    BELIEF_HIDDEN_DIM,
    BOTH_FAIL_CLASS,
    BOTH_SOLVE_CLASS,
    GOAL_EMBEDDING_DIM,
    HARM_CLASS,
    JOINT_OUTCOME_CLASS_COUNT,
    LATENT_ACTION_RESCUE_FEATURE_DIM,
    LATENT_CONTEXT_DIM,
    NATIVE_HIDDEN_DIM,
    PUBLIC_GOAL_FEATURE_DIM,
    RESCUE_CLASS,
    TRACE_HIDDEN_DIM,
    NativeR33JointTerminalOutcomeEnsemble,
    encode_latent_action_rescue_features,
    encode_parent_latent_context,
    encode_public_goal_features,
)
from joint_terminal_outcome_training import _action_masses, _select_action_row


def _parent_output(marker: float = 0.0) -> dict[str, torch.Tensor]:
    return {
        "belief_hidden": torch.full((1, BELIEF_HIDDEN_DIM), marker + 1.0),
        "goal_embedding": torch.full((1, GOAL_EMBEDDING_DIM), marker + 2.0),
        "next_parent_hidden": torch.full((1, NATIVE_HIDDEN_DIM), marker + 3.0),
        "r2_trace_hidden": torch.full((1, TRACE_HIDDEN_DIM), marker + 4.0),
        "r3_attribution_hidden": torch.full((1, ATTRIBUTION_HIDDEN_DIM), marker + 5.0),
        "action_logits": torch.zeros(1, 4),
    }


def _features() -> torch.Tensor:
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
    return encode_latent_action_rescue_features(
        public_goal_features=public,
        latent_context=encode_parent_latent_context(_parent_output()),
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


def test_parameter_count_is_preregistered() -> None:
    model = NativeR33JointTerminalOutcomeEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        outcome_hidden_dim=64,
    )
    assert model.goal_parameter_count() == 107799
    assert model.outcome_parameter_count() == 162828
    assert model.parameter_count() == 270627


def test_joint_classes_preserve_all_four_terminal_realities() -> None:
    assert JOINT_OUTCOME_CLASS_COUNT == 4
    assert (BOTH_FAIL_CLASS, RESCUE_CLASS, HARM_CLASS, BOTH_SOLVE_CLASS) == (0, 1, 2, 3)


def test_pair_representation_is_identical_width_to_r31() -> None:
    features = _features()
    assert PUBLIC_GOAL_FEATURE_DIM == 146
    assert BASE_ACTION_RESCUE_FEATURE_DIM == 246
    assert LATENT_CONTEXT_DIM == 528
    assert LATENT_ACTION_RESCUE_FEATURE_DIM == 774
    assert features.shape == (774,)
    assert torch.isfinite(features).all()


def test_joint_probabilities_are_four_class_distributions() -> None:
    model = NativeR33JointTerminalOutcomeEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        outcome_hidden_dim=16,
    )
    probs = model.joint_outcome_probabilities(
        torch.zeros(LATENT_ACTION_RESCUE_FEATURE_DIM)
    )
    assert probs.shape == (3, 4)
    assert torch.allclose(probs.sum(dim=-1), torch.ones(3), atol=1e-6)


def test_goal_probabilities_still_respect_public_support() -> None:
    model = NativeR33JointTerminalOutcomeEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        outcome_hidden_dim=16,
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
    assert float(probs[:, ~support].abs().sum().item()) == 0.0
    assert torch.allclose(probs.sum(dim=-1), torch.ones(3), atol=1e-6)


def test_action_masses_keep_head_disagreement() -> None:
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
    assert int(masses[0].argmax().item()) == 2
    assert int(masses[1].argmax().item()) == 3


class _FakeJointModel:
    def joint_outcome_probabilities(self, features: torch.Tensor) -> torch.Tensor:
        marker = int(features[0].item())
        if marker == 1:
            return torch.tensor([
                [0.02, 0.91, 0.02, 0.05],
                [0.03, 0.89, 0.03, 0.05],
                [0.02, 0.90, 0.03, 0.05],
            ])
        return torch.tensor([
            [0.05, 0.80, 0.08, 0.07],
            [0.05, 0.81, 0.08, 0.06],
            [0.05, 0.79, 0.09, 0.07],
        ])


def test_selector_uses_direct_joint_rescue_and_harm_probabilities() -> None:
    first = torch.zeros(LATENT_ACTION_RESCUE_FEATURE_DIM)
    second = torch.zeros(LATENT_ACTION_RESCUE_FEATURE_DIM)
    first[0] = 1.0
    second[0] = 2.0
    selected, score = _select_action_row(
        _FakeJointModel(),
        [
            {"features": second, "candidate_action": 3, "candidate_mean_mass": 0.4},
            {"features": first, "candidate_action": 1, "candidate_mean_mass": 0.2},
        ],
        rescue_threshold=0.75,
        harm_ceiling=0.05,
    )
    assert selected is not None
    assert score is not None
    assert int(selected["candidate_action"]) == 1
    assert score["min_rescue"] >= 0.89
    assert score["max_harm"] <= 0.03
