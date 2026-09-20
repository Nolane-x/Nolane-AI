from __future__ import annotations

from typing import Any, Mapping

import torch
from torch import Tensor

from native_core import PublicActionMemory
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_TABLE
from causal_version_space import (
    R9_ACCEPTED_MAX_SUPPORT,
    PublicCausalRuleMemory,
    choose_public_causal_action,
)

_EPS = 1.0e-8


def _normalize(posterior: Tensor) -> Tensor:
    row = posterior.detach().float()
    mass = float(row.sum().item())
    if mass <= 0.0:
        raise ValueError("posterior needs positive mass")
    return row / mass


def _distances(state: Tensor) -> Tensor:
    return torch.remainder(
        GOAL_TABLE - state.unsqueeze(0),
        GOAL_CARDINALITY,
    ).sum(dim=1).float()


def _metrics(state: Tensor, posterior: Tensor) -> dict[str, Any]:
    posterior = _normalize(posterior)
    distance = _distances(state)
    support_mask = posterior > 0.0
    expected_distance = float((posterior * distance).sum().item())
    worst_distance = float(distance[support_mask].max().item())

    integer_distance = distance.to(torch.long)
    expected_support = 0.0
    partitions: list[int] = []
    for shell in sorted({int(v) for v in integer_distance[support_mask].tolist()}):
        mask = support_mask & (integer_distance == int(shell))
        mass = float(posterior[mask].sum().item())
        count = int(mask.sum().item())
        expected_support += mass * float(count)
        partitions.append(count)
    return {
        "expected_distance": expected_distance,
        "worst_distance": worst_distance,
        "expected_support_after_feedback": float(expected_support),
        "partition_sizes": partitions,
        "per_goal_distances": distance[support_mask],
    }


def choose_public_diagnostic_action(
    *,
    observation: Mapping[str, Any],
    exact_memory: PublicActionMemory,
    causal_memory: PublicCausalRuleMemory,
    posterior: Tensor,
    parent_logits: Tensor,
    max_support: int,
    guard_mode: str,
    minimum_expected_support_gain: float = 0.25,
) -> tuple[int, dict[str, Any]]:
    """Complement accepted R11 only while public hidden-goal support is broad."""
    if int(max_support) <= R9_ACCEPTED_MAX_SUPPORT:
        raise ValueError("R15 max_support must exceed accepted R11 support threshold")
    if guard_mode not in {"expected_worst_ref", "pareto_ref"}:
        raise ValueError("unknown R15 guard mode")
    if float(minimum_expected_support_gain) <= 0.0:
        raise ValueError("minimum expected support gain must be positive")

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
        }
    if r11_info.get("reason") == "r9_public_progress_complete":
        return int(r11_action), {
            "override": False,
            "reason": "r11_public_progress_complete",
            "r11_action": int(r11_action),
        }

    posterior = _normalize(posterior)
    support = int((posterior > 0.0).sum().item())
    if support <= R9_ACCEPTED_MAX_SUPPORT:
        return int(r11_action), {
            "override": False,
            "reason": "low_support_r11_authority",
            "support": support,
            "r11_action": int(r11_action),
        }
    if support > int(max_support):
        return int(r11_action), {
            "override": False,
            "reason": "support_above_r15_limit",
            "support": support,
            "r11_action": int(r11_action),
            "max_support": int(max_support),
        }

    descriptions = observation.get("actions")
    if not isinstance(descriptions, list):
        raise ValueError("public actions missing")
    submit = [
        i for i, desc in enumerate(descriptions)
        if "submit" in str(desc).lower()
    ]
    if len(submit) != 1:
        raise ValueError("expected exactly one public submit action")
    submit_action = int(submit[0])
    actions = tuple(i for i in range(len(descriptions)) if i != submit_action)

    state = torch.tensor([int(v) for v in observation["state"]], dtype=torch.long)
    context = exact_memory.context_key(observation)
    current_metrics = _metrics(state, posterior)

    if int(r11_action) != submit_action:
        reference_state, reference_rule_count = causal_memory.predict_certified(
            context=context,
            state=state,
            action=int(r11_action),
        )
    else:
        reference_state, reference_rule_count = None, 0
    if reference_state is None:
        reference_state = state
    reference = _metrics(reference_state, posterior)

    best_action: int | None = None
    best_metrics: dict[str, Any] | None = None
    best_rule_count = 0

    for action in actions:
        if int(action) == int(r11_action):
            continue
        nxt, rule_count = causal_memory.predict_certified(
            context=context,
            state=state,
            action=int(action),
        )
        if nxt is None:
            continue
        candidate = _metrics(nxt, posterior)
        support_gain = (
            float(reference["expected_support_after_feedback"])
            - float(candidate["expected_support_after_feedback"])
        )
        if support_gain < float(minimum_expected_support_gain) - _EPS:
            continue

        if guard_mode == "expected_worst_ref":
            safe = bool(
                float(candidate["expected_distance"])
                <= float(reference["expected_distance"]) + _EPS
                and float(candidate["worst_distance"])
                <= float(reference["worst_distance"]) + _EPS
            )
        else:
            cand = candidate["per_goal_distances"]
            ref = reference["per_goal_distances"]
            safe = bool((cand <= ref + _EPS).all())
        if not safe:
            continue

        if best_metrics is None:
            better = True
        else:
            a = (
                float(candidate["expected_support_after_feedback"]),
                float(candidate["expected_distance"]),
                float(candidate["worst_distance"]),
                -float(parent_logits[int(action)].item()),
                int(action),
            )
            b = (
                float(best_metrics["expected_support_after_feedback"]),
                float(best_metrics["expected_distance"]),
                float(best_metrics["worst_distance"]),
                -float(parent_logits[int(best_action)].item()),
                int(best_action),
            )
            better = a < b
        if better:
            best_action = int(action)
            best_metrics = candidate
            best_rule_count = int(rule_count)

    if best_action is None or best_metrics is None:
        return int(r11_action), {
            "override": False,
            "reason": "no_safe_diagnostic_advantage",
            "support": support,
            "r11_action": int(r11_action),
            "reference_rule_count": int(reference_rule_count),
            "reference_expected_support_after_feedback": float(
                reference["expected_support_after_feedback"]
            ),
            "current_expected_support_after_feedback": float(
                current_metrics["expected_support_after_feedback"]
            ),
            "guard_mode": str(guard_mode),
            "max_support": int(max_support),
        }

    return int(best_action), {
        "override": True,
        "reason": "certified_broad_support_diagnostic",
        "support": support,
        "r11_action": int(r11_action),
        "selected_action": int(best_action),
        "selected_rule_count": int(best_rule_count),
        "reference_rule_count": int(reference_rule_count),
        "reference_expected_support_after_feedback": float(
            reference["expected_support_after_feedback"]
        ),
        "selected_expected_support_after_feedback": float(
            best_metrics["expected_support_after_feedback"]
        ),
        "expected_support_gain": float(
            reference["expected_support_after_feedback"]
            - best_metrics["expected_support_after_feedback"]
        ),
        "reference_expected_distance": float(reference["expected_distance"]),
        "selected_expected_distance": float(best_metrics["expected_distance"]),
        "reference_worst_distance": float(reference["worst_distance"]),
        "selected_worst_distance": float(best_metrics["worst_distance"]),
        "guard_mode": str(guard_mode),
        "max_support": int(max_support),
    }
