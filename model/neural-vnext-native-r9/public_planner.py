from __future__ import annotations

from dataclasses import dataclass, field
import itertools
from typing import Any, Mapping

import torch
from torch import Tensor

from native_core import PublicActionMemory

GOAL_CARDINALITY = 5
GOAL_DIMENSIONS = 3
GOAL_HYPOTHESIS_COUNT = GOAL_CARDINALITY ** GOAL_DIMENSIONS
PROGRESS_DENOMINATOR = GOAL_DIMENSIONS * (GOAL_CARDINALITY - 1)
GOAL_TABLE = torch.tensor(
    list(itertools.product(range(GOAL_CARDINALITY), repeat=GOAL_DIMENSIONS)),
    dtype=torch.long,
)


@dataclass
class PublicGoalConsistencyBelief:
    tolerance: float = 2.0e-6
    _posterior: Tensor = field(
        default_factory=lambda: torch.full(
            (GOAL_HYPOTHESIS_COUNT,),
            1.0 / GOAL_HYPOTHESIS_COUNT,
            dtype=torch.float32,
        )
    )

    def __post_init__(self) -> None:
        self._posterior = self._posterior.detach().clone().float()
        self._posterior /= self._posterior.sum()

    def update(self, observation: Mapping[str, Any]) -> None:
        state = torch.tensor([int(v) for v in observation["state"]], dtype=torch.long)
        progress = float(observation["progress_signal"])
        visible = observation.get("target")
        if isinstance(visible, list) and len(visible) == GOAL_DIMENSIONS:
            target = torch.tensor([int(v) for v in visible], dtype=torch.long)
            posterior = (GOAL_TABLE == target.unsqueeze(0)).all(dim=1).float()
            self._posterior = posterior / posterior.sum()
            return
        distance = torch.remainder(
            GOAL_TABLE - state.unsqueeze(0),
            GOAL_CARDINALITY,
        ).sum(dim=1).float()
        expected = 1.0 - distance / float(PROGRESS_DENOMINATOR)
        error = (expected - progress).abs()
        consistent = error <= float(self.tolerance)
        filtered = self._posterior * consistent.float()
        mass = float(filtered.sum().item())
        if mass <= 0.0:
            closest = error <= (error.min() + float(self.tolerance))
            filtered = self._posterior * closest.float()
            mass = float(filtered.sum().item())
        if mass <= 0.0:
            raise ValueError("public goal posterior lost all mass")
        self._posterior = filtered / mass

    def encode(self) -> Tensor:
        return self._posterior.detach().clone()

    def support_size(self) -> int:
        return int((self._posterior > 0.0).sum().item())


def _expected_distance(state: Tensor, posterior: Tensor) -> float:
    distances = torch.remainder(
        GOAL_TABLE - state.unsqueeze(0),
        GOAL_CARDINALITY,
    ).sum(dim=1).float()
    return float((posterior * distances).sum().item())


def choose_public_counterfactual_action(
    *,
    observation: Mapping[str, Any],
    memory: PublicActionMemory,
    posterior: Tensor,
    parent_logits: Tensor,
    max_support: int,
) -> tuple[int, dict[str, Any]]:
    """Choose only from public evidence; otherwise exactly fall back to R4."""
    if parent_logits.ndim != 1:
        raise ValueError("parent_logits must be one-dimensional")
    descriptions = observation["actions"]
    parent_action = int(parent_logits.argmax().item())

    # Visible-target families are never overridden.
    target = observation.get("target")
    if isinstance(target, list) and len(target) == GOAL_DIMENSIONS:
        return parent_action, {"override": False, "reason": "target_visible"}

    submit = [
        index
        for index, description in enumerate(descriptions)
        if "submit" in str(description).lower()
    ]
    if len(submit) != 1:
        raise ValueError("expected exactly one public submit action")
    submit_action = submit[0]

    # Public progress=1 proves current state has zero forward distance to hidden goal.
    if float(observation["progress_signal"]) >= 1.0 - 1.0e-6:
        return submit_action, {"override": True, "reason": "public_progress_complete"}

    posterior = posterior.detach().float()
    posterior = posterior / posterior.sum()
    support = int((posterior > 0.0).sum().item())
    if support > int(max_support):
        return parent_action, {
            "override": False,
            "reason": "posterior_too_broad",
            "support": support,
        }

    state = torch.tensor([int(v) for v in observation["state"]], dtype=torch.long)
    current_distance = _expected_distance(state, posterior)
    context = memory.context_key(observation)
    parity = memory.parity_key(observation)
    candidates: list[tuple[float, float, int, float]] = []

    for action in range(len(descriptions)):
        if action == submit_action:
            continue
        stat = memory.by_regime_parity.get((context, parity, action))
        if stat is None or stat.count < 1:
            continue
        delta = torch.tensor(
            [int(round(v)) for v in stat.last_state_delta],
            dtype=torch.long,
        )
        predicted = torch.remainder(state + delta, GOAL_CARDINALITY)
        next_distance = _expected_distance(predicted, posterior)
        improvement = current_distance - next_distance
        if improvement > 1.0e-8:
            candidates.append((
                improvement,
                float(parent_logits[action].item()),
                -action,
                next_distance,
            ))

    if not candidates:
        return parent_action, {
            "override": False,
            "reason": "no_known_improving_action",
            "support": support,
        }

    best = max(candidates)
    action = -int(best[2])
    return action, {
        "override": action != parent_action,
        "reason": "known_public_counterfactual_improvement",
        "support": support,
        "expected_distance_before": current_distance,
        "expected_distance_after": float(best[3]),
        "expected_improvement": float(best[0]),
    }
