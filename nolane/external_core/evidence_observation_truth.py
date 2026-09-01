from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_truth import EvidenceLedger, TruthEvidence
from .knowledge_observation_truth import ObservationRequirement
from .knowledge_truth import KnowledgeLedger


PARENT_COMPONENT_ID = "external.evidence"
OBSERVATION_RESULT_PROTOCOL = "truth-observation-results-v10"
OBSERVATION_RESULT_PROJECTION_PROTOCOL = "truth-observation-results-projection-v10"


class ObservationOutcome(str, Enum):
    OBSERVED = "observed"
    MISSING = "missing"
    CENSORED = "censored"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    INTERFERED = "interfered"


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
class ObservationResultRevision:
    requirement: ObservationRequirement
    revision: int
    predecessor_digest: str
    outcome: ObservationOutcome
    evidence_id: str
    evidence_content_digest: str
    reason: str
    digest: str

    @classmethod
    def create(
        cls,
        *,
        requirement: ObservationRequirement,
        revision: int = 1,
        predecessor_digest: str = "",
        outcome: ObservationOutcome,
        evidence: TruthEvidence | None = None,
        reason: str = "",
    ) -> "ObservationResultRevision":
        if not isinstance(requirement, ObservationRequirement):
            raise TypeError("observation result requires exact ObservationRequirement")
        revision = int(revision)
        if revision < 1:
            raise ValueError("observation result revision must be positive")
        predecessor_digest = str(predecessor_digest).strip()
        if revision == 1 and predecessor_digest:
            raise ValueError("first observation result revision cannot have predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later observation result revision requires predecessor digest")

        outcome = ObservationOutcome(outcome)
        reason = str(reason).strip()
        evidence_id = ""
        evidence_content_digest = ""
        if outcome is ObservationOutcome.OBSERVED:
            if evidence is None:
                raise ValueError("observed result requires evidence")
            if not isinstance(evidence, TruthEvidence):
                raise TypeError("observed result requires exact TruthEvidence")
            if reason:
                raise ValueError("observed result cannot carry incomplete reason")
            if evidence.subject_id != requirement.claim_id:
                raise ValueError("observed result evidence claim mismatch")
            if evidence.channel is not requirement.channel:
                raise ValueError("observed result evidence channel mismatch")
            evidence_id = _explicit(evidence.evidence_id, "observation result evidence id")
            evidence_content_digest = _explicit(
                evidence.content_digest,
                "observation result evidence content digest",
            )
        else:
            if evidence is not None:
                raise ValueError("non-observed result cannot bind evidence")
            reason = _explicit(reason, "observation result reason")

        payload = {
            "protocol": OBSERVATION_RESULT_PROTOCOL,
            "requirement": requirement.to_state(),
            "revision": revision,
            "predecessor_digest": predecessor_digest,
            "outcome": outcome.value,
            "evidence_id": evidence_id,
            "evidence_content_digest": evidence_content_digest,
            "reason": reason,
        }
        return cls(
            requirement,
            revision,
            predecessor_digest,
            outcome,
            evidence_id,
            evidence_content_digest,
            reason,
            canonical_digest(payload),
        )

    @property
    def requirement_digest(self) -> str:
        return self.requirement.digest

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": OBSERVATION_RESULT_PROTOCOL,
            "requirement": self.requirement.to_state(),
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "outcome": self.outcome.value,
            "evidence_id": self.evidence_id,
            "evidence_content_digest": self.evidence_content_digest,
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
    ) -> "ObservationResultRevision":
        _unexpected(
            state,
            {
                "protocol",
                "requirement",
                "revision",
                "predecessor_digest",
                "outcome",
                "evidence_id",
                "evidence_content_digest",
                "reason",
                "digest",
            },
            "observation result revision",
        )
        if str(state.get("protocol", "")) != OBSERVATION_RESULT_PROTOCOL:
            raise ValueError("unsupported observation result protocol")
        requirement = ObservationRequirement.from_state(
            state["requirement"],
            knowledge=knowledge,
        )
        outcome = ObservationOutcome(str(state["outcome"]))
        bound_evidence: TruthEvidence | None = None
        if outcome is ObservationOutcome.OBSERVED:
            evidence_id = _explicit(str(state.get("evidence_id", "")), "observation result evidence id")
            bound_evidence = evidence.get(evidence_id)
            if str(state.get("evidence_content_digest", "")) != bound_evidence.content_digest:
                raise ValueError("observation result evidence content digest mismatch")
        elif str(state.get("evidence_id", "")).strip() or str(
            state.get("evidence_content_digest", "")
        ).strip():
            raise ValueError("non-observed result cannot bind evidence")

        row = cls.create(
            requirement=requirement,
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            outcome=outcome,
            evidence=bound_evidence,
            reason=str(state.get("reason", "")),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("observation result revision digest mismatch")
        return row


class ObservationResultLedger:
    """Append-only observation outcomes beneath ``external.evidence``.

    The ledger records whether a required observation produced usable evidence. It never creates
    Evidence and never interprets missingness as support or refutation.
    """

    def __init__(self) -> None:
        self._revisions: dict[str, list[ObservationResultRevision]] = {}

    def history(self, requirement_digest: str) -> tuple[ObservationResultRevision, ...]:
        return tuple(self._revisions.get(str(requirement_digest), ()))

    def current(self, requirement_digest: str) -> ObservationResultRevision | None:
        rows = self.history(str(requirement_digest))
        return rows[-1] if rows else None

    def revisions(self) -> tuple[ObservationResultRevision, ...]:
        return tuple(
            row
            for requirement_digest in sorted(self._revisions)
            for row in self._revisions[requirement_digest]
        )

    def register(
        self,
        row: ObservationResultRevision,
        *,
        evidence: EvidenceLedger,
    ) -> ObservationResultRevision:
        if not isinstance(row, ObservationResultRevision):
            raise TypeError("observation result ledger accepts canonical revisions only")
        if not isinstance(evidence, EvidenceLedger):
            raise TypeError("observation result ledger requires EvidenceLedger")

        if row.outcome is ObservationOutcome.OBSERVED:
            item = evidence.get(row.evidence_id)
            if item.content_digest != row.evidence_content_digest:
                raise ValueError("observation result evidence content digest mismatch")
            if item.subject_id != row.requirement.claim_id:
                raise ValueError("observed result evidence claim mismatch")
            if item.channel is not row.requirement.channel:
                raise ValueError("observed result evidence channel mismatch")
        elif row.evidence_id or row.evidence_content_digest:
            raise ValueError("non-observed result cannot bind evidence")

        history = self._revisions.setdefault(row.requirement_digest, [])
        if not history:
            if row.revision != 1:
                raise ValueError("observation result revision sequence must start at 1")
            if row.predecessor_digest:
                raise ValueError("first observation result revision cannot have predecessor")
        else:
            previous = history[-1]
            if row.requirement != previous.requirement:
                raise ValueError("observation result requirement rebind")
            if row.revision != previous.revision + 1:
                raise ValueError("observation result revision must advance exactly once")
            if row.predecessor_digest != previous.digest:
                raise ValueError("observation result predecessor digest mismatch")

        history.append(row)
        return row

    def projection_state(
        self,
        requirements: tuple[ObservationRequirement, ...],
    ) -> dict[str, Any]:
        by_digest: dict[str, ObservationRequirement] = {}
        for row in tuple(requirements):
            if not isinstance(row, ObservationRequirement):
                raise TypeError("observation result projection requires canonical requirements")
            old = by_digest.get(row.digest)
            if old is not None and old != row:
                raise ValueError("observation result projection requirement digest collision")
            by_digest[row.digest] = row

        rows: list[dict[str, Any]] = []
        for requirement in sorted(by_digest.values(), key=lambda row: (row.observation_id, row.digest)):
            current = self.current(requirement.digest)
            if current is None:
                rows.append(
                    {
                        "requirement_digest": requirement.digest,
                        "observation_id": requirement.observation_id,
                        "status": "unrecorded",
                    }
                )
            else:
                if current.requirement != requirement:
                    raise ValueError("observation result current requirement mismatch")
                rows.append(
                    {
                        "requirement_digest": requirement.digest,
                        "observation_id": requirement.observation_id,
                        "status": current.outcome.value,
                        "revision": current.to_state(),
                    }
                )
        return {
            "protocol": OBSERVATION_RESULT_PROJECTION_PROTOCOL,
            "requested_requirement_digests": sorted(by_digest),
            "requirements": rows,
        }

    def projection_digest(self, requirements: tuple[ObservationRequirement, ...]) -> str:
        return canonical_digest(self.projection_state(tuple(requirements)))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": OBSERVATION_RESULT_PROTOCOL,
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
    ) -> "ObservationResultLedger":
        _unexpected(state, {"protocol", "revisions"}, "observation result ledger")
        if str(state.get("protocol", "")) != OBSERVATION_RESULT_PROTOCOL:
            raise ValueError("unsupported observation result ledger protocol")

        parsed: list[ObservationResultRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = ObservationResultRevision.from_state(
                value,
                knowledge=knowledge,
                evidence=evidence,
            )
            key = (row.requirement_digest, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized observation result revision")
            seen.add(key)
            parsed.append(row)

        ledger = cls()
        for row in sorted(parsed, key=lambda item: (item.requirement_digest, item.revision)):
            ledger.register(row, evidence=evidence)
        return ledger


__all__ = (
    "PARENT_COMPONENT_ID",
    "OBSERVATION_RESULT_PROTOCOL",
    "OBSERVATION_RESULT_PROJECTION_PROTOCOL",
    "ObservationOutcome",
    "ObservationResultRevision",
    "ObservationResultLedger",
)
