from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM
from public_planner import GOAL_HYPOTHESIS_COUNT
from factorized_terminal_value_core import (
    ACTION_VALUE_FEATURE_DIM,
    ATTRIBUTION_HIDDEN_DIM,
    BELIEF_HIDDEN_DIM,
    GOAL_EMBEDDING_DIM,
    LATENT_CONTEXT_DIM,
    NATIVE_HIDDEN_DIM,
    PUBLIC_GOAL_FEATURE_DIM,
    TRACE_HIDDEN_DIM,
    NativeR32FactorizedTerminalValueEnsemble,
    encode_action_value_features,
    encode_parent_latent_context,
    encode_public_goal_features,
)
from factorized_terminal_value_training import (
    _action_masses,
    _select_action_row,
    build_terminal_value_examples,
    pair_outcome_counts,
)


def _parent_output() -> dict[str, torch.Tensor]:
    return {
        "belief_hidden": torch.ones(1, BELIEF_HIDDEN_DIM),
        "goal_embedding": torch.ones(1, GOAL_EMBEDDING_DIM) * 2,
        "next_parent_hidden": torch.ones(1, NATIVE_HIDDEN_DIM) * 3,
        "r2_trace_hidden": torch.ones(1, TRACE_HIDDEN_DIM) * 4,
        "r3_attribution_hidden": torch.ones(1, ATTRIBUTION_HIDDEN_DIM) * 5,
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


def test_parameter_count_is_preregistered() -> None:
    model = NativeR32FactorizedTerminalValueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        value_hidden_dim=64,
    )
    assert model.goal_parameter_count() == 107799
    assert model.value_parameter_count() == 153219
    assert model.parameter_count() == 261018


def test_action_value_feature_shape_and_uncertified_retention() -> None:
    latent = encode_parent_latent_context(_parent_output())
    features = encode_action_value_features(
        public_goal_features=_public_features(),
        latent_context=latent,
        action_features=torch.zeros(ACTION_FEATURE_DIM),
        action_next_state=None,
        support_count=2,
        action_min_mass=0.1,
        action_mean_mass=0.2,
        action_max_mass=0.3,
        action_mass_spread=0.2,
        parent_logit_margin_vs_r11=-0.2,
        action_certified=False,
        action_rule_count=0,
        current_expected_distance=5.0,
        action_expected_distance=5.0,
        expected_distance_improvement=0.0,
        action_seen_in_context=0,
        is_r11_action=False,
    )
    assert PUBLIC_GOAL_FEATURE_DIM == 146
    assert LATENT_CONTEXT_DIM == 528
    assert ACTION_VALUE_FEATURE_DIM == 727
    assert features.shape == (727,)
    assert torch.isfinite(features).all()


def test_terminal_value_head_outputs_ensemble_probabilities() -> None:
    model = NativeR32FactorizedTerminalValueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        value_hidden_dim=16,
    )
    probs = model.solve_probabilities(torch.zeros(ACTION_VALUE_FEATURE_DIM))
    assert probs.shape == (3,)
    assert torch.all(probs >= 0.0)
    assert torch.all(probs <= 1.0)


def test_goal_probabilities_respect_public_support() -> None:
    model = NativeR32FactorizedTerminalValueEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        value_hidden_dim=16,
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


def test_factorized_targets_do_not_conflate_both_solve_and_both_fail() -> None:
    feature = torch.zeros(ACTION_VALUE_FEATURE_DIM)
    rows = [
        {
            "r11_features": feature,
            "candidate_features": feature + 1,
            "baseline_solved": 1,
            "candidate_solved": 1,
            "rescue": 0,
            "harm": 0,
            "task_index": 1,
            "step": 2,
        },
        {
            "r11_features": feature + 2,
            "candidate_features": feature + 3,
            "baseline_solved": 0,
            "candidate_solved": 0,
            "rescue": 0,
            "harm": 0,
            "task_index": 2,
            "step": 3,
        },
    ]
    counts = pair_outcome_counts(rows)
    examples = build_terminal_value_examples(rows)
    labels = [int(example["solved"]) for example in examples]
    assert counts == {"both_fail": 1, "rescue": 0, "harm": 0, "both_solve": 1}
    assert labels.count(1) == 2
    assert labels.count(0) == 2


def test_action_masses_keep_goal_disagreement() -> None:
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


class _FakeValueModel:
    def solve_probabilities(self, features: torch.Tensor) -> torch.Tensor:
        marker = int(features[0].item())
        if marker == 1:
            return torch.tensor([0.10, 0.10, 0.10])
        if marker == 2:
            return torch.tensor([0.90, 0.90, 0.90])
        return torch.tensor([0.20, 0.20, 0.20])


def test_selector_derives_rescue_and_harm_from_terminal_values() -> None:
    r11 = torch.zeros(ACTION_VALUE_FEATURE_DIM)
    r11[0] = 1.0
    good = torch.zeros(ACTION_VALUE_FEATURE_DIM)
    good[0] = 2.0
    weak = torch.zeros(ACTION_VALUE_FEATURE_DIM)
    weak[0] = 3.0

    selected, score = _select_action_row(
        _FakeValueModel(),
        [
            {
                "r11_features": r11,
                "candidate_features": weak,
                "candidate_action": 3,
                "candidate_mean_mass": 0.4,
            },
            {
                "r11_features": r11,
                "candidate_features": good,
                "candidate_action": 1,
                "candidate_mean_mass": 0.2,
            },
        ],
        rescue_threshold=0.70,
        harm_ceiling=0.05,
    )
    assert selected is not None
    assert score is not None
    assert int(selected["candidate_action"]) == 1
    assert score["min_rescue"] >= 0.80
    assert score["max_harm"] <= 0.02
    assert score["min_advantage"] > 0.0
