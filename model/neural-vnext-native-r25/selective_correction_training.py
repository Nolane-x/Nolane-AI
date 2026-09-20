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
from selective_correction_core import (
    NativeR25SelectiveCorrectionEnsemble,
    encode_public_base_features,
)

R11_HORIZON = 1
CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r25-selective-error-correction-v1"


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
    return action_features, valid, parent_output, public_posterior, int(action), decision


def _private_train_goal_index(task: Any) -> int:
    if getattr(task, "split", None) != "train":
        raise ValueError("private goal labels are train-only")
    if getattr(task, "family", None) != "implicit_goal_regimes":
        raise ValueError("private goal labels are hidden-goal-family only")
    if "target" in task.observe():
        raise ValueError("implicit-goal training observation unexpectedly exposes target")
    goal = getattr(task, "_goal", None)
    if not isinstance(goal, tuple) or len(goal) != 3:
        raise ValueError("train-only private goal unavailable")
    a, b, c = (int(value) for value in goal)
    return a * 25 + b * 5 + c


def _teacher_action(
    *,
    goal_index: int,
    observation: Mapping[str, Any],
    state: PublicEpisodeState,
    parent_logits: Tensor,
) -> int:
    posterior = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.float32)
    posterior[int(goal_index)] = 1.0
    action, _ = choose_public_causal_action(
        observation=observation,
        exact_memory=state.exact_memory,
        causal_memory=state.causal_memory,
        posterior=posterior,
        parent_logits=parent_logits,
        horizon=R11_HORIZON,
    )
    return int(action)


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


def collect_training_rows(
    parent: Any,
    *,
    make_task: Any,
    indices: tuple[int, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(int(indices[0]), int(indices[1]) + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        goal_index = _private_train_goal_index(task)
        state = _new_state(parent, task)
        while not task.done:
            observation = task.observe()
            action_features, valid, parent_output, public_posterior, r11_action, decision = (
                _public_step_context(parent, state, observation)
            )
            support_mask = public_posterior > 0.0
            if not bool(support_mask[int(goal_index)]):
                raise AssertionError("true goal fell outside exact public support")
            teacher = _teacher_action(
                goal_index=int(goal_index),
                observation=observation,
                state=state,
                parent_logits=parent_output["action_logits"][0],
            )
            base = encode_public_base_features(
                support_mask=support_mask,
                observation=observation,
                previous_feedback=state.previous_feedback,
                r11_decision=decision,
            )
            rows.append(
                {
                    "base_features": base.detach().clone(),
                    "r11_action_features": action_features[int(r11_action)].detach().clone(),
                    "action_features": action_features.detach().clone(),
                    "valid": valid.detach().clone(),
                    "r11_action": int(r11_action),
                    "teacher_action": int(teacher),
                    "mistake": int(int(teacher) != int(r11_action)),
                    "support_count": int(support_mask.sum().item()),
                    "r11_reason": str(decision.get("reason", "")),
                }
            )
            _advance(
                state=state,
                task=task,
                observation=observation,
                action_features=action_features,
                action=r11_action,
            )
    return rows


def train_selective_ensemble(
    model: NativeR25SelectiveCorrectionEnsemble,
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    epochs: int,
    detector_batch_size: int,
    learning_rate: float,
    weight_decay: float,
) -> dict[str, Any]:
    positives = sum(int(row["mistake"]) for row in rows)
    negatives = len(rows) - positives
    pos_weight = max(1.0, negatives / max(1, positives))
    correction_rows = [row for row in rows if int(row["mistake"]) == 1]
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
            detector_order = list(range(len(rows)))
            rng.shuffle(detector_order)
            detector_losses: list[float] = []
            head.train()
            for start in range(0, len(detector_order), int(detector_batch_size)):
                batch_ids = detector_order[start : start + int(detector_batch_size)]
                base = torch.stack(
                    [rows[i]["base_features"] for i in batch_ids], dim=0
                )
                r11 = torch.stack(
                    [rows[i]["r11_action_features"] for i in batch_ids], dim=0
                )
                labels = torch.tensor(
                    [float(rows[i]["mistake"]) for i in batch_ids],
                    dtype=torch.float32,
                )
                logits = head.detector_logit(base, r11)
                loss = F.binary_cross_entropy_with_logits(
                    logits,
                    labels,
                    pos_weight=torch.tensor(float(pos_weight)),
                )
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                detector_losses.append(float(loss.detach().item()))

            correction_order = list(range(len(correction_rows)))
            rng.shuffle(correction_order)
            correction_losses: list[float] = []
            correction_correct = 0
            for row_id in correction_order:
                row = correction_rows[row_id]
                logits = head.correction_logits(
                    row["base_features"],
                    row["r11_action_features"],
                    row["action_features"],
                )
                valid = row["valid"].bool()
                masked = logits.masked_fill(~valid, torch.finfo(logits.dtype).min)
                label = torch.tensor([int(row["teacher_action"])], dtype=torch.long)
                loss = F.cross_entropy(masked.unsqueeze(0), label)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                correction_losses.append(float(loss.detach().item()))
                correction_correct += int(
                    int(masked.detach().argmax().item()) == int(row["teacher_action"])
                )

            history.append(
                {
                    "epoch": float(epoch + 1),
                    "detector_mean_loss": sum(detector_losses)
                    / max(1, len(detector_losses)),
                    "corrector_mean_loss": sum(correction_losses)
                    / max(1, len(correction_losses)),
                    "corrector_train_accuracy": correction_correct
                    / max(1, len(correction_rows)),
                }
            )
        summaries.append({"head": head_index, "history": history})

    model.eval()
    return {
        "rows": len(rows),
        "mistake_rows": positives,
        "non_mistake_rows": negatives,
        "detector_pos_weight": pos_weight,
        "heads": summaries,
    }


def fit_selective_guard(
    model: NativeR25SelectiveCorrectionEnsemble,
    rows: Sequence[Mapping[str, Any]],
    *,
    thresholds: Sequence[float],
    max_support: int,
    minimum_precision: float,
    minimum_override_rows: int,
) -> dict[str, Any]:
    stats = [
        {
            "threshold": float(threshold),
            "eligible_rows": 0,
            "override_rows": 0,
            "correct_override_rows": 0,
        }
        for threshold in thresholds
    ]
    with torch.no_grad():
        for row in rows:
            if int(row["support_count"]) > int(max_support):
                continue
            if row["r11_reason"] == "r9_public_progress_complete":
                continue
            detector_probs, correction_logits = model.predict(
                base_features=row["base_features"],
                r11_action_features=row["r11_action_features"],
                action_features=row["action_features"],
            )
            valid = row["valid"].bool()
            correction_logits = correction_logits.masked_fill(
                ~valid.unsqueeze(0),
                torch.finfo(correction_logits.dtype).min,
            )
            predicted = correction_logits.argmax(dim=-1)
            agreed = bool(torch.all(predicted == predicted[0]).item())
            if not agreed:
                continue
            correction = int(predicted[0].item())
            min_detector = float(detector_probs.min().item())
            for stat in stats:
                if min_detector < float(stat["threshold"]):
                    continue
                stat["eligible_rows"] += 1
                if correction != int(row["r11_action"]):
                    stat["override_rows"] += 1
                    stat["correct_override_rows"] += int(
                        correction == int(row["teacher_action"])
                    )

    candidates: list[dict[str, Any]] = []
    for stat in stats:
        precision = stat["correct_override_rows"] / max(1, stat["override_rows"])
        eligible = bool(
            stat["override_rows"] >= int(minimum_override_rows)
            and precision >= float(minimum_precision)
        )
        candidates.append(
            {
                **stat,
                "override_precision": precision,
                "eligible": eligible,
            }
        )
    eligible_candidates = [row for row in candidates if row["eligible"]]
    selected = (
        max(
            eligible_candidates,
            key=lambda row: (
                row["override_rows"],
                row["override_precision"],
                row["threshold"],
            ),
        )
        if eligible_candidates
        else None
    )
    return {
        "enabled": selected is not None,
        "minimum_override_precision": float(minimum_precision),
        "minimum_override_rows": int(minimum_override_rows),
        "selected": selected,
        "candidates": candidates,
    }


def rollout_r25(
    parent: Any,
    model: NativeR25SelectiveCorrectionEnsemble,
    task: Any,
    *,
    threshold: float | None,
    max_support: int,
    max_overrides_per_episode: int,
) -> dict[str, Any]:
    state = _new_state(parent, task)
    overrides = guarded_steps = 0
    while not task.done:
        observation = task.observe()
        action_features, valid, parent_output, public_posterior, r11_action, decision = (
            _public_step_context(parent, state, observation)
        )
        action = int(r11_action)
        hidden = not isinstance(observation.get("target"), list)
        support_mask = public_posterior > 0.0
        support_count = int(support_mask.sum().item())

        if (
            threshold is not None
            and hidden
            and overrides < int(max_overrides_per_episode)
            and support_count <= int(max_support)
            and decision.get("reason") != "r9_public_progress_complete"
        ):
            base = encode_public_base_features(
                support_mask=support_mask,
                observation=observation,
                previous_feedback=state.previous_feedback,
                r11_decision=decision,
            )
            detector_probs, correction_logits = model.predict(
                base_features=base,
                r11_action_features=action_features[int(r11_action)],
                action_features=action_features,
            )
            correction_logits = correction_logits.masked_fill(
                ~valid.bool().unsqueeze(0),
                torch.finfo(correction_logits.dtype).min,
            )
            predicted = correction_logits.argmax(dim=-1)
            agreed = bool(torch.all(predicted == predicted[0]).item())
            min_detector = float(detector_probs.min().item())
            if agreed and min_detector >= float(threshold):
                guarded_steps += 1
                correction = int(predicted[0].item())
                if correction != int(r11_action):
                    action = correction
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


def evaluate_r25(
    parent: Any,
    model: NativeR25SelectiveCorrectionEnsemble,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    threshold: float | None,
    max_support: int,
    max_overrides_per_episode: int,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R25 evaluation split must be dev/fresh")
    rows: list[dict[str, Any]] = []
    families_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = guarded = 0
    for family in families:
        fs = fst = fov = fguard = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r25(
                parent,
                model,
                make_task(str(family), str(split), int(index)),
                threshold=threshold,
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
    model: NativeR25SelectiveCorrectionEnsemble,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    r11_authority_blob_sha: str,
    predev_lock_sha256: str,
    training_summary: Mapping[str, Any],
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
