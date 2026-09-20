from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM
from public_planner import GOAL_HYPOTHESIS_COUNT
from latent_state_rescue_core import (
    ATTRIBUTION_HIDDEN_DIM,
    BASE_ACTION_RESCUE_FEATURE_DIM,
    BELIEF_HIDDEN_DIM,
    GOAL_EMBEDDING_DIM,
    LATENT_ACTION_RESCUE_FEATURE_DIM,
    LATENT_CONTEXT_DIM,
    NATIVE_HIDDEN_DIM,
    PUBLIC_GOAL_FEATURE_DIM,
    RESCUE_CLASS_COUNT,
    TRACE_HIDDEN_DIM,
    NativeR31LatentStateRescueEnsemble,
    encode_latent_action_rescue_features,
    encode_parent_latent_context,
    encode_public_goal_features,
)
from latent_state_rescue_training import _action_masses, _select_action_row


def _parent_output(marker: float = 0.0) -> dict[str, torch.Tensor]:
    return {
        "belief_hidden": torch.full((1, BELIEF_HIDDEN_DIM), marker + 1.0),
        "goal_embedding": torch.full((1, GOAL_EMBEDDING_DIM), marker + 2.0),
        "next_parent_hidden": torch.full((1, NATIVE_HIDDEN_DIM), marker + 3.0),
        "r2_trace_hidden": torch.full((1, TRACE_HIDDEN_DIM), marker + 4.0),
        "r3_attribution_hidden": torch.full((1, ATTRIBUTION_HIDDEN_DIM), marker + 5.0),
        "action_logits": torch.zeros(1, 4),
    }


def _public_features() -> torch.Tensor:
    support = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.bool)
    support[5] = True
    support[17] = True
    return encode_public_goal_features(
        support_mask=support,
        observation={
            "state": [1, 2, 3],
            "progress_signal": 0.25,
            "budget_remaining": 24,
            "step": 4,
        },
        previous_feedback=[0.1, 0.2, 0.0],
    )


def _rescue_features(latent: torch.Tensor) -> torch.Tensor:
    return encode_latent_action_rescue_features(
        public_goal_features=_public_features(),
        latent_context=latent,
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
    model = NativeR31LatentStateRescueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        rescue_hidden_dim=64,
    )
    assert model.goal_parameter_count() == 107799
    assert model.rescue_parameter_count() == 162633
    assert model.parameter_count() == 270432


def test_latent_context_is_exact_accepted_r4_width() -> None:
    latent = encode_parent_latent_context(_parent_output())
    assert LATENT_CONTEXT_DIM == 528
    assert latent.shape == (528,)
    assert torch.all(latent[:BELIEF_HIDDEN_DIM] == 1.0)
    assert torch.all(
        latent[BELIEF_HIDDEN_DIM : BELIEF_HIDDEN_DIM + GOAL_EMBEDDING_DIM] == 2.0
    )
    assert torch.isfinite(latent).all()


def test_latent_action_feature_retains_uncertified_candidates() -> None:
    latent = encode_parent_latent_context(_parent_output())
    features = _rescue_features(latent)
    assert PUBLIC_GOAL_FEATURE_DIM == 146
    assert BASE_ACTION_RESCUE_FEATURE_DIM == 246
    assert LATENT_ACTION_RESCUE_FEATURE_DIM == 774
    assert features.shape == (774,)
    assert torch.isfinite(features).all()


def test_latent_state_is_the_only_new_information_surface() -> None:
    first = _rescue_features(encode_parent_latent_context(_parent_output(0.0)))
    second = _rescue_features(encode_parent_latent_context(_parent_output(10.0)))
    assert torch.equal(first[:BASE_ACTION_RESCUE_FEATURE_DIM], second[:BASE_ACTION_RESCUE_FEATURE_DIM])
    assert not torch.equal(first[BASE_ACTION_RESCUE_FEATURE_DIM:], second[BASE_ACTION_RESCUE_FEATURE_DIM:])


def test_goal_probabilities_respect_public_support() -> None:
    model = NativeR31LatentStateRescueEnsemble(
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
    model = NativeR31LatentStateRescueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        rescue_hidden_dim=16,
    )
    probs = model.rescue_class_probabilities(
        torch.zeros(LATENT_ACTION_RESCUE_FEATURE_DIM)
    )
    assert probs.shape == (3, RESCUE_CLASS_COUNT)
    assert RESCUE_CLASS_COUNT == 3
    assert torch.allclose(probs.sum(dim=-1), torch.ones(3), atol=1e-6)


def test_action_masses_keep_disagreement() -> None:
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


def test_selector_still_compares_all_alternatives() -> None:
    first = torch.zeros(LATENT_ACTION_RESCUE_FEATURE_DIM)
    second = torch.zeros(LATENT_ACTION_RESCUE_FEATURE_DIM)
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
