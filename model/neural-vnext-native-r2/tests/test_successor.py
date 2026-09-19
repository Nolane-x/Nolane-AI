from __future__ import annotations

import copy
from pathlib import Path
import random
import sys

import torch

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
PARENT_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, PARENT_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402
from native_core import (  # noqa: E402
    NativeRecurrentPolicy,
    PublicActionMemory,
    encode_public_state,
    state_dict_sha256,
)
from successor_core import (  # noqa: E402
    NativeR2TransitionPolicy,
    PublicTransitionTrace,
    TRACE_TOKEN_DIM,
    successor_state_dict_sha256,
)
from successor_training import (  # noqa: E402
    load_successor_checkpoint,
    save_successor_checkpoint,
    train_episode,
)


def _encoded_inputs(task):
    memory = PublicActionMemory(len(task.action_descriptions))
    global_features, action_features, valid = encode_public_state(
        task.observe(),
        memory,
        previous_feedback=(0.0, 0.0, 0.0),
    )
    trace = PublicTransitionTrace(max_length=8)
    trace_features, trace_valid = trace.encode()
    return global_features, action_features, valid, trace_features, trace_valid


def test_zero_init_successor_is_exact_parent_policy() -> None:
    torch.manual_seed(7)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = NativeR2TransitionPolicy(
        parent,
        trace_hidden_dim=64,
        trace_length=8,
    )
    task = make_r18_task("regime_switch", "train", 3)
    global_features, action_features, valid, trace_features, trace_valid = _encoded_inputs(task)
    hidden = parent.init_hidden(1)

    with torch.no_grad():
        parent_out = parent.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            hidden,
        )
        successor_out = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
        )
    assert torch.equal(
        successor_out["action_logits"],
        parent_out["action_logits"],
    )
    assert torch.count_nonzero(successor_out["residual_logits"]).item() == 0


def test_public_transition_trace_ignores_private_fields() -> None:
    task = make_r18_task("implicit_goal_regimes", "train", 5)
    before = task.observe()
    result = task.step(0)
    after = result.observation

    trace_a = PublicTransitionTrace(max_length=8)
    trace_a.update(
        before=before,
        after=after,
        progress_delta=result.progress_delta,
        information_gain=result.information_gain,
        failed=result.failed,
    )

    private_before = copy.deepcopy(before)
    private_after = copy.deepcopy(after)
    private_before["_goal"] = [4, 4, 4]
    private_before["_secret_rule"] = "do-not-use"
    private_after["_goal"] = [0, 0, 0]
    private_after["_secret_rule"] = "different"

    trace_b = PublicTransitionTrace(max_length=8)
    trace_b.update(
        before=private_before,
        after=private_after,
        progress_delta=result.progress_delta,
        information_gain=result.information_gain,
        failed=result.failed,
    )
    encoded_a, valid_a = trace_a.encode()
    encoded_b, valid_b = trace_b.encode()
    assert encoded_a.shape == (8, TRACE_TOKEN_DIM)
    assert torch.equal(encoded_a, encoded_b)
    assert torch.equal(valid_a, valid_b)


def test_training_changes_only_successor_owned_parameters() -> None:
    torch.manual_seed(11)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = NativeR2TransitionPolicy(
        parent,
        trace_hidden_dim=64,
        trace_length=8,
    )
    parent_before = state_dict_sha256(model.parent.state_dict())
    successor_before = successor_state_dict_sha256(model)
    assert all(not parameter.requires_grad for parameter in model.parent.parameters())

    model.set_training_scope("general")
    optimizer = torch.optim.AdamW(
        model.parameters_for_scope("general"),
        lr=1e-3,
        foreach=False,
        fused=False,
    )
    result = train_episode(
        model,
        make_r18_task("implicit_goal_regimes", "train", 2),
        optimizer,
        oracle_plan=oracle_plan,
        rng=random.Random(11),
        teacher_mix=1.0,
        max_grad_norm=1.0,
        residual_l2_weight=0.0,
        training_scope="general",
    )
    assert result.labelled_steps > 0
    assert state_dict_sha256(model.parent.state_dict()) == parent_before
    assert successor_state_dict_sha256(model) != successor_before


def test_successor_action_permutation_equivariance() -> None:
    torch.manual_seed(13)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = NativeR2TransitionPolicy(
        parent,
        trace_hidden_dim=64,
        trace_length=8,
    )
    with torch.no_grad():
        model.residual_score[-1].weight.normal_(mean=0.0, std=0.02)
        model.residual_score[-1].bias.zero_()

    task = make_r18_task("conditional_regimes", "train", 4)
    global_features, action_features, valid, trace_features, trace_valid = _encoded_inputs(task)
    hidden = parent.init_hidden(1)
    permutation = torch.randperm(action_features.shape[0])
    inverse = torch.argsort(permutation)

    with torch.no_grad():
        original = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
        )["action_logits"][0]
        permuted = model.forward_step(
            global_features.unsqueeze(0),
            action_features[permutation].unsqueeze(0),
            valid[permutation].unsqueeze(0),
            hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
        )["action_logits"][0]
    assert torch.allclose(original, permuted[inverse], atol=1e-6)


def test_successor_checkpoint_roundtrip_audits_parent(tmp_path: Path) -> None:
    torch.manual_seed(17)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = NativeR2TransitionPolicy(
        parent,
        trace_hidden_dim=64,
        trace_length=8,
    )
    parent_sha = state_dict_sha256(model.parent.state_dict())
    path = tmp_path / "successor.pt"
    manifest = save_successor_checkpoint(
        model,
        path,
        parent_checkpoint_sha256="parent-file-sha",
        parent_state_dict_sha256=parent_sha,
        predev_lock_sha256="lock-sha",
        training_summary={"fresh_opened": False},
    )
    restored, metadata = load_successor_checkpoint(path)
    assert metadata["checkpoint_sha256"] == manifest["checkpoint_sha256"]
    assert metadata["state_dict_sha256"] == manifest["state_dict_sha256"]
    assert metadata["parent_state_dict_sha256"] == parent_sha
    assert successor_state_dict_sha256(restored) == successor_state_dict_sha256(model)


def test_successor_training_rejects_dev_split() -> None:
    torch.manual_seed(19)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = NativeR2TransitionPolicy(
        parent,
        trace_hidden_dim=64,
        trace_length=8,
    )
    model.set_training_scope("general")
    optimizer = torch.optim.AdamW(
        model.parameters_for_scope("general"),
        lr=1e-3,
        foreach=False,
        fused=False,
    )
    try:
        train_episode(
            model,
            make_r18_task("regime_switch", "dev", 32),
            optimizer,
            oracle_plan=oracle_plan,
            rng=random.Random(19),
            teacher_mix=1.0,
            max_grad_norm=1.0,
            residual_l2_weight=0.0,
            training_scope="general",
        )
    except ValueError as exc:
        assert "train-split only" in str(exc)
    else:
        raise AssertionError("successor training must reject dev tasks")


def test_hidden_target_head_is_hard_gated_off_for_visible_target() -> None:
    torch.manual_seed(23)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = NativeR2TransitionPolicy(
        parent,
        trace_hidden_dim=64,
        trace_length=8,
    )
    task = make_r18_task("conditional_regimes", "train", 6)
    global_features, action_features, valid, trace_features, trace_valid = _encoded_inputs(task)
    hidden = parent.init_hidden(1)

    with torch.no_grad():
        before = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
        )
        for parameter in model.hidden_target_residual_score.parameters():
            parameter.normal_(mean=0.0, std=10.0)
        after = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
        )
    assert torch.equal(before["action_logits"], after["action_logits"])
    assert torch.count_nonzero(after["hidden_target_residual_logits"]).item() == 0


def test_hidden_target_training_cannot_mutate_general_residual_or_parent() -> None:
    torch.manual_seed(29)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = NativeR2TransitionPolicy(
        parent,
        trace_hidden_dim=64,
        trace_length=8,
    )
    with torch.no_grad():
        model.residual_score[-1].weight.normal_(mean=0.0, std=0.02)

    parent_before = {
        name: tensor.detach().clone()
        for name, tensor in model.parent.state_dict().items()
    }
    general_before = {
        name: tensor.detach().clone()
        for name, tensor in model.state_dict().items()
        if name.startswith("trace_encoder.")
        or name.startswith("trace_recurrent.")
        or name.startswith("residual_score.")
    }
    hidden_before = {
        name: tensor.detach().clone()
        for name, tensor in model.state_dict().items()
        if name.startswith("hidden_target_residual_score.")
    }

    model.set_training_scope("hidden_target")
    optimizer = torch.optim.AdamW(
        model.parameters_for_scope("hidden_target"),
        lr=1e-3,
        foreach=False,
        fused=False,
    )
    result = train_episode(
        model,
        make_r18_task("implicit_goal_regimes", "train", 7),
        optimizer,
        oracle_plan=oracle_plan,
        rng=random.Random(29),
        teacher_mix=1.0,
        max_grad_norm=1.0,
        residual_l2_weight=0.0,
        training_scope="hidden_target",
    )
    assert result.labelled_steps > 0

    for name, tensor in model.parent.state_dict().items():
        assert torch.equal(tensor, parent_before[name])
    for name, tensor in model.state_dict().items():
        if name in general_before:
            assert torch.equal(tensor, general_before[name])
    assert any(
        not torch.equal(model.state_dict()[name], tensor)
        for name, tensor in hidden_before.items()
    )
