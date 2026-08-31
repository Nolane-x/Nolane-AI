from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.reasoning_invention"
COMPONENT_VERSION = "0.0.2"
SCHEMA_VERSION = "reasoning-invention-evaluation-v1"
DESIGN_LINEAGE = (
    "post-Epoch-0 closed-loop Reasoning/Invention evaluation; consumes immutable "
    "regime/budget identities and owns no promotion, transfer-acceptance, Assurance or neural authority"
)


class EvaluationDecision(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


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


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _positive_int(value: object, name: str) -> int:
    number = _nonnegative_int(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


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


def _nonnegative_finite(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _identity(prefix: str, semantic_state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(semantic_state))}"


def _optional_rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


@dataclass(frozen=True, slots=True)
class ClosedLoopBudget:
    regime_id: str
    regime_digest: str
    budget_digest: str
    max_discovery_evidence: int
    max_candidates: int
    max_experiments: int
    max_oracle_calls: int
    max_verification_cost: float
    budget_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "regime_id", _nonempty(self.regime_id, "regime id"))
        object.__setattr__(self, "regime_digest", _nonempty(self.regime_digest, "regime digest"))
        object.__setattr__(self, "budget_digest", _nonempty(self.budget_digest, "budget digest"))
        object.__setattr__(self, "max_discovery_evidence", _positive_int(self.max_discovery_evidence, "max discovery evidence"))
        object.__setattr__(self, "max_candidates", _positive_int(self.max_candidates, "max candidates"))
        object.__setattr__(self, "max_experiments", _positive_int(self.max_experiments, "max experiments"))
        object.__setattr__(self, "max_oracle_calls", _positive_int(self.max_oracle_calls, "max oracle calls"))
        object.__setattr__(self, "max_verification_cost", _positive_finite(self.max_verification_cost, "max verification cost"))
        object.__setattr__(self, "budget_id", _identity("closed-loop-budget", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "regime_id": self.regime_id,
            "regime_digest": self.regime_digest,
            "budget_digest": self.budget_digest,
            "max_discovery_evidence": self.max_discovery_evidence,
            "max_candidates": self.max_candidates,
            "max_experiments": self.max_experiments,
            "max_oracle_calls": self.max_oracle_calls,
            "max_verification_cost": self.max_verification_cost,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "budget_id": self.budget_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ClosedLoopBudget":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported closed-loop evaluation budget schema")
        row = cls(
            regime_id=state["regime_id"],
            regime_digest=state["regime_digest"],
            budget_digest=state["budget_digest"],
            max_discovery_evidence=state["max_discovery_evidence"],
            max_candidates=state["max_candidates"],
            max_experiments=state["max_experiments"],
            max_oracle_calls=state["max_oracle_calls"],
            max_verification_cost=state["max_verification_cost"],
        )
        if str(state.get("budget_id")) != row.budget_id:
            raise ValueError("closed-loop budget identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical closed-loop budget state")
        return row


@dataclass(frozen=True, slots=True)
class ClosedLoopCase:
    benchmark_case_id: str
    reasoning_receipt_id: str
    hypothesis_ids: tuple[str, ...]
    challenge_id: str | None
    independent_support_ids: tuple[str, ...]
    capability_gap_ids: tuple[str, ...]
    transfer_intent_ids: tuple[str, ...]
    expected_decision: EvaluationDecision
    observed_decision: EvaluationDecision
    discovery_evidence_count: int
    candidate_count: int
    experiment_count: int
    oracle_calls: int
    verification_cost: float
    information_gain: float
    transfer_trial_count: int
    transfer_trial_passes: int
    robustness_trial_count: int
    robustness_trial_passes: int
    regression_count: int
    reproduced_evidence_ids: tuple[str, ...]
    case_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "benchmark_case_id", _nonempty(self.benchmark_case_id, "benchmark case id"))
        object.__setattr__(self, "reasoning_receipt_id", _nonempty(self.reasoning_receipt_id, "reasoning receipt id"))
        object.__setattr__(self, "hypothesis_ids", _ids(self.hypothesis_ids, "hypothesis ids", minimum=1))
        challenge = None if self.challenge_id is None else _nonempty(self.challenge_id, "challenge id")
        object.__setattr__(self, "challenge_id", challenge)
        object.__setattr__(self, "independent_support_ids", _ids(self.independent_support_ids, "independent support ids"))
        object.__setattr__(self, "capability_gap_ids", _ids(self.capability_gap_ids, "capability gap ids"))
        object.__setattr__(self, "transfer_intent_ids", _ids(self.transfer_intent_ids, "transfer intent ids"))
        object.__setattr__(self, "expected_decision", EvaluationDecision(self.expected_decision))
        object.__setattr__(self, "observed_decision", EvaluationDecision(self.observed_decision))
        object.__setattr__(self, "discovery_evidence_count", _positive_int(self.discovery_evidence_count, "discovery evidence count"))
        object.__setattr__(self, "candidate_count", _positive_int(self.candidate_count, "candidate count"))
        object.__setattr__(self, "experiment_count", _nonnegative_int(self.experiment_count, "experiment count"))
        object.__setattr__(self, "oracle_calls", _nonnegative_int(self.oracle_calls, "oracle calls"))
        object.__setattr__(self, "verification_cost", _positive_finite(self.verification_cost, "verification cost"))
        object.__setattr__(self, "information_gain", _nonnegative_finite(self.information_gain, "information gain"))
        object.__setattr__(self, "transfer_trial_count", _nonnegative_int(self.transfer_trial_count, "transfer trial count"))
        object.__setattr__(self, "transfer_trial_passes", _nonnegative_int(self.transfer_trial_passes, "transfer trial passes"))
        object.__setattr__(self, "robustness_trial_count", _nonnegative_int(self.robustness_trial_count, "robustness trial count"))
        object.__setattr__(self, "robustness_trial_passes", _nonnegative_int(self.robustness_trial_passes, "robustness trial passes"))
        object.__setattr__(self, "regression_count", _nonnegative_int(self.regression_count, "regression count"))
        object.__setattr__(self, "reproduced_evidence_ids", _ids(self.reproduced_evidence_ids, "reproduced evidence ids", minimum=1))
        if self.transfer_trial_passes > self.transfer_trial_count:
            raise ValueError("transfer trial passes cannot exceed trials")
        if self.robustness_trial_passes > self.robustness_trial_count:
            raise ValueError("robustness trial passes cannot exceed trials")
        if self.observed_decision is EvaluationDecision.ACCEPTED and (
            self.challenge_id is None or not self.independent_support_ids
        ):
            raise ValueError("accepted outcome requires independent challenge support")
        object.__setattr__(self, "case_id", _identity("closed-loop-case", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "benchmark_case_id": self.benchmark_case_id,
            "reasoning_receipt_id": self.reasoning_receipt_id,
            "hypothesis_ids": list(self.hypothesis_ids),
            "challenge_id": self.challenge_id,
            "independent_support_ids": list(self.independent_support_ids),
            "capability_gap_ids": list(self.capability_gap_ids),
            "transfer_intent_ids": list(self.transfer_intent_ids),
            "expected_decision": self.expected_decision.value,
            "observed_decision": self.observed_decision.value,
            "discovery_evidence_count": self.discovery_evidence_count,
            "candidate_count": self.candidate_count,
            "experiment_count": self.experiment_count,
            "oracle_calls": self.oracle_calls,
            "verification_cost": self.verification_cost,
            "information_gain": self.information_gain,
            "transfer_trial_count": self.transfer_trial_count,
            "transfer_trial_passes": self.transfer_trial_passes,
            "robustness_trial_count": self.robustness_trial_count,
            "robustness_trial_passes": self.robustness_trial_passes,
            "regression_count": self.regression_count,
            "reproduced_evidence_ids": list(self.reproduced_evidence_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "case_id": self.case_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ClosedLoopCase":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported closed-loop evaluation case schema")
        row = cls(
            benchmark_case_id=state["benchmark_case_id"],
            reasoning_receipt_id=state["reasoning_receipt_id"],
            hypothesis_ids=tuple(_sequence(state.get("hypothesis_ids", ()), "hypothesis ids state")),
            challenge_id=None if state.get("challenge_id") is None else state["challenge_id"],
            independent_support_ids=tuple(_sequence(state.get("independent_support_ids", ()), "independent support ids state")),
            capability_gap_ids=tuple(_sequence(state.get("capability_gap_ids", ()), "capability gap ids state")),
            transfer_intent_ids=tuple(_sequence(state.get("transfer_intent_ids", ()), "transfer intent ids state")),
            expected_decision=EvaluationDecision(str(state["expected_decision"])),
            observed_decision=EvaluationDecision(str(state["observed_decision"])),
            discovery_evidence_count=state["discovery_evidence_count"],
            candidate_count=state["candidate_count"],
            experiment_count=state["experiment_count"],
            oracle_calls=state["oracle_calls"],
            verification_cost=state["verification_cost"],
            information_gain=state["information_gain"],
            transfer_trial_count=state["transfer_trial_count"],
            transfer_trial_passes=state["transfer_trial_passes"],
            robustness_trial_count=state["robustness_trial_count"],
            robustness_trial_passes=state["robustness_trial_passes"],
            regression_count=state["regression_count"],
            reproduced_evidence_ids=tuple(_sequence(state.get("reproduced_evidence_ids", ()), "reproduced evidence ids state")),
        )
        if str(state.get("case_id")) != row.case_id:
            raise ValueError("closed-loop case identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical closed-loop case state")
        return row


@dataclass(frozen=True, slots=True)
class ClosedLoopMetrics:
    case_count: int
    accepted_count: int
    rejected_count: int
    abstained_count: int
    false_acceptance_count: int
    false_acceptance_rate: float | None
    correct_abstention_count: int
    abstention_precision: float | None
    abstention_recall: float | None
    information_efficiency: float
    generalization_rate: float | None
    robustness_rate: float | None
    regression_count: int

    def __post_init__(self) -> None:
        for name in (
            "case_count",
            "accepted_count",
            "rejected_count",
            "abstained_count",
            "false_acceptance_count",
            "correct_abstention_count",
            "regression_count",
        ):
            object.__setattr__(self, name, _nonnegative_int(getattr(self, name), name.replace("_", " ")))
        if self.case_count <= 0:
            raise ValueError("closed-loop metrics require at least one case")
        if self.accepted_count + self.rejected_count + self.abstained_count != self.case_count:
            raise ValueError("decision counts must sum to case count")
        for name in ("false_acceptance_rate", "abstention_precision", "abstention_recall", "generalization_rate", "robustness_rate"):
            value = getattr(self, name)
            if value is None:
                continue
            number = _finite(value, name.replace("_", " "))
            if number < 0.0 or number > 1.0:
                raise ValueError(f"{name.replace('_', ' ')} must be in [0, 1]")
            object.__setattr__(self, name, number)
        object.__setattr__(self, "information_efficiency", _nonnegative_finite(self.information_efficiency, "information efficiency"))

    def to_state(self) -> dict[str, object]:
        return {
            "case_count": self.case_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "abstained_count": self.abstained_count,
            "false_acceptance_count": self.false_acceptance_count,
            "false_acceptance_rate": self.false_acceptance_rate,
            "correct_abstention_count": self.correct_abstention_count,
            "abstention_precision": self.abstention_precision,
            "abstention_recall": self.abstention_recall,
            "information_efficiency": self.information_efficiency,
            "generalization_rate": self.generalization_rate,
            "robustness_rate": self.robustness_rate,
            "regression_count": self.regression_count,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ClosedLoopMetrics":
        row = cls(
            case_count=state["case_count"],
            accepted_count=state["accepted_count"],
            rejected_count=state["rejected_count"],
            abstained_count=state["abstained_count"],
            false_acceptance_count=state["false_acceptance_count"],
            false_acceptance_rate=state.get("false_acceptance_rate"),
            correct_abstention_count=state["correct_abstention_count"],
            abstention_precision=state.get("abstention_precision"),
            abstention_recall=state.get("abstention_recall"),
            information_efficiency=state["information_efficiency"],
            generalization_rate=state.get("generalization_rate"),
            robustness_rate=state.get("robustness_rate"),
            regression_count=state["regression_count"],
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical closed-loop metrics state")
        return row


@dataclass(frozen=True, slots=True)
class ReasoningInventionEvaluationReceipt:
    budget_id: str
    regime_id: str
    regime_digest: str
    budget_digest: str
    case_ids: tuple[str, ...]
    reproduced_evidence_ids: tuple[str, ...]
    metrics: ClosedLoopMetrics
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "budget_id", _nonempty(self.budget_id, "budget id"))
        object.__setattr__(self, "regime_id", _nonempty(self.regime_id, "regime id"))
        object.__setattr__(self, "regime_digest", _nonempty(self.regime_digest, "regime digest"))
        object.__setattr__(self, "budget_digest", _nonempty(self.budget_digest, "budget digest"))
        object.__setattr__(self, "case_ids", _ids(self.case_ids, "case ids", minimum=1))
        object.__setattr__(self, "reproduced_evidence_ids", _ids(self.reproduced_evidence_ids, "reproduced evidence ids", minimum=1))
        if not isinstance(self.metrics, ClosedLoopMetrics):
            raise TypeError("metrics must be ClosedLoopMetrics")
        if self.metrics.case_count != len(self.case_ids):
            raise ValueError("metrics case count does not match receipt cases")
        object.__setattr__(self, "receipt_id", _identity("reasoning-evaluation", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "budget_id": self.budget_id,
            "regime_id": self.regime_id,
            "regime_digest": self.regime_digest,
            "budget_digest": self.budget_digest,
            "case_ids": list(self.case_ids),
            "reproduced_evidence_ids": list(self.reproduced_evidence_ids),
            "metrics": self.metrics.to_state(),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "receipt_id": self.receipt_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ReasoningInventionEvaluationReceipt":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported Reasoning/Invention evaluation receipt schema")
        metrics_state = state.get("metrics")
        if not isinstance(metrics_state, Mapping):
            raise TypeError("evaluation receipt metrics must be a mapping")
        row = cls(
            budget_id=state["budget_id"],
            regime_id=state["regime_id"],
            regime_digest=state["regime_digest"],
            budget_digest=state["budget_digest"],
            case_ids=tuple(_sequence(state.get("case_ids", ()), "case ids state")),
            reproduced_evidence_ids=tuple(_sequence(state.get("reproduced_evidence_ids", ()), "reproduced evidence ids state")),
            metrics=ClosedLoopMetrics.from_state(metrics_state),
        )
        if str(state.get("receipt_id")) != row.receipt_id:
            raise ValueError("Reasoning/Invention evaluation receipt identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical Reasoning/Invention evaluation receipt state")
        return row


def _validate_budget(case: ClosedLoopCase, budget: ClosedLoopBudget) -> None:
    violations: list[str] = []
    if case.discovery_evidence_count > budget.max_discovery_evidence:
        violations.append("discovery evidence")
    if case.candidate_count > budget.max_candidates:
        violations.append("candidates")
    if case.experiment_count > budget.max_experiments:
        violations.append("experiments")
    if case.oracle_calls > budget.max_oracle_calls:
        violations.append("oracle calls")
    if case.verification_cost > budget.max_verification_cost:
        violations.append("verification cost")
    if violations:
        raise ValueError(f"closed-loop case exceeds fixed budget: {', '.join(violations)}")


def evaluate_closed_loop(
    budget: ClosedLoopBudget,
    cases: Sequence[ClosedLoopCase],
) -> ReasoningInventionEvaluationReceipt:
    if not isinstance(budget, ClosedLoopBudget):
        raise TypeError("budget must be ClosedLoopBudget")
    rows = tuple(_sequence(cases, "closed-loop cases"))
    if not rows:
        raise ValueError("closed-loop evaluation requires at least one case")
    if not all(isinstance(row, ClosedLoopCase) for row in rows):
        raise TypeError("closed-loop cases must contain ClosedLoopCase values")
    ids = tuple(row.case_id for row in rows)
    if len(ids) != len(set(ids)):
        raise ValueError("closed-loop evaluation must not contain duplicate case ids")
    rows = tuple(sorted(rows, key=lambda row: row.case_id))
    for row in rows:
        _validate_budget(row, budget)

    accepted = sum(row.observed_decision is EvaluationDecision.ACCEPTED for row in rows)
    rejected = sum(row.observed_decision is EvaluationDecision.REJECTED for row in rows)
    abstained = sum(row.observed_decision is EvaluationDecision.ABSTAINED for row in rows)
    false_accepts = sum(
        row.observed_decision is EvaluationDecision.ACCEPTED
        and row.expected_decision is not EvaluationDecision.ACCEPTED
        for row in rows
    )
    nonaccept_truth = sum(row.expected_decision is not EvaluationDecision.ACCEPTED for row in rows)
    correct_abstains = sum(
        row.observed_decision is EvaluationDecision.ABSTAINED
        and row.expected_decision is EvaluationDecision.ABSTAINED
        for row in rows
    )
    expected_abstains = sum(row.expected_decision is EvaluationDecision.ABSTAINED for row in rows)
    total_cost = sum(row.verification_cost for row in rows)
    total_gain = sum(row.information_gain for row in rows)
    transfer_trials = sum(row.transfer_trial_count for row in rows)
    transfer_passes = sum(row.transfer_trial_passes for row in rows)
    robustness_trials = sum(row.robustness_trial_count for row in rows)
    robustness_passes = sum(row.robustness_trial_passes for row in rows)

    metrics = ClosedLoopMetrics(
        case_count=len(rows),
        accepted_count=accepted,
        rejected_count=rejected,
        abstained_count=abstained,
        false_acceptance_count=false_accepts,
        false_acceptance_rate=_optional_rate(false_accepts, nonaccept_truth),
        correct_abstention_count=correct_abstains,
        abstention_precision=_optional_rate(correct_abstains, abstained),
        abstention_recall=_optional_rate(correct_abstains, expected_abstains),
        information_efficiency=total_gain / total_cost,
        generalization_rate=_optional_rate(transfer_passes, transfer_trials),
        robustness_rate=_optional_rate(robustness_passes, robustness_trials),
        regression_count=sum(row.regression_count for row in rows),
    )
    evidence_ids = tuple(sorted({evidence_id for row in rows for evidence_id in row.reproduced_evidence_ids}))
    return ReasoningInventionEvaluationReceipt(
        budget_id=budget.budget_id,
        regime_id=budget.regime_id,
        regime_digest=budget.regime_digest,
        budget_digest=budget.budget_digest,
        case_ids=tuple(row.case_id for row in rows),
        reproduced_evidence_ids=evidence_ids,
        metrics=metrics,
    )


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "DESIGN_LINEAGE",
    "EvaluationDecision",
    "ClosedLoopBudget",
    "ClosedLoopCase",
    "ClosedLoopMetrics",
    "ReasoningInventionEvaluationReceipt",
    "evaluate_closed_loop",
)
