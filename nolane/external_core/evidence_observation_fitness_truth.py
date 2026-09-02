from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_observation_truth import ObservationOutcome, ObservationResultLedger, ObservationResultRevision
from .evidence_truth import EvidenceLedger
from .knowledge_observation_fitness_truth import (
    FitnessCheck,
    ObservationFitnessRequirementRegistry,
    ObservationFitnessRequirementRevision,
)
from .knowledge_observation_truth import ObservationRequirementRegistry
from .knowledge_truth import KnowledgeLedger


PARENT_COMPONENT_ID = "external.evidence"
FITNESS_ASSESSMENT_PROTOCOL = "truth-observation-fitness-assessments-v11"
FITNESS_ASSESSMENT_PROJECTION_PROTOCOL = "truth-observation-fitness-assessments-projection-v11"


class FitnessCheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be explicit and unique")
    return rows


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class FitnessCheckAssessment:
    check: FitnessCheck
    status: FitnessCheckStatus

    @classmethod
    def create(
        cls,
        *,
        check: FitnessCheck,
        status: FitnessCheckStatus,
    ) -> "FitnessCheckAssessment":
        return cls(FitnessCheck(check), FitnessCheckStatus(status))

    def to_state(self) -> dict[str, str]:
        return {"check": self.check.value, "status": self.status.value}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "FitnessCheckAssessment":
        _unexpected(state, {"check", "status"}, "fitness check assessment")
        return cls.create(
            check=FitnessCheck(str(state["check"])),
            status=FitnessCheckStatus(str(state["status"])),
        )


@dataclass(frozen=True, slots=True)
class ObservationFitnessAssessmentRevision:
    fitness_requirement: ObservationFitnessRequirementRevision
    observation_result: ObservationResultRevision
    revision: int
    predecessor_digest: str
    checks: tuple[FitnessCheckAssessment, ...]
    basis_evidence_ids: tuple[str, ...]
    reason: str
    digest: str

    @classmethod
    def create(
        cls,
        *,
        fitness_requirement: ObservationFitnessRequirementRevision,
        observation_result: ObservationResultRevision,
        checks: tuple[FitnessCheckAssessment, ...],
        basis_evidence_ids: tuple[str, ...],
        revision: int = 1,
        predecessor_digest: str = "",
        reason: str = "",
    ) -> "ObservationFitnessAssessmentRevision":
        if not isinstance(fitness_requirement, ObservationFitnessRequirementRevision):
            raise TypeError("fitness assessment requires exact fitness requirement revision")
        if not fitness_requirement.enabled:
            raise ValueError("fitness assessment cannot target disabled fitness requirement")
        if not isinstance(observation_result, ObservationResultRevision):
            raise TypeError("fitness assessment requires exact ObservationResultRevision")
        if observation_result.outcome is not ObservationOutcome.OBSERVED:
            raise ValueError("fitness assessment requires OBSERVED observation result")
        if observation_result.requirement != fitness_requirement.observation_requirement:
            raise ValueError("fitness assessment observation requirement mismatch")

        revision = int(revision)
        predecessor_digest = str(predecessor_digest).strip()
        if revision < 1:
            raise ValueError("fitness assessment revision must be positive")
        if revision == 1 and predecessor_digest:
            raise ValueError("first fitness assessment revision cannot have predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later fitness assessment revision requires predecessor digest")

        rows = tuple(sorted(tuple(checks), key=lambda value: value.check.value))
        if not all(isinstance(value, FitnessCheckAssessment) for value in rows):
            raise TypeError("fitness assessment accepts canonical check assessments only")
        row_checks = tuple(value.check for value in rows)
        if len(set(row_checks)) != len(row_checks):
            raise ValueError("fitness assessment checks must be unique")
        if set(row_checks) != set(fitness_requirement.checks):
            raise ValueError("fitness assessment checks must exactly cover required fitness checks")

        basis_evidence_ids = _ids(tuple(basis_evidence_ids), "fitness assessment basis evidence ids")
        if not basis_evidence_ids:
            raise ValueError("fitness assessment requires basis evidence")
        if observation_result.evidence_id in basis_evidence_ids:
            raise ValueError("observed target evidence cannot self-certify fitness")

        has_problem = any(value.status is not FitnessCheckStatus.PASS for value in rows)
        reason = str(reason).strip()
        if has_problem:
            reason = _explicit(reason, "non-passing fitness assessment reason")
        elif reason:
            raise ValueError("passing fitness assessment cannot carry failure reason")

        payload = {
            "protocol": FITNESS_ASSESSMENT_PROTOCOL,
            "fitness_requirement": fitness_requirement.to_state(),
            "observation_result": observation_result.to_state(),
            "revision": revision,
            "predecessor_digest": predecessor_digest,
            "checks": [value.to_state() for value in rows],
            "basis_evidence_ids": list(basis_evidence_ids),
            "reason": reason,
        }
        return cls(
            fitness_requirement,
            observation_result,
            revision,
            predecessor_digest,
            rows,
            basis_evidence_ids,
            reason,
            canonical_digest(payload),
        )

    @property
    def fitness_requirement_digest(self) -> str:
        return self.fitness_requirement.digest

    @property
    def observation_requirement_digest(self) -> str:
        return self.fitness_requirement.observation_requirement_digest

    @property
    def observation_result_digest(self) -> str:
        return self.observation_result.digest

    @property
    def observation_id(self) -> str:
        return self.fitness_requirement.observation_id

    @property
    def evidence_id(self) -> str:
        return self.observation_result.evidence_id

    @property
    def is_fit(self) -> bool:
        return all(value.status is FitnessCheckStatus.PASS for value in self.checks)

    @property
    def has_failure(self) -> bool:
        return any(value.status is FitnessCheckStatus.FAIL for value in self.checks)

    @property
    def has_unknown(self) -> bool:
        return any(value.status is FitnessCheckStatus.UNKNOWN for value in self.checks)

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": FITNESS_ASSESSMENT_PROTOCOL,
            "fitness_requirement": self.fitness_requirement.to_state(),
            "observation_result": self.observation_result.to_state(),
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "checks": [value.to_state() for value in self.checks],
            "basis_evidence_ids": list(self.basis_evidence_ids),
            "reason": self.reason,
            "digest": self.digest,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
    ) -> "ObservationFitnessAssessmentRevision":
        _unexpected(
            state,
            {
                "protocol",
                "fitness_requirement",
                "observation_result",
                "revision",
                "predecessor_digest",
                "checks",
                "basis_evidence_ids",
                "reason",
                "digest",
            },
            "fitness assessment revision",
        )
        if str(state.get("protocol", "")) != FITNESS_ASSESSMENT_PROTOCOL:
            raise ValueError("unsupported fitness assessment protocol")
        fitness_requirement = ObservationFitnessRequirementRevision.from_state(
            state["fitness_requirement"],
            knowledge=knowledge,
        )
        observation_result = ObservationResultRevision.from_state(
            state["observation_result"],
            knowledge=knowledge,
            evidence=evidence,
        )
        row = cls.create(
            fitness_requirement=fitness_requirement,
            observation_result=observation_result,
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            checks=tuple(FitnessCheckAssessment.from_state(value) for value in state.get("checks", ())),
            basis_evidence_ids=tuple(str(value) for value in state.get("basis_evidence_ids", ())),
            reason=str(state.get("reason", "")),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("fitness assessment revision digest mismatch")
        return row


class ObservationFitnessAssessmentLedger:
    """Append-only evidence-backed fitness assessments beneath ``external.evidence``."""

    def __init__(self) -> None:
        self._revisions: dict[tuple[str, str], list[ObservationFitnessAssessmentRevision]] = {}

    @staticmethod
    def _key(
        fitness_requirement_digest: str,
        observation_result_digest: str,
    ) -> tuple[str, str]:
        return (str(fitness_requirement_digest), str(observation_result_digest))

    def history(
        self,
        fitness_requirement_digest: str,
        observation_result_digest: str,
    ) -> tuple[ObservationFitnessAssessmentRevision, ...]:
        return tuple(self._revisions.get(self._key(fitness_requirement_digest, observation_result_digest), ()))

    def current(
        self,
        fitness_requirement_digest: str,
        observation_result_digest: str,
    ) -> ObservationFitnessAssessmentRevision | None:
        rows = self.history(fitness_requirement_digest, observation_result_digest)
        return rows[-1] if rows else None

    def revisions(self) -> tuple[ObservationFitnessAssessmentRevision, ...]:
        return tuple(
            row
            for key in sorted(self._revisions)
            for row in self._revisions[key]
        )

    @staticmethod
    def _fitness_requirement_exists(
        row: ObservationFitnessAssessmentRevision,
        fitness_requirements: ObservationFitnessRequirementRegistry,
    ) -> bool:
        return any(
            candidate == row.fitness_requirement
            for candidate in fitness_requirements.history(row.observation_requirement_digest)
        )

    @staticmethod
    def _observation_result_exists(
        row: ObservationFitnessAssessmentRevision,
        observation_results: ObservationResultLedger,
    ) -> bool:
        return any(
            candidate == row.observation_result
            for candidate in observation_results.history(row.observation_requirement_digest)
        )

    def register(
        self,
        row: ObservationFitnessAssessmentRevision,
        *,
        evidence: EvidenceLedger,
        fitness_requirements: ObservationFitnessRequirementRegistry,
        observation_results: ObservationResultLedger,
    ) -> ObservationFitnessAssessmentRevision:
        if not isinstance(row, ObservationFitnessAssessmentRevision):
            raise TypeError("fitness assessment ledger accepts canonical revisions only")
        if not self._fitness_requirement_exists(row, fitness_requirements):
            raise ValueError("fitness assessment references unknown fitness requirement revision")
        if not self._observation_result_exists(row, observation_results):
            raise ValueError("fitness assessment references unknown observation result revision")
        for evidence_id in row.basis_evidence_ids:
            evidence.get(evidence_id)
        if row.evidence_id in row.basis_evidence_ids:
            raise ValueError("observed target evidence cannot self-certify fitness")

        key = self._key(row.fitness_requirement_digest, row.observation_result_digest)
        history = self._revisions.setdefault(key, [])
        if not history:
            if row.revision != 1:
                raise ValueError("fitness assessment revision sequence must start at 1")
            if row.predecessor_digest:
                raise ValueError("first fitness assessment revision cannot have predecessor")
        else:
            previous = history[-1]
            if row.fitness_requirement != previous.fitness_requirement:
                raise ValueError("fitness assessment lineage cannot rebind fitness requirement")
            if row.observation_result != previous.observation_result:
                raise ValueError("fitness assessment lineage cannot rebind observation result")
            if row.revision != previous.revision + 1:
                raise ValueError("fitness assessment revision must advance exactly once")
            if row.predecessor_digest != previous.digest:
                raise ValueError("fitness assessment predecessor digest mismatch")
        history.append(row)
        return row

    def assessment_for(
        self,
        fitness_requirement: ObservationFitnessRequirementRevision,
        observation_result: ObservationResultRevision,
    ) -> ObservationFitnessAssessmentRevision | None:
        if not isinstance(fitness_requirement, ObservationFitnessRequirementRevision):
            raise TypeError("fitness lookup requires canonical fitness requirement")
        if not isinstance(observation_result, ObservationResultRevision):
            raise TypeError("fitness lookup requires canonical observation result")
        row = self.current(fitness_requirement.digest, observation_result.digest)
        if row is None:
            return None
        if row.fitness_requirement != fitness_requirement or row.observation_result != observation_result:
            raise ValueError("fitness assessment snapshot mismatch")
        return row

    @staticmethod
    def basis_is_active(row: ObservationFitnessAssessmentRevision, evidence: EvidenceLedger) -> bool:
        return all(evidence.is_active(evidence_id) for evidence_id in row.basis_evidence_ids)

    def projection_state(
        self,
        fitness_requirements: tuple[ObservationFitnessRequirementRevision, ...],
        *,
        observation_results: ObservationResultLedger,
        evidence: EvidenceLedger,
    ) -> dict[str, Any]:
        by_digest: dict[str, ObservationFitnessRequirementRevision] = {}
        for requirement in tuple(fitness_requirements):
            if not isinstance(requirement, ObservationFitnessRequirementRevision):
                raise TypeError("fitness assessment projection requires canonical fitness requirements")
            old = by_digest.get(requirement.digest)
            if old is not None and old != requirement:
                raise ValueError("fitness assessment projection requirement digest collision")
            by_digest[requirement.digest] = requirement

        rows: list[dict[str, Any]] = []
        for requirement in sorted(by_digest.values(), key=lambda value: (value.observation_id, value.digest)):
            result = observation_results.current(requirement.observation_requirement_digest)
            if not requirement.enabled:
                status = "disabled"
                payload: dict[str, Any] = {}
            elif result is None or result.outcome is not ObservationOutcome.OBSERVED:
                status = "not_applicable"
                payload = {}
            else:
                assessment = self.assessment_for(requirement, result)
                if assessment is None:
                    status = "unassessed"
                    payload = {"observation_result_digest": result.digest}
                else:
                    status = "assessed"
                    payload = {
                        "observation_result_digest": result.digest,
                        "assessment": assessment.to_state(),
                        "basis_evidence_state": evidence.scoped_state(assessment.basis_evidence_ids),
                    }
            rows.append(
                {
                    "fitness_requirement_digest": requirement.digest,
                    "observation_requirement_digest": requirement.observation_requirement_digest,
                    "observation_id": requirement.observation_id,
                    "status": status,
                    **payload,
                }
            )
        return {
            "protocol": FITNESS_ASSESSMENT_PROJECTION_PROTOCOL,
            "requested_fitness_requirement_digests": sorted(by_digest),
            "assessments": rows,
        }

    def projection_digest(
        self,
        fitness_requirements: tuple[ObservationFitnessRequirementRevision, ...],
        *,
        observation_results: ObservationResultLedger,
        evidence: EvidenceLedger,
    ) -> str:
        return canonical_digest(
            self.projection_state(
                tuple(fitness_requirements),
                observation_results=observation_results,
                evidence=evidence,
            )
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": FITNESS_ASSESSMENT_PROTOCOL,
            "revisions": [row.to_state() for row in self.revisions()],
        }

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        observation_requirements: ObservationRequirementRegistry,
        observation_results: ObservationResultLedger,
        fitness_requirements: ObservationFitnessRequirementRegistry,
    ) -> "ObservationFitnessAssessmentLedger":
        _unexpected(state, {"protocol", "revisions"}, "fitness assessment ledger")
        if str(state.get("protocol", "")) != FITNESS_ASSESSMENT_PROTOCOL:
            raise ValueError("unsupported fitness assessment ledger protocol")
        parsed: list[ObservationFitnessAssessmentRevision] = []
        seen: set[tuple[str, str, int]] = set()
        for value in state.get("revisions", ()):
            row = ObservationFitnessAssessmentRevision.from_state(
                value,
                knowledge=knowledge,
                evidence=evidence,
            )
            key = (row.fitness_requirement_digest, row.observation_result_digest, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized fitness assessment revision")
            seen.add(key)
            parsed.append(row)
        ledger = cls()
        for row in sorted(
            parsed,
            key=lambda value: (value.fitness_requirement_digest, value.observation_result_digest, value.revision),
        ):
            ledger.register(
                row,
                evidence=evidence,
                fitness_requirements=fitness_requirements,
                observation_results=observation_results,
            )
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID",
    "FITNESS_ASSESSMENT_PROTOCOL",
    "FITNESS_ASSESSMENT_PROJECTION_PROTOCOL",
    "FitnessCheckStatus",
    "FitnessCheckAssessment",
    "ObservationFitnessAssessmentRevision",
    "ObservationFitnessAssessmentLedger",
)
