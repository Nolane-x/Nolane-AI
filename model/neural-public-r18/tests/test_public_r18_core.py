from __future__ import annotations

import inspect
import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from npr18 import (  # noqa: E402
    PublicR18RecursiveCore,
    collect_public_teacher_episode,
    encode_public_actions,
    encode_public_text,
    evaluate_public_r18,
    public_r18_parameter_count,
    train_public_r18_epoch,
)
from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402


def test_core_interface_has_no_oracle_or_private_simulator_inputs() -> None:
    parameters = set(inspect.signature(PublicR18RecursiveCore.forward).parameters)
    assert parameters == {
        "self",
        "observation_tokens",
        "action_tokens",
        "action_mask",
        "memory",
        "previous_action",
        "previous_feedback",
    }


def test_public_core_is_recurrent_and_parameter_bounded() -> None:
    torch.manual_seed(3)
    model = PublicR18RecursiveCore(hidden_dim=96, reasoning_steps=3)
    observation = encode_public_text('{"state":[0,1,2]}', max_bytes=model.observation_bytes)
    action_tokens, action_mask = encode_public_actions(
        ("opaque actuator Nox-01", "submit current hypothesis"),
        max_actions=model.max_actions,
        max_bytes=model.action_bytes,
    )
    memory = model.initial_memory(1)
    output = model(
        observation_tokens=observation.unsqueeze(0),
        action_tokens=action_tokens.unsqueeze(0),
        action_mask=action_mask.unsqueeze(0),
        memory=memory,
        previous_action=torch.tensor([-1], dtype=torch.long),
        previous_feedback=torch.zeros(1, 3),
    )
    assert output["action_logits"].shape == (1, model.max_actions)
    assert output["action_logits_trajectory"].shape == (1, 3, model.max_actions)
    assert output["next_memory"].shape == memory.shape
    assert public_r18_parameter_count(model) < 10_000_000
    assert output["action_logits"][0, 2:].max().item() < -1e8


def test_teacher_collector_is_train_only_and_preserves_small_corpus_solvability() -> None:
    for family in (
        "conditional_regimes",
        "regime_switch",
        "implicit_goal_regimes",
        "causal_prerequisites",
    ):
        episode = collect_public_teacher_episode(
            make_r18_task(family, "train", 0),
            oracle_plan=oracle_plan,
        )
        assert episode.steps
        assert episode.solved is True

    try:
        collect_public_teacher_episode(
            make_r18_task("conditional_regimes", "dev", 0),
            oracle_plan=oracle_plan,
        )
    except ValueError as exc:
        assert "train-split only" in str(exc)
    else:
        raise AssertionError("teacher collection must reject dev/fresh tasks")


def test_training_changes_neural_parameters_on_verified_teacher_episode() -> None:
    torch.manual_seed(7)
    model = PublicR18RecursiveCore(hidden_dim=96, reasoning_steps=2)
    episode = collect_public_teacher_episode(
        make_r18_task("conditional_regimes", "train", 1),
        oracle_plan=oracle_plan,
    )
    before = model.policy_head.weight.detach().clone()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    metrics = train_public_r18_epoch(
        model,
        [episode],
        optimizer,
        generator=torch.Generator().manual_seed(7),
    )
    assert metrics["rows"] > 0
    assert metrics["episodes"] == 1
    assert not torch.equal(before, model.policy_head.weight.detach())


def test_generic_evaluator_refuses_fresh_split_before_freeze_court() -> None:
    model = PublicR18RecursiveCore(hidden_dim=96, reasoning_steps=2)
    try:
        evaluate_public_r18(
            model,
            make_task=make_r18_task,
            split="fresh",
            start_index=1160,
            count_per_family=1,
        )
    except ValueError as exc:
        assert "refuses fresh" in str(exc)
    else:
        raise AssertionError("fresh must stay closed")
