from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import random
import sys
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor
import torch.nn.functional as F

HERE = Path(__file__).resolve()
PARENT_ROOT = HERE.parent.parent / "neural-vnext-native"
if str(PARENT_ROOT) not in sys.path:
    sys.path.insert(0, str(PARENT_ROOT))

from native_core import (  # noqa: E402
    NativeRecurrentPolicy,
    PublicActionMemory,
    encode_public_state,
    parameter_count as parent_parameter_count,
    state_dict_sha256,
)
from native_training import public_exploration_teacher  # noqa: E402
from successor_core import (  # noqa: E402
    DualTimescaleResidualPolicy,
    SuccessorState,
    specialist_parameter_count,
    total_parameter_count,
)

S1_CHECKPOINT_FORMAT = "nolane-neural-vnext-native-s1-dual-timescale-v1"


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json_file(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def load_lock(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported S1 PREDEV lock")
    if payload.get("candidate") != "Neural-vNext-Native-S1-Dual-Timescale":
        raise ValueError("unexpected S1 candidate authority")
    if payload.get("fresh_isolation", {}).get("status") != "UNOPENED":
        raise ValueError("S1 PREDEV must keep fresh unopened")
    return payload


def configure_specialist_scope(model: DualTimescaleResidualPolicy) -> dict[str, int]:
    parent_trainable = 0
    specialist_trainable = 0
    for name, parameter in model.named_parameters():
        if name.startswith("parent."):
            parameter.requires_grad_(False)
            parent_trainable += int(parameter.requires_grad) * parameter.numel()
        else:
            parameter.requires_grad_(True)
            specialist_trainable += parameter.numel()
    if parent_trainable != 0:
        raise AssertionError("accepted parent must remain frozen")
    if specialist_trainable < 1:
        raise AssertionError("S1 specialist exposes no trainable parameters")
    return {
        "parent_trainable_parameters": 0,
        "parent_frozen_parameters": parent_parameter_count(model.parent),
        "specialist_trainable_parameters": specialist_trainable,
    }


@dataclass(frozen=True)
class EpisodeTrainResult:
    loss: float
    labelled_steps: int
    behavior_steps: int
    solved: bool


def train_episode(
    model: DualTimescaleResidualPolicy,
    task: Any,
    optimizer: torch.optim.Optimizer,
    *,
    oracle_plan: Any,
    rng: random.Random,
    teacher_mix: float,
    max_grad_norm: float,
) -> EpisodeTrainResult:
    if getattr(task, "split", None) != "train":
        raise ValueError("S1 training is train-split only")
    if not 0.0 <= float(teacher_mix) <= 1.0:
        raise ValueError("teacher_mix must lie in [0,1]")

    memory = PublicActionMemory(len(task.action_descriptions))
    state = model.init_state(1)
    previous_feedback = [0.0, 0.0, 0.0]
    losses: list[Tensor] = []
    steps = 0

    model.train()
    model.parent.eval()
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
        output = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            state,
        )
        state = output["state"]
        target_tensor = torch.tensor([target], dtype=torch.long)
        losses.append(F.cross_entropy(output["action_logits"], target_tensor))

        use_teacher = rng.random() < float(teacher_mix)
        behavior_action = (
            target
            if use_teacher
            else int(output["action_logits"].detach().argmax(-1).item())
        )
        before = observation
        result = task.step(behavior_action)
        memory.update(
            action=behavior_action,
            before=before,
            after=result.observation,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        previous_feedback = [
            float(result.progress_delta),
            float(result.information_gain),
            float(result.failed),
        ]
        steps += 1

    if not losses:
        return EpisodeTrainResult(
            loss=0.0,
            labelled_steps=0,
            behavior_steps=steps,
            solved=bool(task.solved),
        )

    optimizer.zero_grad(set_to_none=True)
    loss = torch.stack(losses).mean()
    loss.backward()
    trainable = [
        parameter
        for parameter in model.parameters()
        if parameter.requires_grad and parameter.grad is not None
    ]
    torch.nn.utils.clip_grad_norm_(
        trainable,
        max_norm=float(max_grad_norm),
        foreach=False,
    )
    optimizer.step()
    return EpisodeTrainResult(
        loss=float(loss.detach().cpu()),
        labelled_steps=len(losses),
        behavior_steps=steps,
        solved=bool(task.solved),
    )


def _task_order(
    family_ranges: Mapping[str, Sequence[int]],
    rng: random.Random,
) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for family, bounds in family_ranges.items():
        if len(bounds) != 2:
            raise ValueError(f"invalid family bounds for {family}")
        start, end = int(bounds[0]), int(bounds[1])
        if start < 0 or end < start:
            raise ValueError(f"invalid family range for {family}: {bounds}")
        rows.extend((str(family), index) for index in range(start, end + 1))
    rng.shuffle(rows)
    return rows


def train_policy(
    model: DualTimescaleResidualPolicy,
    *,
    make_task: Any,
    oracle_plan: Any,
    family_train_indices: Mapping[str, Sequence[int]],
    seed: int,
    expert_epochs: int,
    dagger_teacher_mix: Sequence[float],
    learning_rate: float,
    weight_decay: float,
    max_grad_norm: float,
) -> dict[str, Any]:
    torch.manual_seed(int(seed))
    rng = random.Random(int(seed))
    scope = configure_specialist_scope(model)
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(
        trainable,
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
        labelled = 0
        behavior_steps = 0
        solved = 0
        episodes = 0
        for family, index in _task_order(family_train_indices, rng):
            result = train_episode(
                model,
                make_task(family, "train", index),
                optimizer,
                oracle_plan=oracle_plan,
                rng=rng,
                teacher_mix=teacher_mix,
                max_grad_norm=max_grad_norm,
            )
            total_loss += result.loss * result.labelled_steps
            labelled += result.labelled_steps
            behavior_steps += result.behavior_steps
            solved += int(result.solved)
            episodes += 1
        stages.append(
            {
                "epoch": epoch,
                "stage": stage,
                "teacher_mix": teacher_mix,
                "episodes": episodes,
                "labelled_steps": labelled,
                "behavior_steps": behavior_steps,
                "behavior_solved": solved,
                "behavior_solve_rate": solved / max(1, episodes),
                "mean_label_loss": total_loss / max(1, labelled),
            }
        )
    return {
        "seed": int(seed),
        "scope": scope,
        "training_episodes_per_epoch": sum(
            int(bounds[1]) - int(bounds[0]) + 1
            for bounds in family_train_indices.values()
        ),
        "family_train_indices": {
            str(family): [int(bounds[0]), int(bounds[1])]
            for family, bounds in family_train_indices.items()
        },
        "stages": stages,
    }


@torch.no_grad()
def rollout_policy(model: DualTimescaleResidualPolicy, task: Any) -> dict[str, Any]:
    memory = PublicActionMemory(len(task.action_descriptions))
    state = model.init_state(1)
    previous_feedback = [0.0, 0.0, 0.0]
    actions: list[int] = []
    model.eval()
    model.parent.eval()
    while not task.done:
        observation = task.observe()
        global_features, action_features, valid = encode_public_state(
            observation,
            memory,
            previous_feedback=previous_feedback,
        )
        output = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            state,
        )
        state = output["state"]
        action = int(output["action_logits"].argmax(-1).item())
        result = task.step(action)
        memory.update(
            action=action,
            before=observation,
            after=result.observation,
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


def evaluate_policy(
    model: DualTimescaleResidualPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
) -> dict[str, Any]:
    if split != "dev":
        raise ValueError("S1 development evaluator is dev-only; fresh is forbidden")
    rows: list[dict[str, Any]] = []
    family_rows: dict[str, dict[str, int]] = {}
    solved = 0
    steps = 0
    for family in families:
        family_solved = 0
        family_steps = 0
        for index in range(indices[0], indices[1] + 1):
            result = rollout_policy(model, make_task(str(family), "dev", index))
            family_solved += int(result["solved"])
            family_steps += int(result["steps"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            rows.append(
                {
                    "family": str(family),
                    "split": "dev",
                    "index": int(index),
                    "solved": bool(result["solved"]),
                    "steps": int(result["steps"]),
                }
            )
        family_rows[str(family)] = {
            "episodes": indices[1] - indices[0] + 1,
            "solved": family_solved,
            "steps": family_steps,
        }
    return {
        "split": "dev",
        "indices": list(indices),
        "episodes": len(rows),
        "solved": solved,
        "solve_rate": solved / max(1, len(rows)),
        "steps": steps,
        "families": family_rows,
        "rows": rows,
    }


def save_checkpoint(
    model: DualTimescaleResidualPolicy,
    path: str | Path,
    *,
    predev_lock_sha256: str,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    training_summary: Mapping[str, Any],
) -> dict[str, Any]:
    state = {
        name: value.detach().cpu().clone()
        for name, value in model.state_dict().items()
    }
    state_sha = state_dict_sha256(state)
    parent_sha = state_dict_sha256(model.parent.state_dict())
    if parent_sha != str(parent_state_dict_sha256):
        raise ValueError("S1 parent state mutated before checkpoint save")
    payload = {
        "format": S1_CHECKPOINT_FORMAT,
        "status": "TRAINED_DEV_ONLY_FRESH_UNOPENED",
        "architecture": model.architecture(),
        "parameters": total_parameter_count(model),
        "specialist_parameters": specialist_parameter_count(model),
        "parent_parameters": parent_parameter_count(model.parent),
        "predev_lock_sha256": str(predev_lock_sha256),
        "parent_checkpoint_sha256": str(parent_checkpoint_sha256),
        "parent_state_dict_sha256": str(parent_state_dict_sha256),
        "state_dict_sha256": state_sha,
        "training_summary": dict(training_summary),
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


def load_checkpoint(path: str | Path) -> tuple[DualTimescaleResidualPolicy, dict[str, Any]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != S1_CHECKPOINT_FORMAT:
        raise ValueError("unsupported S1 checkpoint")
    architecture = payload.get("architecture")
    state = payload.get("state_dict")
    if not isinstance(architecture, dict) or not isinstance(state, dict):
        raise ValueError("S1 checkpoint missing architecture/state")
    parent = NativeRecurrentPolicy(
        global_dim=int(architecture["global_dim"]),
        action_dim=int(architecture["action_dim"]),
        hidden_dim=int(architecture["parent_hidden_dim"]),
        attention_heads=4,
    )
    model = DualTimescaleResidualPolicy(
        parent,
        specialist_dim=int(architecture["specialist_dim"]),
    )
    if state_dict_sha256(state) != payload.get("state_dict_sha256"):
        raise ValueError("S1 checkpoint tensor digest mismatch")
    model.load_state_dict(state, strict=True)
    if total_parameter_count(model) != int(payload["parameters"]):
        raise ValueError("S1 checkpoint parameter audit mismatch")
    if state_dict_sha256(model.parent.state_dict()) != payload["parent_state_dict_sha256"]:
        raise ValueError("S1 checkpoint parent tensor digest mismatch")
    model.eval()
    metadata = {key: value for key, value in payload.items() if key != "state_dict"}
    metadata["checkpoint_sha256"] = sha256_file(path)
    return model, metadata
