from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM
from public_planner import GOAL_HYPOTHESIS_COUNT
from trajectory_mechanism_core import (
    ATTRIBUTION_HIDDEN_DIM,
    BASE_PAIR_FEATURE_DIM,
    BELIEF_HIDDEN_DIM,
    BOTH_FAIL_CLASS,
    BOTH_SOLVE_CLASS,
    GOAL_EMBEDDING_DIM,
    HARM_CLASS,
    JOINT_OUTCOME_CLASS_COUNT,
    LATENT_CONTEXT_DIM,
    MECHANISM_BUDGET_EXHAUSTED,
    MECHANISM_REJECTED_SUBMIT,
    MECHANISM_SOLVED,
    NATIVE_HIDDEN_DIM,
    PAIR_FEATURE_DIM,
    PUBLIC_GOAL_FEATURE_DIM,
    RESCUE_CLASS,
    TERMINAL_MECHANISM_CLASS_COUNT,
    TRACE_HIDDEN_DIM,
    TRAJECTORY_REGRESSION_DIM,
    NativeR34TrajectoryMechanismEnsemble,
    encode_pair_features,
    encode_parent_latent_context,
    encode_public_goal_features,
)
from trajectory_mechanism_training import (
    _select_action_row,
    _terminal_mechanism,
    _trajectory_target,
)


def _parent_output(marker: float = 0.0) -> dict[str, torch.Tensor]:
    return {
        "belief_hidden": torch.full((1, BELIEF_HIDDEN_DIM), marker + 1.0),
        "goal_embedding": torch.full((1, GOAL_EMBEDDING_DIM), marker + 2.0),
        "next_parent_hidden": torch.full((1, NATIVE_HIDDEN_DIM), marker + 3.0),
        "r2_trace_hidden": torch.full((1, TRACE_HIDDEN_DIM), marker + 4.0),
        "r3_attribution_hidden": torch.full((1, ATTRIBUTION_HIDDEN_DIM), marker + 5.0),
        "action_logits": torch.zeros(1, 4),
    }


def _pair_features() -> torch.Tensor:
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
    model = NativeR34TrajectoryMechanismEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        mechanism_hidden_dim=64,
    )
    assert model.goal_parameter_count() == 107799
    assert model.mechanism_parameter_count() == 165558
    assert model.parameter_count() == 273357


def test_pair_representation_stays_identical_width_to_r33() -> None:
    features = _pair_features()
    assert PUBLIC_GOAL_FEATURE_DIM == 146
    assert BASE_PAIR_FEATURE_DIM == 246
    assert LATENT_CONTEXT_DIM == 528
    assert PAIR_FEATURE_DIM == 774
    assert features.shape == (774,)
    assert torch.isfinite(features).all()


def test_output_surfaces_are_structured_but_inference_input_is_still_774() -> None:
    model = NativeR34TrajectoryMechanismEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        mechanism_hidden_dim=16,
    )
    output = model.mechanism_outputs(torch.zeros(PAIR_FEATURE_DIM))
    assert output["joint_probabilities"].shape == (3, JOINT_OUTCOME_CLASS_COUNT)
    assert output["baseline_mechanism_probabilities"].shape == (
        3,
        TERMINAL_MECHANISM_CLASS_COUNT,
    )
    assert output["candidate_mechanism_probabilities"].shape == (
        3,
        TERMINAL_MECHANISM_CLASS_COUNT,
    )
    assert output["trajectory"].shape == (3, TRAJECTORY_REGRESSION_DIM)
    assert torch.allclose(
        output["joint_probabilities"].sum(dim=-1), torch.ones(3), atol=1e-6
    )
    assert torch.allclose(
        output["baseline_mechanism_probabilities"].sum(dim=-1),
        torch.ones(3),
        atol=1e-6,
    )
    assert torch.allclose(
        output["candidate_mechanism_probabilities"].sum(dim=-1),
        torch.ones(3),
        atol=1e-6,
    )


def test_joint_and_terminal_classes_are_locked() -> None:
    assert (BOTH_FAIL_CLASS, RESCUE_CLASS, HARM_CLASS, BOTH_SOLVE_CLASS) == (0, 1, 2, 3)
    assert JOINT_OUTCOME_CLASS_COUNT == 4
    assert (
        MECHANISM_SOLVED,
        MECHANISM_REJECTED_SUBMIT,
        MECHANISM_BUDGET_EXHAUSTED,
    ) == (0, 1, 2)
    assert TERMINAL_MECHANISM_CLASS_COUNT == 3
    assert TRAJECTORY_REGRESSION_DIM == 8


class _TerminalTask:
    def __init__(self, solved: bool, event: str) -> None:
        self.solved = solved
        self._event = event

    def observe(self) -> dict[str, str]:
        return {"last_event": self._event}


def test_terminal_mechanism_uses_public_terminal_event_only() -> None:
    assert _terminal_mechanism(_TerminalTask(True, "accepted")) == MECHANISM_SOLVED
    assert (
        _terminal_mechanism(_TerminalTask(False, "submission rejected"))
        == MECHANISM_REJECTED_SUBMIT
    )
    assert (
        _terminal_mechanism(_TerminalTask(False, "action budget exhausted"))
        == MECHANISM_BUDGET_EXHAUSTED
    )


def test_trajectory_target_has_exact_eight_training_only_values() -> None:
    baseline = {
        "branch_steps": 16,
        "progress_sum": 4.0,
        "positive_fraction": 0.5,
        "information_mean": 0.25,
    }
    candidate = {
        "branch_steps": 8,
        "progress_sum": -2.0,
        "positive_fraction": 0.75,
        "information_mean": 0.5,
    }
    target = _trajectory_target(baseline, candidate)
    assert target.shape == (8,)
    assert torch.allclose(
        target,
        torch.tensor([0.5, 0.25, 0.5, -0.25, 0.5, 0.75, 0.25, 0.5]),
        atol=1e-6,
    )


class _FakeMechanismModel:
    def mechanism_outputs(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        marker = int(features[0].item())
        if marker == 1:
            joint = torch.tensor([
                [0.02, 0.91, 0.02, 0.05],
                [0.03, 0.89, 0.03, 0.05],
                [0.02, 0.90, 0.03, 0.05],
            ])
        else:
            joint = torch.tensor([
                [0.05, 0.80, 0.08, 0.07],
                [0.05, 0.81, 0.08, 0.06],
                [0.05, 0.79, 0.09, 0.07],
            ])
        baseline = torch.tensor([[0.1, 0.6, 0.3]]).repeat(3, 1)
        candidate = torch.tensor([[0.8, 0.1, 0.1]]).repeat(3, 1)
        return {
            "joint_probabilities": joint,
            "baseline_mechanism_probabilities": baseline,
            "candidate_mechanism_probabilities": candidate,
            "trajectory": torch.zeros(3, 8),
        }


def test_selector_remains_r33_direct_joint_rescue_harm_policy() -> None:
    first = torch.zeros(PAIR_FEATURE_DIM)
    second = torch.zeros(PAIR_FEATURE_DIM)
    first[0] = 1.0
    second[0] = 2.0
    selected, score = _select_action_row(
        _FakeMechanismModel(),
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
    assert score["min_rescue"] >= 0.889
    assert score["max_harm"] <= 0.03
