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
from successor_core import (
    TRACE_TOKEN_DIM,
    NativeR2TransitionPolicy,
)
from attributed_core import (
    ATTRIBUTION_TOKEN_DIM,
    NativeR3AttributedBeliefPolicy,
    PublicActionAttributedTrace,
)
from attributed_training import (
    load_r3_checkpoint,
    save_r3_checkpoint,
)


def _parent() -> NativeR2TransitionPolicy:
    torch.manual_seed(7)
    native = NativeRecurrentPolicy(
        global_dim=GLOBAL_FEATURE_DIM,
        action_dim=ACTION_FEATURE_DIM,
        hidden_dim=32,
        attention_heads=4,
    )
    return NativeR2TransitionPolicy(
        native,
        trace_token_dim=TRACE_TOKEN_DIM,
        trace_hidden_dim=24,
        trace_length=8,
    )


def _inputs(actions: int = 4) -> tuple[torch.Tensor, ...]:
    global_features = torch.zeros(1, GLOBAL_FEATURE_DIM)
    action_features = torch.randn(1, actions, ACTION_FEATURE_DIM)
    valid_actions = torch.ones(1, actions, dtype=torch.bool)
    parent_hidden = torch.zeros(1, 32)
    trace_features = torch.zeros(1, 8, TRACE_TOKEN_DIM)
    trace_valid = torch.zeros(1, 8, dtype=torch.bool)
    attribution_features = torch.zeros(1, 12, ATTRIBUTION_TOKEN_DIM)
    attribution_valid = torch.zeros(1, 12, dtype=torch.bool)
    return (
        global_features,
        action_features,
        valid_actions,
        parent_hidden,
        trace_features,
        trace_valid,
        attribution_features,
        attribution_valid,
    )


def test_r3_initialization_is_exactly_parent_equivalent() -> None:
    parent = _parent()
    model = NativeR3AttributedBeliefPolicy(
        copy.deepcopy(parent),
        attribution_hidden_dim=24,
        attribution_length=12,
    )
    inputs = _inputs()
    with torch.no_grad():
        expected = parent.forward_step(*inputs[:6])["action_logits"]
        actual = model.forward_step(*inputs)["action_logits"]
    assert torch.equal(actual, expected)


def test_visible_target_hard_gate_blocks_attribution_residual() -> None:
    parent = _parent()
    model = NativeR3AttributedBeliefPolicy(
        copy.deepcopy(parent),
        attribution_hidden_dim=24,
        attribution_length=12,
    )
    with torch.no_grad():
        model.hidden_target_attribution_score[-1].bias.fill_(5.0)
    inputs = list(_inputs())
    inputs[0][:, TARGET_VISIBLE_FEATURE_INDEX] = 1.0
    with torch.no_grad():
        expected = parent.forward_step(*inputs[:6])["action_logits"]
        output = model.forward_step(*inputs)
    assert torch.equal(output["action_logits"], expected)
    assert torch.equal(
        output["attribution_residual_logits"],
        torch.zeros_like(output["attribution_residual_logits"]),
    )


def test_parent_is_frozen_and_successor_is_trainable() -> None:
    model = NativeR3AttributedBeliefPolicy(
        _parent(),
        attribution_hidden_dim=24,
        attribution_length=12,
    )
    model.set_training_scope()
    assert all(
        parameter.requires_grad is False
        for parameter in model.parent.parameters()
    )
    assert model.successor_parameters()
    assert all(
        parameter.requires_grad is True
        for parameter in model.successor_parameters()
    )


def test_public_action_attributed_trace_uses_exact_public_width() -> None:
    memory = PublicActionAttributedTrace(max_length=2)
    before = {
        "state": [0, 1, 2],
        "progress_signal": 0.25,
        "regime": "amber",
    }
    after = {
        "state": [1, 1, 2],
        "progress_signal": 0.333333,
        "regime": "amber",
    }
    memory.update(
        selected_action_features=[0.0] * ACTION_FEATURE_DIM,
        before=before,
        after=after,
        progress_delta=0.083333,
        information_gain=1.0,
        failed=False,
    )
    features, valid = memory.encode()
    assert features.shape == (2, ATTRIBUTION_TOKEN_DIM)
    assert valid.tolist() == [True, False]
    assert len(memory) == 1

    with pytest.raises(ValueError, match="feature width"):
        memory.update(
            selected_action_features=[0.0] * (ACTION_FEATURE_DIM - 1),
            before=before,
            after=after,
            progress_delta=0.0,
            information_gain=0.0,
            failed=False,
        )


def test_attributed_trace_does_not_require_private_goal() -> None:
    memory = PublicActionAttributedTrace(max_length=2)
    before = {
        "state": [0, 0, 0],
        "progress_signal": 0.2,
        "regime": "violet",
        "feedback_hint": "infer from public feedback",
    }
    after = {
        "state": [0, 2, 0],
        "progress_signal": 0.3,
        "regime": "violet",
        "feedback_hint": "infer from public feedback",
    }
    memory.update(
        selected_action_features=torch.zeros(ACTION_FEATURE_DIM),
        before=before,
        after=after,
        progress_delta=0.1,
        information_gain=0.5,
        failed=False,
    )
    features, valid = memory.encode()
    assert valid[0]
    assert torch.isfinite(features).all()


def test_r3_checkpoint_roundtrip_binds_frozen_r2_parent(
    tmp_path: Path,
) -> None:
    model = NativeR3AttributedBeliefPolicy(
        _parent(),
        attribution_hidden_dim=24,
        attribution_length=12,
    )
    parent_state = state_dict_sha256(model.parent.state_dict())
    path = tmp_path / "r3.pt"
    metadata = save_r3_checkpoint(
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
    restored, observed = load_r3_checkpoint(path)
    assert observed["checkpoint_sha256"] == metadata["checkpoint_sha256"]
    assert observed["state_dict_sha256"] == metadata["state_dict_sha256"]
    assert observed["parent_state_dict_sha256"] == parent_state
    assert state_dict_sha256(restored.parent.state_dict()) == parent_state
    assert restored.successor_parameter_count() == model.successor_parameter_count()
