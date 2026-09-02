from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .knowledge_observation_truth import ObservationRequirement, ObservationRequirementRegistry
from .knowledge_truth import KnowledgeLedger


PARENT_COMPONENT_ID = "external.knowledge"
FITNESS_REQUIREMENT_PROTOCOL = "truth-observation-fitness-requirements-v11"
FITNESS_REQUIREMENT_PROJECTION_PROTOCOL = "truth-observation-fitness-requirements-projection-v11"


class FitnessCheck(str, Enum):
    CALIBRATION = "calibration"
    INTEGRITY = "integrity"
    RESOLUTION = "resolution"
    SYNCHRONIZATION = "synchronization"
    INTERFERENCE = "interference"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _checks(values: tuple[FitnessCheck, ...]) -> tuple[FitnessCheck, ...]:
    rows = tuple(sorted((FitnessCheck(value) for value in values), key=lambda value: value.value))
    if not rows:
        raise ValueError("fitness checks must be non-empty")
    if len(set(rows)) != len(rows):
        raise ValueError("fitness checks must be unique")
    return rows


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class ObservationFitnessRequirementRevision:
    observation_requirement: ObservationRequirement
    revision: int
    predecessor_digest: str
    checks: tuple[FitnessCheck, ...]
    enabled: bool
    digest: str

    @classmethod
    def create(
        cls,
        *,
        observation_requirement: ObservationRequirement,
        checks: tuple[FitnessCheck, ...],
        revision: int = 1,
        predecessor_digest: str = "",
        enabled: bool = True,
    ) -> "ObservationFitnessRequirementRevision":
        if not isinstance(observation_requirement, ObservationRequirement):
            raise TypeError("fitness requirement requires exact ObservationRequirement")
        revision = int(revision)
        predecessor_digest = str(predecessor_digest).strip()
        if revision < 1:
            raise ValueError("fitness requirement revision must be positive")
        if revision == 1 and predecessor_digest:
            raise ValueError("first fitness requirement revision cannot have predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later fitness requirement revision requires predecessor digest")
        checks = _checks(tuple(checks))
        payload = {
            "protocol": FITNESS_REQUIREMENT_PROTOCOL,
            "observation_requirement": observation_requirement.to_state(),
            "revision": revision,
            "predecessor_digest": predecessor_digest,
            "checks": [value.value for value in checks],
            "enabled": bool(enabled),
        }
        return cls(
            observation_requirement,
            revision,
            predecessor_digest,
            checks,
            bool(enabled),
            canonical_digest(payload),
        )

    @property
    def observation_requirement_digest(self) -> str:
        return self.observation_requirement.digest

    @property
    def observation_id(self) -> str:
        return self.observation_requirement.observation_id

    @property
    def claim_id(self) -> str:
        return self.observation_requirement.claim_id

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": FITNESS_REQUIREMENT_PROTOCOL,
            "observation_requirement": self.observation_requirement.to_state(),
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "checks": [value.value for value in self.checks],
            "enabled": self.enabled,
            "digest": self.digest,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        knowledge: KnowledgeLedger,
    ) -> "ObservationFitnessRequirementRevision":
        _unexpected(
            state,
            {
                "protocol",
                "observation_requirement",
                "revision",
                "predecessor_digest",
                "checks",
                "enabled",
                "digest",
            },
            "fitness requirement revision",
        )
        if str(state.get("protocol", "")) != FITNESS_REQUIREMENT_PROTOCOL:
            raise ValueError("unsupported fitness requirement protocol")
        requirement = ObservationRequirement.from_state(
            state["observation_requirement"],
            knowledge=knowledge,
        )
        row = cls.create(
            observation_requirement=requirement,
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            checks=tuple(FitnessCheck(str(value)) for value in state.get("checks", ())),
            enabled=bool(state["enabled"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("fitness requirement revision digest mismatch")
        return row


class ObservationFitnessRequirementRegistry:
    """Append-only categorical measurement-fitness constraints beneath ``external.knowledge``."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[ObservationFitnessRequirementRevision]] = {}

    def history(self, observation_requirement_digest: str) -> tuple[ObservationFitnessRequirementRevision, ...]:
        return tuple(self._revisions.get(str(observation_requirement_digest), ()))

    def current(self, observation_requirement_digest: str) -> ObservationFitnessRequirementRevision | None:
        rows = self.history(str(observation_requirement_digest))
        return rows[-1] if rows else None

    def revisions(self) -> tuple[ObservationFitnessRequirementRevision, ...]:
        return tuple(
            row
            for digest in sorted(self._revisions)
            for row in self._revisions[digest]
        )

    @staticmethod
    def _known_requirement(
        row: ObservationFitnessRequirementRevision,
        observation_requirements: ObservationRequirementRegistry,
    ) -> bool:
        return any(
            candidate == row.observation_requirement
            for revision in observation_requirements.revisions(row.claim_id)
            for candidate in revision.requirements
        )

    def register(
        self,
        row: ObservationFitnessRequirementRevision,
        *,
        observation_requirements: ObservationRequirementRegistry,
    ) -> ObservationFitnessRequirementRevision:
        if not isinstance(row, ObservationFitnessRequirementRevision):
            raise TypeError("fitness requirement registry accepts canonical revisions only")
        if not isinstance(observation_requirements, ObservationRequirementRegistry):
            raise TypeError("fitness requirement registry requires ObservationRequirementRegistry")
        if not self._known_requirement(row, observation_requirements):
            raise ValueError("fitness requirement references unknown observation requirement")

        history = self._revisions.setdefault(row.observation_requirement_digest, [])
        if not history:
            if row.revision != 1:
                raise ValueError("fitness requirement revision sequence must start at 1")
            if row.predecessor_digest:
                raise ValueError("first fitness requirement revision cannot have predecessor")
        else:
            previous = history[-1]
            if row.observation_requirement != previous.observation_requirement:
                raise ValueError("fitness requirement lineage cannot rebind observation requirement")
            if row.revision != previous.revision + 1:
                raise ValueError("fitness requirement revision must advance exactly once")
            if row.predecessor_digest != previous.digest:
                raise ValueError("fitness requirement predecessor digest mismatch")
        history.append(row)
        return row

    def constraint(
        self,
        observation_requirement: ObservationRequirement,
    ) -> ObservationFitnessRequirementRevision | None:
        if not isinstance(observation_requirement, ObservationRequirement):
            raise TypeError("fitness constraint requires exact ObservationRequirement")
        row = self.current(observation_requirement.digest)
        if row is None:
            return None
        if row.observation_requirement != observation_requirement:
            raise ValueError("fitness requirement snapshot mismatch")
        return row if row.enabled else None

    def projection_state(
        self,
        observation_requirements: tuple[ObservationRequirement, ...],
    ) -> dict[str, Any]:
        by_digest: dict[str, ObservationRequirement] = {}
        for requirement in tuple(observation_requirements):
            if not isinstance(requirement, ObservationRequirement):
                raise TypeError("fitness projection requires canonical observation requirements")
            old = by_digest.get(requirement.digest)
            if old is not None and old != requirement:
                raise ValueError("fitness projection observation requirement digest collision")
            by_digest[requirement.digest] = requirement
        rows: list[dict[str, Any]] = []
        for requirement in sorted(by_digest.values(), key=lambda value: (value.observation_id, value.digest)):
            current = self.current(requirement.digest)
            if current is None:
                rows.append(
                    {
                        "observation_requirement_digest": requirement.digest,
                        "observation_id": requirement.observation_id,
                        "status": "unconstrained",
                    }
                )
            else:
                if current.observation_requirement != requirement:
                    raise ValueError("fitness projection requirement snapshot mismatch")
                rows.append(
                    {
                        "observation_requirement_digest": requirement.digest,
                        "observation_id": requirement.observation_id,
                        "status": "required" if current.enabled else "disabled",
                        "revision": current.to_state(),
                    }
                )
        return {
            "protocol": FITNESS_REQUIREMENT_PROJECTION_PROTOCOL,
            "requested_observation_requirement_digests": sorted(by_digest),
            "requirements": rows,
        }

    def projection_digest(self, observation_requirements: tuple[ObservationRequirement, ...]) -> str:
        return canonical_digest(self.projection_state(tuple(observation_requirements)))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": FITNESS_REQUIREMENT_PROTOCOL,
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
        observation_requirements: ObservationRequirementRegistry,
    ) -> "ObservationFitnessRequirementRegistry":
        _unexpected(state, {"protocol", "revisions"}, "fitness requirement registry")
        if str(state.get("protocol", "")) != FITNESS_REQUIREMENT_PROTOCOL:
            raise ValueError("unsupported fitness requirement registry protocol")
        parsed: list[ObservationFitnessRequirementRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = ObservationFitnessRequirementRevision.from_state(value, knowledge=knowledge)
            key = (row.observation_requirement_digest, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized fitness requirement revision")
            seen.add(key)
            parsed.append(row)
        registry = cls()
        for row in sorted(parsed, key=lambda value: (value.observation_requirement_digest, value.revision)):
            registry.register(row, observation_requirements=observation_requirements)
        return registry


__all__ = (
    "PARENT_COMPONENT_ID",
    "FITNESS_REQUIREMENT_PROTOCOL",
    "FITNESS_REQUIREMENT_PROJECTION_PROTOCOL",
    "FitnessCheck",
    "ObservationFitnessRequirementRevision",
    "ObservationFitnessRequirementRegistry",
)
