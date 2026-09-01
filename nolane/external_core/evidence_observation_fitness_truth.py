from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_observation_truth import (
    ObservationOutcome,
    ObservationResultLedger,
    ObservationResultRevision,
)
from .knowledge_observation_fitness_truth import (
    ObservationFitnessRequirement,
    ObservationFitnessRequirementRegistry,
)


PARENT_COMPONENT_ID = "external.evidence"
OBSERVATION_FITNESS_ASSESSMENT_PROTOCOL = "truth-observation-fitness-assessments-v11"
OBSERVATION_FITNESS_ASSESSMENT_PROJECTION_PROTOCOL = (
    "truth-observation-fitness-assessments-projection-v11"
)


class ObservationFitness(str, Enum):
    FIT = "fit"
    DEGRADED = "degraded"
    INVALID = "invalid"
    UNKNOWN = "unknown"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


def _fitness_requirement_by_digest(
    registry: ObservationFitnessRequirementRegistry,
    digest: str,
) -> ObservationFitnessRequirement:
    digest = _explicit(digest, "observation fitness requirement digest")
    matches = [
        requirement
        for revision in registry.revisions()
        for requirement in revision.requirements
        if requirement.digest == digest
    ]
    if len(matches) != 1:
        raise ValueError("observation fitness requirement digest is not uniquely registered")
    return matches[0]


def _observation_result_by_digest(
    ledger: ObservationResultLedger,
    digest: str,
) -> ObservationResultRevision:
    digest = _explicit(digest, "observation result digest")
    matches = [row for row in ledger.revisions() if row.digest == digest]
    if len(matches) != 1:
        raise ValueError("observation result digest is not uniquely registered")
    return matches[0]


@dataclass(frozen=True, slots=True)
class ObservationFitnessAssessmentRevision:
    fitness_requirement_digest: str
    claim_id: str
    claim_content_digest: str
    observation_id: str
    observation_requirement_digest: str
    observation_result_digest: str
    observation_result_revision: int
    evidence_id: str
    evidence_content_digest: str
    revision: int
    predecessor_digest: str
    fitness: ObservationFitness
    assessor_id: str
    method_digest: str
    basis_digests: tuple[str, ...]
    reason: str
    digest: str

    @classmethod
    def create(
        cls,
        *,
        fitness_requirement: ObservationFitnessRequirement,
        observation_result: ObservationResultRevision,
        fitness: ObservationFitness,
        assessor_id: str,
        method_digest: str,
        basis_digests: tuple[str, ...],
        reason: str = "",
        revision: int = 1,
        predecessor_digest: str = "",
    ) -> "ObservationFitnessAssessmentRevision":
        if not isinstance(fitness_requirement, ObservationFitnessRequirement):
            raise TypeError("fitness assessment requires exact ObservationFitnessRequirement")
        if not isinstance(observation_result, ObservationResultRevision):
            raise TypeError("fitness assessment requires exact ObservationResultRevision")
        if observation_result.outcome is not ObservationOutcome.OBSERVED:
            raise ValueError("fitness assessment requires an observed result")
        if observation_result.requirement_digest != fitness_requirement.observation_requirement_digest:
            raise ValueError("fitness assessment observation requirement snapshot mismatch")
        if observation_result.requirement.claim_id != fitness_requirement.claim_id:
            raise ValueError("fitness assessment claim binding mismatch")
        if observation_result.requirement.claim_content_digest != fitness_requirement.claim_content_digest:
            raise ValueError("fitness assessment claim content digest mismatch")
        if observation_result.requirement.observation_id != fitness_requirement.observation_id:
            raise ValueError("fitness assessment observation identity mismatch")
        if observation_result.requirement.channel is not fitness_requirement.channel:
            raise ValueError("fitness assessment observation channel mismatch")

        revision = int(revision)
        if revision < 1:
            raise ValueError("fitness assessment revision must be positive")
        predecessor_digest = str(predecessor_digest).strip()
        if revision == 1 and predecessor_digest:
            raise ValueError("first fitness assessment revision cannot have predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later fitness assessment revision requires predecessor digest")

        fitness = ObservationFitness(fitness)
        assessor_id = _explicit(assessor_id, "fitness assessment assessor id")
        method_digest = _explicit(method_digest, "fitness assessment method digest")
        basis = tuple(sorted({_explicit(value, "fitness assessment basis digest") for value in basis_digests}))
        if not basis:
            raise ValueError("fitness assessment basis lineage must be non-empty")
        reason = str(reason).strip()
        if fitness is not ObservationFitness.FIT and not reason:
            raise ValueError("non-fit fitness assessment reason must be explicit")

        payload = {
            "protocol": OBSERVATION_FITNESS_ASSESSMENT_PROTOCOL,
            "fitness_requirement_digest": fitness_requirement.digest,
            "claim_id": fitness_requirement.claim_id,
            "claim_content_digest": fitness_requirement.claim_content_digest,
            "observation_id": fitness_requirement.observation_id,
            "observation_requirement_digest": fitness_requirement.observation_requirement_digest,
            "observation_result_digest": observation_result.digest,
            "observation_result_revision": observation_result.revision,
            "evidence_id": _explicit(observation_result.evidence_id, "fitness assessment evidence id"),
            "evidence_content_digest": _explicit(
                observation_result.evidence_content_digest,
                "fitness assessment evidence content digest",
            ),
            "revision": revision,
            "predecessor_digest": predecessor_digest,
            "fitness": fitness.value,
            "assessor_id": assessor_id,
            "method_digest": method_digest,
            "basis_digests": list(basis),
            "reason": reason,
        }
        return cls(
            payload["fitness_requirement_digest"],
            payload["claim_id"],
            payload["claim_content_digest"],
            payload["observation_id"],
            payload["observation_requirement_digest"],
            payload["observation_result_digest"],
            payload["observation_result_revision"],
            payload["evidence_id"],
            payload["evidence_content_digest"],
            revision,
            predecessor_digest,
            fitness,
            assessor_id,
            method_digest,
            basis,
            reason,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": OBSERVATION_FITNESS_ASSESSMENT_PROTOCOL,
            "fitness_requirement_digest": self.fitness_requirement_digest,
            "claim_id": self.claim_id,
            "claim_content_digest": self.claim_content_digest,
            "observation_id": self.observation_id,
            "observation_requirement_digest": self.observation_requirement_digest,
            "observation_result_digest": self.observation_result_digest,
            "observation_result_revision": self.observation_result_revision,
            "evidence_id": self.evidence_id,
            "evidence_content_digest": self.evidence_content_digest,
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "fitness": self.fitness.value,
            "assessor_id": self.assessor_id,
            "method_digest": self.method_digest,
            "basis_digests": list(self.basis_digests),
            "reason": self.reason,
            "digest": self.digest,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        fitness_requirements: ObservationFitnessRequirementRegistry,
        observation_results: ObservationResultLedger,
    ) -> "ObservationFitnessAssessmentRevision":
        _unexpected(
            state,
            {
                "protocol",
                "fitness_requirement_digest",
                "claim_id",
                "claim_content_digest",
                "observation_id",
                "observation_requirement_digest",
                "observation_result_digest",
                "observation_result_revision",
                "evidence_id",
                "evidence_content_digest",
                "revision",
                "predecessor_digest",
                "fitness",
                "assessor_id",
                "method_digest",
                "basis_digests",
                "reason",
                "digest",
            },
            "observation fitness assessment revision",
        )
        if str(state.get("protocol", "")) != OBSERVATION_FITNESS_ASSESSMENT_PROTOCOL:
            raise ValueError("unsupported observation fitness assessment protocol")

        fitness_requirement = _fitness_requirement_by_digest(
            fitness_requirements,
            str(state["fitness_requirement_digest"]),
        )
        observation_result = _observation_result_by_digest(
            observation_results,
            str(state["observation_result_digest"]),
        )
        row = cls.create(
            fitness_requirement=fitness_requirement,
            observation_result=observation_result,
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            fitness=ObservationFitness(str(state["fitness"])),
            assessor_id=str(state["assessor_id"]),
            method_digest=str(state["method_digest"]),
            basis_digests=tuple(str(value) for value in state.get("basis_digests", ())),
            reason=str(state.get("reason", "")),
        )
        canonical = row.to_state()
        for field in (
            "claim_id",
            "claim_content_digest",
            "observation_id",
            "observation_requirement_digest",
            "observation_result_revision",
            "evidence_id",
            "evidence_content_digest",
        ):
            if state.get(field) != canonical[field]:
                raise ValueError(f"observation fitness assessment {field} mismatch")
        if str(state["digest"]) != row.digest:
            raise ValueError("observation fitness assessment revision digest mismatch")
        return row


class ObservationFitnessAssessmentLedger:
    """Append-only qualification of exact observed-result snapshots beneath external.evidence."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[ObservationFitnessAssessmentRevision]] = {}

    def history(self, observation_result_digest: str) -> tuple[ObservationFitnessAssessmentRevision, ...]:
        return tuple(self._revisions.get(str(observation_result_digest), ()))

    def current(self, observation_result_digest: str) -> ObservationFitnessAssessmentRevision | None:
        rows = self.history(str(observation_result_digest))
        return rows[-1] if rows else None

    def revisions(self) -> tuple[ObservationFitnessAssessmentRevision, ...]:
        return tuple(
            row
            for result_digest in sorted(self._revisions)
            for row in self._revisions[result_digest]
        )

    def register(
        self,
        row: ObservationFitnessAssessmentRevision,
        *,
        observation_results: ObservationResultLedger,
    ) -> ObservationFitnessAssessmentRevision:
        if not isinstance(row, ObservationFitnessAssessmentRevision):
            raise TypeError("fitness assessment ledger accepts canonical revisions only")
        if not isinstance(observation_results, ObservationResultLedger):
            raise TypeError("fitness assessment ledger requires ObservationResultLedger")

        current_result = observation_results.current(row.observation_requirement_digest)
        if current_result is None or current_result.digest != row.observation_result_digest:
            raise ValueError("fitness assessment must bind the current exact observed result")
        if current_result.outcome is not ObservationOutcome.OBSERVED:
            raise ValueError("fitness assessment requires an observed result")
        if current_result.evidence_id != row.evidence_id:
            raise ValueError("fitness assessment evidence id mismatch")
        if current_result.evidence_content_digest != row.evidence_content_digest:
            raise ValueError("fitness assessment evidence content digest mismatch")

        history = self._revisions.setdefault(row.observation_result_digest, [])
        if not history:
            if row.revision != 1:
                raise ValueError("fitness assessment revision sequence must start at 1")
            if row.predecessor_digest:
                raise ValueError("first fitness assessment revision cannot have predecessor")
        else:
            previous = history[-1]
            if row.revision != previous.revision + 1:
                raise ValueError("fitness assessment revision must advance exactly once")
            if row.predecessor_digest != previous.digest:
                raise ValueError("fitness assessment predecessor digest mismatch")
            immutable = (
                "fitness_requirement_digest",
                "claim_id",
                "claim_content_digest",
                "observation_id",
                "observation_requirement_digest",
                "observation_result_digest",
                "observation_result_revision",
                "evidence_id",
                "evidence_content_digest",
            )
            if any(getattr(row, field) != getattr(previous, field) for field in immutable):
                raise ValueError("fitness assessment lineage rebind")

        history.append(row)
        return row

    def projection_state(
        self,
        requirements: tuple[ObservationFitnessRequirement, ...],
        *,
        observation_results: ObservationResultLedger,
    ) -> dict[str, Any]:
        if not isinstance(observation_results, ObservationResultLedger):
            raise TypeError("fitness assessment projection requires ObservationResultLedger")
        by_digest: dict[str, ObservationFitnessRequirement] = {}
        for row in tuple(requirements):
            if not isinstance(row, ObservationFitnessRequirement):
                raise TypeError("fitness assessment projection requires canonical requirements")
            old = by_digest.get(row.digest)
            if old is not None and old != row:
                raise ValueError("fitness assessment projection requirement digest collision")
            by_digest[row.digest] = row

        rows: list[dict[str, Any]] = []
        for requirement in sorted(
            by_digest.values(), key=lambda row: (row.observation_id, row.digest)
        ):
            result = observation_results.current(requirement.observation_requirement_digest)
            base = {
                "fitness_requirement_digest": requirement.digest,
                "observation_requirement_digest": requirement.observation_requirement_digest,
                "observation_id": requirement.observation_id,
            }
            if result is None:
                rows.append({**base, "status": "unobserved"})
                continue
            if result.outcome is not ObservationOutcome.OBSERVED:
                rows.append(
                    {
                        **base,
                        "status": "unobserved",
                        "observation_result_digest": result.digest,
                        "observation_outcome": result.outcome.value,
                    }
                )
                continue
            assessment = self.current(result.digest)
            if assessment is None:
                rows.append(
                    {
                        **base,
                        "status": "unassessed",
                        "observation_result_digest": result.digest,
                    }
                )
                continue
            if assessment.fitness_requirement_digest != requirement.digest:
                raise ValueError("fitness assessment requirement snapshot mismatch")
            rows.append(
                {
                    **base,
                    "status": assessment.fitness.value,
                    "observation_result_digest": result.digest,
                    "assessment": assessment.to_state(),
                }
            )

        return {
            "protocol": OBSERVATION_FITNESS_ASSESSMENT_PROJECTION_PROTOCOL,
            "requested_fitness_requirement_digests": sorted(by_digest),
            "requirements": rows,
        }

    def projection_digest(
        self,
        requirements: tuple[ObservationFitnessRequirement, ...],
        *,
        observation_results: ObservationResultLedger,
    ) -> str:
        return canonical_digest(
            self.projection_state(tuple(requirements), observation_results=observation_results)
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": OBSERVATION_FITNESS_ASSESSMENT_PROTOCOL,
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
        fitness_requirements: ObservationFitnessRequirementRegistry,
        observation_results: ObservationResultLedger,
    ) -> "ObservationFitnessAssessmentLedger":
        _unexpected(state, {"protocol", "revisions"}, "observation fitness assessment ledger")
        if str(state.get("protocol", "")) != OBSERVATION_FITNESS_ASSESSMENT_PROTOCOL:
            raise ValueError("unsupported observation fitness assessment ledger protocol")

        parsed: list[ObservationFitnessAssessmentRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = ObservationFitnessAssessmentRevision.from_state(
                value,
                fitness_requirements=fitness_requirements,
                observation_results=observation_results,
            )
            key = (row.observation_result_digest, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized observation fitness assessment revision")
            seen.add(key)
            parsed.append(row)

        ledger = cls()
        for row in sorted(parsed, key=lambda item: (item.observation_result_digest, item.revision)):
            ledger.register(row, observation_results=observation_results)
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID",
    "OBSERVATION_FITNESS_ASSESSMENT_PROTOCOL",
    "OBSERVATION_FITNESS_ASSESSMENT_PROJECTION_PROTOCOL",
    "ObservationFitness",
    "ObservationFitnessAssessmentRevision",
    "ObservationFitnessAssessmentLedger",
)
