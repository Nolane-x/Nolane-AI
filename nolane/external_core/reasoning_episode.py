from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest

from .reasoning_frontier import ReasoningFrontier
from .reasoning_metacontrol import (
    ControlDisposition,
    MetareasoningBudget,
    ReasoningActionProposal,
    ReasoningControlDecision,
)


COMPONENT_ID = "external.reasoning_invention"
COMPONENT_VERSION = "0.0.3"
SCHEMA_VERSION = "reasoning-episode-v1"
DESIGN_LINEAGE = (
    "post-Epoch-0 replayable reasoning-frontier evolution with exact budget conservation, "
    "stale-state fencing, transition evidence and fail-closed terminal semantics"
)


class ReasoningEpisodeStatus(str, Enum):
    ACTIVE = "active"
    HALTED_NO_FURTHER_VALUE = "halted_no_further_value"
    ABSTAINED_UNRESOLVED = "abstained_unresolved"
    ABSTAINED_BUDGET_OVERRUN = "abstained_budget_overrun"


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return value


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
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


def _positive_finite(value: object, name: str) -> float:
    number = _finite(value, name)
    if number <= 0.0:
        raise ValueError(f"{name} must be positive")
    return number


def _score(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return number


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _identity(prefix: str, state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(state))}"


def _episode_key_state(
    root_frontier: ReasoningFrontier,
    action_limit: int,
    cost_limit: float,
    minimum_actionable_gain: float,
) -> dict[str, object]:
    return {
        "root_frontier_id": root_frontier.frontier_id,
        "action_limit": action_limit,
        "cost_limit": cost_limit,
        "minimum_actionable_gain": minimum_actionable_gain,
    }


def _budget_for(
    frontier: ReasoningFrontier,
    *,
    action_limit: int,
    cost_limit: float,
    minimum_actionable_gain: float,
    spent_actions: int,
    spent_cost: float,
) -> MetareasoningBudget:
    if spent_actions < 0:
        raise ValueError("spent actions must be non-negative")
    spent = _finite(spent_cost, "spent cost")
    if spent < 0.0:
        raise ValueError("spent cost must be non-negative")
    return MetareasoningBudget(
        frontier_id=frontier.frontier_id,
        remaining_actions=max(action_limit - spent_actions, 0),
        remaining_cost=max(cost_limit - spent, 0.0),
        minimum_actionable_gain=minimum_actionable_gain,
    )


def _validate_successor(previous: ReasoningFrontier, next_frontier: ReasoningFrontier) -> None:
    if not isinstance(previous, ReasoningFrontier) or not isinstance(next_frontier, ReasoningFrontier):
        raise TypeError("frontier continuity requires ReasoningFrontier values")
    if previous.frontier_id == next_frontier.frontier_id:
        raise ValueError("reasoning successor frontier must change")
    checks = (
        ("reasoning receipt", previous.reasoning_receipt_id, next_frontier.reasoning_receipt_id),
        ("objective", previous.objective_id, next_frontier.objective_id),
        ("cognitive library", previous.cognitive_library_digest, next_frontier.cognitive_library_digest),
        ("hard constraint", previous.hard_constraint_ids, next_frontier.hard_constraint_ids),
        ("branch budget", previous.branch_budget, next_frontier.branch_budget),
    )
    for label, left, right in checks:
        if left != right:
            raise ValueError(f"reasoning episode continuity forbids {label} drift")


def _validate_control_authority(
    frontier: ReasoningFrontier,
    budget: MetareasoningBudget,
    decision: ReasoningControlDecision,
    action: ReasoningActionProposal,
) -> None:
    if not isinstance(decision, ReasoningControlDecision):
        raise TypeError("control decision must be ReasoningControlDecision")
    if not isinstance(action, ReasoningActionProposal):
        raise TypeError("selected action must be ReasoningActionProposal")
    if decision.disposition is not ControlDisposition.CONTINUE:
        raise ValueError("reasoning episode advance requires a continue control decision")
    if decision.frontier_id != frontier.frontier_id:
        raise ValueError("reasoning control decision is stale for the current frontier")
    if decision.budget_id != budget.budget_id:
        raise ValueError("reasoning control decision is stale for the current budget")
    if decision.unresolved_overturning_unknown_ids != frontier.overturning_unknown_ids:
        raise ValueError("reasoning control decision does not match current overturning unknowns")
    if budget.remaining_actions <= 0:
        raise ValueError("reasoning action budget is exhausted")
    if action.frontier_id != frontier.frontier_id:
        raise ValueError("selected reasoning action is stale for the current frontier")
    if action.action_id not in decision.pareto_action_ids:
        raise ValueError("selected reasoning action is not Pareto-authorized by the control decision")
    if action.estimated_cost > budget.remaining_cost:
        raise ValueError("selected reasoning action estimated cost exceeds the current budget")
    if action.marginal_gain < budget.minimum_actionable_gain:
        raise ValueError("selected reasoning action is below the current actionable-gain floor")


def _validate_terminal_control(
    frontier: ReasoningFrontier,
    budget: MetareasoningBudget,
    decision: ReasoningControlDecision,
) -> ReasoningEpisodeStatus:
    if not isinstance(decision, ReasoningControlDecision):
        raise TypeError("terminal control decision must be ReasoningControlDecision")
    if decision.frontier_id != frontier.frontier_id:
        raise ValueError("terminal control decision is stale for the current frontier")
    if decision.budget_id != budget.budget_id:
        raise ValueError("terminal control decision is stale for the current budget")
    if decision.unresolved_overturning_unknown_ids != frontier.overturning_unknown_ids:
        raise ValueError("terminal control decision does not match current overturning unknowns")
    if decision.disposition is ControlDisposition.CONTINUE:
        raise ValueError("continue control decision cannot close a reasoning episode")
    if decision.disposition is ControlDisposition.HALT_NO_FURTHER_VALUE:
        return ReasoningEpisodeStatus.HALTED_NO_FURTHER_VALUE
    if decision.disposition is ControlDisposition.ABSTAIN_UNRESOLVED:
        return ReasoningEpisodeStatus.ABSTAINED_UNRESOLVED
    raise ValueError("unsupported terminal reasoning disposition")


@dataclass(frozen=True, slots=True)
class ReasoningFrontierDelta:
    previous_frontier_id: str
    next_frontier_id: str
    resolved_unknown_ids: tuple[str, ...]
    introduced_unknown_ids: tuple[str, ...]
    retired_hypothesis_ids: tuple[str, ...]
    introduced_hypothesis_ids: tuple[str, ...]
    revised_hypothesis_ids: tuple[str, ...]
    retired_assumption_ids: tuple[str, ...]
    introduced_assumption_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    delta_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "previous_frontier_id", _nonempty(self.previous_frontier_id, "previous frontier id"))
        object.__setattr__(self, "next_frontier_id", _nonempty(self.next_frontier_id, "next frontier id"))
        if self.previous_frontier_id == self.next_frontier_id:
            raise ValueError("frontier delta requires distinct frontier ids")
        for name in (
            "resolved_unknown_ids",
            "introduced_unknown_ids",
            "retired_hypothesis_ids",
            "introduced_hypothesis_ids",
            "revised_hypothesis_ids",
            "retired_assumption_ids",
            "introduced_assumption_ids",
        ):
            object.__setattr__(self, name, _ids(getattr(self, name), name.replace("_", " ")))
        object.__setattr__(self, "evidence_ids", _ids(self.evidence_ids, "frontier transition evidence ids", minimum=1))
        object.__setattr__(self, "delta_id", _identity("reasoning-frontier-delta", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "previous_frontier_id": self.previous_frontier_id,
            "next_frontier_id": self.next_frontier_id,
            "resolved_unknown_ids": list(self.resolved_unknown_ids),
            "introduced_unknown_ids": list(self.introduced_unknown_ids),
            "retired_hypothesis_ids": list(self.retired_hypothesis_ids),
            "introduced_hypothesis_ids": list(self.introduced_hypothesis_ids),
            "revised_hypothesis_ids": list(self.revised_hypothesis_ids),
            "retired_assumption_ids": list(self.retired_assumption_ids),
            "introduced_assumption_ids": list(self.introduced_assumption_ids),
            "evidence_ids": list(self.evidence_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "delta_id": self.delta_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ReasoningFrontierDelta":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported reasoning frontier delta schema")
        row = cls(
            previous_frontier_id=state["previous_frontier_id"],
            next_frontier_id=state["next_frontier_id"],
            resolved_unknown_ids=tuple(_sequence(state.get("resolved_unknown_ids", ()), "resolved unknown state")),
            introduced_unknown_ids=tuple(_sequence(state.get("introduced_unknown_ids", ()), "introduced unknown state")),
            retired_hypothesis_ids=tuple(_sequence(state.get("retired_hypothesis_ids", ()), "retired hypothesis state")),
            introduced_hypothesis_ids=tuple(_sequence(state.get("introduced_hypothesis_ids", ()), "introduced hypothesis state")),
            revised_hypothesis_ids=tuple(_sequence(state.get("revised_hypothesis_ids", ()), "revised hypothesis state")),
            retired_assumption_ids=tuple(_sequence(state.get("retired_assumption_ids", ()), "retired assumption state")),
            introduced_assumption_ids=tuple(_sequence(state.get("introduced_assumption_ids", ()), "introduced assumption state")),
            evidence_ids=tuple(_sequence(state.get("evidence_ids", ()), "frontier evidence state")),
        )
        if str(state.get("delta_id")) != row.delta_id:
            raise ValueError("reasoning frontier delta identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical reasoning frontier delta state")
        return row


def derive_frontier_delta(
    previous: ReasoningFrontier,
    next_frontier: ReasoningFrontier,
    evidence_ids: Sequence[str],
) -> ReasoningFrontierDelta:
    if not isinstance(previous, ReasoningFrontier) or not isinstance(next_frontier, ReasoningFrontier):
        raise TypeError("frontier delta derivation requires ReasoningFrontier values")
    if previous.frontier_id == next_frontier.frontier_id:
        raise ValueError("frontier delta requires a changed successor frontier")
    evidence = _ids(tuple(evidence_ids), "frontier transition evidence ids", minimum=1)

    previous_unknowns = {row.unknown_id for row in previous.unknowns}
    next_unknowns = {row.unknown_id for row in next_frontier.unknowns}
    previous_rivals = {row.hypothesis_id: row.rival_id for row in previous.rivals}
    next_rivals = {row.hypothesis_id: row.rival_id for row in next_frontier.rivals}
    previous_hypotheses = set(previous_rivals)
    next_hypotheses = set(next_rivals)
    revised = {
        hypothesis_id
        for hypothesis_id in previous_hypotheses & next_hypotheses
        if previous_rivals[hypothesis_id] != next_rivals[hypothesis_id]
    }
    previous_assumptions = set(previous.assumption_ids)
    next_assumptions = set(next_frontier.assumption_ids)

    return ReasoningFrontierDelta(
        previous_frontier_id=previous.frontier_id,
        next_frontier_id=next_frontier.frontier_id,
        resolved_unknown_ids=tuple(previous_unknowns - next_unknowns),
        introduced_unknown_ids=tuple(next_unknowns - previous_unknowns),
        retired_hypothesis_ids=tuple(previous_hypotheses - next_hypotheses),
        introduced_hypothesis_ids=tuple(next_hypotheses - previous_hypotheses),
        revised_hypothesis_ids=tuple(revised),
        retired_assumption_ids=tuple(previous_assumptions - next_assumptions),
        introduced_assumption_ids=tuple(next_assumptions - previous_assumptions),
        evidence_ids=evidence,
    )


@dataclass(frozen=True, slots=True)
class ReasoningFrontierTransition:
    episode_key: str
    generation: int
    previous_frontier_id: str
    next_frontier: ReasoningFrontier
    control_decision: ReasoningControlDecision
    selected_action: ReasoningActionProposal
    delta: ReasoningFrontierDelta
    observed_cost: float
    budget_overrun: bool
    transition_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "episode_key", _nonempty(self.episode_key, "episode key"))
        object.__setattr__(self, "generation", _positive_int(self.generation, "transition generation"))
        object.__setattr__(self, "previous_frontier_id", _nonempty(self.previous_frontier_id, "previous frontier id"))
        if not isinstance(self.next_frontier, ReasoningFrontier):
            raise TypeError("next frontier must be ReasoningFrontier")
        if not isinstance(self.control_decision, ReasoningControlDecision):
            raise TypeError("control decision must be ReasoningControlDecision")
        if not isinstance(self.selected_action, ReasoningActionProposal):
            raise TypeError("selected action must be ReasoningActionProposal")
        if not isinstance(self.delta, ReasoningFrontierDelta):
            raise TypeError("frontier delta must be ReasoningFrontierDelta")
        if self.control_decision.disposition is not ControlDisposition.CONTINUE:
            raise ValueError("frontier transition requires a continue control decision")
        if self.control_decision.frontier_id != self.previous_frontier_id:
            raise ValueError("frontier transition control decision binds the wrong predecessor")
        if self.selected_action.frontier_id != self.previous_frontier_id:
            raise ValueError("frontier transition action binds the wrong predecessor")
        if self.selected_action.action_id not in self.control_decision.pareto_action_ids:
            raise ValueError("frontier transition action is not Pareto-authorized")
        if self.delta.previous_frontier_id != self.previous_frontier_id:
            raise ValueError("frontier delta binds the wrong predecessor")
        if self.delta.next_frontier_id != self.next_frontier.frontier_id:
            raise ValueError("frontier delta binds the wrong successor")
        object.__setattr__(self, "observed_cost", _positive_finite(self.observed_cost, "observed reasoning cost"))
        if not isinstance(self.budget_overrun, bool):
            raise TypeError("budget_overrun must be bool")
        object.__setattr__(self, "transition_id", _identity("reasoning-frontier-transition", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "episode_key": self.episode_key,
            "generation": self.generation,
            "previous_frontier_id": self.previous_frontier_id,
            "next_frontier": self.next_frontier.to_state(),
            "control_decision": self.control_decision.to_state(),
            "selected_action": self.selected_action.to_state(),
            "delta": self.delta.to_state(),
            "observed_cost": self.observed_cost,
            "budget_overrun": self.budget_overrun,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "transition_id": self.transition_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ReasoningFrontierTransition":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported reasoning frontier transition schema")
        row = cls(
            episode_key=state["episode_key"],
            generation=state["generation"],
            previous_frontier_id=state["previous_frontier_id"],
            next_frontier=ReasoningFrontier.from_state(_mapping(state.get("next_frontier"), "next frontier state")),
            control_decision=ReasoningControlDecision.from_state(
                _mapping(state.get("control_decision"), "control decision state")
            ),
            selected_action=ReasoningActionProposal.from_state(
                _mapping(state.get("selected_action"), "selected action state")
            ),
            delta=ReasoningFrontierDelta.from_state(_mapping(state.get("delta"), "frontier delta state")),
            observed_cost=state["observed_cost"],
            budget_overrun=state["budget_overrun"],
        )
        if str(state.get("transition_id")) != row.transition_id:
            raise ValueError("reasoning frontier transition identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical reasoning frontier transition state")
        return row


@dataclass(frozen=True, slots=True)
class ReasoningEpisode:
    root_frontier: ReasoningFrontier
    current_frontier: ReasoningFrontier
    action_limit: int
    cost_limit: float
    minimum_actionable_gain: float
    transitions: tuple[ReasoningFrontierTransition, ...] = ()
    terminal_control_decision: ReasoningControlDecision | None = None
    status: ReasoningEpisodeStatus = ReasoningEpisodeStatus.ACTIVE
    episode_key: str = field(init=False)
    snapshot_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.root_frontier, ReasoningFrontier):
            raise TypeError("root frontier must be ReasoningFrontier")
        if not isinstance(self.current_frontier, ReasoningFrontier):
            raise TypeError("current frontier must be ReasoningFrontier")
        object.__setattr__(self, "action_limit", _positive_int(self.action_limit, "reasoning action limit"))
        object.__setattr__(self, "cost_limit", _positive_finite(self.cost_limit, "reasoning cost limit"))
        object.__setattr__(
            self,
            "minimum_actionable_gain",
            _score(self.minimum_actionable_gain, "minimum actionable gain"),
        )
        transitions = tuple(_sequence(self.transitions, "reasoning episode transitions"))
        if not all(isinstance(row, ReasoningFrontierTransition) for row in transitions):
            raise TypeError("reasoning episode transitions must contain ReasoningFrontierTransition values")
        object.__setattr__(self, "transitions", transitions)
        if self.terminal_control_decision is not None and not isinstance(
            self.terminal_control_decision, ReasoningControlDecision
        ):
            raise TypeError("terminal control decision must be ReasoningControlDecision or None")
        object.__setattr__(self, "status", ReasoningEpisodeStatus(self.status))
        object.__setattr__(
            self,
            "episode_key",
            _identity(
                "reasoning-episode",
                _episode_key_state(
                    self.root_frontier,
                    self.action_limit,
                    self.cost_limit,
                    self.minimum_actionable_gain,
                ),
            ),
        )
        replayed_frontier, replayed_status = _replay_episode(self)
        if self.current_frontier != replayed_frontier:
            raise ValueError("current frontier does not match the replayed transition prefix")
        if self.status is not replayed_status:
            raise ValueError("reasoning episode status does not match replayed transition state")
        object.__setattr__(self, "snapshot_id", _identity("reasoning-episode-snapshot", self._snapshot_state()))

    @property
    def spent_actions(self) -> int:
        return len(self.transitions)

    @property
    def spent_cost(self) -> float:
        return sum((row.observed_cost for row in self.transitions), 0.0)

    @property
    def current_budget(self) -> MetareasoningBudget:
        return _budget_for(
            self.current_frontier,
            action_limit=self.action_limit,
            cost_limit=self.cost_limit,
            minimum_actionable_gain=self.minimum_actionable_gain,
            spent_actions=self.spent_actions,
            spent_cost=self.spent_cost,
        )

    def _snapshot_state(self) -> dict[str, object]:
        return {
            "episode_key": self.episode_key,
            "root_frontier": self.root_frontier.to_state(),
            "current_frontier": self.current_frontier.to_state(),
            "action_limit": self.action_limit,
            "cost_limit": self.cost_limit,
            "minimum_actionable_gain": self.minimum_actionable_gain,
            "transitions": [row.to_state() for row in self.transitions],
            "terminal_control_decision": (
                None if self.terminal_control_decision is None else self.terminal_control_decision.to_state()
            ),
            "status": self.status.value,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "snapshot_id": self.snapshot_id, **self._snapshot_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ReasoningEpisode":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported reasoning episode schema")
        root = ReasoningFrontier.from_state(_mapping(state.get("root_frontier"), "root frontier state"))
        current = ReasoningFrontier.from_state(_mapping(state.get("current_frontier"), "current frontier state"))
        transitions = tuple(
            ReasoningFrontierTransition.from_state(_mapping(raw, "reasoning transition state"))
            for raw in _sequence(state.get("transitions", ()), "reasoning transition state rows")
        )
        raw_terminal = state.get("terminal_control_decision")
        terminal = (
            None
            if raw_terminal is None
            else ReasoningControlDecision.from_state(_mapping(raw_terminal, "terminal control state"))
        )
        row = cls(
            root_frontier=root,
            current_frontier=current,
            action_limit=state["action_limit"],
            cost_limit=state["cost_limit"],
            minimum_actionable_gain=state["minimum_actionable_gain"],
            transitions=transitions,
            terminal_control_decision=terminal,
            status=ReasoningEpisodeStatus(str(state["status"])),
        )
        if str(state.get("episode_key")) != row.episode_key:
            raise ValueError("reasoning episode key does not match canonical root and budget")
        if str(state.get("snapshot_id")) != row.snapshot_id:
            raise ValueError("reasoning episode snapshot identity does not match replayed content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical reasoning episode state")
        return row


def _replay_episode(episode: ReasoningEpisode) -> tuple[ReasoningFrontier, ReasoningEpisodeStatus]:
    current = episode.root_frontier
    spent_actions = 0
    spent_cost = 0.0
    consumed_actions: set[str] = set()
    consumed_decisions: set[str] = set()
    overrun = False

    for expected_generation, transition in enumerate(episode.transitions, start=1):
        if overrun:
            raise ValueError("budget-overrun reasoning episode cannot contain later transitions")
        if transition.episode_key != episode.episode_key:
            raise ValueError("reasoning transition belongs to another episode")
        if transition.generation != expected_generation:
            raise ValueError("reasoning transition generation is not contiguous")
        if transition.previous_frontier_id != current.frontier_id:
            raise ValueError("reasoning transition predecessor does not match replay frontier")
        budget = _budget_for(
            current,
            action_limit=episode.action_limit,
            cost_limit=episode.cost_limit,
            minimum_actionable_gain=episode.minimum_actionable_gain,
            spent_actions=spent_actions,
            spent_cost=spent_cost,
        )
        _validate_control_authority(current, budget, transition.control_decision, transition.selected_action)
        if transition.selected_action.action_id in consumed_actions:
            raise ValueError("reasoning action authority was already consumed")
        if transition.control_decision.decision_id in consumed_decisions:
            raise ValueError("reasoning control decision authority was already consumed")
        _validate_successor(current, transition.next_frontier)
        expected_delta = derive_frontier_delta(current, transition.next_frontier, transition.delta.evidence_ids)
        if transition.delta != expected_delta:
            raise ValueError("reasoning frontier delta does not match replayed frontier change")
        expected_overrun = transition.observed_cost > budget.remaining_cost
        if transition.budget_overrun is not expected_overrun:
            raise ValueError("reasoning transition budget-overrun flag does not match observed cost")
        consumed_actions.add(transition.selected_action.action_id)
        consumed_decisions.add(transition.control_decision.decision_id)
        spent_actions += 1
        spent_cost = _finite(spent_cost + transition.observed_cost, "replayed spent cost")
        current = transition.next_frontier
        overrun = expected_overrun

    if overrun:
        if episode.terminal_control_decision is not None:
            raise ValueError("budget-overrun episode cannot carry a relabeling terminal decision")
        return current, ReasoningEpisodeStatus.ABSTAINED_BUDGET_OVERRUN

    if episode.terminal_control_decision is None:
        return current, ReasoningEpisodeStatus.ACTIVE

    budget = _budget_for(
        current,
        action_limit=episode.action_limit,
        cost_limit=episode.cost_limit,
        minimum_actionable_gain=episode.minimum_actionable_gain,
        spent_actions=spent_actions,
        spent_cost=spent_cost,
    )
    terminal_status = _validate_terminal_control(current, budget, episode.terminal_control_decision)
    return current, terminal_status


def open_reasoning_episode(
    root_frontier: ReasoningFrontier,
    action_limit: int,
    cost_limit: float,
    minimum_actionable_gain: float,
) -> ReasoningEpisode:
    if not isinstance(root_frontier, ReasoningFrontier):
        raise TypeError("root frontier must be ReasoningFrontier")
    return ReasoningEpisode(
        root_frontier=root_frontier,
        current_frontier=root_frontier,
        action_limit=action_limit,
        cost_limit=cost_limit,
        minimum_actionable_gain=minimum_actionable_gain,
    )


def advance_reasoning_episode(
    episode: ReasoningEpisode,
    control_decision: ReasoningControlDecision,
    selected_action: ReasoningActionProposal,
    next_frontier: ReasoningFrontier,
    observed_cost: float,
    evidence_ids: Sequence[str],
) -> ReasoningEpisode:
    if not isinstance(episode, ReasoningEpisode):
        raise TypeError("episode must be ReasoningEpisode")
    if episode.status is not ReasoningEpisodeStatus.ACTIVE:
        raise ValueError("only an active reasoning episode can advance")
    if not isinstance(next_frontier, ReasoningFrontier):
        raise TypeError("next frontier must be ReasoningFrontier")

    budget = episode.current_budget
    _validate_control_authority(episode.current_frontier, budget, control_decision, selected_action)
    consumed_actions = {row.selected_action.action_id for row in episode.transitions}
    consumed_decisions = {row.control_decision.decision_id for row in episode.transitions}
    if selected_action.action_id in consumed_actions:
        raise ValueError("reasoning action authority was already consumed")
    if control_decision.decision_id in consumed_decisions:
        raise ValueError("reasoning control decision authority was already consumed")

    _validate_successor(episode.current_frontier, next_frontier)
    delta = derive_frontier_delta(episode.current_frontier, next_frontier, evidence_ids)
    actual_cost = _positive_finite(observed_cost, "observed reasoning cost")
    budget_overrun = actual_cost > budget.remaining_cost
    transition = ReasoningFrontierTransition(
        episode_key=episode.episode_key,
        generation=episode.spent_actions + 1,
        previous_frontier_id=episode.current_frontier.frontier_id,
        next_frontier=next_frontier,
        control_decision=control_decision,
        selected_action=selected_action,
        delta=delta,
        observed_cost=actual_cost,
        budget_overrun=budget_overrun,
    )
    status = (
        ReasoningEpisodeStatus.ABSTAINED_BUDGET_OVERRUN
        if budget_overrun
        else ReasoningEpisodeStatus.ACTIVE
    )
    return ReasoningEpisode(
        root_frontier=episode.root_frontier,
        current_frontier=next_frontier,
        action_limit=episode.action_limit,
        cost_limit=episode.cost_limit,
        minimum_actionable_gain=episode.minimum_actionable_gain,
        transitions=(*episode.transitions, transition),
        terminal_control_decision=None,
        status=status,
    )


def close_reasoning_episode(
    episode: ReasoningEpisode,
    terminal_control_decision: ReasoningControlDecision,
) -> ReasoningEpisode:
    if not isinstance(episode, ReasoningEpisode):
        raise TypeError("episode must be ReasoningEpisode")
    if episode.status is not ReasoningEpisodeStatus.ACTIVE:
        raise ValueError("only an active reasoning episode can be closed")
    terminal_status = _validate_terminal_control(
        episode.current_frontier,
        episode.current_budget,
        terminal_control_decision,
    )
    return ReasoningEpisode(
        root_frontier=episode.root_frontier,
        current_frontier=episode.current_frontier,
        action_limit=episode.action_limit,
        cost_limit=episode.cost_limit,
        minimum_actionable_gain=episode.minimum_actionable_gain,
        transitions=episode.transitions,
        terminal_control_decision=terminal_control_decision,
        status=terminal_status,
    )


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "DESIGN_LINEAGE",
    "ReasoningEpisodeStatus",
    "ReasoningFrontierDelta",
    "ReasoningFrontierTransition",
    "ReasoningEpisode",
    "derive_frontier_delta",
    "open_reasoning_episode",
    "advance_reasoning_episode",
    "close_reasoning_episode",
)
