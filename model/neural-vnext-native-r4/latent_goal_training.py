from __future__ import annotations

import random
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor
import torch.nn.functional as F

from native_core import (
    NativeRecurrentPolicy,
    PublicActionMemory,
    encode_public_state,
    parameter_count,
    state_dict_sha256,
)
from native_training import public_exploration_teacher
from successor_core import NativeR2TransitionPolicy, PublicTransitionTrace
from attributed_core import NativeR3AttributedBeliefPolicy, PublicActionAttributedTrace
from latent_goal_core import (
    GOAL_CARDINALITY,
    GOAL_DIMENSIONS,
    NativeR4LatentGoalBeliefPolicy,
    r4_state_dict_sha256,
)

CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r4-latent-goal-belief-v1"


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_lock(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported R4 PREDEV lock")
    if payload.get("candidate") != "Neural-vNext-Native-R4-LatentGoalBelief":
        raise ValueError("unexpected R4 candidate identity")
    fresh = payload.get("fresh_isolation")
    if not isinstance(fresh, dict) or fresh.get("status") != "UNOPENED":
        raise ValueError("R4 PREDEV lock must keep fresh unopened")
    benchmark = payload.get("benchmark")
    if not isinstance(benchmark, dict) or benchmark.get("fresh_indices") != [120, 159]:
        raise ValueError("R4 must reserve untouched fresh:120..159")
    return payload


def train_only_private_goal_target(task: Any) -> Tensor:
    """Private benchmark goal is legal here only as train-only auxiliary supervision."""
    if getattr(task, "split", None) != "train":
        raise ValueError("private goal supervision is train-split only")
    if getattr(task, "family", None) != "implicit_goal_regimes":
        raise ValueError("private goal supervision is hidden-goal-family only")
    goal = getattr(task, "_goal", None)
    if not isinstance(goal, tuple) or len(goal) != GOAL_DIMENSIONS:
        raise ValueError("train-only hidden goal has unexpected shape")
    values: list[int] = []
    for value in goal:
        if type(value) is not int or not 0 <= value < GOAL_CARDINALITY:
            raise ValueError("train-only hidden goal value out of range")
        values.append(value)
    return torch.tensor([values], dtype=torch.long)


@dataclass(frozen=True)
class EpisodeTrainResult:
    loss: float
    labelled_steps: int
    behavior_steps: int
    solved: bool
    residual_mse: float
    goal_aux_loss: float
    goal_coordinate_accuracy: float


def _task_order(
    *,
    families: Sequence[str],
    indices: tuple[int, int],
    rng: random.Random,
) -> list[tuple[str, int]]:
    start, end = int(indices[0]), int(indices[1])
    if start < 0 or end < start:
        raise ValueError("invalid R4 training index range")
    rows = [
        (str(family), index)
        for family in families
        for index in range(start, end + 1)
    ]
    rng.shuffle(rows)
    return rows


def train_episode(
    model: NativeR4LatentGoalBeliefPolicy,
    task: Any,
    optimizer: torch.optim.Optimizer,
    *,
    oracle_plan: Any,
    rng: random.Random,
    teacher_mix: float,
    max_grad_norm: float,
    residual_l2_weight: float,
    goal_aux_weight: float,
) -> EpisodeTrainResult:
    if getattr(task, "split", None) != "train":
        raise ValueError("R4 training is train-split only")
    if getattr(task, "family", None) != "implicit_goal_regimes":
        raise ValueError("R4 training is hidden-goal-family only")
    if not 0.0 <= float(teacher_mix) <= 1.0:
        raise ValueError("teacher_mix must lie in [0,1]")
    if float(residual_l2_weight) < 0.0 or float(goal_aux_weight) < 0.0:
        raise ValueError("R4 loss weights must be non-negative")

    private_goal_target = train_only_private_goal_target(task)
    memory = PublicActionMemory(len(task.action_descriptions))
    trace = PublicTransitionTrace(max_length=model.parent.parent.trace_length)
    attributed = PublicActionAttributedTrace(max_length=model.parent.attribution_length)
    parent_hidden = model.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    losses: list[Tensor] = []
    residual_penalties: list[Tensor] = []
    goal_losses: list[Tensor] = []
    goal_correct = 0
    goal_coordinates = 0
    behavior_steps = 0

    model.train()
    while not task.done:
        observation = task.observe()
        try:
            target = public_exploration_teacher(task, memory, oracle_plan)
        except RuntimeError:
            break
        global_features, action_features, valid = encode_public_state(
            observation,
            memory,
            previous_feedback=previous_feedback,
        )
        trace_features, trace_valid = trace.encode()
        attribution_features, attribution_valid = attributed.encode()
        output = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            parent_hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
            attribution_features.unsqueeze(0),
            attribution_valid.unsqueeze(0),
        )
        parent_hidden = output["next_parent_hidden"]
        target_tensor = torch.tensor([target], dtype=torch.long)
        policy_loss = F.cross_entropy(output["action_logits"], target_tensor)
        valid_residual = output["goal_residual_logits"][0][valid]
        residual_penalty = (
            valid_residual.square().mean()
            if int(valid_residual.numel()) > 0
            else policy_loss.new_zeros(())
        )
        has_public_history = bool(attribution_valid.any().item())
        if has_public_history:
            goal_logits = output["goal_logits"].reshape(-1, GOAL_CARDINALITY)
            goal_target = private_goal_target.reshape(-1)
            goal_loss = F.cross_entropy(goal_logits, goal_target)
            prediction = output["goal_logits"].detach().argmax(-1)
            goal_correct += int((prediction == private_goal_target).sum().item())
            goal_coordinates += GOAL_DIMENSIONS
            goal_losses.append(goal_loss.detach())
        else:
            goal_loss = policy_loss.new_zeros(())
        total_loss = (
            policy_loss
            + float(residual_l2_weight) * residual_penalty
            + float(goal_aux_weight) * goal_loss
        )
        losses.append(total_loss)
        residual_penalties.append(residual_penalty.detach())

        behavior_action = (
            target
            if rng.random() < float(teacher_mix)
            else int(output["action_logits"].detach().argmax(-1).item())
        )
        selected_action_features = action_features[
            behavior_action
        ].detach().clone()
        before = observation
        result = task.step(behavior_action)
        after = result.observation
        memory.update(
            action=behavior_action,
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        trace.update(
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        attributed.update(
            selected_action_features=selected_action_features,
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        previous_feedback = [
            float(result.progress_delta),
            float(result.information_gain),
            float(result.failed),
        ]
        behavior_steps += 1

    if not losses:
        return EpisodeTrainResult(
            0.0,
            0,
            behavior_steps,
            bool(task.solved),
            0.0,
            0.0,
            0.0,
        )

    model.zero_grad(set_to_none=True)
    loss = torch.stack(losses).mean()
    loss.backward()
    trainable = [
        parameter
        for parameter in model.successor_parameters()
        if parameter.grad is not None
    ]
    if not trainable:
        raise ValueError("R4 exposes no trainable successor gradients")
    torch.nn.utils.clip_grad_norm_(
        trainable,
        max_norm=float(max_grad_norm),
        foreach=False,
    )
    optimizer.step()
    return EpisodeTrainResult(
        loss=float(loss.detach().cpu()),
        labelled_steps=len(losses),
        behavior_steps=behavior_steps,
        solved=bool(task.solved),
        residual_mse=float(torch.stack(residual_penalties).mean().cpu()),
        goal_aux_loss=(
            float(torch.stack(goal_losses).mean().cpu())
            if goal_losses
            else 0.0
        ),
        goal_coordinate_accuracy=goal_correct / max(1, goal_coordinates),
    )


def train_r4_policy(
    model: NativeR4LatentGoalBeliefPolicy,
    *,
    make_task: Any,
    oracle_plan: Any,
    families: Sequence[str],
    train_indices: tuple[int, int],
    seed: int,
    expert_epochs: int,
    dagger_teacher_mix: Sequence[float],
    learning_rate: float,
    weight_decay: float,
    max_grad_norm: float,
    residual_l2_weight: float,
    goal_aux_weight: float,
) -> dict[str, Any]:
    if tuple(families) != ("implicit_goal_regimes",):
        raise ValueError(
            "R4 training scope must be exactly implicit_goal_regimes"
        )
    if expert_epochs < 0 or (expert_epochs < 1 and not dagger_teacher_mix):
        raise ValueError("at least one R4 training epoch is required")

    torch.manual_seed(int(seed))
    rng = random.Random(int(seed))
    model.set_training_scope()
    parameters = model.successor_parameters()
    optimizer = torch.optim.AdamW(
        parameters,
        lr=float(learning_rate),
        weight_decay=float(weight_decay),
        foreach=False,
        fused=False,
    )
    schedule = [("expert", 1.0)] * int(expert_epochs)
    schedule.extend(
        (f"dagger-{index + 1}", float(mix))
        for index, mix in enumerate(dagger_teacher_mix)
    )
    stages: list[dict[str, Any]] = []
    for epoch, (stage, teacher_mix) in enumerate(schedule, start=1):
        total_loss = 0.0
        total_labelled = 0
        total_steps = 0
        total_solved = 0
        total_residual = 0.0
        total_goal_loss = 0.0
        total_goal_acc = 0.0
        episodes = 0
        for family, index in _task_order(
            families=families,
            indices=train_indices,
            rng=rng,
        ):
            result = train_episode(
                model,
                make_task(str(family), "train", int(index)),
                optimizer,
                oracle_plan=oracle_plan,
                rng=rng,
                teacher_mix=teacher_mix,
                max_grad_norm=max_grad_norm,
                residual_l2_weight=residual_l2_weight,
                goal_aux_weight=goal_aux_weight,
            )
            total_loss += result.loss * max(1, result.labelled_steps)
            total_labelled += result.labelled_steps
            total_steps += result.behavior_steps
            total_solved += int(result.solved)
            total_residual += result.residual_mse
            total_goal_loss += result.goal_aux_loss
            total_goal_acc += result.goal_coordinate_accuracy
            episodes += 1
        stages.append(
            {
                "epoch": epoch,
                "stage": stage,
                "teacher_mix": teacher_mix,
                "episodes": episodes,
                "labelled_steps": total_labelled,
                "behavior_steps": total_steps,
                "behavior_solved": total_solved,
                "behavior_solve_rate": total_solved / max(1, episodes),
                "mean_label_loss": (
                    total_loss / max(1, total_labelled)
                ),
                "mean_episode_residual_mse": (
                    total_residual / max(1, episodes)
                ),
                "mean_episode_goal_aux_loss": (
                    total_goal_loss / max(1, episodes)
                ),
                "mean_episode_goal_coordinate_accuracy": (
                    total_goal_acc / max(1, episodes)
                ),
            }
        )
    return {
        "seed": int(seed),
        "train_indices": list(train_indices),
        "training_episodes_per_epoch": (
            (int(train_indices[1]) - int(train_indices[0]) + 1)
            * len(tuple(families))
        ),
        "scope_trainable_parameters": sum(
            parameter.numel() for parameter in parameters
        ),
        "successor_total_parameters": model.successor_parameter_count(),
        "frozen_parent_parameters": parameter_count(model.parent),
        "private_goal_usage": (
            "train-only auxiliary labels; forbidden in rollout/dev/fresh"
        ),
        "stages": stages,
    }


@torch.no_grad()
def rollout_r4(
    model: NativeR4LatentGoalBeliefPolicy,
    task: Any,
) -> dict[str, Any]:
    memory = PublicActionMemory(len(task.action_descriptions))
    trace = PublicTransitionTrace(max_length=model.parent.parent.trace_length)
    attributed = PublicActionAttributedTrace(
        max_length=model.parent.attribution_length
    )
    parent_hidden = model.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    actions: list[int] = []
    model.eval()

    while not task.done:
        observation = task.observe()
        global_features, action_features, valid = encode_public_state(
            observation,
            memory,
            previous_feedback=previous_feedback,
        )
        trace_features, trace_valid = trace.encode()
        attribution_features, attribution_valid = attributed.encode()
        output = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            parent_hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
            attribution_features.unsqueeze(0),
            attribution_valid.unsqueeze(0),
        )
        parent_hidden = output["next_parent_hidden"]
        action = int(output["action_logits"].argmax(-1).item())
        selected_action_features = action_features[action].detach().clone()
        before = observation
        result = task.step(action)
        after = result.observation
        memory.update(
            action=action,
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        trace.update(
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        attributed.update(
            selected_action_features=selected_action_features,
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        previous_feedback = [
            float(result.progress_delta),
            float(result.information_gain),
            float(result.failed),
        ]
        actions.append(action)

    return {
        "solved": bool(task.solved),
        "steps": int(task.step_count),
        "actions": actions,
    }


def evaluate_r4(
    model: NativeR4LatentGoalBeliefPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R4 evaluation split must be dev or fresh")
    rows: list[dict[str, Any]] = []
    families_result: dict[str, dict[str, int]] = {}
    solved = 0
    steps = 0
    for family in families:
        family_solved = 0
        family_steps = 0
        episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r4(
                model,
                make_task(str(family), str(split), int(index)),
            )
            family_solved += int(result["solved"])
            family_steps += int(result["steps"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            episodes += 1
            rows.append(
                {
                    "family": str(family),
                    "split": str(split),
                    "index": int(index),
                    "solved": bool(result["solved"]),
                    "steps": int(result["steps"]),
                }
            )
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": family_solved,
            "steps": family_steps,
        }
    return {
        "split": str(split),
        "indices": [int(indices[0]), int(indices[1])],
        "episodes": len(rows),
        "solved": solved,
        "solve_rate": solved / max(1, len(rows)),
        "steps": steps,
        "families": families_result,
        "rows": rows,
    }


def save_r4_checkpoint(
    model: NativeR4LatentGoalBeliefPolicy,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    predev_lock_sha256: str,
    training_summary: Mapping[str, Any],
) -> dict[str, Any]:
    state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in model.state_dict().items()
    }
    state_sha = state_dict_sha256(state)
    parent_state_sha = state_dict_sha256(model.parent.state_dict())
    if parent_state_sha != str(parent_state_dict_sha256):
        raise ValueError(
            "frozen R3 parent changed before R4 checkpoint save"
        )
    payload = {
        "format": CHECKPOINT_FORMAT,
        "status": "TRAINED_DEV_ONLY_FRESH_UNOPENED",
        "architecture": model.architecture(),
        "parameters": model.full_parameter_count(),
        "successor_parameters": model.successor_parameter_count(),
        "parent_checkpoint_sha256": str(parent_checkpoint_sha256),
        "parent_state_dict_sha256": str(parent_state_dict_sha256),
        "predev_lock_sha256": str(predev_lock_sha256),
        "training_summary": dict(training_summary),
        "state_dict_sha256": state_sha,
        "state_dict": state,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, destination)
    return {
        key: value
        for key, value in payload.items()
        if key != "state_dict"
    } | {"checkpoint_sha256": sha256_file(destination)}


def load_r4_checkpoint(
    path: str | Path,
) -> tuple[NativeR4LatentGoalBeliefPolicy, dict[str, Any]]:
    payload = torch.load(
        Path(path),
        map_location="cpu",
        weights_only=True,
    )
    if (
        not isinstance(payload, dict)
        or payload.get("format") != CHECKPOINT_FORMAT
    ):
        raise ValueError("unsupported R4 checkpoint")
    architecture = payload.get("architecture")
    state = payload.get("state_dict")
    if not isinstance(architecture, dict) or not isinstance(state, dict):
        raise ValueError("R4 checkpoint is missing architecture/state")

    native = NativeRecurrentPolicy(
        global_dim=int(architecture["native_global_dim"]),
        action_dim=int(architecture["native_action_dim"]),
        hidden_dim=int(architecture["native_hidden_dim"]),
        attention_heads=int(architecture["native_attention_heads"]),
    )
    r2 = NativeR2TransitionPolicy(
        native,
        trace_token_dim=int(architecture["r2_trace_token_dim"]),
        trace_hidden_dim=int(architecture["r2_trace_hidden_dim"]),
        trace_length=int(architecture["r2_trace_length"]),
    )
    r3 = NativeR3AttributedBeliefPolicy(
        r2,
        attribution_token_dim=int(architecture["attribution_token_dim"]),
        attribution_hidden_dim=int(architecture["attribution_hidden_dim"]),
        attribution_length=int(architecture["attribution_length"]),
    )
    model = NativeR4LatentGoalBeliefPolicy(
        r3,
        belief_hidden_dim=int(architecture["belief_hidden_dim"]),
        goal_embedding_dim=int(architecture["goal_embedding_dim"]),
    )
    model.load_state_dict(state, strict=True)
    if r4_state_dict_sha256(model) != payload.get("state_dict_sha256"):
        raise ValueError("R4 checkpoint tensor digest mismatch")
    if state_dict_sha256(model.parent.state_dict()) != payload.get(
        "parent_state_dict_sha256"
    ):
        raise ValueError("R4 checkpoint embedded R3 parent digest mismatch")
    if model.full_parameter_count() != int(payload.get("parameters", -1)):
        raise ValueError("R4 checkpoint parameter audit mismatch")
    if model.successor_parameter_count() != int(
        payload.get("successor_parameters", -1)
    ):
        raise ValueError("R4 successor-owned parameter audit mismatch")
    model.eval()
    metadata = {
        key: value
        for key, value in payload.items()
        if key != "state_dict"
    }
    metadata["checkpoint_sha256"] = sha256_file(path)
    return model, metadata
