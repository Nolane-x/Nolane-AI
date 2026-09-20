from __future__ import annotations

import random
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor
import torch.nn.functional as F

from native_core import PublicActionMemory, encode_public_state, state_dict_sha256
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from public_planner import GOAL_HYPOTHESIS_COUNT, PublicGoalConsistencyBelief
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action
from action_mass_core import (
    NativeR27GoalBeliefEnsemble,
    encode_public_goal_features,
    goal_index,
)

R11_HORIZON = 1
CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r27-action-mass-consensus-v1"


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class PublicEpisodeState:
    exact_memory: PublicActionMemory
    causal_memory: PublicCausalRuleMemory
    trace: PublicTransitionTrace
    attributed: PublicActionAttributedTrace
    belief: PublicGoalConsistencyBelief
    hidden: Tensor
    previous_feedback: list[float]


def _new_state(parent: Any, task: Any) -> PublicEpisodeState:
    return PublicEpisodeState(
        exact_memory=PublicActionMemory(len(task.action_descriptions)),
        causal_memory=PublicCausalRuleMemory(),
        trace=PublicTransitionTrace(max_length=parent.parent.parent.trace_length),
        attributed=PublicActionAttributedTrace(max_length=parent.parent.attribution_length),
        belief=PublicGoalConsistencyBelief(),
        hidden=parent.init_parent_hidden(1),
        previous_feedback=[0.0, 0.0, 0.0],
    )


def _public_step_context(
    parent: Any,
    state: PublicEpisodeState,
    observation: Mapping[str, Any],
):
    state.belief.update(observation)
    global_features, action_features, valid = encode_public_state(
        observation,
        state.exact_memory,
        previous_feedback=state.previous_feedback,
    )
    trace_features, trace_valid = state.trace.encode()
    attribution_features, attribution_valid = state.attributed.encode()
    with torch.no_grad():
        parent_output = parent.forward_step(
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
    public_posterior = state.belief.encode()
    action, decision = choose_public_causal_action(
        observation=observation,
        exact_memory=state.exact_memory,
        causal_memory=state.causal_memory,
        posterior=public_posterior,
        parent_logits=parent_output["action_logits"][0],
        horizon=R11_HORIZON,
    )
    return action_features, parent_output, public_posterior, int(action), decision


def _private_train_goal_label(task: Any) -> int:
    if getattr(task, "split", None) != "train":
        raise ValueError("private goal labels are train-only")
    if getattr(task, "family", None) != "implicit_goal_regimes":
        raise ValueError("private goal labels are hidden-goal-family only")
    if "target" in task.observe():
        raise ValueError("implicit-goal training observation unexpectedly exposes target")
    goal = getattr(task, "_goal", None)
    if not isinstance(goal, tuple) or len(goal) != 3:
        raise ValueError("train-only private goal label unavailable")
    return goal_index(goal)


def _advance(
    *,
    state: PublicEpisodeState,
    task: Any,
    observation: Mapping[str, Any],
    action_features: Tensor,
    action: int,
) -> None:
    selected = action_features[int(action)].detach().clone()
    result = task.step(int(action))
    after = result.observation
    state.exact_memory.update(
        action=int(action),
        before=observation,
        after=after,
        progress_delta=result.progress_delta,
        information_gain=result.information_gain,
        failed=result.failed,
    )
    state.causal_memory.update(action=int(action), before=observation, after=after)
    state.trace.update(
        before=observation,
        after=after,
        progress_delta=result.progress_delta,
        information_gain=result.information_gain,
        failed=result.failed,
    )
    state.attributed.update(
        selected_action_features=selected,
        before=observation,
        after=after,
        progress_delta=result.progress_delta,
        information_gain=result.information_gain,
        failed=result.failed,
    )
    state.previous_feedback = [
        float(result.progress_delta),
        float(result.information_gain),
        float(result.failed),
    ]


def collect_goal_dataset(
    parent: Any,
    *,
    make_task: Any,
    indices: tuple[int, int],
) -> dict[str, Tensor]:
    features: list[Tensor] = []
    supports: list[Tensor] = []
    labels: list[int] = []
    episodes = 0
    for index in range(int(indices[0]), int(indices[1]) + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        label = _private_train_goal_label(task)
        state = _new_state(parent, task)
        episodes += 1
        while not task.done:
            observation = task.observe()
            action_features, _, public_posterior, r11_action, _ = (
                _public_step_context(parent, state, observation)
            )
            support = public_posterior > 0.0
            if not bool(support[label]):
                raise AssertionError("true train goal fell outside exact public support")
            features.append(
                encode_public_goal_features(
                    support_mask=support,
                    observation=dict(observation),
                    previous_feedback=state.previous_feedback,
                )
            )
            supports.append(support.detach().clone())
            labels.append(int(label))
            _advance(
                state=state,
                task=task,
                observation=observation,
                action_features=action_features,
                action=r11_action,
            )
    return {
        "features": torch.stack(features, dim=0),
        "support_mask": torch.stack(supports, dim=0),
        "labels": torch.tensor(labels, dtype=torch.long),
        "episodes": torch.tensor([episodes], dtype=torch.long),
    }


def train_goal_ensemble(
    model: NativeR27GoalBeliefEnsemble,
    dataset: Mapping[str, Tensor],
    *,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
) -> dict[str, Any]:
    features = dataset["features"]
    support = dataset["support_mask"].bool()
    labels = dataset["labels"].long()
    rows = int(features.shape[0])
    summaries: list[dict[str, Any]] = []
    for head_index, head in enumerate(model.heads):
        torch.manual_seed(int(seed) + 97 * head_index)
        optimizer = torch.optim.AdamW(
            head.parameters(),
            lr=float(learning_rate),
            weight_decay=float(weight_decay),
        )
        rng = random.Random(int(seed) + 1009 * head_index)
        history: list[dict[str, float]] = []
        for epoch in range(int(epochs)):
            order = list(range(rows))
            rng.shuffle(order)
            losses: list[float] = []
            correct = 0
            for start in range(0, rows, int(batch_size)):
                ids = order[start : start + int(batch_size)]
                xb = features[ids]
                sb = support[ids]
                yb = labels[ids]
                logits = head(xb).masked_fill(
                    ~sb,
                    torch.finfo(xb.dtype).min,
                )
                loss = F.cross_entropy(logits, yb)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.detach().item()))
                correct += int((logits.detach().argmax(dim=-1) == yb).sum().item())
            history.append(
                {
                    "epoch": float(epoch + 1),
                    "mean_loss": sum(losses) / max(1, len(losses)),
                    "accuracy": correct / max(1, rows),
                }
            )
        summaries.append({"head": head_index, "history": history})
    model.eval()
    return {
        "rows": rows,
        "episodes": int(dataset["episodes"][0].item()),
        "heads": summaries,
    }


def calibrate_temperature(
    model: NativeR27GoalBeliefEnsemble,
    dataset: Mapping[str, Tensor],
    *,
    candidates: Sequence[float],
) -> dict[str, Any]:
    features = dataset["features"]
    support = dataset["support_mask"].bool()
    labels = dataset["labels"].long()
    rows: list[dict[str, float]] = []
    with torch.no_grad():
        raw = torch.stack([head(features) for head in model.heads], dim=0)
        raw = raw.masked_fill(
            ~support.unsqueeze(0),
            torch.finfo(raw.dtype).min,
        )
        for temperature in candidates:
            probabilities = torch.softmax(raw / float(temperature), dim=-1).mean(dim=0)
            true_probability = probabilities[
                torch.arange(labels.shape[0]), labels
            ].clamp_min(1.0e-12)
            nll = float((-true_probability.log()).mean().item())
            accuracy = float(
                (probabilities.argmax(dim=-1) == labels).float().mean().item()
            )
            rows.append(
                {
                    "temperature": float(temperature),
                    "mean_nll": nll,
                    "accuracy": accuracy,
                }
            )
    selected = min(rows, key=lambda row: (row["mean_nll"], row["temperature"]))
    return {
        "selected_temperature": selected["temperature"],
        "candidates": rows,
    }


def _goal_action_map(
    *,
    observation: Mapping[str, Any],
    state: PublicEpisodeState,
    parent_logits: Tensor,
    support_mask: Tensor,
) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for goal_id in torch.nonzero(support_mask, as_tuple=False).flatten().tolist():
        posterior = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.float32)
        posterior[int(goal_id)] = 1.0
        action, _ = choose_public_causal_action(
            observation=observation,
            exact_memory=state.exact_memory,
            causal_memory=state.causal_memory,
            posterior=posterior,
            parent_logits=parent_logits,
            horizon=R11_HORIZON,
        )
        mapping[int(goal_id)] = int(action)
    return mapping


def _action_mass_decision(
    *,
    per_head_goal_probabilities: Tensor,
    goal_actions: Mapping[int, int],
    action_count: int,
) -> tuple[int | None, float, Tensor]:
    if per_head_goal_probabilities.ndim != 2:
        raise ValueError("per-head probabilities must be [heads, goals]")
    masses = torch.zeros(
        per_head_goal_probabilities.shape[0],
        int(action_count),
        dtype=torch.float32,
    )
    for goal_id, action in goal_actions.items():
        masses[:, int(action)] += per_head_goal_probabilities[:, int(goal_id)]
    head_actions = masses.argmax(dim=-1)
    agreed = bool(torch.all(head_actions == head_actions[0]).item())
    if not agreed:
        return None, 0.0, masses
    action = int(head_actions[0].item())
    minimum_mass = float(masses[:, action].min().item())
    return action, minimum_mass, masses


def _evaluate_guard_block(
    parent: Any,
    model: NativeR27GoalBeliefEnsemble,
    *,
    make_task: Any,
    indices: tuple[int, int],
    temperature: float,
    mass_thresholds: Sequence[float],
    max_support: int,
) -> list[dict[str, Any]]:
    stats = [
        {
            "mass_threshold": float(threshold),
            "eligible_rows": 0,
            "override_rows": 0,
            "correct_override_rows": 0,
        }
        for threshold in mass_thresholds
    ]
    for index in range(int(indices[0]), int(indices[1]) + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        label = _private_train_goal_label(task)
        state = _new_state(parent, task)
        while not task.done:
            observation = task.observe()
            action_features, parent_output, public_posterior, r11_action, decision = (
                _public_step_context(parent, state, observation)
            )
            support_mask = public_posterior > 0.0
            support_count = int(support_mask.sum().item())
            if (
                2 <= support_count <= int(max_support)
                and decision.get("reason") != "r9_public_progress_complete"
            ):
                features = encode_public_goal_features(
                    support_mask=support_mask,
                    observation=dict(observation),
                    previous_feedback=state.previous_feedback,
                )
                with torch.no_grad():
                    probabilities = model.per_head_probabilities(
                        features=features,
                        support_mask=support_mask,
                        temperature=float(temperature),
                    )
                goal_actions = _goal_action_map(
                    observation=observation,
                    state=state,
                    parent_logits=parent_output["action_logits"][0],
                    support_mask=support_mask,
                )
                candidate_action, minimum_mass, _ = _action_mass_decision(
                    per_head_goal_probabilities=probabilities,
                    goal_actions=goal_actions,
                    action_count=len(task.action_descriptions),
                )
                teacher_action = int(goal_actions[int(label)])
                if candidate_action is not None:
                    for stat in stats:
                        if minimum_mass < float(stat["mass_threshold"]):
                            continue
                        stat["eligible_rows"] += 1
                        if int(candidate_action) != int(r11_action):
                            stat["override_rows"] += 1
                            stat["correct_override_rows"] += int(
                                int(candidate_action) == teacher_action
                            )
            _advance(
                state=state,
                task=task,
                observation=observation,
                action_features=action_features,
                action=r11_action,
            )
    for stat in stats:
        stat["override_precision"] = (
            stat["correct_override_rows"] / max(1, stat["override_rows"])
        )
    return stats


def fit_robust_action_mass_guard(
    parent: Any,
    model: NativeR27GoalBeliefEnsemble,
    *,
    make_task: Any,
    guard_blocks: Sequence[tuple[int, int]],
    temperature: float,
    mass_thresholds: Sequence[float],
    max_support: int,
    minimum_precision: float,
    minimum_total_override_rows: int,
    minimum_block_override_rows: int,
) -> dict[str, Any]:
    if len(guard_blocks) < 2:
        raise ValueError("robust guard requires at least two disjoint blocks")
    block_results = [
        _evaluate_guard_block(
            parent,
            model,
            make_task=make_task,
            indices=tuple(block),
            temperature=float(temperature),
            mass_thresholds=mass_thresholds,
            max_support=int(max_support),
        )
        for block in guard_blocks
    ]

    candidates: list[dict[str, Any]] = []
    for candidate_index, threshold in enumerate(mass_thresholds):
        blocks: list[dict[str, Any]] = []
        total_override = total_correct = total_eligible = 0
        for block_index, block in enumerate(guard_blocks):
            row = dict(block_results[block_index][candidate_index])
            row["indices"] = [int(block[0]), int(block[1])]
            blocks.append(row)
            total_override += int(row["override_rows"])
            total_correct += int(row["correct_override_rows"])
            total_eligible += int(row["eligible_rows"])
        overall_precision = total_correct / max(1, total_override)
        worst_block_precision = min(
            float(row["override_precision"]) for row in blocks
        )
        block_coverage_ok = all(
            int(row["override_rows"]) >= int(minimum_block_override_rows)
            for row in blocks
        )
        block_precision_ok = all(
            float(row["override_precision"]) >= float(minimum_precision)
            for row in blocks
        )
        eligible = bool(
            total_override >= int(minimum_total_override_rows)
            and overall_precision >= float(minimum_precision)
            and block_coverage_ok
            and block_precision_ok
        )
        candidates.append(
            {
                "mass_threshold": float(threshold),
                "eligible_rows": int(total_eligible),
                "override_rows": int(total_override),
                "correct_override_rows": int(total_correct),
                "override_precision": float(overall_precision),
                "worst_block_precision": float(worst_block_precision),
                "block_coverage_ok": bool(block_coverage_ok),
                "block_precision_ok": bool(block_precision_ok),
                "eligible": eligible,
                "blocks": blocks,
            }
        )

    eligible_candidates = [row for row in candidates if row["eligible"]]
    selected = (
        max(
            eligible_candidates,
            key=lambda row: (
                row["override_rows"],
                row["worst_block_precision"],
                row["override_precision"],
                row["mass_threshold"],
            ),
        )
        if eligible_candidates
        else None
    )
    return {
        "enabled": selected is not None,
        "minimum_override_precision": float(minimum_precision),
        "minimum_total_override_rows": int(minimum_total_override_rows),
        "minimum_block_override_rows": int(minimum_block_override_rows),
        "guard_blocks": [
            [int(block[0]), int(block[1])] for block in guard_blocks
        ],
        "selected": selected,
        "candidates": candidates,
    }

def rollout_r27(
    parent: Any,
    model: NativeR27GoalBeliefEnsemble,
    task: Any,
    *,
    temperature: float,
    mass_threshold: float | None,
    max_support: int,
    max_overrides_per_episode: int,
) -> dict[str, Any]:
    state = _new_state(parent, task)
    overrides = guarded_steps = 0
    while not task.done:
        observation = task.observe()
        action_features, parent_output, public_posterior, r11_action, decision = (
            _public_step_context(parent, state, observation)
        )
        action = int(r11_action)
        hidden = not isinstance(observation.get("target"), list)
        support_mask = public_posterior > 0.0
        support_count = int(support_mask.sum().item())
        if (
            mass_threshold is not None
            and hidden
            and overrides < int(max_overrides_per_episode)
            and 2 <= support_count <= int(max_support)
            and decision.get("reason") != "r9_public_progress_complete"
        ):
            features = encode_public_goal_features(
                support_mask=support_mask,
                observation=dict(observation),
                previous_feedback=state.previous_feedback,
            )
            with torch.no_grad():
                probabilities = model.per_head_probabilities(
                    features=features,
                    support_mask=support_mask,
                    temperature=float(temperature),
                )
            goal_actions = _goal_action_map(
                observation=observation,
                state=state,
                parent_logits=parent_output["action_logits"][0],
                support_mask=support_mask,
            )
            candidate_action, minimum_mass, _ = _action_mass_decision(
                per_head_goal_probabilities=probabilities,
                goal_actions=goal_actions,
                action_count=len(task.action_descriptions),
            )
            if (
                candidate_action is not None
                and minimum_mass >= float(mass_threshold)
            ):
                guarded_steps += 1
                if int(candidate_action) != int(r11_action):
                    action = int(candidate_action)
                    overrides += 1

        _advance(
            state=state,
            task=task,
            observation=observation,
            action_features=action_features,
            action=action,
        )

    return {
        "solved": bool(task.solved),
        "steps": int(task.step_count),
        "overrides_vs_r11": int(overrides),
        "guarded_steps": int(guarded_steps),
    }


def evaluate_r27(
    parent: Any,
    model: NativeR27GoalBeliefEnsemble,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    temperature: float,
    mass_threshold: float | None,
    max_support: int,
    max_overrides_per_episode: int,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R27 evaluation split must be dev/fresh")
    rows: list[dict[str, Any]] = []
    families_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = guarded = 0
    for family in families:
        fs = fst = fov = fguard = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r27(
                parent,
                model,
                make_task(str(family), str(split), int(index)),
                temperature=float(temperature),
                mass_threshold=mass_threshold,
                max_support=int(max_support),
                max_overrides_per_episode=int(max_overrides_per_episode),
            )
            fs += int(result["solved"])
            fst += int(result["steps"])
            fov += int(result["overrides_vs_r11"])
            fguard += int(result["guarded_steps"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            overrides += int(result["overrides_vs_r11"])
            guarded += int(result["guarded_steps"])
            episodes += 1
            rows.append(
                {
                    "family": str(family),
                    "split": str(split),
                    "index": int(index),
                    **result,
                }
            )
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": fs,
            "steps": fst,
            "overrides_vs_r11": fov,
            "guarded_steps": fguard,
        }
    return {
        "split": str(split),
        "indices": [int(indices[0]), int(indices[1])],
        "episodes": len(rows),
        "solved": solved,
        "steps": steps,
        "overrides_vs_r11": overrides,
        "guarded_steps": guarded,
        "families": families_result,
        "rows": rows,
    }


def save_checkpoint(
    model: NativeR27GoalBeliefEnsemble,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    r11_authority_blob_sha: str,
    predev_lock_sha256: str,
    training_summary: Mapping[str, Any],
    temperature_calibration: Mapping[str, Any],
    action_guard: Mapping[str, Any],
) -> dict[str, Any]:
    state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in model.state_dict().items()
    }
    payload = {
        "format": CHECKPOINT_FORMAT,
        "status": "TRAINED_DEV_ONLY_FRESH_UNOPENED",
        "architecture": model.architecture(),
        "successor_parameters": model.parameter_count(),
        "physical_parameters": 877542 + model.parameter_count(),
        "parent_checkpoint_sha256": str(parent_checkpoint_sha256),
        "parent_state_dict_sha256": str(parent_state_dict_sha256),
        "r11_authority_blob_sha": str(r11_authority_blob_sha),
        "predev_lock_sha256": str(predev_lock_sha256),
        "training_summary": dict(training_summary),
        "temperature_calibration": dict(temperature_calibration),
        "action_guard": dict(action_guard),
        "state_dict_sha256": state_dict_sha256(state),
        "state_dict": state,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, destination)
    return {
        **{key: value for key, value in payload.items() if key != "state_dict"},
        "checkpoint_sha256": sha256_file(destination),
    }
