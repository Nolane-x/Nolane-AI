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
    TARGET_VISIBLE_FEATURE_INDEX,
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


def test_goal_belief_cannot_perturb_visible_target_policy() -> None:
    torch.manual_seed(29)
    model = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    model.eval()

    visible_task = make_r18_task("conditional_regimes", "train", 9)
    visible_observation = visible_task.observe()
    visible_memory = PublicActionMemory(len(visible_task.action_descriptions))
    vg, va, vv = encode_public_state(
        visible_observation,
        visible_memory,
        previous_feedback=(0.0, 0.0, 0.0),
    )
    assert float(vg[TARGET_VISIBLE_FEATURE_INDEX]) == 1.0
    hidden = model.init_hidden(1)
    before = model.forward_step(vg.unsqueeze(0), va.unsqueeze(0), vv.unsqueeze(0), hidden)["action_logits"]

    with torch.no_grad():
        global_token = model.global_encoder(vg.unsqueeze(0))
        action_tokens = model.action_encoder(va.unsqueeze(0))
        attended, _ = model.action_attention(
            global_token[:, None, :],
            action_tokens,
            action_tokens,
            key_padding_mask=~vv.unsqueeze(0),
            need_weights=False,
        )
        next_hidden = model.recurrent(
            torch.cat((global_token, attended[:, 0, :]), dim=-1),
            hidden,
        )
        legacy_logits = model.score(
            torch.cat(
                (
                    action_tokens,
                    next_hidden[:, None, :].expand(1, action_tokens.shape[1], model.hidden_dim),
                ),
                dim=-1,
            )
        ).squeeze(-1)
    assert torch.allclose(before, legacy_logits, atol=1e-6)

    with torch.no_grad():
        model.goal_belief_projection.weight.fill_(1000.0)
        model.goal_head.weight.fill_(1000.0)
        model.goal_head.bias.fill_(1000.0)
    after = model.forward_step(vg.unsqueeze(0), va.unsqueeze(0), vv.unsqueeze(0), hidden)["action_logits"]
    assert torch.allclose(before, after, atol=1e-6)

    implicit_task = make_r18_task("implicit_goal_regimes", "train", 9)
    implicit_observation = implicit_task.observe()
    implicit_memory = PublicActionMemory(len(implicit_task.action_descriptions))
    ig, ia, iv = encode_public_state(
        implicit_observation,
        implicit_memory,
        previous_feedback=(0.0, 0.0, 0.0),
    )
    assert float(ig[TARGET_VISIBLE_FEATURE_INDEX]) == 0.0


def test_goal_supervision_rejects_non_train_split() -> None:
    from native_training import train_episode

    torch.manual_seed(31)
    model = NativeRecurrentPolicy(hidden_dim=64, attention_heads=4)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    dev_task = make_r18_task("implicit_goal_regimes", "dev", 0)
    try:
        train_episode(
            model,
            dev_task,
            optimizer,
            oracle_plan=oracle_plan,
            rng=__import__("random").Random(31),
            teacher_mix=1.0,
            max_grad_norm=1.0,
        )
    except ValueError as exc:
        assert "train-split only" in str(exc)
    else:
        raise AssertionError("goal supervision must reject non-train split")
