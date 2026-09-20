from __future__ import annotations

import json
import random
from dataclasses import dataclass
from hashlib import sha256
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
from public_planner import GOAL_CARDINALITY, GOAL_TABLE, PublicGoalConsistencyBelief
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action
from advantage_core import NativeR20AdvantageConsensus, consensus_advantage_action, CAUSAL_FEATURE_DIM

R11_HORIZON = 1
CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r20-advantage-consensus-v1"


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_causal_action_features(
    *,
    observation: Mapping[str, Any],
    causal_memory: PublicCausalRuleMemory,
    posterior: Tensor,
    r11_action: int,
) -> Tensor:
    descriptions = observation["actions"]
    posterior = posterior.detach().float()
    posterior = posterior / posterior.sum()
    state = torch.tensor([int(v) for v in observation["state"]], dtype=torch.long)
    context = PublicActionMemory.context_key(observation)
    distances = torch.remainder(GOAL_TABLE - state.unsqueeze(0), GOAL_CARDINALITY).sum(dim=1).float()
    current_distance = float((posterior * distances).sum().item())
    rows: list[list[float]] = []
    for action, description in enumerate(descriptions):
        is_submit = 1.0 if "submit" in str(description).lower() else 0.0
        predicted, rule_count = (None, 0)
        if not is_submit:
            predicted, rule_count = causal_memory.predict_certified(
                context=context, state=state, action=int(action)
            )
        certified = 1.0 if predicted is not None else 0.0
        if predicted is None:
            predicted_values = [0.0, 0.0, 0.0]
            next_distance = current_distance
            improvement = 0.0
        else:
            predicted_values = [float(v) / 4.0 for v in predicted.tolist()]
            nd = torch.remainder(GOAL_TABLE - predicted.unsqueeze(0), GOAL_CARDINALITY).sum(dim=1).float()
            next_distance = float((posterior * nd).sum().item())
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
    if tensor.shape[-1] != CAUSAL_FEATURE_DIM:
        raise AssertionError("R20 causal feature dimension mismatch")
    return tensor


@dataclass
class _EpisodeState:
    exact_memory: PublicActionMemory
    causal_memory: PublicCausalRuleMemory
    trace: PublicTransitionTrace
    attributed: PublicActionAttributedTrace
    belief: PublicGoalConsistencyBelief
    hidden: Tensor
    previous_feedback: list[float]


def _new_episode_state(model: NativeR20AdvantageConsensus, task: Any) -> _EpisodeState:
    return _EpisodeState(
        exact_memory=PublicActionMemory(len(task.action_descriptions)),
        causal_memory=PublicCausalRuleMemory(),
        trace=PublicTransitionTrace(max_length=model.parent.parent.parent.trace_length),
        attributed=PublicActionAttributedTrace(max_length=model.parent.parent.attribution_length),
        belief=PublicGoalConsistencyBelief(),
        hidden=model.parent.init_parent_hidden(1),
        previous_feedback=[0.0, 0.0, 0.0],
    )


def _encode_step(model: NativeR20AdvantageConsensus, state: _EpisodeState, observation: Mapping[str, Any]):
    state.belief.update(observation)
    global_features, action_features, valid = encode_public_state(
        observation,
        state.exact_memory,
        previous_feedback=state.previous_feedback,
    )
    trace_features, trace_valid = state.trace.encode()
    attribution_features, attribution_valid = state.attributed.encode()
    with torch.no_grad():
        parent_output = model.parent.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            state.hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
            attribution_features.unsqueeze(0),
            attribution_valid.unsqueeze(0),
        )
    state.hidden = parent_output["next_parent_hidden"].detach()
    posterior = state.belief.encode()
    r11_action, r11_decision = choose_public_causal_action(
        observation=observation,
        exact_memory=state.exact_memory,
        causal_memory=state.causal_memory,
        posterior=posterior,
        parent_logits=parent_output["action_logits"][0],
        horizon=R11_HORIZON,
    )
    causal = build_causal_action_features(
        observation=observation,
        causal_memory=state.causal_memory,
        posterior=posterior,
        r11_action=int(r11_action),
    )
    scores = model.score_from_parent(
        global_features=global_features.unsqueeze(0),
        action_features=action_features.unsqueeze(0),
        valid_actions=valid.unsqueeze(0),
        parent_output=parent_output,
        consistency_posterior=posterior.unsqueeze(0),
        causal_action_features=causal.unsqueeze(0),
        r11_actions=torch.tensor([int(r11_action)], dtype=torch.long),
    )[:, 0, :]
    return global_features, action_features, valid, posterior, int(r11_action), r11_decision, scores


def _advance(state: _EpisodeState, task: Any, observation: Mapping[str, Any], action_features: Tensor, action: int) -> None:
    selected = action_features[int(action)].detach().clone()
    result = task.step(int(action))
    after = result.observation
    state.exact_memory.update(
        action=int(action), before=observation, after=after,
        progress_delta=result.progress_delta, information_gain=result.information_gain, failed=result.failed,
    )
    state.causal_memory.update(action=int(action), before=observation, after=after)
    state.trace.update(
        before=observation, after=after,
        progress_delta=result.progress_delta, information_gain=result.information_gain, failed=result.failed,
    )
    state.attributed.update(
        selected_action_features=selected, before=observation, after=after,
        progress_delta=result.progress_delta, information_gain=result.information_gain, failed=result.failed,
    )
    state.previous_feedback = [
        float(result.progress_delta),
        float(result.information_gain),
        float(result.failed),
    ]


def train_episode(
    model: NativeR20AdvantageConsensus,
    task: Any,
    optimizer: torch.optim.Optimizer,
    *,
    oracle_plan: Any,
    behavior: str,
    pairwise_weight: float,
    max_grad_norm: float,
) -> dict[str, float | int | bool]:
    if getattr(task, "split", None) != "train" or getattr(task, "family", None) != "implicit_goal_regimes":
        raise ValueError("R20 training is implicit_goal_regimes/train only")
    if behavior not in {"teacher", "r11"}:
        raise ValueError("unsupported R20 behavior")
    state = _new_episode_state(model, task)
    total_loss = 0.0
    labelled = 0
    model.train()

    while not task.done:
        observation = task.observe()
        try:
            target = int(public_exploration_teacher(task, state.exact_memory, oracle_plan))
        except RuntimeError:
            break
        _, action_features, valid, _, r11_action, _, scores = _encode_step(model, state, observation)
        target_tensor = torch.tensor([target], dtype=torch.long)
        losses: list[Tensor] = []
        for ensemble_index in range(scores.shape[0]):
            row = scores[ensemble_index]
            ce = F.cross_entropy(row.unsqueeze(0), target_tensor)
            if target != r11_action:
                pair = F.relu(row.new_tensor(1.0) - (row[target] - row[r11_action]))
            else:
                other = row.masked_fill(~valid, torch.finfo(row.dtype).min).clone()
                other[r11_action] = torch.finfo(row.dtype).min
                best_other = other.max()
                pair = F.relu(row.new_tensor(0.5) - (row[r11_action] - best_other))
            losses.append(ce + float(pairwise_weight) * pair)
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.successor_parameters(), float(max_grad_norm))
        optimizer.step()
        total_loss += float(loss.detach().item())
        labelled += 1
        action = target if behavior == "teacher" else r11_action
        _advance(state, task, observation, action_features, action)

    return {
        "loss": total_loss / max(1, labelled),
        "labelled_steps": labelled,
        "behavior_steps": int(task.step_count),
        "solved": bool(task.solved),
    }


def train_policy(
    model: NativeR20AdvantageConsensus,
    *,
    make_task: Any,
    oracle_plan: Any,
    indices: tuple[int, int],
    seed: int,
    learning_rate: float,
    weight_decay: float,
    pairwise_weight: float,
    max_grad_norm: float,
) -> dict[str, Any]:
    optimizer = torch.optim.AdamW(
        model.successor_parameters(),
        lr=float(learning_rate),
        weight_decay=float(weight_decay),
    )
    rng = random.Random(int(seed))
    stages = []
    for epoch, behavior in enumerate(("teacher", "r11"), start=1):
        order = list(range(int(indices[0]), int(indices[1]) + 1))
        rng.shuffle(order)
        rows = []
        for index in order:
            rows.append(train_episode(
                model,
                make_task("implicit_goal_regimes", "train", int(index)),
                optimizer,
                oracle_plan=oracle_plan,
                behavior=behavior,
                pairwise_weight=pairwise_weight,
                max_grad_norm=max_grad_norm,
            ))
        stages.append({
            "epoch": epoch,
            "behavior": behavior,
            "episodes": len(rows),
            "mean_loss": sum(float(r["loss"]) for r in rows) / max(1, len(rows)),
            "labelled_steps": sum(int(r["labelled_steps"]) for r in rows),
            "behavior_solved": sum(int(bool(r["solved"])) for r in rows),
        })
    model.eval()
    return {"seed": int(seed), "train_indices": list(indices), "stages": stages}


def _proposal(scores: Tensor, valid: Tensor, r11_action: int) -> tuple[int | None, float | None]:
    masked = scores.masked_fill(~valid.unsqueeze(0), torch.finfo(scores.dtype).min)
    tops = masked.argmax(dim=-1)
    if not bool((tops == tops[0]).all()):
        return None, None
    action = int(tops[0].item())
    if action == int(r11_action):
        return None, None
    margins = masked[:, action] - masked[:, int(r11_action)]
    return action, float(margins.min().item())


def calibrate_threshold(
    model: NativeR20AdvantageConsensus,
    *,
    make_task: Any,
    oracle_plan: Any,
    indices: tuple[int, int],
    max_support: int,
    minimum_precision: float,
    minimum_count: int,
) -> dict[str, Any]:
    opportunities: list[dict[str, Any]] = []
    model.eval()
    for index in range(int(indices[0]), int(indices[1]) + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        state = _new_episode_state(model, task)
        while not task.done:
            observation = task.observe()
            try:
                teacher = int(public_exploration_teacher(task, state.exact_memory, oracle_plan))
            except RuntimeError:
                break
            _, action_features, valid, _, r11_action, r11_decision, scores = _encode_step(model, state, observation)
            support = int(state.belief.support_size())
            hidden = not isinstance(observation.get("target"), list)
            if hidden and support <= int(max_support) and r11_decision.get("reason") != "r9_public_progress_complete":
                action, margin = _proposal(scores.detach(), valid, r11_action)
                if action is not None and margin is not None:
                    opportunities.append({
                        "margin": float(margin),
                        "correct": bool(int(action) == teacher),
                        "action": int(action),
                        "teacher": teacher,
                        "r11_action": int(r11_action),
                    })
            _advance(state, task, observation, action_features, r11_action)

    best = None
    thresholds = sorted({float(row["margin"]) for row in opportunities})
    for threshold in thresholds:
        selected = [row for row in opportunities if float(row["margin"]) >= threshold]
        if len(selected) < int(minimum_count):
            continue
        correct = sum(int(bool(row["correct"])) for row in selected)
        precision = correct / len(selected)
        if precision + 1e-12 < float(minimum_precision):
            continue
        candidate = (len(selected), precision, -threshold)
        if best is None or candidate > best["rank"]:
            best = {
                "rank": candidate,
                "threshold": float(threshold),
                "selected": len(selected),
                "correct": correct,
                "precision": precision,
            }

    if best is None:
        return {
            "status": "FAIL_CLOSED",
            "max_support": int(max_support),
            "opportunities": len(opportunities),
            "threshold": None,
            "selected": 0,
            "correct": 0,
            "precision": None,
            "minimum_precision": float(minimum_precision),
            "minimum_count": int(minimum_count),
        }
    return {
        "status": "CALIBRATED",
        "max_support": int(max_support),
        "opportunities": len(opportunities),
        "threshold": best["threshold"],
        "selected": best["selected"],
        "correct": best["correct"],
        "precision": best["precision"],
        "minimum_precision": float(minimum_precision),
        "minimum_count": int(minimum_count),
    }


def rollout_r20(
    model: NativeR20AdvantageConsensus,
    task: Any,
    *,
    max_support: int,
    threshold: float | None,
) -> dict[str, Any]:
    state = _new_episode_state(model, task)
    overrides = 0
    proposals = 0
    model.eval()
    while not task.done:
        observation = task.observe()
        _, action_features, valid, _, r11_action, r11_decision, scores = _encode_step(model, state, observation)
        action = int(r11_action)
        hidden = not isinstance(observation.get("target"), list)
        support = int(state.belief.support_size())
        if (
            threshold is not None
            and hidden
            and support <= int(max_support)
            and r11_decision.get("reason") != "r9_public_progress_complete"
        ):
            proposed, _ = _proposal(scores.detach(), valid, r11_action)
            proposals += int(proposed is not None)
            action, decision = consensus_advantage_action(
                scores.detach(),
                valid_actions=valid,
                r11_action=r11_action,
                threshold=float(threshold),
            )
            overrides += int(bool(decision.get("override", False)))
        _advance(state, task, observation, action_features, action)
    return {
        "solved": bool(task.solved),
        "steps": int(task.step_count),
        "overrides_vs_r11": int(overrides),
        "consensus_proposals": int(proposals),
    }


def evaluate_r20(
    model: NativeR20AdvantageConsensus,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    max_support: int,
    threshold: float | None,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R20 evaluation split must be dev/fresh")
    rows = []
    families_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = proposals = 0
    for family in families:
        fs = fst = fov = fpr = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r20(
                model,
                make_task(str(family), str(split), int(index)),
                max_support=int(max_support),
                threshold=threshold,
            )
            fs += int(result["solved"])
            fst += int(result["steps"])
            fov += int(result["overrides_vs_r11"])
            fpr += int(result["consensus_proposals"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            overrides += int(result["overrides_vs_r11"])
            proposals += int(result["consensus_proposals"])
            episodes += 1
            rows.append({"family": str(family), "split": str(split), "index": int(index), **result})
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": fs,
            "steps": fst,
            "overrides_vs_r11": fov,
            "consensus_proposals": fpr,
        }
    return {
        "split": str(split),
        "indices": list(indices),
        "episodes": len(rows),
        "solved": solved,
        "steps": steps,
        "overrides_vs_r11": overrides,
        "consensus_proposals": proposals,
        "families": families_result,
        "rows": rows,
    }


def save_checkpoint(
    model: NativeR20AdvantageConsensus,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    r11_authority_blob_sha: str,
    predev_lock_sha256: str,
    training_summary: Mapping[str, Any],
    calibrations: Mapping[str, Any],
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
        "calibrations": dict(calibrations),
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


def load_checkpoint(path: str | Path, *, parent_checkpoint_path: str | Path):
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != CHECKPOINT_FORMAT:
        raise ValueError("unsupported R20 checkpoint")
    parent, parent_metadata = load_r4_checkpoint(parent_checkpoint_path)
    if parent_metadata["checkpoint_sha256"] != payload["parent_checkpoint_sha256"]:
        raise ValueError("R20 parent checkpoint mismatch")
    if parent_metadata["state_dict_sha256"] != payload["parent_state_dict_sha256"]:
        raise ValueError("R20 parent state mismatch")
    architecture = payload["architecture"]
    model = NativeR20AdvantageConsensus(
        parent,
        ensemble_size=int(architecture["r20_ensemble_size"]),
        posterior_embedding_dim=int(architecture["r20_posterior_embedding_dim"]),
        hidden_dim=int(architecture["r20_hidden_dim"]),
    )
    model.load_successor_state_dict(payload["successor_state_dict"])
    if model.successor_state_sha256() != payload["successor_state_dict_sha256"]:
        raise ValueError("R20 successor state digest mismatch")
    model.eval()
    metadata = {k: v for k, v in payload.items() if k != "successor_state_dict"}
    metadata["checkpoint_sha256"] = sha256_file(path)
    return model, metadata
