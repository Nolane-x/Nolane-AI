from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.identity import AgentRegistry


COMPONENT_ID = "evaluation.stress"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.evaluation_stress"


class StressScenarioKind(str, Enum):
    SLEEP_WAKE_CONTINUITY = "sleep_wake_continuity"
    PLAN_DRIFT = "plan_drift"
    MEMORY_CONTAMINATION = "memory_contamination"
    TASK_REASSIGNMENT = "task_reassignment"
    STALE_LEASE = "stale_lease"
    CONFLICT_BACKPRESSURE = "conflict_backpressure"
    EPHEMERAL_RETIREMENT = "ephemeral_retirement"


_REQUIRED = (
    StressScenarioKind.SLEEP_WAKE_CONTINUITY,
    StressScenarioKind.PLAN_DRIFT,
    StressScenarioKind.MEMORY_CONTAMINATION,
    StressScenarioKind.STALE_LEASE,
    StressScenarioKind.CONFLICT_BACKPRESSURE,
    StressScenarioKind.EPHEMERAL_RETIREMENT,
)


@dataclass(frozen=True, slots=True)
class LongHorizonStressObservation:
    observation_id: str
    scenario: StressScenarioKind
    regime_digest: str
    initial_state_digest: str
    final_state_digest: str
    checkpoint_anchor: str
    event_anchor: str
    plan_revision_before: str
    plan_revision_after: str
    contamination_count: int
    stale_context_count: int
    false_accepts: int
    regressions: int
    recovered: bool
    elapsed_logical_epochs: int
    evidence: EvidenceRecord
    subject_agent_id: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "scenario": self.scenario.value,
            "regime_digest": self.regime_digest,
            "initial_state_digest": self.initial_state_digest,
            "final_state_digest": self.final_state_digest,
            "checkpoint_anchor": self.checkpoint_anchor,
            "event_anchor": self.event_anchor,
            "plan_revision_before": self.plan_revision_before,
            "plan_revision_after": self.plan_revision_after,
            "contamination_count": self.contamination_count,
            "stale_context_count": self.stale_context_count,
            "false_accepts": self.false_accepts,
            "regressions": self.regressions,
            "recovered": self.recovered,
            "elapsed_logical_epochs": self.elapsed_logical_epochs,
            "evidence": self.evidence.to_state(),
            "subject_agent_id": self.subject_agent_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "LongHorizonStressObservation":
        row = cls(
            observation_id=str(state["observation_id"]),
            scenario=StressScenarioKind(str(state["scenario"])),
            regime_digest=str(state["regime_digest"]),
            initial_state_digest=str(state["initial_state_digest"]),
            final_state_digest=str(state["final_state_digest"]),
            checkpoint_anchor=str(state["checkpoint_anchor"]),
            event_anchor=str(state["event_anchor"]),
            plan_revision_before=str(state["plan_revision_before"]),
            plan_revision_after=str(state["plan_revision_after"]),
            contamination_count=int(state["contamination_count"]),
            stale_context_count=int(state["stale_context_count"]),
            false_accepts=int(state["false_accepts"]),
            regressions=int(state["regressions"]),
            recovered=bool(state["recovered"]),
            elapsed_logical_epochs=int(state["elapsed_logical_epochs"]),
            evidence=EvidenceRecord.from_state(state["evidence"]),
            subject_agent_id=None if state.get("subject_agent_id") is None else str(state["subject_agent_id"]),
            digest=str(state["digest"]),
        )
        row._validate()
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("long-horizon stress observation digest mismatch")
        return row

    def _validate(self) -> None:
        for value in (
            self.observation_id,
            self.regime_digest,
            self.initial_state_digest,
            self.final_state_digest,
            self.checkpoint_anchor,
            self.event_anchor,
            self.plan_revision_before,
            self.plan_revision_after,
        ):
            if not str(value).strip():
                raise ValueError("stress observation anchors and digests must be explicit")
        if min(
            self.contamination_count,
            self.stale_context_count,
            self.false_accepts,
            self.regressions,
            self.elapsed_logical_epochs,
        ) < 0:
            raise ValueError("stress counters must be non-negative")


@dataclass(frozen=True, slots=True)
class StressSuiteAssessment:
    assessment_id: str
    observation_ids: tuple[str, ...]
    covered_scenarios: tuple[StressScenarioKind, ...]
    missing_scenarios: tuple[StressScenarioKind, ...]
    passed: bool
    reasons: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "observation_ids": list(self.observation_ids),
            "covered_scenarios": [x.value for x in self.covered_scenarios],
            "missing_scenarios": [x.value for x in self.missing_scenarios],
            "passed": self.passed,
            "reasons": list(self.reasons),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "StressSuiteAssessment":
        row = cls(
            assessment_id=str(state["assessment_id"]),
            observation_ids=tuple(str(x) for x in state.get("observation_ids", ())),
            covered_scenarios=tuple(StressScenarioKind(str(x)) for x in state.get("covered_scenarios", ())),
            missing_scenarios=tuple(StressScenarioKind(str(x)) for x in state.get("missing_scenarios", ())),
            passed=bool(state["passed"]),
            reasons=tuple(str(x) for x in state.get("reasons", ())),
            digest=str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("stress suite assessment digest mismatch")
        return row


class LongHorizonStressLedger:
    REQUIRED_SCENARIOS = _REQUIRED

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        observations: tuple[LongHorizonStressObservation, ...] = (),
        assessments: tuple[StressSuiteAssessment, ...] = (),
    ) -> None:
        self.registry = registry
        self._observations: dict[str, LongHorizonStressObservation] = {}
        self._assessments: dict[str, StressSuiteAssessment] = {}
        for row in observations:
            self._validate_external(row)
            if row.observation_id in self._observations:
                raise ValueError("duplicate stress observation id")
            self._observations[row.observation_id] = row
        for row in assessments:
            if row.assessment_id in self._assessments:
                raise ValueError("duplicate stress assessment id")
            for observation_id in row.observation_ids:
                self.get_observation(observation_id)
            self._assessments[row.assessment_id] = row

    def _validate_external(self, row: LongHorizonStressObservation) -> None:
        row._validate()
        self.registry.get(row.evidence.verifier_agent_id)
        if not row.evidence.passed or row.evidence.false_accepts or row.evidence.regressions:
            raise PermissionError("long-horizon stress evidence must be clean")
        if row.subject_agent_id is not None:
            self.registry.get(row.subject_agent_id)
            if row.evidence.verifier_agent_id == row.subject_agent_id:
                raise PermissionError("stress subject cannot self-verify")
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("long-horizon stress observation digest mismatch")

    def record_stress(self, **kwargs: Any) -> LongHorizonStressObservation:
        row0 = LongHorizonStressObservation(
            observation_id=str(kwargs["observation_id"]),
            scenario=StressScenarioKind(kwargs["scenario"]),
            regime_digest=str(kwargs["regime_digest"]),
            initial_state_digest=str(kwargs["initial_state_digest"]),
            final_state_digest=str(kwargs["final_state_digest"]),
            checkpoint_anchor=str(kwargs["checkpoint_anchor"]),
            event_anchor=str(kwargs["event_anchor"]),
            plan_revision_before=str(kwargs["plan_revision_before"]),
            plan_revision_after=str(kwargs["plan_revision_after"]),
            contamination_count=int(kwargs["contamination_count"]),
            stale_context_count=int(kwargs["stale_context_count"]),
            false_accepts=int(kwargs["false_accepts"]),
            regressions=int(kwargs["regressions"]),
            recovered=bool(kwargs["recovered"]),
            elapsed_logical_epochs=int(kwargs["elapsed_logical_epochs"]),
            evidence=kwargs["evidence"],
            subject_agent_id=None if kwargs.get("subject_agent_id") is None else str(kwargs["subject_agent_id"]),
            digest="",
        )
        row = LongHorizonStressObservation(
            observation_id=row0.observation_id,
            scenario=row0.scenario,
            regime_digest=row0.regime_digest,
            initial_state_digest=row0.initial_state_digest,
            final_state_digest=row0.final_state_digest,
            checkpoint_anchor=row0.checkpoint_anchor,
            event_anchor=row0.event_anchor,
            plan_revision_before=row0.plan_revision_before,
            plan_revision_after=row0.plan_revision_after,
            contamination_count=row0.contamination_count,
            stale_context_count=row0.stale_context_count,
            false_accepts=row0.false_accepts,
            regressions=row0.regressions,
            recovered=row0.recovered,
            elapsed_logical_epochs=row0.elapsed_logical_epochs,
            evidence=row0.evidence,
            subject_agent_id=row0.subject_agent_id,
            digest=canonical_digest(row0.payload()),
        )
        self._validate_external(row)
        existing = self._observations.get(row.observation_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError("stress observation id cannot be rebound")
        self._observations[row.observation_id] = row
        return row

    def get_observation(self, observation_id: str) -> LongHorizonStressObservation:
        try:
            return self._observations[str(observation_id)]
        except KeyError as exc:
            raise KeyError(f"unknown stress observation: {observation_id}") from exc

    def get_assessment(self, assessment_id: str) -> StressSuiteAssessment:
        try:
            return self._assessments[str(assessment_id)]
        except KeyError as exc:
            raise KeyError(f"unknown stress assessment: {assessment_id}") from exc

    def assess_suite(self, observation_ids: tuple[str, ...]) -> StressSuiteAssessment:
        rows = tuple(self.get_observation(x) for x in observation_ids)
        covered = tuple(sorted({row.scenario for row in rows}, key=lambda x: x.value))
        missing = tuple(x for x in self.REQUIRED_SCENARIOS if x not in set(covered))
        reasons: list[str] = []
        if missing:
            reasons.append("missing_required_scenarios")
        for row in rows:
            if row.contamination_count:
                reasons.append("memory_contamination_detected")
            if row.stale_context_count:
                reasons.append("stale_context_detected")
            if row.false_accepts:
                reasons.append("false_accept_detected")
            if row.regressions:
                reasons.append("regression_detected")
            if not row.recovered:
                reasons.append("recovery_failed")
        regimes = {row.regime_digest for row in rows}
        if len(regimes) > 1:
            reasons.append("stress_regime_mismatch")
        reasons = list(dict.fromkeys(reasons))
        payload0 = {
            "observation_ids": sorted(row.observation_id for row in rows),
            "covered_scenarios": [x.value for x in covered],
            "missing_scenarios": [x.value for x in missing],
            "passed": not reasons,
            "reasons": reasons,
        }
        assessment_id = "stress-suite-" + canonical_digest(payload0)[:24]
        payload = {"assessment_id": assessment_id, **payload0}
        result = StressSuiteAssessment(
            assessment_id=assessment_id,
            observation_ids=tuple(payload0["observation_ids"]),
            covered_scenarios=covered,
            missing_scenarios=missing,
            passed=not reasons,
            reasons=tuple(reasons),
            digest=canonical_digest(payload),
        )
        self._assessments.setdefault(result.assessment_id, result)
        return self._assessments[result.assessment_id]

    def observations(self) -> tuple[LongHorizonStressObservation, ...]:
        return tuple(self._observations[key] for key in sorted(self._observations))

    def assessments(self) -> tuple[StressSuiteAssessment, ...]:
        return tuple(self._assessments[key] for key in sorted(self._assessments))

    def to_state(self) -> dict[str, Any]:
        return {
            "observations": [x.to_state() for x in self.observations()],
            "assessments": [x.to_state() for x in self.assessments()],
        }

    @classmethod
    def from_state(cls, *, registry: AgentRegistry, state: Mapping[str, Any]) -> "LongHorizonStressLedger":
        return cls(
            registry=registry,
            observations=tuple(LongHorizonStressObservation.from_state(x) for x in state.get("observations", ())),
            assessments=tuple(StressSuiteAssessment.from_state(x) for x in state.get("assessments", ())),
        )
