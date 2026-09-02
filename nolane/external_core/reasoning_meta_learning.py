from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest

from .reasoning_metacontrol import MetaActionKind


COMPONENT_ID = "external.reasoning_invention"
COMPONENT_VERSION = "0.0.5"
SCHEMA_VERSION = "reasoning-meta-learning-v1"
DESIGN_LINEAGE = (
    "post-Epoch-0 descriptive feedback over metareasoning action outcomes and closed-loop evaluation; "
    "evidence compilation only, with no policy mutation authority"
)


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


def _nonnegative_finite(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _positive_finite(value: object, name: str) -> float:
    number = _finite(value, name)
    if number <= 0.0:
        raise ValueError(f"{name} must be positive")
    return number


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _identity(prefix: str, state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(state))}"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


@dataclass(frozen=True, slots=True)
class MetareasoningActionOutcome:
    frontier_id: str
    control_decision_id: str
    action_id: str
    action_kind: MetaActionKind
    evaluation_receipt_id: str
    outcome_evidence_ids: tuple[str, ...]
    decision_correct: bool
    observed_information_gain: float
    actual_cost: float
    regression_count: int
    generalized: bool
    robust: bool
    outcome_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frontier_id", _nonempty(self.frontier_id, "frontier id"))
        object.__setattr__(
            self,
            "control_decision_id",
            _nonempty(self.control_decision_id, "control decision id"),
        )
        object.__setattr__(self, "action_id", _nonempty(self.action_id, "action id"))
        object.__setattr__(self, "action_kind", MetaActionKind(self.action_kind))
        object.__setattr__(
            self,
            "evaluation_receipt_id",
            _nonempty(self.evaluation_receipt_id, "evaluation receipt id"),
        )
        object.__setattr__(
            self,
            "outcome_evidence_ids",
            _ids(self.outcome_evidence_ids, "outcome evidence ids", minimum=1),
        )
        if not isinstance(self.decision_correct, bool):
            raise TypeError("decision_correct must be bool")
        object.__setattr__(
            self,
            "observed_information_gain",
            _nonnegative_finite(self.observed_information_gain, "observed information gain"),
        )
        object.__setattr__(self, "actual_cost", _positive_finite(self.actual_cost, "actual cost"))
        object.__setattr__(
            self,
            "regression_count",
            _nonnegative_int(self.regression_count, "regression count"),
        )
        if not isinstance(self.generalized, bool):
            raise TypeError("generalized must be bool")
        if not isinstance(self.robust, bool):
            raise TypeError("robust must be bool")
        object.__setattr__(self, "outcome_id", _identity("metareasoning-outcome", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "frontier_id": self.frontier_id,
            "control_decision_id": self.control_decision_id,
            "action_id": self.action_id,
            "action_kind": self.action_kind.value,
            "evaluation_receipt_id": self.evaluation_receipt_id,
            "outcome_evidence_ids": list(self.outcome_evidence_ids),
            "decision_correct": self.decision_correct,
            "observed_information_gain": self.observed_information_gain,
            "actual_cost": self.actual_cost,
            "regression_count": self.regression_count,
            "generalized": self.generalized,
            "robust": self.robust,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "outcome_id": self.outcome_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "MetareasoningActionOutcome":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported metareasoning action outcome schema")
        row = cls(
            frontier_id=state["frontier_id"],
            control_decision_id=state["control_decision_id"],
            action_id=state["action_id"],
            action_kind=MetaActionKind(str(state["action_kind"])),
            evaluation_receipt_id=state["evaluation_receipt_id"],
            outcome_evidence_ids=tuple(_sequence(state.get("outcome_evidence_ids", ()), "outcome evidence state")),
            decision_correct=state["decision_correct"],
            observed_information_gain=state["observed_information_gain"],
            actual_cost=state["actual_cost"],
            regression_count=state["regression_count"],
            generalized=state["generalized"],
            robust=state["robust"],
        )
        if str(state.get("outcome_id")) != row.outcome_id:
            raise ValueError("metareasoning action outcome identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical metareasoning action outcome state")
        return row


@dataclass(frozen=True, slots=True)
class MetareasoningLearningMetrics:
    outcome_count: int
    action_kind_counts: tuple[tuple[str, int], ...]
    correct_decision_count: int
    information_efficiency: float
    regression_count: int
    generalized_count: int
    robust_count: int

    def __post_init__(self) -> None:
        for name in (
            "outcome_count",
            "correct_decision_count",
            "regression_count",
            "generalized_count",
            "robust_count",
        ):
            object.__setattr__(self, name, _nonnegative_int(getattr(self, name), name.replace("_", " ")))
        rows = tuple(self.action_kind_counts)
        if not all(isinstance(row, tuple) and len(row) == 2 for row in rows):
            raise TypeError("action kind counts must contain (kind, count) pairs")
        normalized: list[tuple[str, int]] = []
        seen: set[str] = set()
        for raw_kind, raw_count in rows:
            kind = MetaActionKind(str(raw_kind)).value
            count = _nonnegative_int(raw_count, "action kind count")
            if count == 0:
                raise ValueError("action kind counts must omit zero-count kinds")
            if kind in seen:
                raise ValueError("action kind counts must not contain duplicates")
            seen.add(kind)
            normalized.append((kind, count))
        normalized.sort()
        object.__setattr__(self, "action_kind_counts", tuple(normalized))
        object.__setattr__(
            self,
            "information_efficiency",
            _nonnegative_finite(self.information_efficiency, "information efficiency"),
        )
        if sum(count for _, count in self.action_kind_counts) != self.outcome_count:
            raise ValueError("action kind counts must cover every outcome")
        for name in ("correct_decision_count", "generalized_count", "robust_count"):
            if getattr(self, name) > self.outcome_count:
                raise ValueError(f"{name} cannot exceed outcome count")

    def to_state(self) -> dict[str, object]:
        return {
            "outcome_count": self.outcome_count,
            "action_kind_counts": [[kind, count] for kind, count in self.action_kind_counts],
            "correct_decision_count": self.correct_decision_count,
            "information_efficiency": self.information_efficiency,
            "regression_count": self.regression_count,
            "generalized_count": self.generalized_count,
            "robust_count": self.robust_count,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "MetareasoningLearningMetrics":
        raw_counts = _sequence(state.get("action_kind_counts", ()), "action kind count state")
        counts: list[tuple[str, int]] = []
        for raw in raw_counts:
            pair = _sequence(raw, "action kind count pair")
            if len(pair) != 2:
                raise ValueError("action kind count pair must have two values")
            counts.append((str(pair[0]), pair[1]))
        row = cls(
            outcome_count=state["outcome_count"],
            action_kind_counts=tuple(counts),
            correct_decision_count=state["correct_decision_count"],
            information_efficiency=state["information_efficiency"],
            regression_count=state["regression_count"],
            generalized_count=state["generalized_count"],
            robust_count=state["robust_count"],
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical metareasoning learning metrics state")
        return row


@dataclass(frozen=True, slots=True)
class MetareasoningLearningEvidence:
    outcomes: tuple[MetareasoningActionOutcome, ...]
    evaluation_receipt_ids: tuple[str, ...]
    metrics: MetareasoningLearningMetrics
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        outcomes = tuple(_sequence(self.outcomes, "metareasoning outcomes"))
        if len(outcomes) < 2 or not all(isinstance(row, MetareasoningActionOutcome) for row in outcomes):
            raise ValueError("metareasoning learning evidence requires at least two action outcomes")
        outcome_ids = tuple(row.outcome_id for row in outcomes)
        if len(outcome_ids) != len(set(outcome_ids)):
            raise ValueError("metareasoning learning outcomes must be distinct")
        object.__setattr__(self, "outcomes", tuple(sorted(outcomes, key=lambda row: row.outcome_id)))
        object.__setattr__(
            self,
            "evaluation_receipt_ids",
            _ids(self.evaluation_receipt_ids, "evaluation receipt ids", minimum=1),
        )
        if not isinstance(self.metrics, MetareasoningLearningMetrics):
            raise TypeError("metrics must be MetareasoningLearningMetrics")
        expected = _metrics_for(self.outcomes)
        if self.metrics != expected:
            raise ValueError("metareasoning learning metrics do not match canonical outcomes")
        expected_receipts = tuple(sorted({row.evaluation_receipt_id for row in self.outcomes}))
        if self.evaluation_receipt_ids != expected_receipts:
            raise ValueError("evaluation receipt ids must exactly match action outcomes")
        object.__setattr__(self, "evidence_id", _identity("metareasoning-learning", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "outcomes": [row.to_state() for row in self.outcomes],
            "evaluation_receipt_ids": list(self.evaluation_receipt_ids),
            "metrics": self.metrics.to_state(),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "evidence_id": self.evidence_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "MetareasoningLearningEvidence":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported metareasoning learning evidence schema")
        outcomes = tuple(
            MetareasoningActionOutcome.from_state(_mapping(raw, "metareasoning outcome state"))
            for raw in _sequence(state.get("outcomes", ()), "metareasoning outcome state rows")
        )
        metrics = MetareasoningLearningMetrics.from_state(_mapping(state.get("metrics"), "metareasoning metrics state"))
        row = cls(
            outcomes=outcomes,
            evaluation_receipt_ids=tuple(_sequence(state.get("evaluation_receipt_ids", ()), "evaluation receipt state")),
            metrics=metrics,
        )
        if str(state.get("evidence_id")) != row.evidence_id:
            raise ValueError("metareasoning learning evidence identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical metareasoning learning evidence state")
        return row


def _metrics_for(outcomes: Sequence[MetareasoningActionOutcome]) -> MetareasoningLearningMetrics:
    rows = tuple(outcomes)
    counts: dict[str, int] = {}
    total_information_gain = 0.0
    total_cost = 0.0
    correct = 0
    regressions = 0
    generalized = 0
    robust = 0
    for row in rows:
        key = row.action_kind.value
        counts[key] = counts.get(key, 0) + 1
        total_information_gain += row.observed_information_gain
        total_cost += row.actual_cost
        correct += int(row.decision_correct)
        regressions += row.regression_count
        generalized += int(row.generalized)
        robust += int(row.robust)
    return MetareasoningLearningMetrics(
        outcome_count=len(rows),
        action_kind_counts=tuple(sorted(counts.items())),
        correct_decision_count=correct,
        information_efficiency=total_information_gain / total_cost,
        regression_count=regressions,
        generalized_count=generalized,
        robust_count=robust,
    )


def compile_metareasoning_learning_evidence(
    outcomes: Sequence[MetareasoningActionOutcome],
) -> MetareasoningLearningEvidence:
    rows = tuple(_sequence(outcomes, "metareasoning action outcomes"))
    if len(rows) < 2:
        raise ValueError("metareasoning learning requires at least two action outcomes")
    if not all(isinstance(row, MetareasoningActionOutcome) for row in rows):
        raise TypeError("metareasoning action outcomes must contain MetareasoningActionOutcome values")
    outcome_ids = tuple(row.outcome_id for row in rows)
    if len(outcome_ids) != len(set(outcome_ids)):
        raise ValueError("metareasoning action outcomes must be distinct")
    canonical = tuple(sorted(rows, key=lambda row: row.outcome_id))
    receipts = tuple(sorted({row.evaluation_receipt_id for row in canonical}))
    if not receipts:
        raise ValueError("metareasoning learning requires at least one closed-loop evaluation receipt")
    return MetareasoningLearningEvidence(
        outcomes=canonical,
        evaluation_receipt_ids=receipts,
        metrics=_metrics_for(canonical),
    )


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "DESIGN_LINEAGE",
    "MetareasoningActionOutcome",
    "MetareasoningLearningMetrics",
    "MetareasoningLearningEvidence",
    "compile_metareasoning_learning_evidence",
)
