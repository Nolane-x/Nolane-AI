from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest

from .reasoning_frontier import ReasoningFrontier


COMPONENT_ID = "external.reasoning_invention"
COMPONENT_VERSION = "0.0.5"
SCHEMA_VERSION = "reasoning-metacontrol-v1"
DESIGN_LINEAGE = (
    "post-Epoch-0 bounded value-of-thought control over immutable reasoning frontiers; "
    "Pareto action sets preserve explicit tradeoffs"
)


class MetaActionKind(str, Enum):
    TARGET_UNKNOWN = "target_unknown"
    GENERATE_CHALLENGER = "generate_challenger"
    INVERT_ASSUMPTION = "invert_assumption"
    SHIFT_REPRESENTATION = "shift_representation"
    DESIGN_EXPERIMENT = "design_experiment"
    CAUSAL_CHALLENGE = "causal_challenge"
    FRESH_CONTEXT_REVIEW = "fresh_context_review"


class ControlDisposition(str, Enum):
    CONTINUE = "continue"
    HALT_NO_FURTHER_VALUE = "halt_no_further_value"
    ABSTAIN_UNRESOLVED = "abstain_unresolved"


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return value


def _ids(value: object, name: str, *, minimum: int = 0) -> tuple[str, ...]:
    rows = tuple(_nonempty(row, name) for row in _sequence(value, name))
    if len(rows) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} values")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(rows))


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a finite number") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _score(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return number


def _positive_finite(value: object, name: str) -> float:
    number = _finite(value, name)
    if number <= 0.0:
        raise ValueError(f"{name} must be positive")
    return number


def _nonnegative_finite(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _identity(prefix: str, state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(state))}"


@dataclass(frozen=True, slots=True)
class ReasoningActionProposal:
    frontier_id: str
    kind: MetaActionKind
    target_ids: tuple[str, ...]
    expected_decision_value: float
    expected_information_gain: float
    uncertainty_reduction: float
    estimated_cost: float
    residual_risk: float
    reason: str
    action_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frontier_id", _nonempty(self.frontier_id, "frontier id"))
        object.__setattr__(self, "kind", MetaActionKind(self.kind))
        object.__setattr__(self, "target_ids", _ids(self.target_ids, "action target ids", minimum=1))
        object.__setattr__(
            self,
            "expected_decision_value",
            _score(self.expected_decision_value, "expected decision value"),
        )
        object.__setattr__(
            self,
            "expected_information_gain",
            _score(self.expected_information_gain, "expected information gain"),
        )
        object.__setattr__(
            self,
            "uncertainty_reduction",
            _score(self.uncertainty_reduction, "uncertainty reduction"),
        )
        object.__setattr__(self, "estimated_cost", _positive_finite(self.estimated_cost, "estimated cost"))
        object.__setattr__(self, "residual_risk", _score(self.residual_risk, "residual risk"))
        object.__setattr__(self, "reason", _nonempty(self.reason, "action reason"))
        object.__setattr__(self, "action_id", _identity("reasoning-action", self._semantic_state()))

    @property
    def marginal_gain(self) -> float:
        return max(
            self.expected_decision_value,
            self.expected_information_gain,
            self.uncertainty_reduction,
        )

    def _semantic_state(self) -> dict[str, object]:
        return {
            "frontier_id": self.frontier_id,
            "kind": self.kind.value,
            "target_ids": list(self.target_ids),
            "expected_decision_value": self.expected_decision_value,
            "expected_information_gain": self.expected_information_gain,
            "uncertainty_reduction": self.uncertainty_reduction,
            "estimated_cost": self.estimated_cost,
            "residual_risk": self.residual_risk,
            "reason": self.reason,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "action_id": self.action_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ReasoningActionProposal":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported metareasoning action schema")
        row = cls(
            frontier_id=state["frontier_id"],
            kind=MetaActionKind(str(state["kind"])),
            target_ids=tuple(_sequence(state.get("target_ids", ()), "action target id state")),
            expected_decision_value=state["expected_decision_value"],
            expected_information_gain=state["expected_information_gain"],
            uncertainty_reduction=state["uncertainty_reduction"],
            estimated_cost=state["estimated_cost"],
            residual_risk=state["residual_risk"],
            reason=state["reason"],
        )
        if str(state.get("action_id")) != row.action_id:
            raise ValueError("reasoning action identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical reasoning action state")
        return row


def dominates_action(left: ReasoningActionProposal, right: ReasoningActionProposal) -> bool:
    if not isinstance(left, ReasoningActionProposal) or not isinstance(right, ReasoningActionProposal):
        raise TypeError("action dominance requires ReasoningActionProposal values")
    if left.frontier_id != right.frontier_id:
        raise ValueError("action dominance requires one reasoning frontier")

    maximize_left = (
        left.expected_decision_value,
        left.expected_information_gain,
        left.uncertainty_reduction,
    )
    maximize_right = (
        right.expected_decision_value,
        right.expected_information_gain,
        right.uncertainty_reduction,
    )
    minimize_left = (left.estimated_cost, left.residual_risk)
    minimize_right = (right.estimated_cost, right.residual_risk)

    no_worse = all(a >= b for a, b in zip(maximize_left, maximize_right)) and all(
        a <= b for a, b in zip(minimize_left, minimize_right)
    )
    strictly_better = any(a > b for a, b in zip(maximize_left, maximize_right)) or any(
        a < b for a, b in zip(minimize_left, minimize_right)
    )
    return no_worse and strictly_better


def pareto_action_frontier(
    proposals: Sequence[ReasoningActionProposal],
) -> tuple[ReasoningActionProposal, ...]:
    rows = tuple(_sequence(proposals, "reasoning action proposals"))
    if not all(isinstance(row, ReasoningActionProposal) for row in rows):
        raise TypeError("reasoning action proposals must contain ReasoningActionProposal values")
    action_ids = tuple(row.action_id for row in rows)
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("reasoning action proposals must not contain duplicate action ids")
    if not rows:
        return ()
    frontier_ids = {row.frontier_id for row in rows}
    if len(frontier_ids) != 1:
        raise ValueError("reasoning action proposals must bind one reasoning frontier")

    nondominated = tuple(
        candidate
        for candidate in rows
        if not any(
            other.action_id != candidate.action_id and dominates_action(other, candidate)
            for other in rows
        )
    )
    return tuple(sorted(nondominated, key=lambda row: row.action_id))


@dataclass(frozen=True, slots=True)
class MetareasoningBudget:
    frontier_id: str
    remaining_actions: int
    remaining_cost: float
    minimum_actionable_gain: float
    budget_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frontier_id", _nonempty(self.frontier_id, "frontier id"))
        object.__setattr__(
            self,
            "remaining_actions",
            _nonnegative_int(self.remaining_actions, "remaining actions"),
        )
        object.__setattr__(
            self,
            "remaining_cost",
            _nonnegative_finite(self.remaining_cost, "remaining cost"),
        )
        object.__setattr__(
            self,
            "minimum_actionable_gain",
            _score(self.minimum_actionable_gain, "minimum actionable gain"),
        )
        object.__setattr__(self, "budget_id", _identity("metareasoning-budget", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "frontier_id": self.frontier_id,
            "remaining_actions": self.remaining_actions,
            "remaining_cost": self.remaining_cost,
            "minimum_actionable_gain": self.minimum_actionable_gain,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "budget_id": self.budget_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "MetareasoningBudget":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported metareasoning budget schema")
        row = cls(
            frontier_id=state["frontier_id"],
            remaining_actions=state["remaining_actions"],
            remaining_cost=state["remaining_cost"],
            minimum_actionable_gain=state["minimum_actionable_gain"],
        )
        if str(state.get("budget_id")) != row.budget_id:
            raise ValueError("metareasoning budget identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical metareasoning budget state")
        return row


@dataclass(frozen=True, slots=True)
class ReasoningControlDecision:
    frontier_id: str
    budget_id: str
    disposition: ControlDisposition
    pareto_action_ids: tuple[str, ...]
    unresolved_overturning_unknown_ids: tuple[str, ...]
    reason: str
    decision_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frontier_id", _nonempty(self.frontier_id, "frontier id"))
        object.__setattr__(self, "budget_id", _nonempty(self.budget_id, "metareasoning budget id"))
        object.__setattr__(self, "disposition", ControlDisposition(self.disposition))
        actions = _ids(self.pareto_action_ids, "Pareto action ids")
        unresolved = _ids(
            self.unresolved_overturning_unknown_ids,
            "unresolved overturning unknown ids",
        )
        if self.disposition is ControlDisposition.CONTINUE and not actions:
            raise ValueError("continue disposition requires at least one Pareto action")
        if self.disposition is not ControlDisposition.CONTINUE and actions:
            raise ValueError("terminal metareasoning disposition cannot carry next actions")
        if self.disposition is ControlDisposition.ABSTAIN_UNRESOLVED and not unresolved:
            raise ValueError("unresolved abstention requires an overturning unknown")
        if self.disposition is ControlDisposition.HALT_NO_FURTHER_VALUE and unresolved:
            raise ValueError("no-further-value halt cannot hide an overturning unknown")
        object.__setattr__(self, "pareto_action_ids", actions)
        object.__setattr__(self, "unresolved_overturning_unknown_ids", unresolved)
        object.__setattr__(self, "reason", _nonempty(self.reason, "control decision reason"))
        object.__setattr__(self, "decision_id", _identity("reasoning-control", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "frontier_id": self.frontier_id,
            "budget_id": self.budget_id,
            "disposition": self.disposition.value,
            "pareto_action_ids": list(self.pareto_action_ids),
            "unresolved_overturning_unknown_ids": list(self.unresolved_overturning_unknown_ids),
            "reason": self.reason,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "decision_id": self.decision_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ReasoningControlDecision":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported reasoning control decision schema")
        row = cls(
            frontier_id=state["frontier_id"],
            budget_id=state["budget_id"],
            disposition=ControlDisposition(str(state["disposition"])),
            pareto_action_ids=tuple(_sequence(state.get("pareto_action_ids", ()), "Pareto action id state")),
            unresolved_overturning_unknown_ids=tuple(
                _sequence(
                    state.get("unresolved_overturning_unknown_ids", ()),
                    "unresolved overturning unknown id state",
                )
            ),
            reason=state["reason"],
        )
        if str(state.get("decision_id")) != row.decision_id:
            raise ValueError("reasoning control decision identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical reasoning control decision state")
        return row


def plan_next_reasoning_actions(
    frontier: ReasoningFrontier,
    budget: MetareasoningBudget,
    proposals: Sequence[ReasoningActionProposal],
) -> ReasoningControlDecision:
    if not isinstance(frontier, ReasoningFrontier):
        raise TypeError("frontier must be ReasoningFrontier")
    if not isinstance(budget, MetareasoningBudget):
        raise TypeError("budget must be MetareasoningBudget")
    if budget.frontier_id != frontier.frontier_id:
        raise ValueError("metareasoning budget is bound to the wrong frontier")

    rows = tuple(_sequence(proposals, "reasoning action proposals"))
    if not all(isinstance(row, ReasoningActionProposal) for row in rows):
        raise TypeError("reasoning action proposals must contain ReasoningActionProposal values")
    ids = tuple(row.action_id for row in rows)
    if len(ids) != len(set(ids)):
        raise ValueError("reasoning action proposals must not contain duplicate action ids")
    if any(row.frontier_id != frontier.frontier_id for row in rows):
        raise ValueError("reasoning action proposal is bound to the wrong frontier")

    unresolved = frontier.overturning_unknown_ids
    viable = tuple(
        row
        for row in rows
        if row.estimated_cost <= budget.remaining_cost
        and row.marginal_gain >= budget.minimum_actionable_gain
    )

    if budget.remaining_actions > 0 and viable:
        action_frontier = pareto_action_frontier(viable)
        return ReasoningControlDecision(
            frontier_id=frontier.frontier_id,
            budget_id=budget.budget_id,
            disposition=ControlDisposition.CONTINUE,
            pareto_action_ids=tuple(row.action_id for row in action_frontier),
            unresolved_overturning_unknown_ids=unresolved,
            reason="at least one budget-feasible reasoning action clears the declared marginal-value floor",
        )

    if unresolved:
        return ReasoningControlDecision(
            frontier_id=frontier.frontier_id,
            budget_id=budget.budget_id,
            disposition=ControlDisposition.ABSTAIN_UNRESOLVED,
            pareto_action_ids=(),
            unresolved_overturning_unknown_ids=unresolved,
            reason="no viable reasoning action remains while a decision-overturning unknown is unresolved",
        )

    return ReasoningControlDecision(
        frontier_id=frontier.frontier_id,
        budget_id=budget.budget_id,
        disposition=ControlDisposition.HALT_NO_FURTHER_VALUE,
        pareto_action_ids=(),
        unresolved_overturning_unknown_ids=(),
        reason="no viable reasoning action clears the declared marginal-value floor and no overturning unknown remains",
    )


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "DESIGN_LINEAGE",
    "MetaActionKind",
    "ControlDisposition",
    "ReasoningActionProposal",
    "MetareasoningBudget",
    "ReasoningControlDecision",
    "dominates_action",
    "pareto_action_frontier",
    "plan_next_reasoning_actions",
)
