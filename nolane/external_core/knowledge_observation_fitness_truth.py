from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_truth import EvidenceChannel
from .knowledge_observation_truth import ObservationRequirement, ObservationRequirementRegistry
from .knowledge_truth import KnowledgeClaim, KnowledgeLedger


PARENT_COMPONENT_ID = "external.knowledge"
OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL = "truth-observation-fitness-requirements-v11"
OBSERVATION_FITNESS_REQUIREMENT_PROJECTION_PROTOCOL = (
    "truth-observation-fitness-requirements-projection-v11"
)


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


def _current_observation_requirement(
    *,
    claim_id: str,
    observation_id: str,
    observation_requirements: ObservationRequirementRegistry,
) -> ObservationRequirement | None:
    for requirement in observation_requirements.requirements(claim_id):
        if requirement.observation_id == observation_id:
            return requirement
    return None


@dataclass(frozen=True, slots=True)
class ObservationFitnessRequirement:
    """Knowledge-owned requirement that an exact required observation be fitness-qualified.

    The row does not assign a score and does not assert that the observation is fit. It only
    says that downstream v11 epistemic closure must possess a valid fitness assessment for
    this exact v10 observation-requirement snapshot.
    """

    claim_id: str
    claim_content_digest: str
    observation_id: str
    observation_requirement_digest: str
    channel: EvidenceChannel
    digest: str

    @classmethod
    def create(
        cls,
        *,
        claim: KnowledgeClaim,
        observation_requirement: ObservationRequirement,
    ) -> "ObservationFitnessRequirement":
        if not isinstance(claim, KnowledgeClaim):
            raise TypeError("observation fitness requirement requires exact KnowledgeClaim")
        if not isinstance(observation_requirement, ObservationRequirement):
            raise TypeError(
                "observation fitness requirement requires exact ObservationRequirement"
            )
        if observation_requirement.claim_id != claim.claim_id:
            raise ValueError("observation fitness requirement claim binding mismatch")
        if observation_requirement.claim_content_digest != claim.content_digest:
            raise ValueError("observation fitness requirement claim content digest mismatch")

        payload = {
            "protocol": OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL,
            "claim_id": _explicit(claim.claim_id, "observation fitness requirement claim id"),
            "claim_content_digest": _explicit(
                claim.content_digest,
                "observation fitness requirement claim content digest",
            ),
            "observation_id": _explicit(
                observation_requirement.observation_id,
                "observation fitness requirement observation id",
            ),
            "observation_requirement_digest": _explicit(
                observation_requirement.digest,
                "observation fitness requirement observation requirement digest",
            ),
            "channel": EvidenceChannel(observation_requirement.channel).value,
        }
        return cls(
            payload["claim_id"],
            payload["claim_content_digest"],
            payload["observation_id"],
            payload["observation_requirement_digest"],
            EvidenceChannel(payload["channel"]),
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL,
            "claim_id": self.claim_id,
            "claim_content_digest": self.claim_content_digest,
            "observation_id": self.observation_id,
            "observation_requirement_digest": self.observation_requirement_digest,
            "channel": self.channel.value,
            "digest": self.digest,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        knowledge: KnowledgeLedger,
        observation_requirements: ObservationRequirementRegistry,
    ) -> "ObservationFitnessRequirement":
        _unexpected(
            state,
            {
                "protocol",
                "claim_id",
                "claim_content_digest",
                "observation_id",
                "observation_requirement_digest",
                "channel",
                "digest",
            },
            "observation fitness requirement",
        )
        if str(state.get("protocol", "")) != OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL:
            raise ValueError("unsupported observation fitness requirement protocol")

        claim = knowledge.get(str(state["claim_id"]))
        if str(state["claim_content_digest"]) != claim.content_digest:
            raise ValueError("observation fitness requirement claim content digest mismatch")
        current = _current_observation_requirement(
            claim_id=claim.claim_id,
            observation_id=str(state["observation_id"]),
            observation_requirements=observation_requirements,
        )
        if current is None:
            raise ValueError("observation fitness requirement is not a current required observation")
        if str(state["observation_requirement_digest"]) != current.digest:
            raise ValueError("observation fitness requirement observation snapshot mismatch")
        if EvidenceChannel(str(state["channel"])) is not current.channel:
            raise ValueError("observation fitness requirement channel mismatch")

        row = cls.create(claim=claim, observation_requirement=current)
        if str(state["digest"]) != row.digest:
            raise ValueError("observation fitness requirement digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class ObservationFitnessRequirementSetRevision:
    claim_id: str
    claim_content_digest: str
    revision: int
    predecessor_digest: str
    requirements: tuple[ObservationFitnessRequirement, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        claim: KnowledgeClaim,
        requirements: tuple[ObservationFitnessRequirement, ...],
        revision: int = 1,
        predecessor_digest: str = "",
    ) -> "ObservationFitnessRequirementSetRevision":
        if not isinstance(claim, KnowledgeClaim):
            raise TypeError("observation fitness requirement set requires exact KnowledgeClaim")
        revision = int(revision)
        if revision < 1:
            raise ValueError("observation fitness requirement revision must be positive")
        predecessor_digest = str(predecessor_digest).strip()
        if revision == 1 and predecessor_digest:
            raise ValueError("first observation fitness requirement revision cannot have predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later observation fitness requirement revision requires predecessor digest")

        rows = tuple(sorted(tuple(requirements), key=lambda row: row.observation_id))
        if not rows:
            raise ValueError("observation fitness requirement set must be non-empty")
        if not all(isinstance(row, ObservationFitnessRequirement) for row in rows):
            raise TypeError(
                "observation fitness requirement set accepts canonical requirements only"
            )
        observation_ids = tuple(row.observation_id for row in rows)
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("observation fitness requirement observation ids must be unique")
        for row in rows:
            if row.claim_id != claim.claim_id or row.claim_content_digest != claim.content_digest:
                raise ValueError("observation fitness requirement claim/content binding mismatch")

        payload = {
            "protocol": OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL,
            "claim_id": _explicit(claim.claim_id, "observation fitness requirement set claim id"),
            "claim_content_digest": _explicit(
                claim.content_digest,
                "observation fitness requirement set claim content digest",
            ),
            "revision": revision,
            "predecessor_digest": predecessor_digest,
            "requirements": [row.to_state() for row in rows],
        }
        return cls(
            payload["claim_id"],
            payload["claim_content_digest"],
            revision,
            predecessor_digest,
            rows,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL,
            "claim_id": self.claim_id,
            "claim_content_digest": self.claim_content_digest,
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "requirements": [row.to_state() for row in self.requirements],
            "digest": self.digest,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        knowledge: KnowledgeLedger,
        observation_requirements: ObservationRequirementRegistry,
    ) -> "ObservationFitnessRequirementSetRevision":
        _unexpected(
            state,
            {
                "protocol",
                "claim_id",
                "claim_content_digest",
                "revision",
                "predecessor_digest",
                "requirements",
                "digest",
            },
            "observation fitness requirement revision",
        )
        if str(state.get("protocol", "")) != OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL:
            raise ValueError("unsupported observation fitness requirement revision protocol")
        claim = knowledge.get(str(state["claim_id"]))
        if str(state["claim_content_digest"]) != claim.content_digest:
            raise ValueError("observation fitness requirement claim content digest mismatch")
        requirements = tuple(
            ObservationFitnessRequirement.from_state(
                value,
                knowledge=knowledge,
                observation_requirements=observation_requirements,
            )
            for value in state.get("requirements", ())
        )
        row = cls.create(
            claim=claim,
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            requirements=requirements,
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("observation fitness requirement revision digest mismatch")
        return row


class ObservationFitnessRequirementRegistry:
    """Append-only v11 fitness-obligation sidecar under ``external.knowledge``."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[ObservationFitnessRequirementSetRevision]] = {}
        self._content_digests: dict[str, str] = {}

    def revisions(
        self, claim_id: str | None = None
    ) -> tuple[ObservationFitnessRequirementSetRevision, ...]:
        if claim_id is not None:
            return tuple(self._revisions.get(str(claim_id), ()))
        return tuple(
            row
            for key in sorted(self._revisions)
            for row in self._revisions[key]
        )

    def current(self, claim_id: str) -> ObservationFitnessRequirementSetRevision | None:
        rows = self.revisions(str(claim_id))
        return rows[-1] if rows else None

    def requirements(self, claim_id: str) -> tuple[ObservationFitnessRequirement, ...]:
        row = self.current(str(claim_id))
        return row.requirements if row is not None else ()

    def register(
        self,
        row: ObservationFitnessRequirementSetRevision,
        *,
        knowledge: KnowledgeLedger,
        observation_requirements: ObservationRequirementRegistry,
    ) -> ObservationFitnessRequirementSetRevision:
        if not isinstance(row, ObservationFitnessRequirementSetRevision):
            raise TypeError(
                "observation fitness requirement registry accepts canonical revisions only"
            )
        claim = knowledge.get(row.claim_id)
        if claim.content_digest != row.claim_content_digest:
            raise ValueError("observation fitness requirement claim content digest mismatch")
        bound = self._content_digests.get(row.claim_id)
        if bound is not None and bound != row.claim_content_digest:
            raise ValueError("observation fitness requirement claim/content rebind")

        current_by_id = {
            requirement.observation_id: requirement
            for requirement in observation_requirements.requirements(row.claim_id)
        }
        for requirement in row.requirements:
            current = current_by_id.get(requirement.observation_id)
            if current is None or current.digest != requirement.observation_requirement_digest:
                raise ValueError(
                    "observation fitness requirement must bind a current required observation"
                )
            if current.channel is not requirement.channel:
                raise ValueError("observation fitness requirement channel mismatch")

        history = self._revisions.setdefault(row.claim_id, [])
        if not history:
            if row.revision != 1:
                raise ValueError("observation fitness requirement revision sequence must start at 1")
            if row.predecessor_digest:
                raise ValueError("first observation fitness requirement revision cannot have predecessor")
        else:
            previous = history[-1]
            if row.revision != previous.revision + 1:
                raise ValueError("observation fitness requirement revision must advance exactly once")
            if row.predecessor_digest != previous.digest:
                raise ValueError("observation fitness requirement predecessor digest mismatch")
            if row.claim_content_digest != previous.claim_content_digest:
                raise ValueError("observation fitness requirement claim/content rebind")

        history.append(row)
        self._content_digests[row.claim_id] = row.claim_content_digest
        return row

    def projection_state(self, claim_ids: tuple[str, ...]) -> dict[str, Any]:
        requested = tuple(
            sorted(
                {
                    _explicit(value, "observation fitness requirement projection claim id")
                    for value in claim_ids
                }
            )
        )
        claims: list[dict[str, Any]] = []
        for claim_id in requested:
            row = self.current(claim_id)
            if row is None:
                claims.append({"claim_id": claim_id, "status": "unconstrained"})
            else:
                claims.append(
                    {
                        "claim_id": claim_id,
                        "status": "fitness-required",
                        "claim_content_digest": row.claim_content_digest,
                        "revision": row.revision,
                        "revision_digest": row.digest,
                        "requirements": [value.to_state() for value in row.requirements],
                    }
                )
        return {
            "protocol": OBSERVATION_FITNESS_REQUIREMENT_PROJECTION_PROTOCOL,
            "requested_claim_ids": list(requested),
            "claims": claims,
        }

    def projection_digest(self, claim_ids: tuple[str, ...]) -> str:
        return canonical_digest(self.projection_state(tuple(claim_ids)))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL,
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
        _unexpected(
            state,
            {"protocol", "revisions"},
            "observation fitness requirement registry",
        )
        if str(state.get("protocol", "")) != OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL:
            raise ValueError("unsupported observation fitness requirement registry protocol")

        parsed: list[ObservationFitnessRequirementSetRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = ObservationFitnessRequirementSetRevision.from_state(
                value,
                knowledge=knowledge,
                observation_requirements=observation_requirements,
            )
            key = (row.claim_id, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized observation fitness requirement revision")
            seen.add(key)
            parsed.append(row)

        registry = cls()
        for row in sorted(parsed, key=lambda item: (item.claim_id, item.revision)):
            registry.register(
                row,
                knowledge=knowledge,
                observation_requirements=observation_requirements,
            )
        return registry


__all__ = (
    "PARENT_COMPONENT_ID",
    "OBSERVATION_FITNESS_REQUIREMENT_PROTOCOL",
    "OBSERVATION_FITNESS_REQUIREMENT_PROJECTION_PROTOCOL",
    "ObservationFitnessRequirement",
    "ObservationFitnessRequirementSetRevision",
    "ObservationFitnessRequirementRegistry",
)
