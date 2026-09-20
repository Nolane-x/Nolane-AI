from __future__ import annotations

import copy
from pathlib import Path

import pytest
import torch

from native_core import (
    ACTION_FEATURE_DIM,
    GLOBAL_FEATURE_DIM,
    TARGET_VISIBLE_FEATURE_INDEX,
    NativeRecurrentPolicy,
    state_dict_sha256,
)
from successor_core import TRACE_TOKEN_DIM, NativeR2TransitionPolicy
from attributed_core import (
    ATTRIBUTION_TOKEN_DIM,
    NativeR3AttributedBeliefPolicy,
)
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from threshold_core import (
    GOAL_HYPOTHESIS_COUNT,
    GOAL_TABLE,
    NativeR7ThresholdConsistencyPolicy,
    PublicGoalConsistencyBelief,
)
from threshold_training import (
    load_r7_checkpoint,
    save_r7_checkpoint,
)


def _r4_parent() -> NativeR4LatentGoalBeliefPolicy:
    torch.manual_seed(17)
    native = NativeRecurrentPolicy(
        global_dim=GLOBAL_FEATURE_DIM,
        action_dim=ACTION_FEATURE_DIM,
        hidden_dim=32,
        attention_heads=4,
    )
    r2 = NativeR2TransitionPolicy(
        native,
        trace_token_dim=TRACE_TOKEN_DIM,
        trace_hidden_dim=24,
        trace_length=8,
    )
    r3 = NativeR3AttributedBeliefPolicy(
        r2,
        attribution_hidden_dim=24,
        attribution_length=12,
    )
    return NativeR4LatentGoalBeliefPolicy(
        r3,
        belief_hidden_dim=20,
        goal_embedding_dim=12,
    )


def _inputs(actions: int = 4) -> tuple[torch.Tensor, ...]:
    return (
        torch.zeros(1, GLOBAL_FEATURE_DIM),
        torch.randn(1, actions, ACTION_FEATURE_DIM),
        torch.ones(1, actions, dtype=torch.bool),
        torch.zeros(1, 32),
        torch.zeros(1, 8, TRACE_TOKEN_DIM),
        torch.zeros(1, 8, dtype=torch.bool),
        torch.zeros(1, 12, ATTRIBUTION_TOKEN_DIM),
        torch.zeros(1, 12, dtype=torch.bool),
    )


def test_public_consistency_uses_only_public_state_and_progress() -> None:
    belief = PublicGoalConsistencyBelief()
    belief.update({"state": [0, 0, 0], "progress_signal": 0.75})
    first_support = belief.support_size()
    assert 1 < first_support < GOAL_HYPOTHESIS_COUNT
    belief.update({"state": [1, 0, 0], "progress_signal": 0.833333})
    assert 0 < belief.support_size() <= first_support
    posterior = belief.encode()
    true_row = int(
        ((GOAL_TABLE == torch.tensor([2, 1, 0])).all(dim=1))
        .nonzero()[0]
        .item()
    )
    assert float(posterior[true_row]) > 0.0
    assert torch.isclose(posterior.sum(), torch.tensor(1.0))


def test_r7_initialization_is_exactly_r4_equivalent() -> None:
    parent = _r4_parent()
    model = NativeR7ThresholdConsistencyPolicy(
        copy.deepcopy(parent),
        consistency_embedding_dim=16,
        residual_hidden_dim=24,
    )
    inputs = _inputs()
    posterior = torch.full(
        (1, GOAL_HYPOTHESIS_COUNT),
        1.0 / GOAL_HYPOTHESIS_COUNT,
    )
    with torch.no_grad():
        expected = parent.forward_step(*inputs)["action_logits"]
        actual = model.forward_step(*inputs, posterior)["action_logits"]
    assert torch.equal(actual, expected)


def test_visible_target_hard_gate_blocks_r7_residual() -> None:
    parent = _r4_parent()
    model = NativeR7ThresholdConsistencyPolicy(
        copy.deepcopy(parent),
        consistency_embedding_dim=16,
        residual_hidden_dim=24,
    )
    with torch.no_grad():
        model.hidden_target_consistency_score[-1].bias.fill_(9.0)
    inputs = list(_inputs())
    inputs[0][:, TARGET_VISIBLE_FEATURE_INDEX] = 1.0
    posterior = torch.full(
        (1, GOAL_HYPOTHESIS_COUNT),
        1.0 / GOAL_HYPOTHESIS_COUNT,
    )
    with torch.no_grad():
        expected = parent.forward_step(*inputs)["action_logits"]
        output = model.forward_step(*inputs, posterior)
    assert torch.equal(output["action_logits"], expected)
    assert torch.equal(
        output["consistency_residual_logits"],
        torch.zeros_like(output["consistency_residual_logits"]),
    )


def test_parent_frozen_and_only_r7_parameters_trainable() -> None:
    model = NativeR7ThresholdConsistencyPolicy(
        _r4_parent(),
        consistency_embedding_dim=16,
        residual_hidden_dim=24,
    )
    model.set_training_scope()
    assert all(not p.requires_grad for p in model.parent.parameters())
    assert model.successor_parameters()
    assert all(p.requires_grad for p in model.successor_parameters())


def test_invalid_consistency_posterior_is_rejected() -> None:
    model = NativeR7ThresholdConsistencyPolicy(
        _r4_parent(),
        consistency_embedding_dim=16,
        residual_hidden_dim=24,
    )
    with pytest.raises(ValueError, match="positive mass"):
        model.forward_step(
            *_inputs(),
            torch.zeros(1, GOAL_HYPOTHESIS_COUNT),
        )


def test_r7_checkpoint_roundtrip_binds_frozen_r4_parent(
    tmp_path: Path,
) -> None:
    model = NativeR7ThresholdConsistencyPolicy(
        _r4_parent(),
        consistency_embedding_dim=16,
        residual_hidden_dim=24,
    )
    parent_state = state_dict_sha256(model.parent.state_dict())
    path = tmp_path / "r7.pt"
    metadata = save_r7_checkpoint(
        model,
        path,
        parent_checkpoint_sha256="parent-file",
        parent_state_dict_sha256=parent_state,
        predev_lock_sha256="predev",
        training_summary={
            "selected_candidate": "fixture",
            "fresh_opened": False,
        },
    )
    restored, observed = load_r7_checkpoint(path)
    assert observed["checkpoint_sha256"] == metadata["checkpoint_sha256"]
    assert observed["state_dict_sha256"] == metadata["state_dict_sha256"]
    assert observed["parent_state_dict_sha256"] == parent_state
    assert state_dict_sha256(restored.parent.state_dict()) == parent_state
    assert (
        restored.successor_parameter_count()
        == model.successor_parameter_count()
    )


def test_uniform_public_posterior_calibration_gate_falls_back_to_r4() -> None:
    parent = _r4_parent()
    model = NativeR7ThresholdConsistencyPolicy(
        copy.deepcopy(parent),
        consistency_embedding_dim=16,
        residual_hidden_dim=24,
        max_support=3,
        confidence_power=1.0,
    )
    with torch.no_grad():
        model.hidden_target_consistency_score[-1].bias.fill_(9.0)
    inputs = _inputs()
    posterior = torch.full(
        (1, GOAL_HYPOTHESIS_COUNT),
        1.0 / GOAL_HYPOTHESIS_COUNT,
    )
    with torch.no_grad():
        expected = parent.forward_step(*inputs)["action_logits"]
        output = model.forward_step(*inputs, posterior)
    assert torch.equal(output["action_logits"], expected)
    assert torch.equal(
        output["evidence_gate"],
        torch.zeros_like(output["evidence_gate"]),
    )


def test_calibration_gate_is_bounded() -> None:
    model = NativeR7ThresholdConsistencyPolicy(
        _r4_parent(),
        consistency_embedding_dim=16,
        residual_hidden_dim=24,
        max_support=3,
        confidence_power=2.0,
    )
    inputs = _inputs()
    posterior = torch.zeros(1, GOAL_HYPOTHESIS_COUNT)
    posterior[:, 0] = 1.0
    with torch.no_grad():
        output = model.forward_step(*inputs, posterior)
    assert bool((output["evidence_gate"] >= 0.0).all())
    assert bool((output["evidence_gate"] <= 1.0).all())


def test_one_hot_public_evidence_opens_threshold_gate() -> None:
    model = NativeR7ThresholdConsistencyPolicy(
        _r4_parent(),
        consistency_embedding_dim=16,
        residual_hidden_dim=24,
        max_support=1,
        confidence_power=1.0,
    )
    inputs = _inputs()
    posterior = torch.zeros(1, GOAL_HYPOTHESIS_COUNT)
    posterior[:, 0] = 1.0
    with torch.no_grad():
        output = model.forward_step(*inputs, posterior)
    assert torch.equal(
        output["evidence_gate"],
        torch.ones_like(output["evidence_gate"]),
    )
