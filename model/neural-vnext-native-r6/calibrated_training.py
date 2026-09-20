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
    state_dict_sha256,
)
from native_training import public_exploration_teacher
from successor_core import (
    NativeR2TransitionPolicy,
    PublicTransitionTrace,
)
from attributed_core import (
    NativeR3AttributedBeliefPolicy,
    PublicActionAttributedTrace,
)
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from calibrated_core import (
    NativeR6CalibratedConsistencyPolicy,
    PublicGoalConsistencyBelief,
    r6_state_dict_sha256,
)

CHECKPOINT_FORMAT = (
    "nolane-neural-vnext-native-r6-calibrated-consistency-v1"
)


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)
    return digest.hexdigest()


def load_lock(path: str | Path) -> dict[str, Any]:
    payload = json.loads(
        Path(path).read_text(encoding="utf-8")
    )
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
    ):
        raise ValueError("unsupported R6 PREDEV lock")
    if (
        payload.get("candidate")
        != "Neural-vNext-Native-R6-CalibratedConsistency"
    ):
        raise ValueError("unexpected R6 candidate identity")
    fresh = payload.get("fresh_isolation")
    if (
        not isinstance(fresh, dict)
        or fresh.get("status") != "UNOPENED"
    ):
        raise ValueError(
            "R6 PREDEV lock must keep fresh unopened"
        )
    benchmark = payload.get("benchmark")
    if (
        not isinstance(benchmark, dict)
        or benchmark.get("fresh_indices") != [200, 239]
    ):
        raise ValueError(
            "R6 must reserve untouched fresh:200..239"
        )
    return payload


@dataclass(frozen=True)
class EpisodeTrainResult:
    loss: float
    labelled_steps: int
    behavior_steps: int
    solved: bool
    residual_mse: float
    mean_support_size: float


def _task_order(
    *,
    families: Sequence[str],
    indices: tuple[int, int],
    rng: random.Random,
) -> list[tuple[str, int]]:
    start, end = int(indices[0]), int(indices[1])
    if start < 0 or end < start:
        raise ValueError("invalid R6 training index range")
    rows = [
        (str(family), index)
        for family in families
        for index in range(start, end + 1)
    ]
    rng.shuffle(rows)
    return rows


def train_episode(
    model: NativeR6CalibratedConsistencyPolicy,
    task: Any,
    optimizer: torch.optim.Optimizer,
    *,
    oracle_plan: Any,
    rng: random.Random,
    teacher_mix: float,
    max_grad_norm: float,
    residual_l2_weight: float,
) -> EpisodeTrainResult:
    if getattr(task, "split", None) != "train":
        raise ValueError("R6 training is train-split only")
    if (
        getattr(task, "family", None)
        != "implicit_goal_regimes"
    ):
        raise ValueError(
            "R6 training is hidden-goal-family only"
        )
    if not 0.0 <= float(teacher_mix) <= 1.0:
        raise ValueError(
            "teacher_mix must lie in [0,1]"
        )

    memory = PublicActionMemory(
        len(task.action_descriptions)
    )
    trace = PublicTransitionTrace(
        max_length=model.parent.parent.parent.trace_length
    )
    attributed = PublicActionAttributedTrace(
        max_length=model.parent.parent.attribution_length
    )
    consistency = PublicGoalConsistencyBelief()
    parent_hidden = model.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    losses: list[Tensor] = []
    residual_penalties: list[Tensor] = []
    support_sizes: list[int] = []
    behavior_steps = 0

    model.train()
    while not task.done:
        observation = task.observe()
        consistency.update(observation)
        support_sizes.append(
            consistency.support_size()
        )
        try:
            target = public_exploration_teacher(
                task,
                memory,
                oracle_plan,
            )
        except RuntimeError:
            break
        (
            global_features,
            action_features,
            valid,
        ) = encode_public_state(
            observation,
            memory,
            previous_feedback=previous_feedback,
        )
        trace_features, trace_valid = trace.encode()
        (
            attribution_features,
            attribution_valid,
        ) = attributed.encode()
        output = model.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            parent_hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
            attribution_features.unsqueeze(0),
            attribution_valid.unsqueeze(0),
            consistency.encode().unsqueeze(0),
        )
        parent_hidden = output["next_parent_hidden"]
        target_tensor = torch.tensor(
            [target],
            dtype=torch.long,
        )
        policy_loss = F.cross_entropy(
            output["action_logits"],
            target_tensor,
        )
        valid_residual = (
            output["consistency_residual_logits"][0][valid]
        )
        residual_penalty = (
            valid_residual.square().mean()
            if int(valid_residual.numel()) > 0
            else policy_loss.new_zeros(())
        )
        loss = (
            policy_loss
            + float(residual_l2_weight)
            * residual_penalty
        )
        losses.append(loss)
        residual_penalties.append(
            residual_penalty.detach()
        )

        behavior_action = (
            target
            if rng.random() < float(teacher_mix)
            else int(
                output["action_logits"]
                .detach()
                .argmax(-1)
                .item()
            )
        )
        selected_action_features = (
            action_features[behavior_action]
            .detach()
            .clone()
        )
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
            selected_action_features=
                selected_action_features,
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

    mean_support = float(
        sum(support_sizes)
        / max(1, len(support_sizes))
    )
    if not losses:
        return EpisodeTrainResult(
            0.0,
            0,
            behavior_steps,
            bool(task.solved),
            0.0,
            mean_support,
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
        raise ValueError(
            "R6 exposes no trainable successor gradients"
        )
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
        residual_mse=float(
            torch.stack(
                residual_penalties
            ).mean().cpu()
        ),
        mean_support_size=mean_support,
    )


def train_r6_policy(
    model: NativeR6CalibratedConsistencyPolicy,
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
) -> dict[str, Any]:
    if tuple(families) != (
        "implicit_goal_regimes",
    ):
        raise ValueError(
            "R6 training scope must be exactly "
            "implicit_goal_regimes"
        )
    torch.manual_seed(int(seed))
    rng = random.Random(int(seed))
    model.set_training_scope()
    optimizer = torch.optim.AdamW(
        model.successor_parameters(),
        lr=float(learning_rate),
        weight_decay=float(weight_decay),
        foreach=False,
        fused=False,
    )
    schedule = (
        [("expert", 1.0)] * int(expert_epochs)
    )
    schedule.extend(
        (
            f"dagger-{index + 1}",
            float(mix),
        )
        for index, mix in enumerate(
            dagger_teacher_mix
        )
    )
    if not schedule:
        raise ValueError(
            "R6 requires at least one training stage"
        )
    stages: list[dict[str, Any]] = []
    for epoch, (
        stage,
        teacher_mix,
    ) in enumerate(schedule):
        rows = _task_order(
            families=families,
            indices=train_indices,
            rng=rng,
        )
        losses: list[float] = []
        residuals: list[float] = []
        supports: list[float] = []
        solved = 0
        labelled_steps = 0
        behavior_steps = 0
        for family, index in rows:
            result = train_episode(
                model,
                make_task(
                    family,
                    "train",
                    index,
                ),
                optimizer,
                oracle_plan=oracle_plan,
                rng=rng,
                teacher_mix=teacher_mix,
                max_grad_norm=max_grad_norm,
                residual_l2_weight=
                    residual_l2_weight,
            )
            losses.append(result.loss)
            residuals.append(
                result.residual_mse
            )
            supports.append(
                result.mean_support_size
            )
            solved += int(result.solved)
            labelled_steps += (
                result.labelled_steps
            )
            behavior_steps += (
                result.behavior_steps
            )
        stages.append(
            {
                "epoch": epoch,
                "stage": stage,
                "teacher_mix": teacher_mix,
                "episodes": len(rows),
                "solved": solved,
                "mean_loss": (
                    sum(losses)
                    / max(1, len(losses))
                ),
                "mean_residual_mse": (
                    sum(residuals)
                    / max(1, len(residuals))
                ),
                "mean_public_consistency_support": (
                    sum(supports)
                    / max(1, len(supports))
                ),
                "labelled_steps":
                    labelled_steps,
                "behavior_steps":
                    behavior_steps,
            }
        )
    model.eval()
    return {"stages": stages}


def rollout_r6(
    model: NativeR6CalibratedConsistencyPolicy,
    task: Any,
) -> dict[str, Any]:
    memory = PublicActionMemory(
        len(task.action_descriptions)
    )
    trace = PublicTransitionTrace(
        max_length=model.parent.parent.parent.trace_length
    )
    attributed = PublicActionAttributedTrace(
        max_length=model.parent.parent.attribution_length
    )
    consistency = PublicGoalConsistencyBelief()
    parent_hidden = model.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    actions: list[int] = []
    support_sizes: list[int] = []
    model.eval()

    while not task.done:
        observation = task.observe()
        consistency.update(observation)
        support_sizes.append(
            consistency.support_size()
        )
        (
            global_features,
            action_features,
            valid,
        ) = encode_public_state(
            observation,
            memory,
            previous_feedback=
                previous_feedback,
        )
        trace_features, trace_valid = trace.encode()
        (
            attribution_features,
            attribution_valid,
        ) = attributed.encode()
        with torch.no_grad():
            output = model.forward_step(
                global_features.unsqueeze(0),
                action_features.unsqueeze(0),
                valid.unsqueeze(0),
                parent_hidden,
                trace_features.unsqueeze(0),
                trace_valid.unsqueeze(0),
                attribution_features.unsqueeze(0),
                attribution_valid.unsqueeze(0),
                consistency.encode().unsqueeze(0),
            )
        parent_hidden = output[
            "next_parent_hidden"
        ]
        action = int(
            output["action_logits"]
            .argmax(-1)
            .item()
        )
        selected_action_features = (
            action_features[action]
            .detach()
            .clone()
        )
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
            selected_action_features=
                selected_action_features,
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
        "final_consistency_support": (
            support_sizes[-1]
            if support_sizes
            else 125
        ),
        "minimum_consistency_support": (
            min(support_sizes)
            if support_sizes
            else 125
        ),
    }


def evaluate_r6(
    model: NativeR6CalibratedConsistencyPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError(
            "R6 evaluation split must be dev or fresh"
        )
    rows: list[dict[str, Any]] = []
    families_result: dict[
        str,
        dict[str, int],
    ] = {}
    solved = 0
    steps = 0
    for family in families:
        family_solved = 0
        family_steps = 0
        episodes = 0
        for index in range(
            int(indices[0]),
            int(indices[1]) + 1,
        ):
            result = rollout_r6(
                model,
                make_task(
                    str(family),
                    str(split),
                    int(index),
                ),
            )
            family_solved += int(
                result["solved"]
            )
            family_steps += int(
                result["steps"]
            )
            solved += int(result["solved"])
            steps += int(result["steps"])
            episodes += 1
            rows.append(
                {
                    "family": str(family),
                    "split": str(split),
                    "index": int(index),
                    "solved": bool(
                        result["solved"]
                    ),
                    "steps": int(
                        result["steps"]
                    ),
                    "final_consistency_support":
                        int(
                            result[
                                "final_consistency_support"
                            ]
                        ),
                    "minimum_consistency_support":
                        int(
                            result[
                                "minimum_consistency_support"
                            ]
                        ),
                }
            )
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": family_solved,
            "steps": family_steps,
        }
    return {
        "split": str(split),
        "indices": [
            int(indices[0]),
            int(indices[1]),
        ],
        "episodes": len(rows),
        "solved": solved,
        "solve_rate":
            solved / max(1, len(rows)),
        "steps": steps,
        "families": families_result,
        "rows": rows,
    }


def save_r6_checkpoint(
    model: NativeR6CalibratedConsistencyPolicy,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    predev_lock_sha256: str,
    training_summary: Mapping[str, Any],
) -> dict[str, Any]:
    state = {
        name: tensor.detach().cpu().clone()
        for name, tensor
        in model.state_dict().items()
    }
    state_sha = state_dict_sha256(state)
    parent_state_sha = state_dict_sha256(
        model.parent.state_dict()
    )
    if (
        parent_state_sha
        != str(parent_state_dict_sha256)
    ):
        raise ValueError(
            "frozen R4 parent changed before "
            "R6 checkpoint save"
        )
    payload = {
        "format": CHECKPOINT_FORMAT,
        "status":
            "TRAINED_DEV_ONLY_FRESH_UNOPENED",
        "architecture": model.architecture(),
        "parameters":
            model.full_parameter_count(),
        "successor_parameters":
            model.successor_parameter_count(),
        "parent_checkpoint_sha256":
            str(parent_checkpoint_sha256),
        "parent_state_dict_sha256":
            str(parent_state_dict_sha256),
        "predev_lock_sha256":
            str(predev_lock_sha256),
        "training_summary":
            dict(training_summary),
        "state_dict_sha256": state_sha,
        "state_dict": state,
    }
    destination = Path(path)
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    torch.save(payload, destination)
    return {
        key: value
        for key, value in payload.items()
        if key != "state_dict"
    } | {
        "checkpoint_sha256":
            sha256_file(destination)
    }


def load_r6_checkpoint(
    path: str | Path,
) -> tuple[
    NativeR6CalibratedConsistencyPolicy,
    dict[str, Any],
]:
    payload = torch.load(
        Path(path),
        map_location="cpu",
        weights_only=True,
    )
    if (
        not isinstance(payload, dict)
        or payload.get("format")
        != CHECKPOINT_FORMAT
    ):
        raise ValueError(
            "unsupported R6 checkpoint"
        )
    architecture = payload.get("architecture")
    state = payload.get("state_dict")
    if (
        not isinstance(architecture, dict)
        or not isinstance(state, dict)
    ):
        raise ValueError(
            "R6 checkpoint is missing "
            "architecture/state"
        )

    native = NativeRecurrentPolicy(
        global_dim=int(
            architecture["native_global_dim"]
        ),
        action_dim=int(
            architecture["native_action_dim"]
        ),
        hidden_dim=int(
            architecture["native_hidden_dim"]
        ),
        attention_heads=int(
            architecture[
                "native_attention_heads"
            ]
        ),
    )
    r2 = NativeR2TransitionPolicy(
        native,
        trace_token_dim=int(
            architecture["r2_trace_token_dim"]
        ),
        trace_hidden_dim=int(
            architecture[
                "r2_trace_hidden_dim"
            ]
        ),
        trace_length=int(
            architecture["r2_trace_length"]
        ),
    )
    r3 = NativeR3AttributedBeliefPolicy(
        r2,
        attribution_token_dim=int(
            architecture["attribution_token_dim"]
        ),
        attribution_hidden_dim=int(
            architecture[
                "attribution_hidden_dim"
            ]
        ),
        attribution_length=int(
            architecture[
                "attribution_length"
            ]
        ),
    )
    r4 = NativeR4LatentGoalBeliefPolicy(
        r3,
        belief_hidden_dim=int(
            architecture["belief_hidden_dim"]
        ),
        goal_embedding_dim=int(
            architecture["goal_embedding_dim"]
        ),
    )
    model = NativeR6CalibratedConsistencyPolicy(
        r4,
        consistency_embedding_dim=int(
            architecture[
                "consistency_embedding_dim"
            ]
        ),
        residual_hidden_dim=int(
            architecture["residual_hidden_dim"]
        ),
        calibration_power=float(
            architecture["calibration_power"]
        ),
    )
    model.load_state_dict(state, strict=True)
    if (
        r6_state_dict_sha256(model)
        != payload.get("state_dict_sha256")
    ):
        raise ValueError(
            "R6 checkpoint tensor digest mismatch"
        )
    if (
        state_dict_sha256(
            model.parent.state_dict()
        )
        != payload.get(
            "parent_state_dict_sha256"
        )
    ):
        raise ValueError(
            "R6 checkpoint embedded R4 "
            "parent digest mismatch"
        )
    if (
        model.full_parameter_count()
        != int(payload.get("parameters", -1))
    ):
        raise ValueError(
            "R6 checkpoint parameter audit mismatch"
        )
    if (
        model.successor_parameter_count()
        != int(
            payload.get(
                "successor_parameters",
                -1,
            )
        )
    ):
        raise ValueError(
            "R6 successor-owned parameter "
            "audit mismatch"
        )
    model.eval()
    metadata = {
        key: value
        for key, value in payload.items()
        if key != "state_dict"
    }
    metadata["checkpoint_sha256"] = (
        sha256_file(path)
    )
    return model, metadata
