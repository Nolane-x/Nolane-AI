from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from ._truth_digest import truth_digest

COMPONENT_ID = "external.evidence.truth"
COMPONENT_VERSION = "0.1.0"


class EvidencePolarity(str, Enum):
    SUPPORT = "support"
    REFUTE = "refute"
    NEUTRAL = "neutral"


class EvidenceChannel(str, Enum):
    OBSERVATION = "observation"
    TEST = "test"
    REPRODUCTION = "reproduction"
    ADVERSARIAL = "adversarial"
    AUDIT = "audit"
    EXTERNAL = "external"


def _explicit(value: str, field: str) -> str:
    out = str(value).strip()
    if not out:
        raise ValueError(f"{field} must be explicit")
    return out


@dataclass(frozen=True, slots=True)
class TruthEvidence:
    evidence_id: str
    subject_id: str
    source_id: str
    source_family: str
    channel: EvidenceChannel
    polarity: EvidencePolarity
    payload_digest: str
    content_digest: str

    @classmethod
    def create(cls, *, evidence_id: str, subject_id: str, source_id: str, source_family: str,
               channel: EvidenceChannel, polarity: EvidencePolarity, payload_digest: str) -> "TruthEvidence":
        payload = {
            "evidence_id": _explicit(evidence_id, "evidence_id"),
            "subject_id": _explicit(subject_id, "subject_id"),
            "source_id": _explicit(source_id, "source_id"),
            "source_family": _explicit(source_family, "source_family"),
            "channel": EvidenceChannel(channel).value,
            "polarity": EvidencePolarity(polarity).value,
            "payload_digest": _explicit(payload_digest, "payload_digest"),
        }
        return cls(
            payload["evidence_id"], payload["subject_id"], payload["source_id"], payload["source_family"],
            EvidenceChannel(payload["channel"]), EvidencePolarity(payload["polarity"]), payload["payload_digest"],
            truth_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "subject_id": self.subject_id,
            "source_id": self.source_id,
            "source_family": self.source_family,
            "channel": self.channel.value,
            "polarity": self.polarity.value,
            "payload_digest": self.payload_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "content_digest": self.content_digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthEvidence":
        row = cls.create(
            evidence_id=str(state["evidence_id"]), subject_id=str(state["subject_id"]),
            source_id=str(state["source_id"]), source_family=str(state["source_family"]),
            channel=EvidenceChannel(str(state["channel"])), polarity=EvidencePolarity(str(state["polarity"])),
            payload_digest=str(state["payload_digest"]),
        )
        if str(state["content_digest"]) != row.content_digest:
            raise ValueError("evidence content digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EvidenceRevocation:
    evidence_id: str
    reason: str
    revocation_id: str

    @classmethod
    def create(cls, evidence_id: str, reason: str) -> "EvidenceRevocation":
        evidence_id = _explicit(evidence_id, "evidence_id")
        reason = _explicit(reason, "revocation reason")
        return cls(evidence_id, reason, truth_digest({"evidence_id": evidence_id, "reason": reason}))

    def to_state(self) -> dict[str, str]:
        return {"evidence_id": self.evidence_id, "reason": self.reason, "revocation_id": self.revocation_id}


class EvidenceLedger:
    """Append-only truth evidence plus explicit revocation tombstones."""

    def __init__(self) -> None:
        self._records: dict[str, TruthEvidence] = {}
        self._revocations: dict[str, EvidenceRevocation] = {}

    def record(self, row: TruthEvidence) -> TruthEvidence:
        previous = self._records.get(row.evidence_id)
        if previous is not None and previous != row:
            raise ValueError("evidence id collision")
        self._records[row.evidence_id] = row
        return row

    def get(self, evidence_id: str) -> TruthEvidence:
        try:
            return self._records[str(evidence_id)]
        except KeyError as exc:
            raise KeyError(f"unknown truth evidence: {evidence_id}") from exc

    def revoke(self, evidence_id: str, *, reason: str) -> EvidenceRevocation:
        self.get(evidence_id)
        row = EvidenceRevocation.create(str(evidence_id), reason)
        previous = self._revocations.get(row.evidence_id)
        if previous is not None and previous != row:
            raise ValueError("evidence already revoked with different reason")
        self._revocations[row.evidence_id] = row
        return row

    def is_active(self, evidence_id: str) -> bool:
        return str(evidence_id) in self._records and str(evidence_id) not in self._revocations

    def records(self, *, subject_id: str | None = None, active_only: bool = False) -> tuple[TruthEvidence, ...]:
        rows = self._records.values()
        if subject_id is not None:
            rows = (row for row in rows if row.subject_id == str(subject_id))
        if active_only:
            rows = (row for row in rows if self.is_active(row.evidence_id))
        return tuple(sorted(rows, key=lambda row: row.evidence_id))

    @property
    def digest(self) -> str:
        return truth_digest(self.to_state())

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": "truth-evidence-v1",
            "records": [row.to_state() for row in self.records()],
            "revocations": [self._revocations[key].to_state() for key in sorted(self._revocations)],
        }


__all__ = ("EvidencePolarity", "EvidenceChannel", "TruthEvidence", "EvidenceRevocation", "EvidenceLedger")
