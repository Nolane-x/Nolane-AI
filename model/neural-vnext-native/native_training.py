from __future__ import annotations

import copy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import random
from typing import Any, Iterable, Mapping, Sequence

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

CHECKPOINT_FORMAT = "nolane-neural-vnext-native-recurrent-v1"


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
        raise ValueError("unsupported native vNext lock")
    benchmark = payload.get("benchmark")
    if not isinstance(benchmark, dict) or benchmark.get("name") != "nolane-figg18-v1":
        raise ValueError("native vNext lock must bind FIGG-18 v1")
    return payload


def _submit_index(observation: Mapping[str, Any]) -> int:
    matches = [
        index
        for index, description in enumerate(observation["actions"])
        if "submit" in str(description).lower()
    ]
    if len(matches) != 1:
        raise ValueError("FIGG-18 observation must expose exactly one submit action")
    return matches[0]


def public_exploration_teacher(task: Any, memory: PublicActionMemory, oracle_plan: Any) -> int:
    """Train-only teacher: explore public action slots before using oracle supervision.

    The exploration prefix is derivable from public memory. Oracle access is used
    only as a supervision target after each non-submit action has public evidence
    in the current context. Private task state is never serialized into model input.
    """

    observation = task.observe()
    submit = _submit_index(observation)
    if float(observation["progress_signal"]) >= 0.999999:
        return submit

    unseen = [
        action
        for action in range(len(observation["actions"]))
        if action != submit and memory.seen_in_context(observation, action) == 0
    ]
    if unseen:
        return int(unseen[0])

    plan = oracle_plan(copy.deepcopy(task))
    if not plan:
        return submit
    return int(plan[0])


@dataclass(frozen=True)
class EpisodeTrainResult:
    loss: float
    labelled_steps: int
    behavior_steps: int
    solved: bool


def train_episode(
    model: NativeRecurrentPolicy,
    task: Any,
    optimizer: torch.optim.Optimizer,
    *,
    oracle_plan: Any,
    rng: random.Random,
    teacher_mix: float,
    max_grad_norm: float,
) -> EpisodeTrainResult:
    if not 0.0 <= float(teacher_mix) <= 1.0:
        raise ValueError("teacher_mix must lie in [0,1]")
    memory = PublicActionMemory(len(task.action_descriptions))
    hidden = model.init_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    losses: list[Tensor] = []
    labelled = 0
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
        output = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            hidden,
        )
        hidden = output["next_hidden"]
        target_tensor = torch.tensor([target], dtype=torch.long)
        losses.append(F.cross_entropy(output["action_logits"], target_tensor))
        labelled += 1

        use_teacher = rng.random() < float(teacher_mix)
        behavior_action = target if use_teacher else int(output["action_logits"].detach().argmax(-1).item())
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
        previous_feedback = [
            float(result.progress_delta),
            float(result.information_gain),
            float(result.failed),
        ]
        behavior_steps += 1

    if not losses:
        return EpisodeTrainResult(loss=0.0, labelled_steps=0, behavior_steps=behavior_steps, solved=bool(task.solved))

    optimizer.zero_grad(set_to_none=True)
    loss = torch.stack(losses).mean()
    loss.backward()
    trainable = [
        parameter
        for parameter in model.parameters()
        if parameter.requires_grad and parameter.grad is not None
    ]
    torch.nn.utils.clip_grad_norm_(trainable, max_norm=float(max_grad_norm))
    optimizer.step()
    return EpisodeTrainResult(
        loss=float(loss.detach().cpu()),
        labelled_steps=labelled,
        behavior_steps=behavior_steps,
        solved=bool(task.solved),
    )


def _task_order(
    *,
    families: Sequence[str],
    start_index: int,
    end_index: int,
    rng: random.Random,
) -> list[tuple[str, int]]:
    rows = [
        (str(family), int(index))
        for family in families
        for index in range(int(start_index), int(end_index) + 1)
    ]
    rng.shuffle(rows)
    return rows


def train_native_policy(
    model: NativeRecurrentPolicy,
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
) -> dict[str, Any]:
    if expert_epochs < 0:
        raise ValueError("expert_epochs must be non-negative")
    if not dagger_teacher_mix and expert_epochs < 1:
        raise ValueError("at least one training epoch is required")
    torch.manual_seed(int(seed))
    rng = random.Random(int(seed))
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(learning_rate),
        weight_decay=float(weight_decay),
    )
    stages: list[dict[str, Any]] = []

    schedule = [("expert", 1.0)] * int(expert_epochs)
    schedule.extend((f"dagger-{index + 1}", float(mix)) for index, mix in enumerate(dagger_teacher_mix))
    for epoch, (stage, teacher_mix) in enumerate(schedule, start=1):
        total_loss = 0.0
        labelled_steps = 0
        behavior_steps = 0
        solved = 0
        episodes = 0
        for family, index in _task_order(
            families=families,
            start_index=train_indices[0],
            end_index=train_indices[1],
            rng=rng,
        ):
            result = train_episode(
                model,
                make_task(family, "train", index),
                optimizer,
                oracle_plan=oracle_plan,
                rng=rng,
                teacher_mix=teacher_mix,
                max_grad_norm=max_grad_norm,
            )
            if result.labelled_steps:
                total_loss += result.loss * result.labelled_steps
                labelled_steps += result.labelled_steps
            behavior_steps += result.behavior_steps
            solved += int(result.solved)
            episodes += 1
        stages.append(
            {
                "epoch": epoch,
                "stage": stage,
                "teacher_mix": teacher_mix,
                "episodes": episodes,
                "labelled_steps": labelled_steps,
                "behavior_steps": behavior_steps,
                "behavior_solved": solved,
                "behavior_solve_rate": solved / max(1, episodes),
                "mean_label_loss": total_loss / max(1, labelled_steps),
            }
        )
    return {
        "seed": int(seed),
        "train_indices": list(train_indices),
        "training_episodes_per_epoch": len(families) * (train_indices[1] - train_indices[0] + 1),
        "stages": stages,
    }


@torch.no_grad()
def rollout_policy(model: NativeRecurrentPolicy, task: Any) -> dict[str, Any]:
    memory = PublicActionMemory(len(task.action_descriptions))
    hidden = model.init_hidden(1)
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
        output = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            hidden,
        )
        hidden = output["next_hidden"]
        action = int(output["action_logits"].argmax(-1).item())
        before = observation
        result = task.step(action)
        memory.update(
            action=action,
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
        actions.append(action)
    return {
        "solved": bool(task.solved),
        "steps": int(task.step_count),
        "actions": actions,
    }


def evaluate_policy(
    model: NativeRecurrentPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("evaluation split must be dev or fresh")
    family_rows: dict[str, dict[str, int]] = {}
    episode_rows: list[dict[str, Any]] = []
    solved = 0
    steps = 0
    for family in families:
        family_solved = 0
        family_steps = 0
        episodes = 0
        for index in range(indices[0], indices[1] + 1):
            result = rollout_policy(model, make_task(str(family), split, index))
            family_solved += int(result["solved"])
            family_steps += int(result["steps"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            episodes += 1
            episode_rows.append(
                {
                    "family": str(family),
                    "split": split,
                    "index": int(index),
                    "solved": bool(result["solved"]),
                    "steps": int(result["steps"]),
                }
            )
        family_rows[str(family)] = {
            "episodes": episodes,
            "solved": family_solved,
            "steps": family_steps,
        }
    return {
        "split": split,
        "indices": list(indices),
        "episodes": len(episode_rows),
        "solved": solved,
        "solve_rate": solved / max(1, len(episode_rows)),
        "steps": steps,
        "families": family_rows,
        "rows": episode_rows,
    }


def save_checkpoint(
    model: NativeRecurrentPolicy,
    path: str | Path,
    *,
    predev_lock_sha256: str,
    training_summary: Mapping[str, Any],
) -> dict[str, Any]:
    state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    state_sha = state_dict_sha256(state)
    payload = {
        "format": CHECKPOINT_FORMAT,
        "status": "TRAINED_DEV_ONLY_FRESH_UNOPENED",
        "architecture": model.architecture(),
        "parameters": parameter_count(model),
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


def load_checkpoint(path: str | Path) -> tuple[NativeRecurrentPolicy, dict[str, Any]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != CHECKPOINT_FORMAT:
        raise ValueError("unsupported native vNext checkpoint")
    architecture = payload.get("architecture")
    state = payload.get("state_dict")
    if not isinstance(architecture, dict) or not isinstance(state, dict):
        raise ValueError("native vNext checkpoint is missing architecture/state")
    if state_dict_sha256(state) != payload.get("state_dict_sha256"):
        raise ValueError("native vNext checkpoint tensor digest mismatch")
    model = NativeRecurrentPolicy(**architecture)
    model.load_state_dict(state, strict=True)
    if parameter_count(model) != payload.get("parameters"):
        raise ValueError("native vNext checkpoint parameter audit mismatch")
    model.eval()
    metadata = {key: value for key, value in payload.items() if key != "state_dict"}
    metadata["checkpoint_sha256"] = sha256_file(path)
    return model, metadata
