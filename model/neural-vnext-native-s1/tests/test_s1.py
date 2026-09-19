from __future__ import annotations

import json
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
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402
from native_core import (  # noqa: E402
    NativeRecurrentPolicy,
    PublicActionMemory,
    encode_public_state,
    state_dict_sha256,
)
from successor_core import DualTimescaleResidualPolicy  # noqa: E402
from successor_training import (  # noqa: E402
    configure_specialist_scope,
    evaluate_policy,
    train_episode,
)


def _encoded(task):
    observation = task.observe()
    memory = PublicActionMemory(len(task.action_descriptions))
    return encode_public_state(
        observation,
        memory,
        previous_feedback=(0.0, 0.0, 0.0),
    )


def test_s1_starts_as_exact_parent_and_parent_is_frozen() -> None:
    torch.manual_seed(41)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = DualTimescaleResidualPolicy(parent, specialist_dim=32)
    task = make_r18_task("conditional_regimes", "train", 0)
    global_features, action_features, valid = _encoded(task)

    parent_hidden = parent.init_hidden(1)
    with torch.no_grad():
        expected = parent.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            parent_hidden,
        )["action_logits"]
    actual = model.forward_step(
        global_features.unsqueeze(0),
        action_features.unsqueeze(0),
        valid.unsqueeze(0),
        model.init_state(1),
    )["action_logits"]

    assert torch.allclose(actual, expected, atol=0.0, rtol=0.0)
    assert all(not parameter.requires_grad for parameter in model.parent.parameters())
    scope = configure_specialist_scope(model)
    assert scope["parent_trainable_parameters"] == 0
    assert scope["specialist_trainable_parameters"] > 0


def test_s1_action_order_equivariance() -> None:
    torch.manual_seed(43)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = DualTimescaleResidualPolicy(parent, specialist_dim=32)
    task = make_r18_task("conditional_regimes", "train", 2)
    global_features, action_features, valid = _encoded(task)
    state = model.init_state(1)

    original = model.forward_step(
        global_features.unsqueeze(0),
        action_features.unsqueeze(0),
        valid.unsqueeze(0),
        state,
    )["action_logits"]
    permutation = torch.tensor([2, 0, 3, 1])
    permuted = model.forward_step(
        global_features.unsqueeze(0),
        action_features[permutation].unsqueeze(0),
        valid[permutation].unsqueeze(0),
        model.init_state(1),
    )["action_logits"]

    assert torch.allclose(
        permuted,
        original[:, permutation],
        atol=1e-6,
        rtol=0.0,
    )


def test_s1_training_changes_specialist_but_not_parent() -> None:
    torch.manual_seed(47)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = DualTimescaleResidualPolicy(parent, specialist_dim=32)
    configure_specialist_scope(model)

    parent_before = state_dict_sha256(model.parent.state_dict())
    specialist_before = {
        name: tensor.detach().clone()
        for name, tensor in model.state_dict().items()
        if not name.startswith("parent.")
    }
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=1e-3,
        foreach=False,
        fused=False,
    )
    result = train_episode(
        model,
        make_r18_task("implicit_goal_regimes", "train", 1),
        optimizer,
        oracle_plan=oracle_plan,
        rng=random.Random(47),
        teacher_mix=1.0,
        max_grad_norm=1.0,
    )
    assert result.labelled_steps > 0
    assert state_dict_sha256(model.parent.state_dict()) == parent_before
    changed = any(
        not torch.equal(specialist_before[name], tensor.detach())
        for name, tensor in model.state_dict().items()
        if not name.startswith("parent.")
    )
    assert changed


def test_s1_development_evaluator_rejects_fresh() -> None:
    torch.manual_seed(53)
    parent = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model = DualTimescaleResidualPolicy(parent, specialist_dim=32)
    try:
        evaluate_policy(
            model,
            make_task=make_r18_task,
            families=("conditional_regimes",),
            split="fresh",
            indices=(40, 40),
        )
    except ValueError as exc:
        assert "dev-only" in str(exc)
    else:
        raise AssertionError("S1 dev evaluator must never open fresh")


def test_s1_lock_reserves_new_dev_and_fresh_blocks() -> None:
    lock = json.loads((ROOT / "PREDEV_LOCK.json").read_text(encoding="utf-8"))
    benchmark = lock["benchmark"]
    assert benchmark["development_indices"] == [32, 63]
    assert benchmark["fresh_indices_reserved"] == [40, 79]
    assert benchmark["consumed_parent_fresh_indices_forbidden"] == [0, 39]
    assert lock["fresh_isolation"]["status"] == "UNOPENED"
    assert lock["parent_authority"]["parent_parameter_updates_allowed"] is False
