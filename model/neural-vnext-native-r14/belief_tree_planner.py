from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import torch
from torch import Tensor

from native_core import PublicActionMemory
from public_planner import (
    GOAL_CARDINALITY,
    GOAL_DIMENSIONS,
    GOAL_TABLE,
)
from causal_version_space import (
    R9_ACCEPTED_MAX_SUPPORT,
    PublicCausalRuleMemory,
    choose_public_causal_action,
)

_EPS = 1.0e-8


@dataclass(frozen=True)
class BeliefTreeValue:
    expected_distance: float
    worst_distance: float
    expected_support: float
    first_expected_distance: float
    first_worst_distance: float
    first_action: int


def _normalize(posterior: Tensor) -> Tensor:
    row = posterior.detach().float()
    mass = float(row.sum().item())
    if mass <= 0.0:
        raise ValueError("posterior needs positive mass")
    return row / mass


def _distance_vector(state: Tensor) -> Tensor:
    return torch.remainder(
        GOAL_TABLE - state.unsqueeze(0),
        GOAL_CARDINALITY,
    ).sum(dim=1).float()


def _support_mask(posterior: Tensor) -> Tensor:
    return posterior > 0.0


def _state_value(state: Tensor, posterior: Tensor, *, first_action: int) -> BeliefTreeValue:
    posterior = _normalize(posterior)
    distances = _distance_vector(state)
    support = _support_mask(posterior)
    expected = float((posterior * distances).sum().item())
    worst = float(distances[support].max().item())
    count = float(support.sum().item())
    return BeliefTreeValue(
        expected_distance=expected,
        worst_distance=worst,
        expected_support=count,
        first_expected_distance=expected,
        first_worst_distance=worst,
        first_action=int(first_action),
    )


def posterior_branches(
    state: Tensor,
    posterior: Tensor,
) -> tuple[tuple[float, int, Tensor], ...]:
    """Public progress feedback partitions hidden goals by exact distance shell."""
    posterior = _normalize(posterior)
    distances = _distance_vector(state).to(torch.long)
    support = _support_mask(posterior)
    branches: list[tuple[float, int, Tensor]] = []
    for distance in sorted({int(v) for v in distances[support].tolist()}):
        mask = support & (distances == int(distance))
        mass = float(posterior[mask].sum().item())
        if mass <= 0.0:
            continue
        branch = posterior * mask.to(posterior.dtype)
        branch = branch / branch.sum()
        branches.append((mass, int(distance), branch))
    if not branches:
        raise ValueError("public posterior produced no feedback branch")
    total = sum(row[0] for row in branches)
    if abs(total - 1.0) > 1.0e-5:
        raise AssertionError("feedback branch mass must sum to one")
    return tuple(branches)


def _value_key(value: BeliefTreeValue) -> tuple[float, float, float, int]:
    return (
        float(value.expected_distance),
        float(value.worst_distance),
        float(value.expected_support),
        int(value.first_action),
    )


def _best_future_value(
    *,
    state: Tensor,
    posterior: Tensor,
    context: str,
    actions: tuple[int, ...],
    causal_memory: PublicCausalRuleMemory,
    depth: int,
) -> BeliefTreeValue | None:
    if int(depth) <= 0:
        return _state_value(state, posterior, first_action=-1)
    best: BeliefTreeValue | None = None
    for action in actions:
        candidate = _action_tree_value(
            state=state,
            posterior=posterior,
            context=context,
            actions=actions,
            causal_memory=causal_memory,
            action=int(action),
            depth=int(depth),
        )
        if candidate is None:
            continue
        if best is None or _value_key(candidate) < _value_key(best):
            best = candidate
    return best


def _action_tree_value(
    *,
    state: Tensor,
    posterior: Tensor,
    context: str,
    actions: tuple[int, ...],
    causal_memory: PublicCausalRuleMemory,
    action: int,
    depth: int,
) -> BeliefTreeValue | None:
    posterior = _normalize(posterior)
    nxt, _rule_count = causal_memory.predict_certified(
        context=str(context),
        state=state,
        action=int(action),
    )
    if nxt is None:
        return None

    immediate = _state_value(nxt, posterior, first_action=int(action))
    branches = posterior_branches(nxt, posterior)

    expected_terminal = 0.0
    worst_terminal = 0.0
    expected_support = 0.0
    for mass, _distance, branch in branches:
        if int(depth) > 1:
            future = _best_future_value(
                state=nxt,
                posterior=branch,
                context=str(context),
                actions=actions,
                causal_memory=causal_memory,
                depth=int(depth) - 1,
            )
        else:
            future = None
        if future is None:
            future = _state_value(nxt, branch, first_action=int(action))
        expected_terminal += float(mass) * float(future.expected_distance)
        worst_terminal = max(worst_terminal, float(future.worst_distance))
        expected_support += float(mass) * float(future.expected_support)

    return BeliefTreeValue(
        expected_distance=float(expected_terminal),
        worst_distance=float(worst_terminal),
        expected_support=float(expected_support),
        first_expected_distance=float(immediate.expected_distance),
        first_worst_distance=float(immediate.worst_distance),
        first_action=int(action),
    )


def _per_goal_distances(state: Tensor, posterior: Tensor) -> Tensor:
    distances = _distance_vector(state)
    return distances[_support_mask(posterior)]


def _strictly_better(candidate: BeliefTreeValue, reference: BeliefTreeValue) -> bool:
    if candidate.expected_distance < reference.expected_distance - _EPS:
        return True
    if abs(candidate.expected_distance - reference.expected_distance) <= _EPS:
        if candidate.worst_distance < reference.worst_distance - _EPS:
            return True
        if abs(candidate.worst_distance - reference.worst_distance) <= _EPS:
            return candidate.expected_support < reference.expected_support - _EPS
    return False


def choose_public_belief_tree_action(
    *,
    observation: Mapping[str, Any],
    exact_memory: PublicActionMemory,
    causal_memory: PublicCausalRuleMemory,
    posterior: Tensor,
    parent_logits: Tensor,
    depth: int,
    guard_mode: str,
) -> tuple[int, dict[str, Any]]:
    """Accepted R11 fallback plus observation-aware certified causal planning."""
    if int(depth) not in (2, 3):
        raise ValueError("R14 belief-tree depth must be 2 or 3")
    if guard_mode not in {"expected_worst", "pareto_current"}:
        raise ValueError("unknown R14 guard mode")

    r11_action, r11_info = choose_public_causal_action(
        observation=observation,
        exact_memory=exact_memory,
        causal_memory=causal_memory,
        posterior=posterior,
        parent_logits=parent_logits,
        horizon=1,
    )

    target = observation.get("target")
    if isinstance(target, list) and len(target) == GOAL_DIMENSIONS:
        return int(r11_action), {
            "override": False,
            "reason": "target_visible_r11_exact",
            "r11_action": int(r11_action),
            "depth": int(depth),
            "guard_mode": str(guard_mode),
        }
    if r11_info.get("reason") == "r9_public_progress_complete":
        return int(r11_action), {
            "override": False,
            "reason": "r11_public_progress_complete",
            "r11_action": int(r11_action),
            "depth": int(depth),
            "guard_mode": str(guard_mode),
        }

    posterior = _normalize(posterior)
    support = int(_support_mask(posterior).sum().item())
    if support > R9_ACCEPTED_MAX_SUPPORT:
        return int(r11_action), {
            "override": False,
            "reason": "posterior_too_broad_r11_fallback",
            "support": support,
            "r11_action": int(r11_action),
            "depth": int(depth),
            "guard_mode": str(guard_mode),
        }

    descriptions = observation.get("actions")
    if not isinstance(descriptions, list):
        raise ValueError("public actions missing")
    submits = [
        i for i, description in enumerate(descriptions)
        if "submit" in str(description).lower()
    ]
    if len(submits) != 1:
        raise ValueError("expected exactly one public submit action")
    submit_action = int(submits[0])
    actions = tuple(i for i in range(len(descriptions)) if i != submit_action)

    state = torch.tensor(
        [int(v) for v in observation["state"]],
        dtype=torch.long,
    )
    context = exact_memory.context_key(observation)
    current = _state_value(state, posterior, first_action=-1)

    if int(r11_action) != submit_action:
        reference = _action_tree_value(
            state=state,
            posterior=posterior,
            context=context,
            actions=actions,
            causal_memory=causal_memory,
            action=int(r11_action),
            depth=int(depth),
        )
    else:
        reference = None
    if reference is None:
        reference = current

    current_distances = _per_goal_distances(state, posterior)
    reference_state, _ = (
        causal_memory.predict_certified(
            context=context,
            state=state,
            action=int(r11_action),
        )
        if int(r11_action) != submit_action
        else (None, 0)
    )
    reference_distances = (
        _per_goal_distances(reference_state, posterior)
        if reference_state is not None
        else current_distances
    )

    best: BeliefTreeValue | None = None
    best_action: int | None = None
    best_info: dict[str, Any] | None = None

    for action in actions:
        if int(action) == int(r11_action):
            continue
        candidate = _action_tree_value(
            state=state,
            posterior=posterior,
            context=context,
            actions=actions,
            causal_memory=causal_memory,
            action=int(action),
            depth=int(depth),
        )
        if candidate is None or not _strictly_better(candidate, reference):
            continue

        candidate_state, rule_count = causal_memory.predict_certified(
            context=context,
            state=state,
            action=int(action),
        )
        if candidate_state is None:
            continue
        candidate_distances = _per_goal_distances(candidate_state, posterior)

        if guard_mode == "pareto_current":
            safe = bool(
                (candidate_distances <= current_distances + _EPS).all()
            )
        else:
            safe = bool(
                candidate.first_expected_distance
                <= reference.first_expected_distance + _EPS
                and candidate.first_worst_distance
                <= reference.first_worst_distance + _EPS
            )
        if not safe:
            continue

        if best is None:
            better = True
        else:
            a = (
                float(candidate.expected_distance),
                float(candidate.worst_distance),
                float(candidate.expected_support),
                -float(parent_logits[int(action)].item()),
                int(action),
            )
            b = (
                float(best.expected_distance),
                float(best.worst_distance),
                float(best.expected_support),
                -float(parent_logits[int(best_action)].item()),
                int(best_action),
            )
            better = a < b
        if not better:
            continue

        best = candidate
        best_action = int(action)
        best_info = {
            "selected_rule_count": int(rule_count),
            "selected_immediate_distances": [
                float(v) for v in candidate_distances.tolist()
            ],
            "reference_immediate_distances": [
                float(v) for v in reference_distances.tolist()
            ],
        }

    if best is None or best_action is None:
        return int(r11_action), {
            "override": False,
            "reason": "no_belief_tree_advantage",
            "support": support,
            "r11_action": int(r11_action),
            "reference_expected_terminal_distance": float(reference.expected_distance),
            "reference_worst_terminal_distance": float(reference.worst_distance),
            "reference_expected_terminal_support": float(reference.expected_support),
            "depth": int(depth),
            "guard_mode": str(guard_mode),
        }

    return int(best_action), {
        "override": True,
        "reason": "certified_belief_tree_advantage",
        "support": support,
        "r11_action": int(r11_action),
        "selected_action": int(best_action),
        "reference_expected_terminal_distance": float(reference.expected_distance),
        "selected_expected_terminal_distance": float(best.expected_distance),
        "reference_worst_terminal_distance": float(reference.worst_distance),
        "selected_worst_terminal_distance": float(best.worst_distance),
        "reference_expected_terminal_support": float(reference.expected_support),
        "selected_expected_terminal_support": float(best.expected_support),
        "selected_first_expected_distance": float(best.first_expected_distance),
        "selected_first_worst_distance": float(best.first_worst_distance),
        "depth": int(depth),
        "guard_mode": str(guard_mode),
        **(best_info or {}),
    }
