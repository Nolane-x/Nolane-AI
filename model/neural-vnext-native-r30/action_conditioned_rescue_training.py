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
from public_planner import GOAL_HYPOTHESIS_COUNT, GOAL_TABLE, PublicGoalConsistencyBelief
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action
from action_conditioned_rescue_core import (
    HARM_CLASS,
    NEUTRAL_CLASS,
    RESCUE_CLASS,
    NativeR30ActionConditionedRescueEnsemble,
    encode_action_rescue_features,
    encode_public_goal_features,
    goal_index,
)

R11_HORIZON = 1
CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r30-action-conditioned-rescue-v1"


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
            action_features, _, _, public_posterior, r11_action, _ = (
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
    model: NativeR30ActionConditionedRescueEnsemble,
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
    for head_index, head in enumerate(model.goal_heads):
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
                logits = head(xb).masked_fill(~sb, torch.finfo(xb.dtype).min)
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
    model: NativeR30ActionConditionedRescueEnsemble,
    dataset: Mapping[str, Tensor],
    *,
    candidates: Sequence[float],
) -> dict[str, Any]:
    features = dataset["features"]
    support = dataset["support_mask"].bool()
    labels = dataset["labels"].long()
    rows: list[dict[str, float]] = []
    with torch.no_grad():
        raw = torch.stack([head(features) for head in model.goal_heads], dim=0)
        raw = raw.masked_fill(~support.unsqueeze(0), torch.finfo(raw.dtype).min)
        for temperature in candidates:
            probabilities = torch.softmax(raw / float(temperature), dim=-1).mean(dim=0)
            true_probability = probabilities[
                torch.arange(labels.shape[0]), labels
            ].clamp_min(1.0e-12)
            rows.append(
                {
                    "temperature": float(temperature),
                    "mean_nll": float((-true_probability.log()).mean().item()),
                    "accuracy": float(
                        (probabilities.argmax(dim=-1) == labels).float().mean().item()
                    ),
                }
            )
    selected = min(rows, key=lambda row: (row["mean_nll"], row["temperature"]))
    return {"selected_temperature": selected["temperature"], "candidates": rows}


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


def _action_masses(
    *,
    per_head_goal_probabilities: Tensor,
    goal_actions: Mapping[int, int],
    action_count: int,
) -> Tensor:
    masses = torch.zeros(
        per_head_goal_probabilities.shape[0],
        int(action_count),
        dtype=torch.float32,
    )
    for goal_id, action in goal_actions.items():
        masses[:, int(action)] += per_head_goal_probabilities[:, int(goal_id)]
    return masses


def _expected_distance(state: Tensor, posterior: Tensor) -> float:
    distances = torch.remainder(
        GOAL_TABLE - state.unsqueeze(0),
        5,
    ).sum(dim=1).float()
    posterior = posterior.float()
    posterior = posterior / posterior.sum().clamp_min(1.0e-12)
    return float((posterior * distances).sum().item())


def _candidate_feature_rows(
    model: NativeR30ActionConditionedRescueEnsemble,
    *,
    observation: Mapping[str, Any],
    state: PublicEpisodeState,
    action_features: Tensor,
    valid_actions: Tensor,
    parent_logits: Tensor,
    public_posterior: Tensor,
    r11_action: int,
    temperature: float,
    max_support: int,
) -> list[dict[str, Any]]:
    support_mask = public_posterior > 0.0
    support_count = int(support_mask.sum().item())
    if not (2 <= support_count <= int(max_support)):
        return []

    public_features = encode_public_goal_features(
        support_mask=support_mask,
        observation=dict(observation),
        previous_feedback=state.previous_feedback,
    )
    with torch.no_grad():
        probabilities = model.per_head_goal_probabilities(
            features=public_features,
            support_mask=support_mask,
            temperature=float(temperature),
        )
    goal_actions = _goal_action_map(
        observation=observation,
        state=state,
        parent_logits=parent_logits,
        support_mask=support_mask,
    )
    masses = _action_masses(
        per_head_goal_probabilities=probabilities,
        goal_actions=goal_actions,
        action_count=int(action_features.shape[0]),
    )

    current_state = torch.tensor(
        [int(v) for v in observation["state"]], dtype=torch.long
    )
    mean_posterior = probabilities.mean(dim=0)
    current_distance = _expected_distance(current_state, mean_posterior)
    context = state.exact_memory.context_key(observation)
    r11_next, r11_rule_count = state.causal_memory.predict_certified(
        context=context,
        state=current_state,
        action=int(r11_action),
    )
    r11_certified = r11_next is not None
    r11_distance = (
        _expected_distance(r11_next, mean_posterior)
        if r11_next is not None
        else current_distance
    )
    r11_mass_values = masses[:, int(r11_action)]
    r11_mean_mass = float(r11_mass_values.mean().item())
    r11_mass_spread = float(
        (r11_mass_values.max() - r11_mass_values.min()).item()
    )
    r11_seen = state.exact_memory.seen_in_context(observation, int(r11_action))

    rows: list[dict[str, Any]] = []
    for candidate_action in range(int(action_features.shape[0])):
        if int(candidate_action) == int(r11_action):
            continue
        if not bool(valid_actions[int(candidate_action)].item()):
            continue

        candidate_next, candidate_rule_count = state.causal_memory.predict_certified(
            context=context,
            state=current_state,
            action=int(candidate_action),
        )
        candidate_certified = candidate_next is not None
        candidate_distance = (
            _expected_distance(candidate_next, mean_posterior)
            if candidate_next is not None
            else current_distance
        )
        candidate_mass_values = masses[:, int(candidate_action)]
        candidate_min_mass = float(candidate_mass_values.min().item())
        candidate_mean_mass = float(candidate_mass_values.mean().item())
        candidate_mass_spread = float(
            (candidate_mass_values.max() - candidate_mass_values.min()).item()
        )
        mass_margin = candidate_mean_mass - r11_mean_mass
        distance_advantage = r11_distance - candidate_distance
        rule_count_advantage = float(candidate_rule_count - r11_rule_count)
        parent_logit_margin = float(
            torch.tanh(
                (
                    parent_logits[int(candidate_action)]
                    - parent_logits[int(r11_action)]
                )
                / 4.0
            ).item()
        )
        candidate_seen = state.exact_memory.seen_in_context(
            observation, int(candidate_action)
        )

        features = encode_action_rescue_features(
            public_goal_features=public_features,
            r11_action_features=action_features[int(r11_action)],
            candidate_action_features=action_features[int(candidate_action)],
            r11_next_state=r11_next,
            candidate_next_state=candidate_next,
            support_count=support_count,
            candidate_min_mass=candidate_min_mass,
            candidate_mean_mass=candidate_mean_mass,
            r11_mean_mass=r11_mean_mass,
            mass_margin=mass_margin,
            candidate_mass_spread=candidate_mass_spread,
            r11_mass_spread=r11_mass_spread,
            parent_logit_margin=parent_logit_margin,
            r11_certified=r11_certified,
            candidate_certified=candidate_certified,
            r11_rule_count=int(r11_rule_count),
            candidate_rule_count=int(candidate_rule_count),
            current_expected_distance=current_distance,
            r11_expected_distance=r11_distance,
            candidate_expected_distance=candidate_distance,
            distance_advantage=distance_advantage,
            rule_count_advantage=rule_count_advantage,
            candidate_seen_in_context=int(candidate_seen),
            r11_seen_in_context=int(r11_seen),
        )
        rows.append(
            {
                "features": features.detach().clone(),
                "candidate_action": int(candidate_action),
                "r11_action": int(r11_action),
                "support_count": support_count,
                "candidate_min_mass": candidate_min_mass,
                "candidate_mean_mass": candidate_mean_mass,
                "r11_mean_mass": r11_mean_mass,
                "mass_margin": mass_margin,
                "candidate_mass_spread": candidate_mass_spread,
                "r11_mass_spread": r11_mass_spread,
                "r11_certified": int(r11_certified),
                "candidate_certified": int(candidate_certified),
                "r11_rule_count": int(r11_rule_count),
                "candidate_rule_count": int(candidate_rule_count),
                "current_expected_distance": current_distance,
                "r11_expected_distance": r11_distance,
                "candidate_expected_distance": candidate_distance,
                "distance_advantage": distance_advantage,
                "rule_count_advantage": rule_count_advantage,
                "parent_logit_margin": parent_logit_margin,
            }
        )
    return rows


def _finish_with_r11(parent: Any, task: Any, state: PublicEpisodeState) -> tuple[bool, int]:
    while not task.done:
        observation = task.observe()
        action_features, _, _, _, r11_action, _ = _public_step_context(
            parent, state, observation
        )
        _advance(
            state=state,
            task=task,
            observation=observation,
            action_features=action_features,
            action=r11_action,
        )
    return bool(task.solved), int(task.step_count)


def _branch_outcome(
    parent: Any,
    *,
    task: Any,
    state: PublicEpisodeState,
    action_features: Tensor,
    first_action: int,
) -> tuple[bool, int]:
    branch_task = copy.deepcopy(task)
    branch_state = copy.deepcopy(state)
    observation = branch_task.observe()
    _advance(
        state=branch_state,
        task=branch_task,
        observation=observation,
        action_features=action_features,
        action=int(first_action),
    )
    return _finish_with_r11(parent, branch_task, branch_state)


def collect_action_rescue_rows(
    parent: Any,
    model: NativeR30ActionConditionedRescueEnsemble,
    *,
    make_task: Any,
    indices: tuple[int, int],
    temperature: float,
    max_support: int,
    max_decision_steps_per_episode: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(int(indices[0]), int(indices[1]) + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        state = _new_state(parent, task)
        decision_steps = 0
        while not task.done:
            observation = task.observe()
            (
                action_features,
                valid_actions,
                parent_output,
                public_posterior,
                r11_action,
                decision,
            ) = _public_step_context(parent, state, observation)
            if (
                decision_steps < int(max_decision_steps_per_episode)
                and decision.get("reason") != "r9_public_progress_complete"
            ):
                candidates = _candidate_feature_rows(
                    model,
                    observation=observation,
                    state=state,
                    action_features=action_features,
                    valid_actions=valid_actions,
                    parent_logits=parent_output["action_logits"][0],
                    public_posterior=public_posterior,
                    r11_action=r11_action,
                    temperature=float(temperature),
                    max_support=int(max_support),
                )
                if candidates:
                    baseline_solved, baseline_steps = _branch_outcome(
                        parent,
                        task=task,
                        state=state,
                        action_features=action_features,
                        first_action=r11_action,
                    )
                    for candidate in candidates:
                        candidate_solved, candidate_steps = _branch_outcome(
                            parent,
                            task=task,
                            state=state,
                            action_features=action_features,
                            first_action=int(candidate["candidate_action"]),
                        )
                        rescue = int(candidate_solved and not baseline_solved)
                        harm = int(baseline_solved and not candidate_solved)
                        class_id = (
                            RESCUE_CLASS
                            if rescue
                            else HARM_CLASS
                            if harm
                            else NEUTRAL_CLASS
                        )
                        rows.append(
                            {
                                **candidate,
                                "class_id": int(class_id),
                                "rescue": rescue,
                                "harm": harm,
                                "baseline_solved": int(baseline_solved),
                                "candidate_solved": int(candidate_solved),
                                "baseline_steps": int(baseline_steps),
                                "candidate_steps": int(candidate_steps),
                                "task_index": int(index),
                                "step": int(observation["step"]),
                            }
                        )
                    decision_steps += 1
            _advance(
                state=state,
                task=task,
                observation=observation,
                action_features=action_features,
                action=r11_action,
            )
    return rows


def train_rescue_ensemble(
    model: NativeR30ActionConditionedRescueEnsemble,
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
) -> dict[str, Any]:
    if not rows:
        return {
            "rows": 0,
            "class_counts": {"neutral": 0, "rescue": 0, "harm": 0},
            "heads": [],
        }
    features = torch.stack([row["features"] for row in rows], dim=0)
    labels = torch.tensor([int(row["class_id"]) for row in rows], dtype=torch.long)
    class_counts = [
        int((labels == class_id).sum().item()) for class_id in range(3)
    ]
    total = len(rows)
    class_weights = torch.tensor(
        [
            (total / (3.0 * count)) if count > 0 else 0.0
            for count in class_counts
        ],
        dtype=torch.float32,
    )
    summaries: list[dict[str, Any]] = []
    for head_index, head in enumerate(model.rescue_heads):
        torch.manual_seed(int(seed) + 701 * head_index)
        optimizer = torch.optim.AdamW(
            head.parameters(),
            lr=float(learning_rate),
            weight_decay=float(weight_decay),
        )
        rng = random.Random(int(seed) + 4001 * head_index)
        history: list[dict[str, float]] = []
        for epoch in range(int(epochs)):
            order = list(range(len(rows)))
            rng.shuffle(order)
            losses: list[float] = []
            correct = 0
            for start in range(0, len(order), int(batch_size)):
                ids = order[start : start + int(batch_size)]
                xb = features[ids]
                yb = labels[ids]
                logits = head(xb)
                loss = F.cross_entropy(logits, yb, weight=class_weights)
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
                    "accuracy": correct / max(1, len(rows)),
                }
            )
        summaries.append({"head": head_index, "history": history})
    model.eval()
    return {
        "rows": len(rows),
        "class_counts": {
            "neutral": class_counts[NEUTRAL_CLASS],
            "rescue": class_counts[RESCUE_CLASS],
            "harm": class_counts[HARM_CLASS],
        },
        "class_weights": [float(v) for v in class_weights.tolist()],
        "heads": summaries,
    }


def _score_action_row(
    model: NativeR30ActionConditionedRescueEnsemble,
    row: Mapping[str, Any],
) -> dict[str, float]:
    probs = model.rescue_class_probabilities(row["features"])
    return {
        "min_rescue": float(probs[:, RESCUE_CLASS].min().item()),
        "mean_rescue": float(probs[:, RESCUE_CLASS].mean().item()),
        "max_harm": float(probs[:, HARM_CLASS].max().item()),
        "mean_harm": float(probs[:, HARM_CLASS].mean().item()),
    }


def _select_action_row(
    model: NativeR30ActionConditionedRescueEnsemble,
    rows: Sequence[Mapping[str, Any]],
    *,
    rescue_threshold: float,
    harm_ceiling: float,
) -> tuple[Mapping[str, Any] | None, dict[str, float] | None]:
    eligible: list[tuple[tuple[float, ...], Mapping[str, Any], dict[str, float]]] = []
    with torch.no_grad():
        for row in rows:
            score = _score_action_row(model, row)
            if (
                score["min_rescue"] < float(rescue_threshold)
                or score["max_harm"] > float(harm_ceiling)
            ):
                continue
            key = (
                score["min_rescue"] - score["max_harm"],
                score["min_rescue"],
                -score["max_harm"],
                score["mean_rescue"],
                float(row.get("candidate_mean_mass", 0.0)),
                -float(row["candidate_action"]),
            )
            eligible.append((key, row, score))
    if not eligible:
        return None, None
    _, row, score = max(eligible, key=lambda item: item[0])
    return row, score


def _group_rows(rows: Sequence[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    groups: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    order: list[tuple[int, int]] = []
    for row in rows:
        key = (int(row["task_index"]), int(row["step"]))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    return [groups[key] for key in order]


def fit_rescue_guard(
    model: NativeR30ActionConditionedRescueEnsemble,
    *,
    block_rows: Sequence[Sequence[Mapping[str, Any]]],
    rescue_thresholds: Sequence[float],
    harm_ceilings: Sequence[float],
    minimum_precision: float,
    minimum_total_selections: int,
    minimum_block_selections: int,
    require_zero_harm: bool,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for rescue_threshold in rescue_thresholds:
        for harm_ceiling in harm_ceilings:
            blocks: list[dict[str, Any]] = []
            total_selected = total_rescue = total_harm = 0
            for block_index, rows in enumerate(block_rows):
                selected = rescued = harmed = 0
                groups = _group_rows(rows)
                for group in groups:
                    row, _ = _select_action_row(
                        model,
                        group,
                        rescue_threshold=float(rescue_threshold),
                        harm_ceiling=float(harm_ceiling),
                    )
                    if row is None:
                        continue
                    selected += 1
                    rescued += int(row["class_id"] == RESCUE_CLASS)
                    harmed += int(row["class_id"] == HARM_CLASS)
                precision = rescued / max(1, selected)
                blocks.append(
                    {
                        "block_index": int(block_index),
                        "candidate_rows": len(rows),
                        "decision_groups": len(groups),
                        "selected_actions": selected,
                        "rescue_actions": rescued,
                        "harm_actions": harmed,
                        "rescue_precision": precision,
                    }
                )
                total_selected += selected
                total_rescue += rescued
                total_harm += harmed
            worst_precision = min(
                (float(block["rescue_precision"]) for block in blocks),
                default=0.0,
            )
            block_coverage_ok = all(
                int(block["selected_actions"]) >= int(minimum_block_selections)
                for block in blocks
            )
            block_precision_ok = all(
                float(block["rescue_precision"]) >= float(minimum_precision)
                for block in blocks
            )
            harm_ok = (total_harm == 0) if require_zero_harm else True
            eligible = bool(
                total_selected >= int(minimum_total_selections)
                and block_coverage_ok
                and block_precision_ok
                and harm_ok
            )
            candidates.append(
                {
                    "rescue_threshold": float(rescue_threshold),
                    "harm_ceiling": float(harm_ceiling),
                    "selected_actions": total_selected,
                    "rescue_actions": total_rescue,
                    "harm_actions": total_harm,
                    "rescue_precision": total_rescue / max(1, total_selected),
                    "worst_block_precision": worst_precision,
                    "block_coverage_ok": block_coverage_ok,
                    "block_precision_ok": block_precision_ok,
                    "harm_ok": harm_ok,
                    "eligible": eligible,
                    "blocks": blocks,
                }
            )
    eligible = [row for row in candidates if row["eligible"]]
    selected = (
        max(
            eligible,
            key=lambda row: (
                row["rescue_actions"],
                row["worst_block_precision"],
                row["rescue_precision"],
                row["rescue_threshold"],
                -row["harm_ceiling"],
            ),
        )
        if eligible
        else None
    )
    return {
        "enabled": selected is not None,
        "minimum_precision": float(minimum_precision),
        "minimum_total_selections": int(minimum_total_selections),
        "minimum_block_selections": int(minimum_block_selections),
        "require_zero_harm": bool(require_zero_harm),
        "selected": selected,
        "candidates": candidates,
    }


def rollout_r30(
    parent: Any,
    model: NativeR30ActionConditionedRescueEnsemble,
    task: Any,
    *,
    temperature: float,
    rescue_threshold: float | None,
    harm_ceiling: float | None,
    max_support: int,
    max_overrides_per_episode: int,
) -> dict[str, Any]:
    state = _new_state(parent, task)
    overrides = rescue_guarded = 0
    while not task.done:
        observation = task.observe()
        (
            action_features,
            valid_actions,
            parent_output,
            public_posterior,
            r11_action,
            decision,
        ) = _public_step_context(parent, state, observation)
        action = int(r11_action)
        hidden = not isinstance(observation.get("target"), list)
        if (
            rescue_threshold is not None
            and harm_ceiling is not None
            and hidden
            and overrides < int(max_overrides_per_episode)
            and decision.get("reason") != "r9_public_progress_complete"
        ):
            candidates = _candidate_feature_rows(
                model,
                observation=observation,
                state=state,
                action_features=action_features,
                valid_actions=valid_actions,
                parent_logits=parent_output["action_logits"][0],
                public_posterior=public_posterior,
                r11_action=r11_action,
                temperature=float(temperature),
                max_support=int(max_support),
            )
            selected, _ = _select_action_row(
                model,
                candidates,
                rescue_threshold=float(rescue_threshold),
                harm_ceiling=float(harm_ceiling),
            )
            if selected is not None:
                rescue_guarded += 1
                action = int(selected["candidate_action"])
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
        "rescue_guarded_steps": int(rescue_guarded),
    }


def evaluate_r30(
    parent: Any,
    model: NativeR30ActionConditionedRescueEnsemble,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    temperature: float,
    rescue_threshold: float | None,
    harm_ceiling: float | None,
    max_support: int,
    max_overrides_per_episode: int,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R30 evaluation split must be dev/fresh")
    rows: list[dict[str, Any]] = []
    families_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = guarded = 0
    for family in families:
        fs = fst = fov = fguard = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r30(
                parent,
                model,
                make_task(str(family), str(split), int(index)),
                temperature=float(temperature),
                rescue_threshold=rescue_threshold,
                harm_ceiling=harm_ceiling,
                max_support=int(max_support),
                max_overrides_per_episode=int(max_overrides_per_episode),
            )
            fs += int(result["solved"])
            fst += int(result["steps"])
            fov += int(result["overrides_vs_r11"])
            fguard += int(result["rescue_guarded_steps"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            overrides += int(result["overrides_vs_r11"])
            guarded += int(result["rescue_guarded_steps"])
            episodes += 1
            rows.append({"family": str(family), "split": str(split), "index": int(index), **result})
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": fs,
            "steps": fst,
            "overrides_vs_r11": fov,
            "rescue_guarded_steps": fguard,
        }
    return {
        "split": str(split),
        "indices": [int(indices[0]), int(indices[1])],
        "episodes": len(rows),
        "solved": solved,
        "steps": steps,
        "overrides_vs_r11": overrides,
        "rescue_guarded_steps": guarded,
        "families": families_result,
        "rows": rows,
    }


def save_checkpoint(
    model: NativeR30ActionConditionedRescueEnsemble,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    r11_authority_blob_sha: str,
    predev_lock_sha256: str,
    goal_training_summary: Mapping[str, Any],
    temperature_calibration: Mapping[str, Any],
    rescue_training_summary: Mapping[str, Any],
    rescue_guard: Mapping[str, Any],
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
        "goal_successor_parameters": model.goal_parameter_count(),
        "rescue_successor_parameters": model.rescue_parameter_count(),
        "physical_parameters": 877542 + model.parameter_count(),
        "parent_checkpoint_sha256": str(parent_checkpoint_sha256),
        "parent_state_dict_sha256": str(parent_state_dict_sha256),
        "r11_authority_blob_sha": str(r11_authority_blob_sha),
        "predev_lock_sha256": str(predev_lock_sha256),
        "goal_training_summary": dict(goal_training_summary),
        "temperature_calibration": dict(temperature_calibration),
        "rescue_training_summary": dict(rescue_training_summary),
        "rescue_guard": dict(rescue_guard),
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
