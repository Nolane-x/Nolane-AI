from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import torch
from torch import Tensor

from native_core import PublicActionMemory
from public_planner import (
    GOAL_CARDINALITY,
    GOAL_DIMENSIONS,
    GOAL_HYPOTHESIS_COUNT,
    GOAL_TABLE,
    choose_public_counterfactual_action,
)

R9_ACCEPTED_MAX_SUPPORT = 3


def _expected_distance(state: Tensor, posterior: Tensor) -> float:
    distances = torch.remainder(
        GOAL_TABLE - state.unsqueeze(0),
        GOAL_CARDINALITY,
    ).sum(dim=1).float()
    return float((posterior * distances).sum().item())


def _known_transition(
    *,
    memory: PublicActionMemory,
    context: str,
    state: Tensor,
    action: int,
) -> Tensor | None:
    parity = tuple(int(v) % 2 for v in state.tolist())
    stat = memory.by_regime_parity.get((context, parity, int(action)))
    if stat is None or int(stat.count) < 1:
        return None
    rounded = [int(round(float(v))) for v in stat.last_state_delta]
    if any(abs(float(v) - float(r)) > 1.0e-6 for v, r in zip(stat.last_state_delta, rounded)):
        return None
    delta = torch.tensor(rounded, dtype=torch.long)
    return torch.remainder(state + delta, GOAL_CARDINALITY)


@dataclass(frozen=True)
class _Plan:
    first_action: int
    final_distance: float
    depth: int
    first_distance: float
    sequence: tuple[int, ...]


def _better_plan(candidate: _Plan, incumbent: _Plan | None, parent_logits: Tensor) -> bool:
    if incumbent is None:
        return True
    key_candidate = (
        -float(candidate.final_distance),
        -int(candidate.depth),
        float(parent_logits[candidate.first_action].item()),
        -int(candidate.first_action),
        tuple(-int(v) for v in candidate.sequence),
    )
    key_incumbent = (
        -float(incumbent.final_distance),
        -int(incumbent.depth),
        float(parent_logits[incumbent.first_action].item()),
        -int(incumbent.first_action),
        tuple(-int(v) for v in incumbent.sequence),
    )
    return key_candidate > key_incumbent


def choose_public_multistep_action(
    *,
    observation: Mapping[str, Any],
    memory: PublicActionMemory,
    posterior: Tensor,
    parent_logits: Tensor,
    max_support: int = R9_ACCEPTED_MAX_SUPPORT,
    horizon: int = 2,
) -> tuple[int, dict[str, Any]]:
    """R10: exact accepted R9 fallback plus conservative known-model lookahead."""
    if parent_logits.ndim != 1:
        raise ValueError("parent_logits must be one-dimensional")
    if int(max_support) != R9_ACCEPTED_MAX_SUPPORT:
        raise ValueError("R10 keeps the accepted R9 max_support=3 fixed")
    if int(horizon) < 2 or int(horizon) > 4:
        raise ValueError("R10 horizon must lie in [2,4]")

    r9_action, r9_info = choose_public_counterfactual_action(
        observation=observation,
        memory=memory,
        posterior=posterior,
        parent_logits=parent_logits,
        max_support=R9_ACCEPTED_MAX_SUPPORT,
    )

    target = observation.get("target")
    if isinstance(target, list) and len(target) == GOAL_DIMENSIONS:
        return r9_action, {
            "override": False,
            "reason": "target_visible_r9_exact",
            "r9_action": r9_action,
            "horizon": int(horizon),
        }
    if r9_info.get("reason") == "public_progress_complete":
        return r9_action, {
            "override": False,
            "reason": "r9_public_progress_complete",
            "r9_action": r9_action,
            "horizon": int(horizon),
        }

    posterior = posterior.detach().float()
    mass = float(posterior.sum().item())
    if mass <= 0.0:
        raise ValueError("posterior needs positive mass")
    posterior = posterior / mass
    support = int((posterior > 0.0).sum().item())
    if support > int(max_support):
        return r9_action, {
            "override": False,
            "reason": "posterior_too_broad_r9_fallback",
            "support": support,
            "r9_action": r9_action,
            "horizon": int(horizon),
        }

    descriptions = observation["actions"]
    submit_actions = [
        i for i, description in enumerate(descriptions)
        if "submit" in str(description).lower()
    ]
    if len(submit_actions) != 1:
        raise ValueError("expected exactly one public submit action")
    submit_action = int(submit_actions[0])
    non_submit = [i for i in range(len(descriptions)) if i != submit_action]

    state = torch.tensor([int(v) for v in observation["state"]], dtype=torch.long)
    context = memory.context_key(observation)
    current_distance = _expected_distance(state, posterior)

    r9_next = None if r9_action == submit_action else _known_transition(
        memory=memory,
        context=context,
        state=state,
        action=r9_action,
    )
    r9_first_distance = (
        _expected_distance(r9_next, posterior)
        if r9_next is not None
        else current_distance
    )

    best_by_first: dict[int, _Plan] = {}

    def explore(
        current_state: Tensor,
        sequence: tuple[int, ...],
        depth: int,
        first_distance: float,
        visited: set[tuple[int, int, int]],
    ) -> None:
        if depth >= 2:
            plan = _Plan(
                first_action=int(sequence[0]),
                final_distance=_expected_distance(current_state, posterior),
                depth=int(depth),
                first_distance=float(first_distance),
                sequence=sequence,
            )
            incumbent = best_by_first.get(plan.first_action)
            if _better_plan(plan, incumbent, parent_logits):
                best_by_first[plan.first_action] = plan
        if depth >= int(horizon):
            return
        for action in non_submit:
            nxt = _known_transition(
                memory=memory,
                context=context,
                state=current_state,
                action=action,
            )
            if nxt is None:
                continue
            signature = tuple(int(v) for v in nxt.tolist())
            if signature in visited:
                continue
            next_first_distance = (
                _expected_distance(nxt, posterior)
                if depth == 0
                else first_distance
            )
            explore(
                nxt,
                sequence + (int(action),),
                depth + 1,
                float(next_first_distance),
                visited | {signature},
            )

    explore(
        state,
        (),
        0,
        current_distance,
        {tuple(int(v) for v in state.tolist())},
    )

    r9_plan = best_by_first.get(int(r9_action))
    r9_reference_distance = (
        float(r9_plan.final_distance)
        if r9_plan is not None
        else float(r9_first_distance)
    )

    best: _Plan | None = None
    for action, plan in best_by_first.items():
        if int(action) == int(r9_action):
            continue
        # Conservative guard: never accept a first step whose expected
        # distance is worse than R9's first step.
        if float(plan.first_distance) > float(r9_first_distance) + 1.0e-8:
            continue
        # Require a strict known-model multi-step advantage over the best
        # known continuation that starts with the accepted R9 action.
        if float(plan.final_distance) >= float(r9_reference_distance) - 1.0e-8:
            continue
        if _better_plan(plan, best, parent_logits):
            best = plan

    if best is None:
        return r9_action, {
            "override": False,
            "reason": "no_certified_multistep_advantage",
            "support": support,
            "r9_action": r9_action,
            "r9_first_distance": r9_first_distance,
            "r9_reference_distance": r9_reference_distance,
            "horizon": int(horizon),
        }

    return int(best.first_action), {
        "override": int(best.first_action) != int(r9_action),
        "reason": "certified_multistep_advantage",
        "support": support,
        "r9_action": int(r9_action),
        "r9_first_distance": float(r9_first_distance),
        "r9_reference_distance": float(r9_reference_distance),
        "selected_first_distance": float(best.first_distance),
        "selected_final_distance": float(best.final_distance),
        "selected_depth": int(best.depth),
        "selected_sequence": [int(v) for v in best.sequence],
        "horizon": int(horizon),
    }
