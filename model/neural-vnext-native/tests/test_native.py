from __future__ import annotations

from pathlib import Path
import sys

import torch

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402
from native_core import (  # noqa: E402
    ACTION_FEATURE_DIM,
    GLOBAL_FEATURE_DIM,
    NativeRecurrentPolicy,
    PublicActionMemory,
    encode_public_state,
    parameter_count,
)
from native_training import (  # noqa: E402
    load_checkpoint,
    public_exploration_teacher,
    save_checkpoint,
    train_native_policy,
)


def test_public_encoder_has_locked_shapes_and_uses_public_observation_only() -> None:
    task = make_r18_task("causal_prerequisites", "train", 3)
    observation = task.observe()
    memory = PublicActionMemory(len(task.action_descriptions))
    global_features, action_features, valid = encode_public_state(
        observation,
        memory,
        previous_feedback=(0.0, 0.0, 0.0),
    )
    assert global_features.shape == (GLOBAL_FEATURE_DIM,)
    assert action_features.shape == (len(task.action_descriptions), ACTION_FEATURE_DIM)
    assert valid.tolist() == [True] * len(task.action_descriptions)
    assert "_goal" not in observation
    assert "_action_kinds" not in observation


def test_public_teacher_explores_unseen_slots_then_uses_supervision() -> None:
    task = make_r18_task("conditional_regimes", "train", 5)
    memory = PublicActionMemory(len(task.action_descriptions))
    observation = task.observe()
    submit = next(
        index
        for index, description in enumerate(observation["actions"])
        if "submit" in description.lower()
    )
    non_submit = [index for index in range(len(observation["actions"])) if index != submit]
    first = public_exploration_teacher(task, memory, oracle_plan)
    assert first == non_submit[0]

    for action in non_submit:
        before = task.observe()
        result = task.step(action)
        memory.update(
            action=action,
            before=before,
            after=result.observation,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        if task.done:
            break

    if not task.done and float(task.observe()["progress_signal"]) < 0.999999:
        target = public_exploration_teacher(task, memory, oracle_plan)
        assert 0 <= target < len(task.action_descriptions)


def test_policy_is_action_permutation_equivariant() -> None:
    torch.manual_seed(7)
    model = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    global_features = torch.randn(1, GLOBAL_FEATURE_DIM)
    action_features = torch.randn(1, 5, ACTION_FEATURE_DIM)
    valid = torch.ones(1, 5, dtype=torch.bool)
    hidden = model.init_hidden(1)
    out = model.forward_step(global_features, action_features, valid, hidden)

    permutation = torch.tensor([3, 0, 4, 1, 2])
    permuted = model.forward_step(
        global_features,
        action_features[:, permutation],
        valid[:, permutation],
        hidden,
    )
    inverse = torch.argsort(permutation)
    assert torch.allclose(out["action_logits"], permuted["action_logits"][:, inverse], atol=1e-6)
    assert torch.allclose(out["next_hidden"], permuted["next_hidden"], atol=1e-6)


def test_tiny_real_figg18_training_changes_neural_weights() -> None:
    torch.manual_seed(11)
    model = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    before = model.score[-1].weight.detach().clone()
    summary = train_native_policy(
        model,
        make_task=make_r18_task,
        oracle_plan=oracle_plan,
        families=("conditional_regimes",),
        train_indices=(0, 1),
        seed=19,
        expert_epochs=1,
        dagger_teacher_mix=(),
        learning_rate=1e-3,
        weight_decay=0.0,
        max_grad_norm=1.0,
    )
    assert summary["stages"][0]["labelled_steps"] > 0
    assert not torch.equal(before, model.score[-1].weight.detach())


def test_checkpoint_round_trip_binds_neural_tensor_digest(tmp_path: Path) -> None:
    torch.manual_seed(13)
    model = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    destination = tmp_path / "native.pt"
    manifest = save_checkpoint(
        model,
        destination,
        predev_lock_sha256="a" * 64,
        training_summary={"seed": 13, "fresh_opened": False},
    )
    restored, metadata = load_checkpoint(destination)
    assert metadata["state_dict_sha256"] == manifest["state_dict_sha256"]
    assert metadata["checkpoint_sha256"] == manifest["checkpoint_sha256"]
    assert metadata["parameters"] == parameter_count(model)
    for name, tensor in model.state_dict().items():
        assert torch.equal(tensor.cpu(), restored.state_dict()[name].cpu())
