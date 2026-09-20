from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM
from public_planner import GOAL_HYPOTHESIS_COUNT
from branch_sequence_decoder_core import (
    ATTRIBUTION_HIDDEN_DIM,
    BASE_PAIR_FEATURE_DIM,
    BELIEF_HIDDEN_DIM,
    BOTH_FAIL_CLASS,
    BOTH_SOLVE_CLASS,
    BRANCH_SEQUENCE_CHANNELS,
    BRANCH_SEQUENCE_HORIZON,
    GOAL_EMBEDDING_DIM,
    HARM_CLASS,
    JOINT_OUTCOME_CLASS_COUNT,
    LATENT_CONTEXT_DIM,
    NATIVE_HIDDEN_DIM,
    PAIR_FEATURE_DIM,
    PUBLIC_GOAL_FEATURE_DIM,
    RESCUE_CLASS,
    TIME_EMBEDDING_DIM,
    TRACE_HIDDEN_DIM,
    NativeR35BranchSequenceDecoderEnsemble,
    encode_pair_features,
    encode_parent_latent_context,
    encode_public_goal_features,
)
from branch_sequence_decoder_training import _select_action_row, _sequence_target


def _parent_output() -> dict[str, torch.Tensor]:
    return {
        "belief_hidden": torch.ones(1, BELIEF_HIDDEN_DIM),
        "goal_embedding": torch.ones(1, GOAL_EMBEDDING_DIM),
        "next_parent_hidden": torch.ones(1, NATIVE_HIDDEN_DIM),
        "r2_trace_hidden": torch.ones(1, TRACE_HIDDEN_DIM),
        "r3_attribution_hidden": torch.ones(1, ATTRIBUTION_HIDDEN_DIM),
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
    return encode_pair_features(
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
    model = NativeR35BranchSequenceDecoderEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        decoder_hidden_dim=64,
        horizon=6,
        time_embedding_dim=16,
    )
    assert model.goal_parameter_count() == 107799
    assert model.sequence_parameter_count() == 283716
    assert model.parameter_count() == 391515


def test_sequence_architecture_is_locked() -> None:
    assert PUBLIC_GOAL_FEATURE_DIM == 146
    assert BASE_PAIR_FEATURE_DIM == 246
    assert LATENT_CONTEXT_DIM == 528
    assert PAIR_FEATURE_DIM == 774
    assert BRANCH_SEQUENCE_HORIZON == 6
    assert BRANCH_SEQUENCE_CHANNELS == 4
    assert TIME_EMBEDDING_DIM == 16
    assert _features().shape == (774,)


def test_branch_decoder_outputs_feed_joint_head() -> None:
    model = NativeR35BranchSequenceDecoderEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        decoder_hidden_dim=16,
    )
    output = model.branch_outputs(torch.zeros(PAIR_FEATURE_DIM))
    assert output["joint_probabilities"].shape == (3, JOINT_OUTCOME_CLASS_COUNT)
    assert output["baseline_sequences"].shape == (3, 6, 4)
    assert output["candidate_sequences"].shape == (3, 6, 4)
    assert torch.allclose(
        output["joint_probabilities"].sum(dim=-1), torch.ones(3), atol=1e-6
    )


def test_sequence_target_padding_is_terminal_and_non_oracular_input() -> None:
    rows = [
        torch.tensor([0.25, 1.0, 0.0, 0.0]),
        torch.tensor([-0.10, 0.5, 1.0, 1.0]),
    ]
    target = _sequence_target(rows, True)
    assert target.shape == (6, 4)
    assert torch.allclose(target[0], rows[0])
    assert torch.allclose(target[1], rows[1])
    assert torch.allclose(target[2:], torch.tensor([[0.0,0.0,1.0,1.0]]).repeat(4,1))


def test_joint_classes_remain_identical_to_r33() -> None:
    assert (BOTH_FAIL_CLASS, RESCUE_CLASS, HARM_CLASS, BOTH_SOLVE_CLASS) == (0,1,2,3)
    assert JOINT_OUTCOME_CLASS_COUNT == 4


class _FakeSequenceModel:
    def branch_outputs(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        marker = int(features[0].item())
        if marker == 1:
            joint = torch.tensor([
                [0.02,0.91,0.02,0.05],
                [0.03,0.89,0.03,0.05],
                [0.02,0.90,0.03,0.05],
            ])
        else:
            joint = torch.tensor([
                [0.05,0.80,0.08,0.07],
                [0.05,0.81,0.08,0.06],
                [0.05,0.79,0.09,0.07],
            ])
        return {
            "joint_probabilities": joint,
            "baseline_sequences": torch.zeros(3,6,4),
            "candidate_sequences": torch.zeros(3,6,4),
        }


def test_selector_remains_direct_joint_rescue_harm_guard() -> None:
    first=torch.zeros(PAIR_FEATURE_DIM)
    second=torch.zeros(PAIR_FEATURE_DIM)
    first[0]=1.0
    second[0]=2.0
    selected,score=_select_action_row(
        _FakeSequenceModel(),
        [
            {"features":second,"candidate_action":3,"candidate_mean_mass":0.4},
            {"features":first,"candidate_action":1,"candidate_mean_mass":0.2},
        ],
        rescue_threshold=0.75,
        harm_ceiling=0.05,
    )
    assert selected is not None
    assert score is not None
    assert int(selected["candidate_action"])==1
    assert score["min_rescue"]>=0.889
    assert score["max_harm"]<=0.03
