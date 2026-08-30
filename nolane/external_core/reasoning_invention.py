from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.reasoning_invention"
COMPONENT_VERSION = "0.0.1"
SCHEMA_VERSION = "reasoning-invention-v1"
DESIGN_LINEAGE = "post-Epoch-0 native reasoning/invention protocol; Nolane World 0.12.0 is design provenance only"


class EvidencePhase(str, Enum):
    DISCOVERY = "discovery"
    INDEPENDENT_CHALLENGE = "independent_challenge"
    FINAL_ASSURANCE = "final_assurance"


class ChallengeVerdict(str, Enum):
    VERIFIED = "verified"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"
    ABSTAIN = "abstain"


class CapabilityKind(str, Enum):
    OPERATOR = "operator"
    ABSTRACTION = "abstraction"
    PROCEDURE = "procedure"
    REPRESENTATION = "representation"
    STRATEGY = "strategy"
    OTHER = "other"


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _sequence(values: object, name: str) -> Sequence[object]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return values


def _sorted_unique_ids(values: object, name: str, *, minimum: int = 0) -> tuple[str, ...]:
    source = _sequence(values, name)
    rows = tuple(_nonempty(value, name) for value in source)
    if len(rows) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} values")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{name} must not contain duplicate values")
    return tuple(sorted(rows))


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a finite number") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _bounded_score(value: object, name: str) -> float:
    number = _finite_number(value, name)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return number


def _positive_number(value: object, name: str) -> float:
    number = _finite_number(value, name)
    if number <= 0.0:
        raise ValueError(f"{name} must be positive")
    return number


def _nonnegative_number(value: object, name: str) -> float:
    number = _finite_number(value, name)
    if number < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _identity(prefix: str, semantic_state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(semantic_state))}"


@dataclass(frozen=True, slots=True)
class ReasoningEvidenceRef:
    evidence_id: str
    phase: EvidencePhase
    source_component: str
    witness_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _nonempty(self.evidence_id, "evidence id"))
        object.__setattr__(self, "phase", EvidencePhase(self.phase))
        object.__setattr__(self, "source_component", _nonempty(self.source_component, "source component"))
        object.__setattr__(self, "witness_id", _nonempty(self.witness_id, "witness id"))

    def to_state(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "phase": self.phase.value,
            "source_component": self.source_component,
            "witness_id": self.witness_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ReasoningEvidenceRef":
        row = cls(
            evidence_id=state["evidence_id"],
            phase=EvidencePhase(str(state["phase"])),
            source_component=state["source_component"],
            witness_id=state["witness_id"],
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical reasoning evidence reference state")
        return row


def _evidence_tuple(
    values: object,
    name: str,
    *,
    minimum: int = 0,
    allowed_phases: frozenset[EvidencePhase] | None = None,
) -> tuple[ReasoningEvidenceRef, ...]:
    source = _sequence(values, name)
    rows = tuple(source)
    if len(rows) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} values")
    if not all(isinstance(row, ReasoningEvidenceRef) for row in rows):
        raise TypeError(f"{name} must contain ReasoningEvidenceRef values")
    ids = tuple(row.evidence_id for row in rows)
    if len(ids) != len(set(ids)):
        raise ValueError(f"{name} must not contain duplicate evidence ids")
    if allowed_phases is not None and any(row.phase not in allowed_phases for row in rows):
        allowed = ", ".join(sorted(phase.value for phase in allowed_phases))
        raise ValueError(f"{name} must use only {allowed} evidence")
    return tuple(sorted(rows, key=lambda row: row.evidence_id))


@dataclass(frozen=True, slots=True)
class VerificationPlan:
    metric_id: str
    baseline_id: str
    success_threshold: float
    perturbation_ids: tuple[str, ...]
    negative_control_ids: tuple[str, ...]
    ablation_ids: tuple[str, ...]
    stop_condition_ids: tuple[str, ...]
    max_cost: float
    expected_information_gain: float
    plan_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _nonempty(self.metric_id, "metric id"))
        object.__setattr__(self, "baseline_id", _nonempty(self.baseline_id, "baseline id"))
        object.__setattr__(self, "success_threshold", _finite_number(self.success_threshold, "success threshold"))
        object.__setattr__(self, "perturbation_ids", _sorted_unique_ids(self.perturbation_ids, "perturbation ids", minimum=1))
        object.__setattr__(self, "negative_control_ids", _sorted_unique_ids(self.negative_control_ids, "negative control ids", minimum=1))
        object.__setattr__(self, "ablation_ids", _sorted_unique_ids(self.ablation_ids, "ablation ids", minimum=1))
        object.__setattr__(self, "stop_condition_ids", _sorted_unique_ids(self.stop_condition_ids, "stop condition ids", minimum=1))
        object.__setattr__(self, "max_cost", _positive_number(self.max_cost, "max cost"))
        object.__setattr__(self, "expected_information_gain", _nonnegative_number(self.expected_information_gain, "expected information gain"))
        object.__setattr__(self, "plan_id", _identity("verification-plan", self._semantic_state()))

    @property
    def information_efficiency(self) -> float:
        return self.expected_information_gain / self.max_cost

    def _semantic_state(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "baseline_id": self.baseline_id,
            "success_threshold": self.success_threshold,
            "perturbation_ids": list(self.perturbation_ids),
            "negative_control_ids": list(self.negative_control_ids),
            "ablation_ids": list(self.ablation_ids),
            "stop_condition_ids": list(self.stop_condition_ids),
            "max_cost": self.max_cost,
            "expected_information_gain": self.expected_information_gain,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "plan_id": self.plan_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "VerificationPlan":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported Reasoning/Invention verification plan schema")
        row = cls(
            metric_id=state["metric_id"],
            baseline_id=state["baseline_id"],
            success_threshold=state["success_threshold"],
            perturbation_ids=tuple(_sequence(state.get("perturbation_ids", ()), "perturbation ids state")),
            negative_control_ids=tuple(_sequence(state.get("negative_control_ids", ()), "negative control ids state")),
            ablation_ids=tuple(_sequence(state.get("ablation_ids", ()), "ablation ids state")),
            stop_condition_ids=tuple(_sequence(state.get("stop_condition_ids", ()), "stop condition ids state")),
            max_cost=state["max_cost"],
            expected_information_gain=state["expected_information_gain"],
        )
        if str(state.get("plan_id")) != row.plan_id:
            raise ValueError("verification plan identity does not match semantic state")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical verification plan state")
        return row


@dataclass(frozen=True, slots=True)
class PredictedDelta:
    metric_id: str
    minimum_delta: float
    maximum_delta: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", _nonempty(self.metric_id, "predicted delta metric id"))
        minimum = _finite_number(self.minimum_delta, "minimum predicted delta")
        maximum = _finite_number(self.maximum_delta, "maximum predicted delta")
        if minimum > maximum:
            raise ValueError("minimum predicted delta must not exceed maximum predicted delta")
        object.__setattr__(self, "minimum_delta", minimum)
        object.__setattr__(self, "maximum_delta", maximum)

    def to_state(self) -> dict[str, object]:
        return {"metric_id": self.metric_id, "minimum_delta": self.minimum_delta, "maximum_delta": self.maximum_delta}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PredictedDelta":
        row = cls(state["metric_id"], state["minimum_delta"], state["maximum_delta"])
        if row.to_state() != dict(state):
            raise ValueError("non-canonical predicted delta state")
        return row


def _predicted_delta_tuple(values: object) -> tuple[PredictedDelta, ...]:
    source = _sequence(values, "predicted deltas")
    rows = tuple(source)
    if not rows:
        raise ValueError("predicted deltas must contain at least 1 values")
    if not all(isinstance(row, PredictedDelta) for row in rows):
        raise TypeError("predicted deltas must contain PredictedDelta values")
    metric_ids = tuple(row.metric_id for row in rows)
    if len(metric_ids) != len(set(metric_ids)):
        raise ValueError("predicted deltas must not contain duplicate metric ids")
    return tuple(sorted(rows, key=lambda row: row.metric_id))


@dataclass(frozen=True, slots=True)
class InventionHypothesis:
    statement: str
    discovery_evidence: tuple[ReasoningEvidenceRef, ...]
    assumptions: tuple[str, ...]
    generalized_variables: tuple[str, ...]
    invariants: tuple[str, ...]
    predicted_deltas: tuple[PredictedDelta, ...]
    verification_plan: VerificationPlan
    candidate_synthesis_id: str | None = None
    hypothesis_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "statement", _nonempty(self.statement, "hypothesis statement"))
        object.__setattr__(self, "discovery_evidence", _evidence_tuple(self.discovery_evidence, "discovery evidence", minimum=1, allowed_phases=frozenset({EvidencePhase.DISCOVERY})))
        object.__setattr__(self, "assumptions", _sorted_unique_ids(self.assumptions, "assumptions"))
        object.__setattr__(self, "generalized_variables", _sorted_unique_ids(self.generalized_variables, "generalized variables", minimum=1))
        object.__setattr__(self, "invariants", _sorted_unique_ids(self.invariants, "invariants", minimum=1))
        object.__setattr__(self, "predicted_deltas", _predicted_delta_tuple(self.predicted_deltas))
        if not isinstance(self.verification_plan, VerificationPlan):
            raise TypeError("verification plan must be a VerificationPlan")
        if self.candidate_synthesis_id is not None:
            object.__setattr__(self, "candidate_synthesis_id", _nonempty(self.candidate_synthesis_id, "candidate synthesis id"))
        object.__setattr__(self, "hypothesis_id", _identity("hypothesis", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "statement": self.statement,
            "discovery_evidence": [row.to_state() for row in self.discovery_evidence],
            "assumptions": list(self.assumptions),
            "generalized_variables": list(self.generalized_variables),
            "invariants": list(self.invariants),
            "predicted_deltas": [row.to_state() for row in self.predicted_deltas],
            "verification_plan": self.verification_plan.to_state(),
            "candidate_synthesis_id": self.candidate_synthesis_id,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "hypothesis_id": self.hypothesis_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "InventionHypothesis":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported Reasoning/Invention hypothesis schema")
        evidence = tuple(ReasoningEvidenceRef.from_state(_mapping(row, "discovery evidence row")) for row in _sequence(state.get("discovery_evidence", ()), "discovery evidence state"))
        deltas = tuple(PredictedDelta.from_state(_mapping(row, "predicted delta row")) for row in _sequence(state.get("predicted_deltas", ()), "predicted deltas state"))
        row = cls(
            statement=state["statement"],
            discovery_evidence=evidence,
            assumptions=tuple(_sequence(state.get("assumptions", ()), "assumptions state")),
            generalized_variables=tuple(_sequence(state.get("generalized_variables", ()), "generalized variables state")),
            invariants=tuple(_sequence(state.get("invariants", ()), "invariants state")),
            predicted_deltas=deltas,
            verification_plan=VerificationPlan.from_state(_mapping(state["verification_plan"], "verification plan state")),
            candidate_synthesis_id=None if state.get("candidate_synthesis_id") is None else state["candidate_synthesis_id"],
        )
        if str(state.get("hypothesis_id")) != row.hypothesis_id:
            raise ValueError("hypothesis identity does not match semantic state")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical hypothesis state")
        return row


@dataclass(frozen=True, slots=True)
class InventionAssessment:
    evidence_alignment: float
    anomaly_coverage: float
    expected_gain: float
    robustness: float
    transferability: float
    uncertainty: float
    complexity: float
    verification_cost: float

    def __post_init__(self) -> None:
        for name in ("evidence_alignment", "anomaly_coverage", "expected_gain", "robustness", "transferability", "uncertainty", "complexity", "verification_cost"):
            object.__setattr__(self, name, _bounded_score(getattr(self, name), name.replace("_", " ")))

    def to_state(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "evidence_alignment": self.evidence_alignment,
            "anomaly_coverage": self.anomaly_coverage,
            "expected_gain": self.expected_gain,
            "robustness": self.robustness,
            "transferability": self.transferability,
            "uncertainty": self.uncertainty,
            "complexity": self.complexity,
            "verification_cost": self.verification_cost,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "InventionAssessment":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported Reasoning/Invention assessment schema")
        row = cls(
            evidence_alignment=state["evidence_alignment"], anomaly_coverage=state["anomaly_coverage"], expected_gain=state["expected_gain"], robustness=state["robustness"], transferability=state["transferability"], uncertainty=state["uncertainty"], complexity=state["complexity"], verification_cost=state["verification_cost"],
        )
        if row.to_state() != dict(state):
            raise ValueError("non-canonical invention assessment state")
        return row


_MAXIMIZE_FIELDS = ("evidence_alignment", "anomaly_coverage", "expected_gain", "robustness", "transferability")
_MINIMIZE_FIELDS = ("uncertainty", "complexity", "verification_cost")


def dominates(left: InventionAssessment, right: InventionAssessment) -> bool:
    if not isinstance(left, InventionAssessment) or not isinstance(right, InventionAssessment):
        raise TypeError("dominance requires InventionAssessment values")
    no_worse = all(getattr(left, name) >= getattr(right, name) for name in _MAXIMIZE_FIELDS) and all(getattr(left, name) <= getattr(right, name) for name in _MINIMIZE_FIELDS)
    strictly_better = any(getattr(left, name) > getattr(right, name) for name in _MAXIMIZE_FIELDS) or any(getattr(left, name) < getattr(right, name) for name in _MINIMIZE_FIELDS)
    return no_worse and strictly_better


@dataclass(frozen=True, slots=True)
class InventionCandidate:
    hypothesis: InventionHypothesis
    assessment: InventionAssessment
    causal_program_ids: tuple[str, ...] = ()
    experiment_receipt_ids: tuple[str, ...] = ()
    candidate_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, InventionHypothesis):
            raise TypeError("invention candidate hypothesis must be an InventionHypothesis")
        if not isinstance(self.assessment, InventionAssessment):
            raise TypeError("invention candidate assessment must be an InventionAssessment")
        object.__setattr__(self, "causal_program_ids", _sorted_unique_ids(self.causal_program_ids, "causal program ids"))
        object.__setattr__(self, "experiment_receipt_ids", _sorted_unique_ids(self.experiment_receipt_ids, "experiment receipt ids"))
        object.__setattr__(self, "candidate_id", _identity("invention-candidate", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {"hypothesis_id": self.hypothesis.hypothesis_id, "assessment": self.assessment.to_state(), "causal_program_ids": list(self.causal_program_ids), "experiment_receipt_ids": list(self.experiment_receipt_ids)}

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "candidate_id": self.candidate_id, "hypothesis": self.hypothesis.to_state(), "assessment": self.assessment.to_state(), "causal_program_ids": list(self.causal_program_ids), "experiment_receipt_ids": list(self.experiment_receipt_ids)}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "InventionCandidate":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported Reasoning/Invention candidate schema")
        row = cls(
            hypothesis=InventionHypothesis.from_state(_mapping(state["hypothesis"], "candidate hypothesis state")),
            assessment=InventionAssessment.from_state(_mapping(state["assessment"], "candidate assessment state")),
            causal_program_ids=tuple(_sequence(state.get("causal_program_ids", ()), "causal program ids state")),
            experiment_receipt_ids=tuple(_sequence(state.get("experiment_receipt_ids", ()), "experiment receipt ids state")),
        )
        if str(state.get("candidate_id")) != row.candidate_id:
            raise ValueError("invention candidate identity does not match semantic state")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical invention candidate state")
        return row


def pareto_frontier(candidates: Sequence[InventionCandidate]) -> tuple[InventionCandidate, ...]:
    rows = tuple(_sequence(candidates, "invention candidates"))
    if not all(isinstance(row, InventionCandidate) for row in rows):
        raise TypeError("invention candidates must contain InventionCandidate values")
    ids = tuple(row.candidate_id for row in rows)
    if len(ids) != len(set(ids)):
        raise ValueError("invention candidates must not contain duplicate candidate ids")
    frontier = tuple(candidate for candidate in rows if not any(other.candidate_id != candidate.candidate_id and dominates(other.assessment, candidate.assessment) for other in rows))
    return tuple(sorted(frontier, key=lambda row: row.candidate_id))


@dataclass(frozen=True, slots=True)
class HypothesisChallenge:
    hypothesis_id: str
    challenge_evidence: tuple[ReasoningEvidenceRef, ...]
    causal_program_ids: tuple[str, ...]
    experiment_receipt_ids: tuple[str, ...]
    verdict: ChallengeVerdict
    reason: str
    challenge_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hypothesis_id", _nonempty(self.hypothesis_id, "hypothesis id"))
        evidence = _evidence_tuple(self.challenge_evidence, "independent-challenge evidence", minimum=1, allowed_phases=frozenset({EvidencePhase.INDEPENDENT_CHALLENGE}))
        object.__setattr__(self, "challenge_evidence", evidence)
        causal = _sorted_unique_ids(self.causal_program_ids, "causal program ids")
        experiments = _sorted_unique_ids(self.experiment_receipt_ids, "experiment receipt ids")
        object.__setattr__(self, "causal_program_ids", causal)
        object.__setattr__(self, "experiment_receipt_ids", experiments)
        verdict = ChallengeVerdict(self.verdict)
        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(self, "reason", _nonempty(self.reason, "challenge reason"))
        if verdict is ChallengeVerdict.VERIFIED and not causal and not experiments:
            raise ValueError("verified challenge requires causal or experiment support")
        object.__setattr__(self, "challenge_id", _identity("challenge", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {"hypothesis_id": self.hypothesis_id, "challenge_evidence": [row.to_state() for row in self.challenge_evidence], "causal_program_ids": list(self.causal_program_ids), "experiment_receipt_ids": list(self.experiment_receipt_ids), "verdict": self.verdict.value, "reason": self.reason}

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "challenge_id": self.challenge_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "HypothesisChallenge":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported Reasoning/Invention challenge schema")
        row = cls(
            hypothesis_id=state["hypothesis_id"],
            challenge_evidence=tuple(ReasoningEvidenceRef.from_state(_mapping(item, "challenge evidence row")) for item in _sequence(state.get("challenge_evidence", ()), "challenge evidence state")),
            causal_program_ids=tuple(_sequence(state.get("causal_program_ids", ()), "causal program ids state")),
            experiment_receipt_ids=tuple(_sequence(state.get("experiment_receipt_ids", ()), "experiment receipt ids state")),
            verdict=ChallengeVerdict(str(state["verdict"])), reason=state["reason"],
        )
        if str(state.get("challenge_id")) != row.challenge_id:
            raise ValueError("challenge identity does not match semantic state")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical challenge state")
        return row


@dataclass(frozen=True, slots=True)
class CapabilityGap:
    objective: str
    capability_kind: CapabilityKind
    cognitive_library_digest: str
    insufficiency_evidence: tuple[ReasoningEvidenceRef, ...]
    acceptance_test_ids: tuple[str, ...]
    candidate_synthesis_id: str
    verified_challenge_id: str | None = None
    gap_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective", _nonempty(self.objective, "capability gap objective"))
        object.__setattr__(self, "capability_kind", CapabilityKind(self.capability_kind))
        object.__setattr__(self, "cognitive_library_digest", _nonempty(self.cognitive_library_digest, "cognitive library digest"))
        object.__setattr__(self, "insufficiency_evidence", _evidence_tuple(self.insufficiency_evidence, "insufficiency evidence", minimum=1, allowed_phases=frozenset({EvidencePhase.DISCOVERY, EvidencePhase.INDEPENDENT_CHALLENGE})))
        object.__setattr__(self, "acceptance_test_ids", _sorted_unique_ids(self.acceptance_test_ids, "acceptance test ids", minimum=1))
        object.__setattr__(self, "candidate_synthesis_id", _nonempty(self.candidate_synthesis_id, "candidate synthesis id"))
        if self.verified_challenge_id is not None:
            object.__setattr__(self, "verified_challenge_id", _nonempty(self.verified_challenge_id, "verified challenge id"))
        object.__setattr__(self, "gap_id", _identity("capability-gap", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {"objective": self.objective, "capability_kind": self.capability_kind.value, "cognitive_library_digest": self.cognitive_library_digest, "insufficiency_evidence": [row.to_state() for row in self.insufficiency_evidence], "acceptance_test_ids": list(self.acceptance_test_ids), "candidate_synthesis_id": self.candidate_synthesis_id, "verified_challenge_id": self.verified_challenge_id}

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "gap_id": self.gap_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "CapabilityGap":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported Reasoning/Invention capability-gap schema")
        row = cls(
            objective=state["objective"], capability_kind=CapabilityKind(str(state["capability_kind"])), cognitive_library_digest=state["cognitive_library_digest"],
            insufficiency_evidence=tuple(ReasoningEvidenceRef.from_state(_mapping(item, "insufficiency evidence row")) for item in _sequence(state.get("insufficiency_evidence", ()), "insufficiency evidence state")),
            acceptance_test_ids=tuple(_sequence(state.get("acceptance_test_ids", ()), "acceptance test ids state")), candidate_synthesis_id=state["candidate_synthesis_id"], verified_challenge_id=None if state.get("verified_challenge_id") is None else state["verified_challenge_id"],
        )
        if str(state.get("gap_id")) != row.gap_id:
            raise ValueError("capability-gap identity does not match semantic state")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical capability-gap state")
        return row


@dataclass(frozen=True, slots=True)
class TransferIntent:
    source_domain: str
    target_domain: str
    source_receipt_ids: tuple[str, ...]
    verified_challenge_ids: tuple[str, ...]
    generalized_variables: tuple[str, ...]
    invariants: tuple[str, ...]
    target_assumptions: tuple[str, ...]
    transfer_trial_ids: tuple[str, ...]
    transfer_intent_id: str = field(init=False)

    def __post_init__(self) -> None:
        source = _nonempty(self.source_domain, "source domain")
        target = _nonempty(self.target_domain, "target domain")
        if source == target:
            raise ValueError("source and target domains must differ")
        object.__setattr__(self, "source_domain", source)
        object.__setattr__(self, "target_domain", target)
        receipts = _sorted_unique_ids(self.source_receipt_ids, "source receipt ids")
        challenges = _sorted_unique_ids(self.verified_challenge_ids, "verified challenge ids")
        if not receipts and not challenges:
            raise ValueError("transfer intent requires at least one source receipt or verified challenge")
        object.__setattr__(self, "source_receipt_ids", receipts)
        object.__setattr__(self, "verified_challenge_ids", challenges)
        object.__setattr__(self, "generalized_variables", _sorted_unique_ids(self.generalized_variables, "generalized variables", minimum=1))
        object.__setattr__(self, "invariants", _sorted_unique_ids(self.invariants, "invariants", minimum=1))
        object.__setattr__(self, "target_assumptions", _sorted_unique_ids(self.target_assumptions, "target assumptions"))
        object.__setattr__(self, "transfer_trial_ids", _sorted_unique_ids(self.transfer_trial_ids, "transfer trial ids", minimum=1))
        object.__setattr__(self, "transfer_intent_id", _identity("transfer-intent", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {"source_domain": self.source_domain, "target_domain": self.target_domain, "source_receipt_ids": list(self.source_receipt_ids), "verified_challenge_ids": list(self.verified_challenge_ids), "generalized_variables": list(self.generalized_variables), "invariants": list(self.invariants), "target_assumptions": list(self.target_assumptions), "transfer_trial_ids": list(self.transfer_trial_ids)}

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "transfer_intent_id": self.transfer_intent_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "TransferIntent":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported Reasoning/Invention transfer-intent schema")
        row = cls(
            source_domain=state["source_domain"], target_domain=state["target_domain"], source_receipt_ids=tuple(_sequence(state.get("source_receipt_ids", ()), "source receipt ids state")), verified_challenge_ids=tuple(_sequence(state.get("verified_challenge_ids", ()), "verified challenge ids state")), generalized_variables=tuple(_sequence(state.get("generalized_variables", ()), "generalized variables state")), invariants=tuple(_sequence(state.get("invariants", ()), "invariants state")), target_assumptions=tuple(_sequence(state.get("target_assumptions", ()), "target assumptions state")), transfer_trial_ids=tuple(_sequence(state.get("transfer_trial_ids", ()), "transfer trial ids state")),
        )
        if str(state.get("transfer_intent_id")) != row.transfer_intent_id:
            raise ValueError("transfer-intent identity does not match semantic state")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical transfer-intent state")
        return row


@dataclass(frozen=True, slots=True)
class ReasoningInventionReceipt:
    hypothesis_ids: tuple[str, ...]
    frontier_candidate_ids: tuple[str, ...]
    challenge_ids: tuple[str, ...]
    capability_gap_ids: tuple[str, ...]
    transfer_intent_ids: tuple[str, ...]
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hypothesis_ids", _sorted_unique_ids(self.hypothesis_ids, "hypothesis ids"))
        object.__setattr__(self, "frontier_candidate_ids", _sorted_unique_ids(self.frontier_candidate_ids, "frontier candidate ids"))
        object.__setattr__(self, "challenge_ids", _sorted_unique_ids(self.challenge_ids, "challenge ids"))
        object.__setattr__(self, "capability_gap_ids", _sorted_unique_ids(self.capability_gap_ids, "capability gap ids"))
        object.__setattr__(self, "transfer_intent_ids", _sorted_unique_ids(self.transfer_intent_ids, "transfer intent ids"))
        if not (self.hypothesis_ids or self.frontier_candidate_ids or self.challenge_ids or self.capability_gap_ids or self.transfer_intent_ids):
            raise ValueError("reasoning/invention receipt must bind at least one canonical id")
        object.__setattr__(self, "receipt_id", _identity("reasoning-invention", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {"hypothesis_ids": list(self.hypothesis_ids), "frontier_candidate_ids": list(self.frontier_candidate_ids), "challenge_ids": list(self.challenge_ids), "capability_gap_ids": list(self.capability_gap_ids), "transfer_intent_ids": list(self.transfer_intent_ids)}

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "receipt_id": self.receipt_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ReasoningInventionReceipt":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported Reasoning/Invention receipt schema")
        row = cls(
            hypothesis_ids=tuple(_sequence(state.get("hypothesis_ids", ()), "hypothesis ids state")), frontier_candidate_ids=tuple(_sequence(state.get("frontier_candidate_ids", ()), "frontier candidate ids state")), challenge_ids=tuple(_sequence(state.get("challenge_ids", ()), "challenge ids state")), capability_gap_ids=tuple(_sequence(state.get("capability_gap_ids", ()), "capability gap ids state")), transfer_intent_ids=tuple(_sequence(state.get("transfer_intent_ids", ()), "transfer intent ids state")),
        )
        if str(state.get("receipt_id")) != row.receipt_id:
            raise ValueError("reasoning/invention receipt identity does not match semantic state")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical reasoning/invention receipt state")
        return row


__all__ = (
    "COMPONENT_ID", "COMPONENT_VERSION", "SCHEMA_VERSION", "DESIGN_LINEAGE", "EvidencePhase", "ChallengeVerdict", "CapabilityKind", "ReasoningEvidenceRef", "VerificationPlan", "PredictedDelta", "InventionHypothesis", "InventionAssessment", "InventionCandidate", "dominates", "pareto_frontier", "HypothesisChallenge", "CapabilityGap", "TransferIntent", "ReasoningInventionReceipt",
)
