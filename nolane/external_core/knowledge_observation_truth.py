from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_truth import EvidenceChannel
from .knowledge_truth import KnowledgeClaim, KnowledgeLedger


PARENT_COMPONENT_ID = "external.knowledge"
OBSERVATION_REQUIREMENT_PROTOCOL = "truth-observation-requirements-v10"
OBSERVATION_REQUIREMENT_PROJECTION_PROTOCOL = "truth-observation-requirements-projection-v10"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class ObservationRequirement:
    claim_id: str
    claim_content_digest: str
    observation_id: str
    channel: EvidenceChannel
    digest: str

    @classmethod
    def create(
        cls,
        *,
        claim: KnowledgeClaim,
        observation_id: str,
        channel: EvidenceChannel,
    ) -> "ObservationRequirement":
        if not isinstance(claim, KnowledgeClaim):
            raise TypeError("observation requirement requires exact KnowledgeClaim")
        observation_id = _explicit(observation_id, "observation requirement observation id")
        channel = EvidenceChannel(channel)
        payload = {
            "protocol": OBSERVATION_REQUIREMENT_PROTOCOL,
            "claim_id": _explicit(claim.claim_id, "observation requirement claim id"),
            "claim_content_digest": _explicit(
                claim.content_digest,
                "observation requirement claim content digest",
            ),
            "observation_id": observation_id,
            "channel": channel.value,
        }
        return cls(
            payload["claim_id"],
            payload["claim_content_digest"],
            observation_id,
            channel,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": OBSERVATION_REQUIREMENT_PROTOCOL,
            "claim_id": self.claim_id,
            "claim_content_digest": self.claim_content_digest,
            "observation_id": self.observation_id,
            "channel": self.channel.value,
            "digest": self.digest,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        knowledge: KnowledgeLedger,
    ) -> "ObservationRequirement":
        _unexpected(
            state,
            {
                "protocol",
                "claim_id",
                "claim_content_digest",
                "observation_id",
                "channel",
                "digest",
            },
            "observation requirement",
        )
        if str(state.get("protocol", "")) != OBSERVATION_REQUIREMENT_PROTOCOL:
            raise ValueError("unsupported observation requirement protocol")
        claim = knowledge.get(str(state["claim_id"]))
        if str(state["claim_content_digest"]) != claim.content_digest:
            raise ValueError("observation requirement claim content digest mismatch")
        row = cls.create(
            claim=claim,
            observation_id=str(state["observation_id"]),
            channel=EvidenceChannel(str(state["channel"])),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("observation requirement digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class ObservationRequirementSetRevision:
    claim_id: str
    claim_content_digest: str
    revision: int
    predecessor_digest: str
    requirements: tuple[ObservationRequirement, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        claim: KnowledgeClaim,
        revision: int = 1,
        predecessor_digest: str = "",
        requirements: tuple[ObservationRequirement, ...],
    ) -> "ObservationRequirementSetRevision":
        if not isinstance(claim, KnowledgeClaim):
            raise TypeError("observation requirement set requires exact KnowledgeClaim")
        revision = int(revision)
        if revision < 1:
            raise ValueError("observation requirement revision must be positive")
        predecessor_digest = str(predecessor_digest).strip()
        if revision == 1 and predecessor_digest:
            raise ValueError("first observation requirement revision cannot have predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later observation requirement revision requires predecessor digest")

        rows = tuple(sorted(tuple(requirements), key=lambda row: row.observation_id))
        if not rows:
            raise ValueError("observation requirement set must be non-empty")
        if not all(isinstance(row, ObservationRequirement) for row in rows):
            raise TypeError("observation requirement set accepts canonical requirements only")
        observation_ids = tuple(row.observation_id for row in rows)
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("observation requirement observation ids must be unique")
        for row in rows:
            if row.claim_id != claim.claim_id or row.claim_content_digest != claim.content_digest:
                raise ValueError("observation requirement claim/content binding mismatch")

        payload = {
            "protocol": OBSERVATION_REQUIREMENT_PROTOCOL,
            "claim_id": _explicit(claim.claim_id, "observation requirement set claim id"),
            "claim_content_digest": _explicit(
                claim.content_digest,
                "observation requirement set claim content digest",
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
            "protocol": OBSERVATION_REQUIREMENT_PROTOCOL,
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
    ) -> "ObservationRequirementSetRevision":
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
            "observation requirement revision",
        )
        if str(state.get("protocol", "")) != OBSERVATION_REQUIREMENT_PROTOCOL:
            raise ValueError("unsupported observation requirement revision protocol")
        claim = knowledge.get(str(state["claim_id"]))
        if str(state["claim_content_digest"]) != claim.content_digest:
            raise ValueError("observation requirement claim content digest mismatch")
        requirements = tuple(
            ObservationRequirement.from_state(value, knowledge=knowledge)
            for value in state.get("requirements", ())
        )
        row = cls.create(
            claim=claim,
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            requirements=requirements,
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("observation requirement revision digest mismatch")
        return row


class ObservationRequirementRegistry:
    """Append-only required-observation sidecar under ``external.knowledge``."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[ObservationRequirementSetRevision]] = {}
        self._content_digests: dict[str, str] = {}

    def revisions(self, claim_id: str | None = None) -> tuple[ObservationRequirementSetRevision, ...]:
        if claim_id is not None:
            return tuple(self._revisions.get(str(claim_id), ()))
        return tuple(
            row
            for key in sorted(self._revisions)
            for row in self._revisions[key]
        )

    def current(self, claim_id: str) -> ObservationRequirementSetRevision | None:
        rows = self.revisions(str(claim_id))
        return rows[-1] if rows else None

    def requirements(self, claim_id: str) -> tuple[ObservationRequirement, ...]:
        row = self.current(str(claim_id))
        return row.requirements if row is not None else ()

    def register(
        self,
        row: ObservationRequirementSetRevision,
        *,
        knowledge: KnowledgeLedger,
    ) -> ObservationRequirementSetRevision:
        if not isinstance(row, ObservationRequirementSetRevision):
            raise TypeError("observation requirement registry accepts canonical revisions only")
        claim = knowledge.get(row.claim_id)
        if claim.content_digest != row.claim_content_digest:
            raise ValueError("observation requirement claim content digest mismatch")
        bound = self._content_digests.get(row.claim_id)
        if bound is not None and bound != row.claim_content_digest:
            raise ValueError("observation requirement claim/content rebind")

        history = self._revisions.setdefault(row.claim_id, [])
        if not history:
            if row.revision != 1:
                raise ValueError("observation requirement revision sequence must start at 1")
            if row.predecessor_digest:
                raise ValueError("first observation requirement revision cannot have predecessor")
        else:
            previous = history[-1]
            if row.revision != previous.revision + 1:
                raise ValueError("observation requirement revision must advance exactly once")
            if row.predecessor_digest != previous.digest:
                raise ValueError("observation requirement predecessor digest mismatch")
            if row.claim_content_digest != previous.claim_content_digest:
                raise ValueError("observation requirement claim/content rebind")

        history.append(row)
        self._content_digests[row.claim_id] = row.claim_content_digest
        return row

    def projection_state(self, claim_ids: tuple[str, ...]) -> dict[str, Any]:
        requested = tuple(
            sorted({_explicit(value, "observation requirement projection claim id") for value in claim_ids})
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
                        "status": "required",
                        "claim_content_digest": row.claim_content_digest,
                        "revision": row.revision,
                        "revision_digest": row.digest,
                        "requirements": [value.to_state() for value in row.requirements],
                    }
                )
        return {
            "protocol": OBSERVATION_REQUIREMENT_PROJECTION_PROTOCOL,
            "requested_claim_ids": list(requested),
            "claims": claims,
        }

    def projection_digest(self, claim_ids: tuple[str, ...]) -> str:
        return canonical_digest(self.projection_state(tuple(claim_ids)))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": OBSERVATION_REQUIREMENT_PROTOCOL,
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
    ) -> "ObservationRequirementRegistry":
        _unexpected(state, {"protocol", "revisions"}, "observation requirement registry")
        if str(state.get("protocol", "")) != OBSERVATION_REQUIREMENT_PROTOCOL:
            raise ValueError("unsupported observation requirement registry protocol")

        parsed: list[ObservationRequirementSetRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = ObservationRequirementSetRevision.from_state(value, knowledge=knowledge)
            key = (row.claim_id, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized observation requirement revision")
            seen.add(key)
            parsed.append(row)

        registry = cls()
        for row in sorted(parsed, key=lambda item: (item.claim_id, item.revision)):
            registry.register(row, knowledge=knowledge)
        return registry


__all__ = (
    "PARENT_COMPONENT_ID",
    "OBSERVATION_REQUIREMENT_PROTOCOL",
    "OBSERVATION_REQUIREMENT_PROJECTION_PROTOCOL",
    "ObservationRequirement",
    "ObservationRequirementSetRevision",
    "ObservationRequirementRegistry",
)
