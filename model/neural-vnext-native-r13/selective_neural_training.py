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

from native_core import PublicActionMemory, encode_public_state, state_dict_sha256
from native_training import public_exploration_teacher
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from latent_goal_training import load_r4_checkpoint
from public_planner import (
    GOAL_CARDINALITY,
    GOAL_TABLE,
    PublicGoalConsistencyBelief,
)
from causal_version_space import (
    PublicCausalRuleMemory,
    choose_public_causal_action,
)
from causal_runtime import evaluate_r11
from selective_neural_core import (
    CAUSAL_FEATURE_DIM,
    NativeR13SelectiveNeuralCausalPolicy,
)

CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r13-selective-neural-causal-v1"
R11_ACCEPTED_HORIZON = 1


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_lock(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported R13 PREDEV lock")
    if payload.get("candidate") != "Neural-vNext-Native-R13-SelectiveNeuralCausal":
        raise ValueError("unexpected R13 candidate")
    if payload["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("R13 fresh must remain unopened")
    if payload["benchmark"]["fresh_indices"] != [280, 319]:
        raise ValueError("R13 must reserve fresh:280..319")
    return payload


def _expected_distance(state: Tensor, posterior: Tensor) -> float:
    distances = torch.remainder(
        GOAL_TABLE - state.unsqueeze(0),
        GOAL_CARDINALITY,
    ).sum(dim=1).float()
    return float((posterior * distances).sum().item())


def build_causal_action_features(
    *,
    observation: Mapping[str, Any],
    causal_memory: PublicCausalRuleMemory,
    posterior: Tensor,
    r11_action: int,
) -> Tensor:
    descriptions = observation["actions"]
    actions = len(descriptions)
    posterior = posterior.detach().float()
    posterior = posterior / posterior.sum()
    state = torch.tensor([int(v) for v in observation["state"]], dtype=torch.long)
    context = PublicActionMemory.context_key(observation)
    current_distance = _expected_distance(state, posterior)
    rows: list[list[float]] = []
    for action in range(actions):
        is_submit = 1.0 if "submit" in str(descriptions[action]).lower() else 0.0
        predicted, rule_count = (
            (None, 0)
            if is_submit
            else causal_memory.predict_certified(
                context=context,
                state=state,
                action=int(action),
            )
        )
        certified = 1.0 if predicted is not None else 0.0
        if predicted is None:
            predicted_values = [0.0, 0.0, 0.0]
            next_distance = current_distance
            improvement = 0.0
        else:
            predicted_values = [float(v) / 4.0 for v in predicted.tolist()]
            next_distance = _expected_distance(predicted, posterior)
            improvement = current_distance - next_distance
        rows.append([
            is_submit,
            certified,
            min(1.0, float(rule_count) / 18.0),
            *predicted_values,
            float(current_distance) / 12.0,
            float(next_distance) / 12.0,
            float(improvement) / 12.0,
            1.0 if int(action) == int(r11_action) else 0.0,
        ])
    tensor = torch.tensor(rows, dtype=torch.float32)
    if tensor.shape != (actions, CAUSAL_FEATURE_DIM):
        raise AssertionError("unexpected R13 causal feature shape")
    return tensor


@dataclass(frozen=True)
class EpisodeTrainResult:
    loss: float
    labelled_steps: int
    behavior_steps: int
    solved: bool
    residual_mse: float


def train_episode(
    model: NativeR13SelectiveNeuralCausalPolicy,
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
        raise ValueError("R13 training is train-split only")
    if getattr(task, "family", None) != "implicit_goal_regimes":
        raise ValueError("R13 training is hidden-goal-family only")
    exact_memory = PublicActionMemory(len(task.action_descriptions))
    causal_memory = PublicCausalRuleMemory()
    trace = PublicTransitionTrace(max_length=model.parent.parent.parent.trace_length)
    attributed = PublicActionAttributedTrace(max_length=model.parent.parent.attribution_length)
    belief = PublicGoalConsistencyBelief()
    parent_hidden = model.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    losses: list[Tensor] = []
    penalties: list[Tensor] = []
    behavior_steps = 0

    model.train()
    while not task.done:
        observation = task.observe()
        belief.update(observation)
        try:
            target = public_exploration_teacher(task, exact_memory, oracle_plan)
        except RuntimeError:
            break
        global_features, action_features, valid = encode_public_state(
            observation,
            exact_memory,
            previous_feedback=previous_feedback,
        )
        trace_features, trace_valid = trace.encode()
        attribution_features, attribution_valid = attributed.encode()
        with torch.no_grad():
            parent_output = model.parent.forward_step(
                global_features.unsqueeze(0),
                action_features.unsqueeze(0),
                valid.unsqueeze(0),
                parent_hidden,
                trace_features.unsqueeze(0),
                trace_valid.unsqueeze(0),
                attribution_features.unsqueeze(0),
                attribution_valid.unsqueeze(0),
            )
        parent_hidden = parent_output["next_parent_hidden"].detach()
        posterior = belief.encode()
        r11_action, _decision = choose_public_causal_action(
            observation=observation,
            exact_memory=exact_memory,
            causal_memory=causal_memory,
            posterior=posterior,
            parent_logits=parent_output["action_logits"][0],
            horizon=R11_ACCEPTED_HORIZON,
        )
        causal_features = build_causal_action_features(
            observation=observation,
            causal_memory=causal_memory,
            posterior=posterior,
            r11_action=r11_action,
        )
        output = model.forward_from_parent(
            global_features=global_features.unsqueeze(0),
            action_features=action_features.unsqueeze(0),
            valid_actions=valid.unsqueeze(0),
            parent_output=parent_output,
            consistency_posterior=posterior.unsqueeze(0),
            causal_action_features=causal_features.unsqueeze(0),
            r11_actions=torch.tensor([r11_action], dtype=torch.long),
        )
        target_tensor = torch.tensor([int(target)], dtype=torch.long)
        policy_loss = F.cross_entropy(output["proposal_logits"], target_tensor)
        valid_residual = output["causal_residual_logits"][0][valid]
        residual_penalty = (
            valid_residual.square().mean()
            if int(valid_residual.numel()) > 0
            else policy_loss.new_zeros(())
        )
        total_loss = policy_loss + float(residual_l2_weight) * residual_penalty
        losses.append(total_loss)
        penalties.append(residual_penalty.detach())

        behavior_action = (
            int(target)
            if rng.random() < float(teacher_mix)
            else int(output["action_logits"].detach().argmax(-1).item())
        )
        selected_action_features = action_features[behavior_action].detach().clone()
        before = observation
        result = task.step(behavior_action)
        after = result.observation
        exact_memory.update(
            action=behavior_action,
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        causal_memory.update(action=behavior_action, before=before, after=after)
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
        return EpisodeTrainResult(0.0, 0, behavior_steps, bool(task.solved), 0.0)
    model.zero_grad(set_to_none=True)
    loss = torch.stack(losses).mean()
    loss.backward()
    trainable = [
        parameter for parameter in model.successor_parameters()
        if parameter.grad is not None
    ]
    if not trainable:
        raise ValueError("R13 exposes no trainable gradients")
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
        residual_mse=float(torch.stack(penalties).mean().cpu()),
    )


def train_r13_policy(
    model: NativeR13SelectiveNeuralCausalPolicy,
    *,
    make_task: Any,
    oracle_plan: Any,
    train_indices: tuple[int, int],
    seed: int,
    expert_epochs: int,
    dagger_teacher_mix: Sequence[float],
    learning_rate: float,
    weight_decay: float,
    max_grad_norm: float,
    residual_l2_weight: float,
) -> dict[str, Any]:
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
    schedule = [("expert", 1.0)] * int(expert_epochs)
    schedule.extend(
        (f"dagger-{i+1}", float(mix))
        for i, mix in enumerate(dagger_teacher_mix)
    )
    stages: list[dict[str, Any]] = []
    start, end = int(train_indices[0]), int(train_indices[1])
    for epoch, (stage, teacher_mix) in enumerate(schedule):
        order = list(range(start, end + 1))
        rng.shuffle(order)
        results: list[EpisodeTrainResult] = []
        for index in order:
            results.append(train_episode(
                model,
                make_task("implicit_goal_regimes", "train", int(index)),
                optimizer,
                oracle_plan=oracle_plan,
                rng=rng,
                teacher_mix=teacher_mix,
                max_grad_norm=max_grad_norm,
                residual_l2_weight=residual_l2_weight,
            ))
        stages.append({
            "epoch": epoch + 1,
            "stage": stage,
            "teacher_mix": teacher_mix,
            "episodes": len(results),
            "mean_loss": sum(r.loss for r in results) / max(1, len(results)),
            "mean_residual_mse": sum(r.residual_mse for r in results) / max(1, len(results)),
            "behavior_solved": sum(int(r.solved) for r in results),
            "labelled_steps": sum(r.labelled_steps for r in results),
        })
    model.eval()
    return {
        "seed": int(seed),
        "train_indices": [start, end],
        "stages": stages,
    }


def rollout_r13(
    model: NativeR13SelectiveNeuralCausalPolicy,
    task: Any,
) -> dict[str, Any]:
    exact_memory = PublicActionMemory(len(task.action_descriptions))
    causal_memory = PublicCausalRuleMemory()
    trace = PublicTransitionTrace(max_length=model.parent.parent.parent.trace_length)
    attributed = PublicActionAttributedTrace(max_length=model.parent.parent.attribution_length)
    belief = PublicGoalConsistencyBelief()
    parent_hidden = model.init_parent_hidden(1)
    previous_feedback = [0.0, 0.0, 0.0]
    overrides_vs_r11 = 0

    model.eval()
    while not task.done:
        observation = task.observe()
        belief.update(observation)
        global_features, action_features, valid = encode_public_state(
            observation,
            exact_memory,
            previous_feedback=previous_feedback,
        )
        trace_features, trace_valid = trace.encode()
        attribution_features, attribution_valid = attributed.encode()
        with torch.no_grad():
            parent_output = model.parent.forward_step(
                global_features.unsqueeze(0),
                action_features.unsqueeze(0),
                valid.unsqueeze(0),
                parent_hidden,
                trace_features.unsqueeze(0),
                trace_valid.unsqueeze(0),
                attribution_features.unsqueeze(0),
                attribution_valid.unsqueeze(0),
            )
        parent_hidden = parent_output["next_parent_hidden"].detach()
        posterior = belief.encode()
        r11_action, _decision = choose_public_causal_action(
            observation=observation,
            exact_memory=exact_memory,
            causal_memory=causal_memory,
            posterior=posterior,
            parent_logits=parent_output["action_logits"][0],
            horizon=R11_ACCEPTED_HORIZON,
        )
        causal_features = build_causal_action_features(
            observation=observation,
            causal_memory=causal_memory,
            posterior=posterior,
            r11_action=r11_action,
        )
        with torch.no_grad():
            output = model.forward_from_parent(
                global_features=global_features.unsqueeze(0),
                action_features=action_features.unsqueeze(0),
                valid_actions=valid.unsqueeze(0),
                parent_output=parent_output,
                consistency_posterior=posterior.unsqueeze(0),
                causal_action_features=causal_features.unsqueeze(0),
                r11_actions=torch.tensor([r11_action], dtype=torch.long),
            )
        action = int(output["action_logits"].argmax(-1).item())
        overrides_vs_r11 += int(action != int(r11_action))
        selected_action_features = action_features[action].detach().clone()
        before = observation
        result = task.step(action)
        after = result.observation
        exact_memory.update(
            action=action,
            before=before,
            after=after,
            progress_delta=result.progress_delta,
            information_gain=result.information_gain,
            failed=result.failed,
        )
        causal_memory.update(action=action, before=before, after=after)
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

    return {
        "solved": bool(task.solved),
        "steps": int(task.step_count),
        "overrides_vs_r11": int(overrides_vs_r11),
    }


def evaluate_r13(
    model: NativeR13SelectiveNeuralCausalPolicy,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R13 evaluation split must be dev or fresh")
    rows: list[dict[str, Any]] = []
    families_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = 0
    for family in families:
        fs = fst = fov = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r13(
                model,
                make_task(str(family), str(split), int(index)),
            )
            fs += int(result["solved"])
            fst += int(result["steps"])
            fov += int(result["overrides_vs_r11"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            overrides += int(result["overrides_vs_r11"])
            episodes += 1
            rows.append({
                "family": str(family),
                "split": str(split),
                "index": int(index),
                **result,
            })
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": fs,
            "steps": fst,
            "overrides_vs_r11": fov,
        }
    return {
        "split": str(split),
        "indices": [int(indices[0]), int(indices[1])],
        "episodes": len(rows),
        "solved": solved,
        "solve_rate": solved / max(1, len(rows)),
        "steps": steps,
        "overrides_vs_r11": overrides,
        "families": families_result,
        "rows": rows,
    }


def save_r13_checkpoint(
    model: NativeR13SelectiveNeuralCausalPolicy,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    r11_authority_blob_sha: str,
    predev_lock_sha256: str,
    training_summary: Mapping[str, Any],
) -> dict[str, Any]:
    successor_state = model.successor_state_dict()
    payload = {
        "format": CHECKPOINT_FORMAT,
        "status": "TRAINED_DEV_ONLY_FRESH_UNOPENED",
        "architecture": model.architecture(),
        "parameters": model.full_parameter_count(),
        "successor_parameters": model.successor_parameter_count(),
        "parent_checkpoint_sha256": str(parent_checkpoint_sha256),
        "parent_state_dict_sha256": str(parent_state_dict_sha256),
        "r11_authority_blob_sha": str(r11_authority_blob_sha),
        "predev_lock_sha256": str(predev_lock_sha256),
        "training_summary": dict(training_summary),
        "successor_state_dict_sha256": state_dict_sha256(successor_state),
        "successor_state_dict": successor_state,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, destination)
    return {
        key: value for key, value in payload.items()
        if key != "successor_state_dict"
    } | {"checkpoint_sha256": sha256_file(destination)}


def load_r13_checkpoint(
    path: str | Path,
    *,
    parent_checkpoint_path: str | Path,
) -> tuple[NativeR13SelectiveNeuralCausalPolicy, dict[str, Any]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != CHECKPOINT_FORMAT:
        raise ValueError("unsupported R13 checkpoint")
    architecture = payload.get("architecture")
    successor_state = payload.get("successor_state_dict")
    if not isinstance(architecture, dict) or not isinstance(successor_state, dict):
        raise ValueError("R13 checkpoint missing architecture/state")

    parent, parent_metadata = load_r4_checkpoint(parent_checkpoint_path)
    if parent_metadata["checkpoint_sha256"] != payload["parent_checkpoint_sha256"]:
        raise ValueError("R13 embedded parent checkpoint authority mismatch")
    if parent_metadata["state_dict_sha256"] != payload["parent_state_dict_sha256"]:
        raise ValueError("R13 embedded parent state authority mismatch")

    model = NativeR13SelectiveNeuralCausalPolicy(
        parent,
        posterior_embedding_dim=int(architecture["r13_posterior_embedding_dim"]),
        residual_hidden_dim=int(architecture["r13_residual_hidden_dim"]),
        max_support=int(architecture["r13_max_support"]),
        parent_margin=float(architecture["r13_parent_margin"]),
        override_margin_threshold=float(
            architecture["r13_override_margin_threshold"]
        ),
    )
    model.load_successor_state_dict(successor_state)
    if model.successor_state_sha256() != payload["successor_state_dict_sha256"]:
        raise ValueError("R13 successor state digest mismatch")
    if model.full_parameter_count() != int(payload["parameters"]):
        raise ValueError("R13 parameter audit mismatch")
    if model.successor_parameter_count() != int(payload["successor_parameters"]):
        raise ValueError("R13 successor parameter audit mismatch")
    model.eval()
    metadata = {
        key: value for key, value in payload.items()
        if key != "successor_state_dict"
    }
    metadata["checkpoint_sha256"] = sha256_file(path)
    return model, metadata


def calibrate_override_margin(
    model: NativeR13SelectiveNeuralCausalPolicy,
    *,
    make_task: Any,
    oracle_plan: Any,
    calibration_indices: tuple[int, int],
    precision_floor: float = 0.90,
) -> dict[str, Any]:
    """Select the override margin using only disjoint train-split calibration episodes."""
    if not 0.5 <= float(precision_floor) <= 1.0:
        raise ValueError("precision_floor must lie in [0.5,1]")
    model.eval()
    original_threshold = float(model.override_margin_threshold)
    model.set_override_margin_threshold(1.0e9)
    samples: list[dict[str, Any]] = []
    start, end = int(calibration_indices[0]), int(calibration_indices[1])

    for index in range(start, end + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        exact_memory = PublicActionMemory(len(task.action_descriptions))
        causal_memory = PublicCausalRuleMemory()
        trace = PublicTransitionTrace(max_length=model.parent.parent.parent.trace_length)
        attributed = PublicActionAttributedTrace(max_length=model.parent.parent.attribution_length)
        belief = PublicGoalConsistencyBelief()
        parent_hidden = model.init_parent_hidden(1)
        previous_feedback = [0.0, 0.0, 0.0]

        while not task.done:
            observation = task.observe()
            belief.update(observation)
            try:
                plan = oracle_plan(task)
            except RuntimeError:
                # Train-only calibration has no trustworthy oracle label
                # once the current public trajectory is outside the
                # remaining-budget solvable set. Fail closed: do not
                # manufacture a positive/negative override label.
                break
            if not plan:
                break
            oracle_action = int(plan[0])
            global_features, action_features, valid = encode_public_state(
                observation,
                exact_memory,
                previous_feedback=previous_feedback,
            )
            trace_features, trace_valid = trace.encode()
            attribution_features, attribution_valid = attributed.encode()
            with torch.no_grad():
                parent_output = model.parent.forward_step(
                    global_features.unsqueeze(0),
                    action_features.unsqueeze(0),
                    valid.unsqueeze(0),
                    parent_hidden,
                    trace_features.unsqueeze(0),
                    trace_valid.unsqueeze(0),
                    attribution_features.unsqueeze(0),
                    attribution_valid.unsqueeze(0),
                )
            parent_hidden = parent_output["next_parent_hidden"].detach()
            posterior = belief.encode()
            r11_action, _ = choose_public_causal_action(
                observation=observation,
                exact_memory=exact_memory,
                causal_memory=causal_memory,
                posterior=posterior,
                parent_logits=parent_output["action_logits"][0],
                horizon=R11_ACCEPTED_HORIZON,
            )
            causal_features = build_causal_action_features(
                observation=observation,
                causal_memory=causal_memory,
                posterior=posterior,
                r11_action=r11_action,
            )
            with torch.no_grad():
                output = model.forward_from_parent(
                    global_features=global_features.unsqueeze(0),
                    action_features=action_features.unsqueeze(0),
                    valid_actions=valid.unsqueeze(0),
                    parent_output=parent_output,
                    consistency_posterior=posterior.unsqueeze(0),
                    causal_action_features=causal_features.unsqueeze(0),
                    r11_actions=torch.tensor([r11_action], dtype=torch.long),
                )
            proposal = int(output["proposed_actions"].item())
            margin = float(output["proposal_margin"].item())
            if proposal != int(r11_action):
                label = int(
                    proposal == oracle_action
                    and int(r11_action) != oracle_action
                )
                samples.append({
                    "margin": margin,
                    "label": label,
                    "proposal": proposal,
                    "r11_action": int(r11_action),
                    "oracle_action": oracle_action,
                })

            behavior_action = int(r11_action)
            selected_action_features = action_features[behavior_action].detach().clone()
            before = observation
            result = task.step(behavior_action)
            after = result.observation
            exact_memory.update(
                action=behavior_action,
                before=before,
                after=after,
                progress_delta=result.progress_delta,
                information_gain=result.information_gain,
                failed=result.failed,
            )
            causal_memory.update(
                action=behavior_action,
                before=before,
                after=after,
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

    candidates = sorted({max(0.0, float(row["margin"])) for row in samples})
    candidates.append(1.0e9)
    scored: list[dict[str, Any]] = []
    for threshold in candidates:
        approved = [
            row for row in samples
            if float(row["margin"]) >= float(threshold)
        ]
        tp = sum(int(row["label"]) for row in approved)
        fp = len(approved) - tp
        precision = tp / max(1, len(approved))
        eligible = bool(tp >= 1 and precision >= float(precision_floor))
        scored.append({
            "threshold": float(threshold),
            "approved": len(approved),
            "true_positive": tp,
            "false_positive": fp,
            "precision": precision,
            "eligible": eligible,
        })
    eligible_rows = [row for row in scored if row["eligible"]]
    if eligible_rows:
        selected = max(
            eligible_rows,
            key=lambda row: (
                int(row["true_positive"]),
                -int(row["false_positive"]),
                -float(row["threshold"]),
            ),
        )
        threshold = float(selected["threshold"])
    else:
        threshold = 1.0e9
        selected = next(row for row in scored if row["threshold"] == 1.0e9)

    model.set_override_margin_threshold(threshold)
    return {
        "calibration_indices": [start, end],
        "precision_floor": float(precision_floor),
        "proposal_samples": len(samples),
        "positive_samples": sum(int(row["label"]) for row in samples),
        "negative_samples": sum(1 - int(row["label"]) for row in samples),
        "selected_threshold": threshold,
        "selected_stats": selected,
        "candidate_thresholds": scored,
        "initial_threshold": original_threshold,
    }
