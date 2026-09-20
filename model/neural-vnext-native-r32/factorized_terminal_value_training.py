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
from factorized_terminal_value_core import (
    NativeR32FactorizedTerminalValueEnsemble,
    encode_action_value_features,
    encode_parent_latent_context,
    encode_public_goal_features,
    goal_index,
)

R11_HORIZON = 1
CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r32-factorized-terminal-value-v1"


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
    model: NativeR32FactorizedTerminalValueEnsemble,
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
    model: NativeR32FactorizedTerminalValueEnsemble,
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


def _decision_action_value_rows(
    model: NativeR32FactorizedTerminalValueEnsemble,
    *,
    observation: Mapping[str, Any],
    state: PublicEpisodeState,
    action_features: Tensor,
    valid_actions: Tensor,
    parent_output: Mapping[str, Tensor],
    public_posterior: Tensor,
    r11_action: int,
    temperature: float,
    max_support: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    support_mask = public_posterior > 0.0
    support_count = int(support_mask.sum().item())
    if not (2 <= support_count <= int(max_support)):
        return None, []

    parent_logits = parent_output["action_logits"][0]
    latent_context = encode_parent_latent_context(parent_output)
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

    rows: list[dict[str, Any]] = []
    for action in range(int(action_features.shape[0])):
        if not bool(valid_actions[int(action)].item()):
            continue
        next_state, rule_count = state.causal_memory.predict_certified(
            context=context,
            state=current_state,
            action=int(action),
        )
        certified = next_state is not None
        action_distance = (
            _expected_distance(next_state, mean_posterior)
            if next_state is not None
            else current_distance
        )
        mass_values = masses[:, int(action)]
        min_mass = float(mass_values.min().item())
        mean_mass = float(mass_values.mean().item())
        max_mass = float(mass_values.max().item())
        spread = float((mass_values.max() - mass_values.min()).item())
        logit_margin = float(
            torch.tanh(
                (
                    parent_logits[int(action)]
                    - parent_logits[int(r11_action)]
                )
                / 4.0
            ).item()
        )
        seen = state.exact_memory.seen_in_context(observation, int(action))
        features = encode_action_value_features(
            public_goal_features=public_features,
            latent_context=latent_context,
            action_features=action_features[int(action)],
            action_next_state=next_state,
            support_count=support_count,
            action_min_mass=min_mass,
            action_mean_mass=mean_mass,
            action_max_mass=max_mass,
            action_mass_spread=spread,
            parent_logit_margin_vs_r11=logit_margin,
            action_certified=certified,
            action_rule_count=int(rule_count),
            current_expected_distance=current_distance,
            action_expected_distance=action_distance,
            expected_distance_improvement=current_distance - action_distance,
            action_seen_in_context=int(seen),
            is_r11_action=int(action) == int(r11_action),
        )
        rows.append(
            {
                "features": features.detach().clone(),
                "action": int(action),
                "is_r11_action": int(int(action) == int(r11_action)),
                "support_count": support_count,
                "action_min_mass": min_mass,
                "action_mean_mass": mean_mass,
                "action_max_mass": max_mass,
                "action_mass_spread": spread,
                "action_certified": int(certified),
                "action_rule_count": int(rule_count),
                "action_expected_distance": action_distance,
                "expected_distance_improvement": current_distance - action_distance,
                "parent_logit_margin_vs_r11": logit_margin,
            }
        )
    r11_rows = [row for row in rows if int(row["is_r11_action"]) == 1]
    if len(r11_rows) != 1:
        return None, []
    r11_row = r11_rows[0]
    candidates = [
        row
        for row in rows
        if int(row["is_r11_action"]) == 0
    ]
    return r11_row, candidates


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


def collect_terminal_value_pairs(
    parent: Any,
    model: NativeR32FactorizedTerminalValueEnsemble,
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
                r11_row, candidates = _decision_action_value_rows(
                    model,
                    observation=observation,
                    state=state,
                    action_features=action_features,
                    valid_actions=valid_actions,
                    parent_output=parent_output,
                    public_posterior=public_posterior,
                    r11_action=r11_action,
                    temperature=float(temperature),
                    max_support=int(max_support),
                )
                if r11_row is not None and candidates:
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
                            first_action=int(candidate["action"]),
                        )
                        rescue = int(candidate_solved and not baseline_solved)
                        harm = int(baseline_solved and not candidate_solved)
                        rows.append(
                            {
                                "r11_features": r11_row["features"],
                                "candidate_features": candidate["features"],
                                "r11_action": int(r11_action),
                                "candidate_action": int(candidate["action"]),
                                "candidate_mean_mass": float(candidate["action_mean_mass"]),
                                "r11_certified": int(r11_row["action_certified"]),
                                "candidate_certified": int(candidate["action_certified"]),
                                "baseline_solved": int(baseline_solved),
                                "candidate_solved": int(candidate_solved),
                                "rescue": rescue,
                                "harm": harm,
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


def build_terminal_value_examples(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    baseline_seen: set[tuple[int, int]] = set()
    for row in rows:
        key = (int(row["task_index"]), int(row["step"]))
        if key not in baseline_seen:
            examples.append(
                {
                    "features": row["r11_features"],
                    "solved": int(row["baseline_solved"]),
                    "role": "r11",
                    "task_index": key[0],
                    "step": key[1],
                }
            )
            baseline_seen.add(key)
        examples.append(
            {
                "features": row["candidate_features"],
                "solved": int(row["candidate_solved"]),
                "role": "candidate",
                "task_index": key[0],
                "step": key[1],
            }
        )
    return examples


def train_value_ensemble(
    model: NativeR32FactorizedTerminalValueEnsemble,
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
) -> dict[str, Any]:
    examples = build_terminal_value_examples(rows)
    if not examples:
        return {
            "pair_rows": 0,
            "value_examples": 0,
            "solved_examples": 0,
            "failed_examples": 0,
            "heads": [],
        }
    features = torch.stack([row["features"] for row in examples], dim=0)
    labels = torch.tensor(
        [float(row["solved"]) for row in examples],
        dtype=torch.float32,
    )
    solved_count = int(labels.sum().item())
    failed_count = int(labels.shape[0] - solved_count)
    pos_weight = float(failed_count / max(1, solved_count))
    summaries: list[dict[str, Any]] = []

    for head_index, head in enumerate(model.value_heads):
        torch.manual_seed(int(seed) + 701 * head_index)
        optimizer = torch.optim.AdamW(
            head.parameters(),
            lr=float(learning_rate),
            weight_decay=float(weight_decay),
        )
        rng = random.Random(int(seed) + 4001 * head_index)
        history: list[dict[str, float]] = []
        for epoch in range(int(epochs)):
            order = list(range(len(examples)))
            rng.shuffle(order)
            losses: list[float] = []
            correct = 0
            brier_total = 0.0
            for start in range(0, len(order), int(batch_size)):
                ids = order[start : start + int(batch_size)]
                xb = features[ids]
                yb = labels[ids]
                logits = head(xb)
                loss = F.binary_cross_entropy_with_logits(
                    logits,
                    yb,
                    pos_weight=torch.tensor(pos_weight, dtype=torch.float32),
                )
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.detach().item()))
                probs = torch.sigmoid(logits.detach())
                correct += int(((probs >= 0.5).float() == yb).sum().item())
                brier_total += float(((probs - yb) ** 2).sum().item())
            history.append(
                {
                    "epoch": float(epoch + 1),
                    "mean_loss": sum(losses) / max(1, len(losses)),
                    "accuracy": correct / max(1, len(examples)),
                    "brier": brier_total / max(1, len(examples)),
                }
            )
        summaries.append({"head": head_index, "history": history})
    model.eval()
    return {
        "pair_rows": len(rows),
        "value_examples": len(examples),
        "solved_examples": solved_count,
        "failed_examples": failed_count,
        "positive_weight": pos_weight,
        "heads": summaries,
    }


def _score_pair(
    model: NativeR32FactorizedTerminalValueEnsemble,
    row: Mapping[str, Any],
) -> dict[str, float]:
    r11 = model.solve_probabilities(row["r11_features"])
    candidate = model.solve_probabilities(row["candidate_features"])
    rescue = candidate * (1.0 - r11)
    harm = r11 * (1.0 - candidate)
    advantage = candidate - r11
    return {
        "min_rescue": float(rescue.min().item()),
        "mean_rescue": float(rescue.mean().item()),
        "max_harm": float(harm.max().item()),
        "mean_harm": float(harm.mean().item()),
        "min_candidate_solve": float(candidate.min().item()),
        "max_r11_solve": float(r11.max().item()),
        "min_advantage": float(advantage.min().item()),
        "mean_advantage": float(advantage.mean().item()),
    }


def _select_action_row(
    model: NativeR32FactorizedTerminalValueEnsemble,
    rows: Sequence[Mapping[str, Any]],
    *,
    rescue_threshold: float,
    harm_ceiling: float,
) -> tuple[Mapping[str, Any] | None, dict[str, float] | None]:
    eligible: list[tuple[tuple[float, ...], Mapping[str, Any], dict[str, float]]] = []
    with torch.no_grad():
        for row in rows:
            score = _score_pair(model, row)
            if (
                score["min_rescue"] < float(rescue_threshold)
                or score["max_harm"] > float(harm_ceiling)
                or score["min_advantage"] <= 0.0
            ):
                continue
            key = (
                score["min_rescue"] - score["max_harm"],
                score["min_advantage"],
                score["min_candidate_solve"],
                -score["max_r11_solve"],
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
    model: NativeR32FactorizedTerminalValueEnsemble,
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
                    rescued += int(row["rescue"])
                    harmed += int(row["harm"])
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


def _inference_pair_rows(
    model: NativeR32FactorizedTerminalValueEnsemble,
    *,
    observation: Mapping[str, Any],
    state: PublicEpisodeState,
    action_features: Tensor,
    valid_actions: Tensor,
    parent_output: Mapping[str, Tensor],
    public_posterior: Tensor,
    r11_action: int,
    temperature: float,
    max_support: int,
) -> list[dict[str, Any]]:
    r11_row, candidates = _decision_action_value_rows(
        model,
        observation=observation,
        state=state,
        action_features=action_features,
        valid_actions=valid_actions,
        parent_output=parent_output,
        public_posterior=public_posterior,
        r11_action=r11_action,
        temperature=float(temperature),
        max_support=int(max_support),
    )
    if r11_row is None:
        return []
    return [
        {
            "r11_features": r11_row["features"],
            "candidate_features": candidate["features"],
            "r11_action": int(r11_action),
            "candidate_action": int(candidate["action"]),
            "candidate_mean_mass": float(candidate["action_mean_mass"]),
        }
        for candidate in candidates
    ]


def rollout_r32(
    parent: Any,
    model: NativeR32FactorizedTerminalValueEnsemble,
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
            pairs = _inference_pair_rows(
                model,
                observation=observation,
                state=state,
                action_features=action_features,
                valid_actions=valid_actions,
                parent_output=parent_output,
                public_posterior=public_posterior,
                r11_action=r11_action,
                temperature=float(temperature),
                max_support=int(max_support),
            )
            selected, _ = _select_action_row(
                model,
                pairs,
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


def evaluate_r32(
    parent: Any,
    model: NativeR32FactorizedTerminalValueEnsemble,
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
        raise ValueError("R32 evaluation split must be dev/fresh")
    rows: list[dict[str, Any]] = []
    families_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = guarded = 0
    for family in families:
        fs = fst = fov = fguard = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r32(
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


def pair_outcome_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "both_fail": sum(
            int(not row["baseline_solved"] and not row["candidate_solved"])
            for row in rows
        ),
        "rescue": sum(int(row["rescue"]) for row in rows),
        "harm": sum(int(row["harm"]) for row in rows),
        "both_solve": sum(
            int(row["baseline_solved"] and row["candidate_solved"])
            for row in rows
        ),
    }


def certification_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "rows": len(rows),
        "r11_certified_rows": sum(int(row["r11_certified"]) for row in rows),
        "candidate_certified_rows": sum(int(row["candidate_certified"]) for row in rows),
        "dual_certified_rows": sum(
            int(row["r11_certified"] and row["candidate_certified"])
            for row in rows
        ),
    }


def save_checkpoint(
    model: NativeR32FactorizedTerminalValueEnsemble,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    r11_authority_blob_sha: str,
    predev_lock_sha256: str,
    goal_training_summary: Mapping[str, Any],
    temperature_calibration: Mapping[str, Any],
    value_training_summary: Mapping[str, Any],
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
        "value_successor_parameters": model.value_parameter_count(),
        "physical_parameters": 877542 + model.parameter_count(),
        "parent_checkpoint_sha256": str(parent_checkpoint_sha256),
        "parent_state_dict_sha256": str(parent_state_dict_sha256),
        "r11_authority_blob_sha": str(r11_authority_blob_sha),
        "predev_lock_sha256": str(predev_lock_sha256),
        "goal_training_summary": dict(goal_training_summary),
        "temperature_calibration": dict(temperature_calibration),
        "value_training_summary": dict(value_training_summary),
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
