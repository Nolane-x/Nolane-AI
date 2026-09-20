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
from binary_rescue_set_ranker_core import (
    BOTH_FAIL_CLASS,
    BOTH_SOLVE_CLASS,
    HARM_CLASS,
    RESCUE_CLASS,
    NativeR39BinaryRescueSetRankerEnsemble,
    encode_pair_features,
    encode_parent_latent_context,
    encode_public_goal_features,
    goal_index,
)

R11_HORIZON = 1
CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r39-binary-rescue-confidence-v1"


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
    model: NativeR39BinaryRescueSetRankerEnsemble,
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
    model: NativeR39BinaryRescueSetRankerEnsemble,
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
    model: NativeR39BinaryRescueSetRankerEnsemble,
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
    support_mask = public_posterior > 0.0
    support_count = int(support_mask.sum().item())
    if not (2 <= support_count <= int(max_support)):
        return []

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

        features = encode_pair_features(
            public_goal_features=public_features,
            latent_context=latent_context,
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


def collect_joint_outcome_rows(
    parent: Any,
    model: NativeR39BinaryRescueSetRankerEnsemble,
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
                    parent_output=parent_output,
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
                        if rescue:
                            class_id = RESCUE_CLASS
                        elif harm:
                            class_id = HARM_CLASS
                        elif baseline_solved and candidate_solved:
                            class_id = BOTH_SOLVE_CLASS
                        else:
                            class_id = BOTH_FAIL_CLASS
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


def _balanced_weights(labels: Tensor, class_count: int) -> Tensor:
    total = int(labels.shape[0])
    counts = [int((labels == index).sum().item()) for index in range(int(class_count))]
    return torch.tensor(
        [
            (total / (float(class_count) * count)) if count > 0 else 0.0
            for count in counts
        ],
        dtype=torch.float32,
    )


def _training_stratum(
    group: Sequence[Mapping[str, Any]],
    *,
    minimum_index: int,
    maximum_index: int,
    stratum_count: int,
) -> int:
    if not group:
        raise ValueError("empty R39 decision group")
    task_index = int(group[0]["task_index"])
    span = max(1, int(maximum_index) - int(minimum_index) + 1)
    offset = max(0, min(span - 1, task_index - int(minimum_index)))
    stratum = int(offset * int(stratum_count) / span)
    return min(int(stratum_count) - 1, max(0, stratum))


def _round_robin_stratified_order(
    groups: Sequence[Sequence[Mapping[str, Any]]],
    *,
    stratum_count: int,
    rng: random.Random,
) -> tuple[list[int], list[int]]:
    if not groups:
        return [], []
    task_indices = [int(group[0]["task_index"]) for group in groups]
    minimum_index = min(task_indices)
    maximum_index = max(task_indices)
    buckets: list[list[int]] = [[] for _ in range(int(stratum_count))]
    group_strata: list[int] = []
    for group_index, group in enumerate(groups):
        stratum = _training_stratum(
            group,
            minimum_index=minimum_index,
            maximum_index=maximum_index,
            stratum_count=int(stratum_count),
        )
        group_strata.append(stratum)
        buckets[stratum].append(group_index)
    for bucket in buckets:
        rng.shuffle(bucket)
    order: list[int] = []
    positions = [0 for _ in buckets]
    remaining = True
    while remaining:
        remaining = False
        for stratum, bucket in enumerate(buckets):
            position = positions[stratum]
            if position < len(bucket):
                order.append(bucket[position])
                positions[stratum] += 1
                remaining = True
    return order, group_strata


def train_decision_set_ensemble(
    model: NativeR39BinaryRescueSetRankerEnsemble,
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
    listwise_loss_weight: float,
    harm_mass_weight: float,
    stratum_count: int,
    group_dro_eta: float,
    rescue_group_listwise_multiplier: float,
    rescue_binary_loss_weight: float,
) -> dict[str, Any]:
    groups = _group_rows(rows)
    if not groups:
        return {
            "rows": 0,
            "groups": 0,
            "class_counts": {"both_fail": 0, "rescue": 0, "harm": 0, "both_solve": 0},
            "heads": [],
        }
    if int(stratum_count) < 2:
        raise ValueError("R39 stratum_count must be >=2")

    all_labels = torch.tensor([int(row["class_id"]) for row in rows], dtype=torch.long)
    class_weights = _balanced_weights(all_labels, 4)
    class_counts = [
        int((all_labels == class_id).sum().item()) for class_id in range(4)
    ]
    rescue_positive_count = max(1, class_counts[RESCUE_CLASS])
    rescue_negative_count = max(1, len(rows) - class_counts[RESCUE_CLASS])
    rescue_positive_weight = torch.tensor(
        float(rescue_negative_count) / float(rescue_positive_count),
        dtype=torch.float32,
    )
    task_indices = [int(group[0]["task_index"]) for group in groups]
    minimum_index = min(task_indices)
    maximum_index = max(task_indices)
    group_strata = [
        _training_stratum(
            group,
            minimum_index=minimum_index,
            maximum_index=maximum_index,
            stratum_count=int(stratum_count),
        )
        for group in groups
    ]
    stratum_group_counts = [
        sum(int(value == stratum) for value in group_strata)
        for stratum in range(int(stratum_count))
    ]
    stratum_rescue_group_counts = [
        sum(
            int(
                group_strata[group_index] == stratum
                and any(int(row["class_id"]) == RESCUE_CLASS for row in group)
            )
            for group_index, group in enumerate(groups)
        )
        for stratum in range(int(stratum_count))
    ]

    summaries: list[dict[str, Any]] = []
    for head_index, head in enumerate(model.set_heads):
        torch.manual_seed(int(seed) + 701 * head_index)
        optimizer = torch.optim.AdamW(
            head.parameters(),
            lr=float(learning_rate),
            weight_decay=float(weight_decay),
        )
        rng = random.Random(int(seed) + 4001 * head_index)
        dro_weights = torch.ones(int(stratum_count), dtype=torch.float32)
        dro_weights = dro_weights / dro_weights.sum()
        history: list[dict[str, Any]] = []

        for epoch in range(int(epochs)):
            order, epoch_group_strata = _round_robin_stratified_order(
                groups,
                stratum_count=int(stratum_count),
                rng=rng,
            )
            losses: list[float] = []
            outcome_correct = 0
            outcome_rows = 0
            selected_rescue = 0
            selected_harm = 0
            selected_null_correct = 0
            no_rescue_groups = 0
            stratum_loss_sums = [0.0 for _ in range(int(stratum_count))]
            stratum_loss_counts = [0 for _ in range(int(stratum_count))]
            stratum_selected_rescue = [0 for _ in range(int(stratum_count))]
            stratum_selected_harm = [0 for _ in range(int(stratum_count))]
            stratum_no_rescue_correct = [0 for _ in range(int(stratum_count))]
            stratum_no_rescue_total = [0 for _ in range(int(stratum_count))]

            for batch_start in range(0, len(order), int(batch_size)):
                batch_group_indices = order[batch_start : batch_start + int(batch_size)]
                per_stratum_losses: dict[int, list[Tensor]] = {}
                batch_metrics: list[tuple[int, Tensor, Tensor, Tensor]] = []

                for group_index in batch_group_indices:
                    group = groups[group_index]
                    stratum = int(epoch_group_strata[group_index])
                    features = torch.stack([row["features"] for row in group], dim=0)
                    labels = torch.tensor(
                        [int(row["class_id"]) for row in group],
                        dtype=torch.long,
                    )
                    output = head(features)
                    outcome_logits = output["outcome_logits"]
                    rescue_logits = output["rescue_logits"]
                    selection_logits = output["selection_logits"]

                    outcome_loss = F.cross_entropy(
                        outcome_logits,
                        labels,
                        weight=class_weights,
                    )
                    rescue_mask = labels == RESCUE_CLASS
                    rescue_loss = F.binary_cross_entropy_with_logits(
                        rescue_logits,
                        rescue_mask.float(),
                        pos_weight=rescue_positive_weight,
                    )
                    log_probs = F.log_softmax(selection_logits, dim=0)
                    if bool(rescue_mask.any().item()):
                        rescue_indices = (
                            torch.nonzero(rescue_mask, as_tuple=False).flatten() + 1
                        )
                        listwise_loss = -torch.logsumexp(
                            log_probs[rescue_indices], dim=0
                        )
                        listwise_multiplier = float(
                            rescue_group_listwise_multiplier
                        )
                    else:
                        listwise_loss = -log_probs[0]
                        listwise_multiplier = 1.0
                        no_rescue_groups += 1

                    selection_probs = torch.softmax(selection_logits, dim=0)
                    harm_mask = labels == HARM_CLASS
                    harm_mass = (
                        selection_probs[1:][harm_mask].sum()
                        if bool(harm_mask.any().item())
                        else torch.zeros((), dtype=selection_probs.dtype)
                    )
                    harm_penalty = -torch.log(
                        (1.0 - harm_mass).clamp_min(1.0e-6)
                    )
                    group_loss = (
                        outcome_loss
                        + float(listwise_loss_weight)
                        * listwise_multiplier
                        * listwise_loss
                        + float(harm_mass_weight) * harm_penalty
                        + float(rescue_binary_loss_weight) * rescue_loss
                    )
                    per_stratum_losses.setdefault(stratum, []).append(group_loss)
                    batch_metrics.append(
                        (stratum, outcome_logits, labels, selection_logits)
                    )

                stratum_means: dict[int, Tensor] = {
                    stratum: torch.stack(values).mean()
                    for stratum, values in per_stratum_losses.items()
                }
                with torch.no_grad():
                    for stratum, value in stratum_means.items():
                        dro_weights[stratum] *= torch.exp(
                            torch.tensor(
                                float(group_dro_eta) * float(value.detach().item()),
                                dtype=dro_weights.dtype,
                            )
                        )
                    dro_weights /= dro_weights.sum().clamp_min(1.0e-12)

                present = sorted(stratum_means)
                present_weights = dro_weights[present]
                present_weights = present_weights / present_weights.sum().clamp_min(
                    1.0e-12
                )
                batch_loss = torch.zeros((), dtype=torch.float32)
                for position, stratum in enumerate(present):
                    batch_loss = batch_loss + present_weights[position] * stratum_means[stratum]

                optimizer.zero_grad(set_to_none=True)
                batch_loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()

                for stratum, outcome_logits, labels, selection_logits in batch_metrics:
                    group_loss_value = float(
                        (
                            F.cross_entropy(
                                outcome_logits.detach(),
                                labels,
                                weight=class_weights,
                            )
                        ).item()
                    )
                    stratum_loss_sums[stratum] += group_loss_value
                    stratum_loss_counts[stratum] += 1
                    outcome_correct += int(
                        (
                            outcome_logits.detach().argmax(dim=-1) == labels
                        ).sum().item()
                    )
                    outcome_rows += int(labels.numel())
                    rescue_mask = labels == RESCUE_CLASS
                    selected_index = int(selection_logits.detach().argmax().item())
                    if selected_index == 0:
                        if not bool(rescue_mask.any().item()):
                            selected_null_correct += 1
                            stratum_no_rescue_correct[stratum] += 1
                        if not bool(rescue_mask.any().item()):
                            stratum_no_rescue_total[stratum] += 1
                    else:
                        selected_class = int(labels[selected_index - 1].item())
                        selected_rescue += int(selected_class == RESCUE_CLASS)
                        selected_harm += int(selected_class == HARM_CLASS)
                        stratum_selected_rescue[stratum] += int(
                            selected_class == RESCUE_CLASS
                        )
                        stratum_selected_harm[stratum] += int(
                            selected_class == HARM_CLASS
                        )
                        if not bool(rescue_mask.any().item()):
                            stratum_no_rescue_total[stratum] += 1
                    losses.append(group_loss_value)

            history.append(
                {
                    "epoch": float(epoch + 1),
                    "mean_outcome_loss_proxy": sum(losses) / max(1, len(losses)),
                    "outcome_accuracy": outcome_correct / max(1, outcome_rows),
                    "selected_rescue_groups": float(selected_rescue),
                    "selected_harm_groups": float(selected_harm),
                    "null_accuracy_no_rescue": selected_null_correct
                    / max(1, no_rescue_groups),
                    "dro_weights": [float(value) for value in dro_weights.tolist()],
                    "stratum_selected_rescue_groups": [
                        int(value) for value in stratum_selected_rescue
                    ],
                    "stratum_selected_harm_groups": [
                        int(value) for value in stratum_selected_harm
                    ],
                    "stratum_null_accuracy_no_rescue": [
                        stratum_no_rescue_correct[index]
                        / max(1, stratum_no_rescue_total[index])
                        for index in range(int(stratum_count))
                    ],
                }
            )
        summaries.append({"head": head_index, "history": history})

    model.eval()
    return {
        "rows": len(rows),
        "groups": len(groups),
        "class_counts": {
            "both_fail": class_counts[BOTH_FAIL_CLASS],
            "rescue": class_counts[RESCUE_CLASS],
            "harm": class_counts[HARM_CLASS],
            "both_solve": class_counts[BOTH_SOLVE_CLASS],
        },
        "class_weights": [float(v) for v in class_weights.tolist()],
        "listwise_loss_weight": float(listwise_loss_weight),
        "harm_mass_weight": float(harm_mass_weight),
        "stratum_count": int(stratum_count),
        "group_dro_eta": float(group_dro_eta),
        "rescue_group_listwise_multiplier": float(
            rescue_group_listwise_multiplier
        ),
        "rescue_binary_loss_weight": float(rescue_binary_loss_weight),
        "rescue_positive_weight": float(rescue_positive_weight.item()),
        "stratum_group_counts": [int(value) for value in stratum_group_counts],
        "stratum_rescue_group_counts": [
            int(value) for value in stratum_rescue_group_counts
        ],
        "heads": summaries,
    }


def _score_decision_set(
    model: NativeR39BinaryRescueSetRankerEnsemble,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not rows:
        return {"selected_index": None}
    features = torch.stack([row["features"] for row in rows], dim=0)
    output = model.decision_set_outputs(features)
    selection_probs = output["selection_probabilities"]
    rescue_probs = output["rescue_probabilities"]
    outcome_probs = output["outcome_probabilities"]
    mean_selection = selection_probs.mean(dim=0)
    selected_index = int(mean_selection.argmax().item())
    if selected_index == 0:
        return {
            "selected_index": 0,
            "min_selection": float(selection_probs[:, 0].min().item()),
            "mean_selection": float(mean_selection[0].item()),
            "null_preferred_heads": int((selection_probs.argmax(dim=-1) == 0).sum().item()),
        }
    candidate_index = selected_index - 1
    return {
        "selected_index": selected_index,
        "candidate_index": candidate_index,
        "min_selection": float(selection_probs[:, selected_index].min().item()),
        "mean_selection": float(mean_selection[selected_index].item()),
        "min_rescue": float(rescue_probs[:, candidate_index].min().item()),
        "mean_rescue": float(rescue_probs[:, candidate_index].mean().item()),
        "max_harm": float(outcome_probs[:, candidate_index, HARM_CLASS].max().item()),
        "mean_harm": float(outcome_probs[:, candidate_index, HARM_CLASS].mean().item()),
        "null_probability": float(mean_selection[0].item()),
        "selection_margin_vs_null": float(
            mean_selection[selected_index].item() - mean_selection[0].item()
        ),
        "candidate_preferred_heads": int(
            (selection_probs.argmax(dim=-1) == selected_index).sum().item()
        ),
    }


def _select_action_row(
    model: NativeR39BinaryRescueSetRankerEnsemble,
    rows: Sequence[Mapping[str, Any]],
    *,
    selection_threshold: float,
    rescue_threshold: float,
    harm_ceiling: float,
) -> tuple[Mapping[str, Any] | None, dict[str, float] | None]:
    if not rows:
        return None, None
    with torch.no_grad():
        score = _score_decision_set(model, rows)
    selected_index = score.get("selected_index")
    if selected_index is None or int(selected_index) == 0:
        return None, score
    if (
        float(score["min_selection"]) < float(selection_threshold)
        or float(score["min_rescue"]) < float(rescue_threshold)
        or float(score["max_harm"]) > float(harm_ceiling)
        or float(score["selection_margin_vs_null"]) <= 0.0
        or int(score["candidate_preferred_heads"]) < model.ensemble_size
    ):
        return None, score
    return rows[int(score["candidate_index"])], score


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
    model: NativeR39BinaryRescueSetRankerEnsemble,
    *,
    block_rows: Sequence[Sequence[Mapping[str, Any]]],
    selection_thresholds: Sequence[float],
    rescue_thresholds: Sequence[float],
    harm_ceilings: Sequence[float],
    minimum_precision: float,
    minimum_total_selections: int,
    minimum_block_selections: int,
    require_zero_harm: bool,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for selection_threshold in selection_thresholds:
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
                            selection_threshold=float(selection_threshold),
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
                        "selection_threshold": float(selection_threshold),
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
                row["selection_threshold"],
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


def rollout_r39(
    parent: Any,
    model: NativeR39BinaryRescueSetRankerEnsemble,
    task: Any,
    *,
    temperature: float,
    selection_threshold: float | None,
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
            selection_threshold is not None
            and rescue_threshold is not None
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
                parent_output=parent_output,
                public_posterior=public_posterior,
                r11_action=r11_action,
                temperature=float(temperature),
                max_support=int(max_support),
            )
            selected, _ = _select_action_row(
                model,
                candidates,
                selection_threshold=float(selection_threshold),
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


def evaluate_r39(
    parent: Any,
    model: NativeR39BinaryRescueSetRankerEnsemble,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    temperature: float,
    selection_threshold: float | None,
    rescue_threshold: float | None,
    harm_ceiling: float | None,
    max_support: int,
    max_overrides_per_episode: int,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R39 evaluation split must be dev/fresh")
    rows: list[dict[str, Any]] = []
    families_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = guarded = 0
    for family in families:
        fs = fst = fov = fguard = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r39(
                parent,
                model,
                make_task(str(family), str(split), int(index)),
                temperature=float(temperature),
                selection_threshold=selection_threshold,
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
    model: NativeR39BinaryRescueSetRankerEnsemble,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    r11_authority_blob_sha: str,
    predev_lock_sha256: str,
    goal_training_summary: Mapping[str, Any],
    temperature_calibration: Mapping[str, Any],
    set_training_summary: Mapping[str, Any],
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
        "set_successor_parameters": model.set_parameter_count(),
        "physical_parameters": 877542 + model.parameter_count(),
        "parent_checkpoint_sha256": str(parent_checkpoint_sha256),
        "parent_state_dict_sha256": str(parent_state_dict_sha256),
        "r11_authority_blob_sha": str(r11_authority_blob_sha),
        "predev_lock_sha256": str(predev_lock_sha256),
        "goal_training_summary": dict(goal_training_summary),
        "temperature_calibration": dict(temperature_calibration),
        "set_training_summary": dict(set_training_summary),
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


