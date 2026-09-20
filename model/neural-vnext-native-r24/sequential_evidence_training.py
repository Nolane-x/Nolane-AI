from __future__ import annotations

import copy
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
from sequential_evidence_core import (
    NativeR24SequentialEvidenceEnsemble,
    encode_transition_evidence,
    goal_index,
)

R11_HORIZON = 1
CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r24-sequential-evidence-filter-v1"


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
    cumulative_logits: Tensor
    evidence_steps: int = 0


def _new_state(
    parent: Any,
    task: Any,
    *,
    ensemble_size: int,
) -> PublicEpisodeState:
    return PublicEpisodeState(
        exact_memory=PublicActionMemory(len(task.action_descriptions)),
        causal_memory=PublicCausalRuleMemory(),
        trace=PublicTransitionTrace(max_length=parent.parent.parent.trace_length),
        attributed=PublicActionAttributedTrace(max_length=parent.parent.attribution_length),
        belief=PublicGoalConsistencyBelief(),
        hidden=parent.init_parent_hidden(1),
        previous_feedback=[0.0, 0.0, 0.0],
        cumulative_logits=torch.zeros(
            int(ensemble_size), GOAL_HYPOTHESIS_COUNT, dtype=torch.float32
        ),
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


def _support_after_transition(
    state: PublicEpisodeState,
    after: Mapping[str, Any],
) -> Tensor:
    next_belief = copy.deepcopy(state.belief)
    next_belief.update(after)
    return next_belief.encode() > 0.0


def _apply_transition(
    *,
    state: PublicEpisodeState,
    task: Any,
    observation: Mapping[str, Any],
    action_features: Tensor,
    action: int,
    model: NativeR24SequentialEvidenceEnsemble | None,
) -> tuple[Tensor, Tensor]:
    selected = action_features[int(action)].detach().clone()
    result = task.step(int(action))
    after = result.observation
    evidence_feature = encode_transition_evidence(
        before=dict(observation),
        after=dict(after),
        selected_action_features=selected,
        progress_delta=float(result.progress_delta),
        information_gain=float(result.information_gain),
        failed=bool(result.failed),
    )
    support_after = _support_after_transition(state, after)

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
    if model is not None:
        with torch.no_grad():
            increment = model.evidence_logits(evidence_feature.unsqueeze(0))[:, 0, :]
        state.cumulative_logits = state.cumulative_logits + increment.detach()
        state.evidence_steps += 1
    return evidence_feature, support_after


def collect_evidence_episodes(
    parent: Any,
    *,
    make_task: Any,
    indices: tuple[int, int],
    ensemble_size: int,
) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for index in range(int(indices[0]), int(indices[1]) + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        label = _private_train_goal_label(task)
        state = _new_state(parent, task, ensemble_size=int(ensemble_size))
        features: list[Tensor] = []
        supports: list[Tensor] = []
        while not task.done:
            observation = task.observe()
            action_features, _, public_posterior, r11_action, _ = _public_step_context(
                parent, state, observation
            )
            if not bool((public_posterior > 0.0)[label]):
                raise AssertionError("true goal fell outside exact public support")
            feature, support_after = _apply_transition(
                state=state,
                task=task,
                observation=observation,
                action_features=action_features,
                action=r11_action,
                model=None,
            )
            if not bool(support_after[label]):
                raise AssertionError("true goal fell outside post-transition support")
            features.append(feature)
            supports.append(support_after.detach().clone())
        episodes.append(
            {
                "index": int(index),
                "label": int(label),
                "features": torch.stack(features, dim=0),
                "support_mask": torch.stack(supports, dim=0),
            }
        )
    return episodes


def train_evidence_ensemble(
    model: NativeR24SequentialEvidenceEnsemble,
    episodes: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    epochs: int,
    learning_rate: float,
    weight_decay: float,
) -> dict[str, Any]:
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
            order = list(range(len(episodes)))
            rng.shuffle(order)
            losses: list[float] = []
            final_correct = 0
            for episode_id in order:
                episode = episodes[episode_id]
                features = episode["features"]
                supports = episode["support_mask"].bool()
                label = int(episode["label"])
                increments = head(features)
                cumulative = increments.cumsum(dim=0)
                masked = cumulative.masked_fill(
                    ~supports,
                    torch.finfo(cumulative.dtype).min,
                )
                labels = torch.full(
                    (masked.shape[0],), label, dtype=torch.long
                )
                loss = F.cross_entropy(masked, labels)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.detach().item()))
                final_correct += int(int(masked[-1].detach().argmax().item()) == label)
            history.append(
                {
                    "epoch": float(epoch + 1),
                    "mean_loss": sum(losses) / max(1, len(losses)),
                    "final_goal_accuracy": final_correct / max(1, len(episodes)),
                }
            )
        summaries.append({"head": head_index, "history": history})
    model.eval()
    return {
        "episodes": len(episodes),
        "transition_rows": sum(int(ep["features"].shape[0]) for ep in episodes),
        "heads": summaries,
    }


def _episode_probabilities(
    model: NativeR24SequentialEvidenceEnsemble,
    episode: Mapping[str, Any],
    *,
    temperature: float,
) -> Tensor:
    features = episode["features"]
    supports = episode["support_mask"].bool()
    with torch.no_grad():
        increments = model.evidence_logits(features)
        cumulative = increments.cumsum(dim=1)
        masked = cumulative.masked_fill(
            ~supports.unsqueeze(0),
            torch.finfo(cumulative.dtype).min,
        )
        per_head = torch.softmax(masked / float(temperature), dim=-1)
        mean = per_head.mean(dim=0) * supports.float()
        mean = mean / mean.sum(dim=-1, keepdim=True).clamp_min(1.0e-12)
    return mean


def calibrate_temperature(
    model: NativeR24SequentialEvidenceEnsemble,
    episodes: Sequence[Mapping[str, Any]],
    *,
    candidates: Sequence[float],
) -> dict[str, Any]:
    rows: list[dict[str, float]] = []
    for value in candidates:
        total_nll = 0.0
        total_rows = 0
        final_correct = 0
        for episode in episodes:
            mean = _episode_probabilities(model, episode, temperature=float(value))
            label = int(episode["label"])
            chosen = mean[:, label].clamp_min(1.0e-12)
            total_nll += float((-chosen.log()).sum().item())
            total_rows += int(chosen.numel())
            final_correct += int(int(mean[-1].argmax().item()) == label)
        rows.append(
            {
                "temperature": float(value),
                "mean_nll": total_nll / max(1, total_rows),
                "final_goal_accuracy": final_correct / max(1, len(episodes)),
            }
        )
    selected = min(rows, key=lambda row: (row["mean_nll"], row["temperature"]))
    return {"selected_temperature": selected["temperature"], "candidates": rows}


def _action_for_goal(
    *,
    goal_index_value: int,
    observation: Mapping[str, Any],
    state: PublicEpisodeState,
    parent_logits: Tensor,
) -> int:
    posterior = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.float32)
    posterior[int(goal_index_value)] = 1.0
    action, _ = choose_public_causal_action(
        observation=observation,
        exact_memory=state.exact_memory,
        causal_memory=state.causal_memory,
        posterior=posterior,
        parent_logits=parent_logits,
        horizon=R11_HORIZON,
    )
    return int(action)


def _neural_candidate_action(
    *,
    model: NativeR24SequentialEvidenceEnsemble,
    state: PublicEpisodeState,
    support_mask: Tensor,
    temperature: float,
    threshold: float,
    observation: Mapping[str, Any],
    parent_logits: Tensor,
) -> tuple[int | None, dict[str, Any]]:
    mean, per_head = model.posterior(
        cumulative_logits=state.cumulative_logits,
        support_mask=support_mask,
        temperature=float(temperature),
    )
    head_top = per_head.argmax(dim=-1)
    agreed = bool(torch.all(head_top == head_top[0]).item())
    top_goal = int(mean.argmax().item())
    confidence = float(mean[top_goal].item())
    if not agreed or int(head_top[0].item()) != top_goal or confidence < float(threshold):
        return None, {
            "agreed": agreed,
            "top_goal": top_goal,
            "confidence": confidence,
        }
    action, _ = choose_public_causal_action(
        observation=observation,
        exact_memory=state.exact_memory,
        causal_memory=state.causal_memory,
        posterior=mean,
        parent_logits=parent_logits,
        horizon=R11_HORIZON,
    )
    return int(action), {
        "agreed": True,
        "top_goal": top_goal,
        "confidence": confidence,
    }


def fit_action_guard(
    parent: Any,
    model: NativeR24SequentialEvidenceEnsemble,
    *,
    make_task: Any,
    indices: tuple[int, int],
    temperature: float,
    thresholds: Sequence[float],
    max_support: int,
    minimum_evidence_steps: int,
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
    for index in range(int(indices[0]), int(indices[1]) + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        label = _private_train_goal_label(task)
        state = _new_state(parent, task, ensemble_size=model.ensemble_size)
        while not task.done:
            observation = task.observe()
            action_features, parent_output, public_posterior, r11_action, r11_decision = (
                _public_step_context(parent, state, observation)
            )
            support_mask = public_posterior > 0.0
            support_count = int(support_mask.sum().item())
            teacher_action = None
            if (
                state.evidence_steps >= int(minimum_evidence_steps)
                and 2 <= support_count <= int(max_support)
                and r11_decision.get("reason") != "r9_public_progress_complete"
            ):
                teacher_action = _action_for_goal(
                    goal_index_value=label,
                    observation=observation,
                    state=state,
                    parent_logits=parent_output["action_logits"][0],
                )
                for row in stats:
                    candidate_action, info = _neural_candidate_action(
                        model=model,
                        state=state,
                        support_mask=support_mask,
                        temperature=float(temperature),
                        threshold=float(row["threshold"]),
                        observation=observation,
                        parent_logits=parent_output["action_logits"][0],
                    )
                    if candidate_action is None:
                        continue
                    row["eligible_rows"] += 1
                    if int(candidate_action) != int(r11_action):
                        row["override_rows"] += 1
                        row["correct_override_rows"] += int(
                            int(candidate_action) == int(teacher_action)
                        )
            _apply_transition(
                state=state,
                task=task,
                observation=observation,
                action_features=action_features,
                action=r11_action,
                model=model,
            )

    candidates: list[dict[str, Any]] = []
    for row in stats:
        precision = row["correct_override_rows"] / max(1, row["override_rows"])
        eligible = bool(
            row["override_rows"] >= int(minimum_override_rows)
            and precision >= float(minimum_precision)
        )
        candidates.append(
            {
                **row,
                "override_precision": precision,
                "eligible": eligible,
            }
        )
    eligible_rows = [row for row in candidates if row["eligible"]]
    selected = (
        max(
            eligible_rows,
            key=lambda row: (
                row["override_rows"],
                row["override_precision"],
                row["threshold"],
            ),
        )
        if eligible_rows
        else None
    )
    return {
        "enabled": selected is not None,
        "minimum_override_precision": float(minimum_precision),
        "minimum_override_rows": int(minimum_override_rows),
        "selected": selected,
        "candidates": candidates,
    }


def rollout_r24(
    parent: Any,
    model: NativeR24SequentialEvidenceEnsemble,
    task: Any,
    *,
    temperature: float,
    threshold: float | None,
    max_support: int,
    minimum_evidence_steps: int,
    max_overrides_per_episode: int,
) -> dict[str, Any]:
    state = _new_state(parent, task, ensemble_size=model.ensemble_size)
    overrides = guarded_steps = 0
    while not task.done:
        observation = task.observe()
        action_features, parent_output, public_posterior, r11_action, r11_decision = (
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
            and state.evidence_steps >= int(minimum_evidence_steps)
            and 2 <= support_count <= int(max_support)
            and r11_decision.get("reason") != "r9_public_progress_complete"
        ):
            candidate_action, _ = _neural_candidate_action(
                model=model,
                state=state,
                support_mask=support_mask,
                temperature=float(temperature),
                threshold=float(threshold),
                observation=observation,
                parent_logits=parent_output["action_logits"][0],
            )
            if candidate_action is not None:
                guarded_steps += 1
                if int(candidate_action) != int(r11_action):
                    action = int(candidate_action)
                    overrides += 1

        _apply_transition(
            state=state,
            task=task,
            observation=observation,
            action_features=action_features,
            action=action,
            model=model,
        )
    return {
        "solved": bool(task.solved),
        "steps": int(task.step_count),
        "overrides_vs_r11": int(overrides),
        "guarded_steps": int(guarded_steps),
        "evidence_steps": int(state.evidence_steps),
    }


def evaluate_r24(
    parent: Any,
    model: NativeR24SequentialEvidenceEnsemble,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    temperature: float,
    threshold: float | None,
    max_support: int,
    minimum_evidence_steps: int,
    max_overrides_per_episode: int,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R24 evaluation split must be dev/fresh")
    rows: list[dict[str, Any]] = []
    families_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = guarded = 0
    for family in families:
        fs = fst = fov = fguard = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r24(
                parent,
                model,
                make_task(str(family), str(split), int(index)),
                temperature=float(temperature),
                threshold=threshold,
                max_support=int(max_support),
                minimum_evidence_steps=int(minimum_evidence_steps),
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
    model: NativeR24SequentialEvidenceEnsemble,
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


def load_checkpoint(
    path: str | Path,
) -> tuple[NativeR24SequentialEvidenceEnsemble, dict[str, Any]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != CHECKPOINT_FORMAT:
        raise ValueError("unsupported R24 checkpoint")
    architecture = payload["architecture"]
    model = NativeR24SequentialEvidenceEnsemble(
        ensemble_size=int(architecture["r24_ensemble_size"]),
        hidden_dim=int(architecture["r24_hidden_dim"]),
    )
    model.load_state_dict(payload["state_dict"], strict=True)
    if model.state_sha256() != payload["state_dict_sha256"]:
        raise ValueError("R24 state digest mismatch")
    model.eval()
    metadata = {key: value for key, value in payload.items() if key != "state_dict"}
    metadata["checkpoint_sha256"] = sha256_file(path)
    return model, metadata
