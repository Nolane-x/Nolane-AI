from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class PublicTransitionSample:
    before: tuple[int, int, int]
    after: tuple[int, int, int]


@dataclass
class PublicCausalRuleMemory:
    """Version space over FIGG-18 public action-effect rules."""

    samples: dict[tuple[str, int], list[PublicTransitionSample]] = field(
        default_factory=dict
    )

    @staticmethod
    def _context(observation: Mapping[str, Any]) -> str:
        regime = observation.get("regime")
        return str(regime) if isinstance(regime, str) else "prereq"

    def update(
        self,
        *,
        action: int,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
    ) -> None:
        descriptions = before.get("actions")
        if not isinstance(descriptions, list):
            return
        if not 0 <= int(action) < len(descriptions):
            return
        if "submit" in str(descriptions[int(action)]).lower():
            return
        before_state = before.get("state")
        after_state = after.get("state")
        if (
            not isinstance(before_state, list)
            or not isinstance(after_state, list)
            or len(before_state) != GOAL_DIMENSIONS
            or len(after_state) != GOAL_DIMENSIONS
        ):
            return
        b = tuple(int(v) for v in before_state)
        a = tuple(int(v) for v in after_state)
        if b == a:
            return
        key = (self._context(before), int(action))
        row = PublicTransitionSample(before=b, after=a)
        bucket = self.samples.setdefault(key, [])
        if row not in bucket:
            bucket.append(row)

    @staticmethod
    def _apply_rule(
        state: tuple[int, int, int],
        *,
        target_dim: int,
        condition_dim: int,
        even_delta: int,
    ) -> tuple[int, int, int]:
        row = list(state)
        delta = (
            int(even_delta)
            if int(state[condition_dim]) % 2 == 0
            else 3 - int(even_delta)
        )
        row[target_dim] = (int(row[target_dim]) + int(delta)) % GOAL_CARDINALITY
        return tuple(int(v) for v in row)

    def consistent_rules(
        self,
        *,
        context: str,
        action: int,
    ) -> tuple[tuple[int, int, int], ...]:
        rows = self.samples.get((str(context), int(action)), [])
        if not rows:
            return ()
        rules: list[tuple[int, int, int]] = []
        for target_dim in range(GOAL_DIMENSIONS):
            for condition_dim in range(GOAL_DIMENSIONS):
                for even_delta in (1, 2):
                    if all(
                        self._apply_rule(
                            sample.before,
                            target_dim=target_dim,
                            condition_dim=condition_dim,
                            even_delta=even_delta,
                        )
                        == sample.after
                        for sample in rows
                    ):
                        rules.append(
                            (
                                int(target_dim),
                                int(condition_dim),
                                int(even_delta),
                            )
                        )
        return tuple(rules)

    def predict_certified(
        self,
        *,
        context: str,
        state: Tensor,
        action: int,
    ) -> tuple[Tensor | None, int]:
        rules = self.consistent_rules(context=context, action=action)
        if not rules:
            return None, 0
        state_tuple = tuple(int(v) for v in state.tolist())
        predictions = {
            self._apply_rule(
                state_tuple,
                target_dim=target_dim,
                condition_dim=condition_dim,
                even_delta=even_delta,
            )
            for target_dim, condition_dim, even_delta in rules
        }
        if len(predictions) != 1:
            return None, len(rules)
        only = next(iter(predictions))
        return torch.tensor(only, dtype=torch.long), len(rules)


@dataclass(frozen=True)
class _Plan:
    first_action: int
    final_distance: float
    first_distance: float
    depth: int
    sequence: tuple[int, ...]


def _expected_distance(state: Tensor, posterior: Tensor) -> float:
    distances = torch.remainder(
        GOAL_TABLE - state.unsqueeze(0),
        GOAL_CARDINALITY,
    ).sum(dim=1).float()
    return float((posterior * distances).sum().item())


def _better(plan: _Plan, incumbent: _Plan | None, parent_logits: Tensor) -> bool:
    if incumbent is None:
        return True
    a = (
        -float(plan.final_distance),
        -int(plan.depth),
        float(parent_logits[plan.first_action].item()),
        -int(plan.first_action),
        tuple(-int(v) for v in plan.sequence),
    )
    b = (
        -float(incumbent.final_distance),
        -int(incumbent.depth),
        float(parent_logits[incumbent.first_action].item()),
        -int(incumbent.first_action),
        tuple(-int(v) for v in incumbent.sequence),
    )
    return a > b


def choose_public_causal_action(
    *,
    observation: Mapping[str, Any],
    exact_memory: PublicActionMemory,
    causal_memory: PublicCausalRuleMemory,
    posterior: Tensor,
    parent_logits: Tensor,
    horizon: int,
) -> tuple[int, dict[str, Any]]:
    """Accepted R9 fallback plus certified causal version-space planning."""
    if int(horizon) < 1 or int(horizon) > 3:
        raise ValueError("R11 horizon must lie in [1,3]")

    r9_action, r9_info = choose_public_counterfactual_action(
        observation=observation,
        memory=exact_memory,
        posterior=posterior,
        parent_logits=parent_logits,
        max_support=R9_ACCEPTED_MAX_SUPPORT,
    )

    target = observation.get("target")
    if isinstance(target, list) and len(target) == GOAL_DIMENSIONS:
        return r9_action, {
            "override": False,
            "reason": "target_visible_r9_exact",
            "r9_action": int(r9_action),
            "horizon": int(horizon),
        }
    if r9_info.get("reason") == "public_progress_complete":
        return r9_action, {
            "override": False,
            "reason": "r9_public_progress_complete",
            "r9_action": int(r9_action),
            "horizon": int(horizon),
        }

    posterior = posterior.detach().float()
    mass = float(posterior.sum().item())
    if mass <= 0.0:
        raise ValueError("posterior needs positive mass")
    posterior = posterior / mass
    support = int((posterior > 0.0).sum().item())
    if support > R9_ACCEPTED_MAX_SUPPORT:
        return r9_action, {
            "override": False,
            "reason": "posterior_too_broad_r9_fallback",
            "support": support,
            "r9_action": int(r9_action),
            "horizon": int(horizon),
        }

    descriptions = observation["actions"]
    submits = [
        i for i, description in enumerate(descriptions)
        if "submit" in str(description).lower()
    ]
    if len(submits) != 1:
        raise ValueError("expected exactly one public submit action")
    submit_action = int(submits[0])
    actions = [i for i in range(len(descriptions)) if i != submit_action]

    state = torch.tensor([int(v) for v in observation["state"]], dtype=torch.long)
    context = exact_memory.context_key(observation)
    current_distance = _expected_distance(state, posterior)

    r9_next = None
    r9_rule_count = 0
    if int(r9_action) != submit_action:
        r9_next, r9_rule_count = causal_memory.predict_certified(
            context=context,
            state=state,
            action=int(r9_action),
        )
    r9_first_distance = (
        _expected_distance(r9_next, posterior)
        if r9_next is not None
        else current_distance
    )

    best_by_first: dict[int, _Plan] = {}
    rule_counts: dict[int, int] = {}

    def explore(
        current_state: Tensor,
        sequence: tuple[int, ...],
        depth: int,
        first_distance: float,
        visited: set[tuple[int, int, int]],
    ) -> None:
        if depth >= 1:
            plan = _Plan(
                first_action=int(sequence[0]),
                final_distance=_expected_distance(current_state, posterior),
                first_distance=float(first_distance),
                depth=int(depth),
                sequence=sequence,
            )
            incumbent = best_by_first.get(plan.first_action)
            if _better(plan, incumbent, parent_logits):
                best_by_first[plan.first_action] = plan
        if depth >= int(horizon):
            return
        for action in actions:
            nxt, count = causal_memory.predict_certified(
                context=context,
                state=current_state,
                action=int(action),
            )
            rule_counts[int(action)] = max(rule_counts.get(int(action), 0), int(count))
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
        if float(plan.first_distance) > float(r9_first_distance) + 1.0e-8:
            continue
        if float(plan.final_distance) >= float(r9_reference_distance) - 1.0e-8:
            continue
        if _better(plan, best, parent_logits):
            best = plan

    if best is None:
        return r9_action, {
            "override": False,
            "reason": "no_certified_causal_advantage",
            "support": support,
            "r9_action": int(r9_action),
            "r9_rule_count": int(r9_rule_count),
            "r9_first_distance": float(r9_first_distance),
            "r9_reference_distance": float(r9_reference_distance),
            "horizon": int(horizon),
        }

    return int(best.first_action), {
        "override": True,
        "reason": "certified_causal_advantage",
        "support": support,
        "r9_action": int(r9_action),
        "r9_rule_count": int(r9_rule_count),
        "selected_rule_count": int(rule_counts.get(int(best.first_action), 0)),
        "r9_first_distance": float(r9_first_distance),
        "r9_reference_distance": float(r9_reference_distance),
        "selected_first_distance": float(best.first_distance),
        "selected_final_distance": float(best.final_distance),
        "selected_depth": int(best.depth),
        "selected_sequence": [int(v) for v in best.sequence],
        "horizon": int(horizon),
    }
