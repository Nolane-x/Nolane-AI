from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

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
from latent_goal_core import (
    GOAL_CARDINALITY,
    GOAL_DIMENSIONS,
    NativeR4LatentGoalBeliefPolicy,
)
from latent_goal_training import (
    load_r4_checkpoint,
    save_r4_checkpoint,
    train_only_private_goal_target,
)


def _r3_parent() -> NativeR3AttributedBeliefPolicy:
    torch.manual_seed(11)
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
    return NativeR3AttributedBeliefPolicy(
        r2,
        attribution_hidden_dim=24,
        attribution_length=12,
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


def test_r4_initialization_is_exactly_r3_equivalent() -> None:
    parent = _r3_parent()
    model = NativeR4LatentGoalBeliefPolicy(
        copy.deepcopy(parent),
        belief_hidden_dim=20,
        goal_embedding_dim=12,
    )
    inputs = _inputs()
    with torch.no_grad():
        expected = parent.forward_step(*inputs)["action_logits"]
        actual = model.forward_step(*inputs)["action_logits"]
    assert torch.equal(actual, expected)


def test_visible_target_hard_gate_blocks_r4_residual() -> None:
    parent = _r3_parent()
    model = NativeR4LatentGoalBeliefPolicy(
        copy.deepcopy(parent),
        belief_hidden_dim=20,
        goal_embedding_dim=12,
    )
    with torch.no_grad():
        model.hidden_target_goal_score[-1].bias.fill_(7.0)
    inputs = list(_inputs())
    inputs[0][:, TARGET_VISIBLE_FEATURE_INDEX] = 1.0
    with torch.no_grad():
        expected = parent.forward_step(*inputs)["action_logits"]
        output = model.forward_step(*inputs)
    assert torch.equal(output["action_logits"], expected)
    assert torch.equal(
        output["goal_residual_logits"],
        torch.zeros_like(output["goal_residual_logits"]),
    )


def test_goal_posterior_has_exact_shape_and_normalization() -> None:
    model = NativeR4LatentGoalBeliefPolicy(
        _r3_parent(),
        belief_hidden_dim=20,
        goal_embedding_dim=12,
    )
    inputs = list(_inputs())
    inputs[-2][:, 0, :] = 0.25
    inputs[-1][:, 0] = True
    with torch.no_grad():
        output = model.forward_step(*inputs)
    probabilities = output["goal_probabilities"]
    assert probabilities.shape == (
        1,
        GOAL_DIMENSIONS,
        GOAL_CARDINALITY,
    )
    assert torch.allclose(
        probabilities.sum(-1),
        torch.ones(1, GOAL_DIMENSIONS),
    )
    assert torch.isfinite(probabilities).all()


def test_parent_frozen_and_only_r4_parameters_trainable() -> None:
    model = NativeR4LatentGoalBeliefPolicy(
        _r3_parent(),
        belief_hidden_dim=20,
        goal_embedding_dim=12,
    )
    model.set_training_scope()
    assert all(
        not parameter.requires_grad
        for parameter in model.parent.parameters()
    )
    assert model.successor_parameters()
    assert all(
        parameter.requires_grad
        for parameter in model.successor_parameters()
    )


def test_private_goal_auxiliary_supervision_is_train_only() -> None:
    train = SimpleNamespace(
        split="train",
        family="implicit_goal_regimes",
        _goal=(1, 4, 2),
    )
    target = train_only_private_goal_target(train)
    assert target.tolist() == [[1, 4, 2]]

    with pytest.raises(ValueError, match="train-split only"):
        train_only_private_goal_target(
            SimpleNamespace(
                split="dev",
                family="implicit_goal_regimes",
                _goal=(1, 2, 3),
            )
        )
    with pytest.raises(ValueError, match="hidden-goal-family only"):
        train_only_private_goal_target(
            SimpleNamespace(
                split="train",
                family="regime_switch",
                _goal=(1, 2, 3),
            )
        )


def test_forward_inference_does_not_accept_or_require_private_goal() -> None:
    model = NativeR4LatentGoalBeliefPolicy(
        _r3_parent(),
        belief_hidden_dim=20,
        goal_embedding_dim=12,
    )
    with torch.no_grad():
        output = model.forward_step(*_inputs())
    assert "goal_logits" in output
    assert "action_logits" in output


def test_r4_checkpoint_roundtrip_binds_frozen_r3_parent(
    tmp_path: Path,
) -> None:
    model = NativeR4LatentGoalBeliefPolicy(
        _r3_parent(),
        belief_hidden_dim=20,
        goal_embedding_dim=12,
    )
    parent_state = state_dict_sha256(model.parent.state_dict())
    path = tmp_path / "r4.pt"
    metadata = save_r4_checkpoint(
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
    restored, observed = load_r4_checkpoint(path)
    assert observed["checkpoint_sha256"] == metadata["checkpoint_sha256"]
    assert observed["state_dict_sha256"] == metadata["state_dict_sha256"]
    assert observed["parent_state_dict_sha256"] == parent_state
    assert state_dict_sha256(restored.parent.state_dict()) == parent_state
    assert (
        restored.successor_parameter_count()
        == model.successor_parameter_count()
    )
