from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol

from ._truth_digest import truth_digest

COMPONENT_ID = "external.knowledge"
COMPONENT_VERSION = "0.1.0"


class KnowledgeRisk(str, Enum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"
    CRITICAL = "critical"


class _EvidenceLedgerLike(Protocol):
    def is_active(self, evidence_id: str) -> bool: ...


def _uniq(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    out = tuple(str(v).strip() for v in values)
    if any(not v for v in out):
        raise ValueError(f"{field} entries must be explicit")
    if len(set(out)) != len(out):
        raise ValueError(f"{field} entries must be unique")
    return out


@dataclass(frozen=True, slots=True)
class KnowledgeClaim:
    claim_id: str
    subject: str
    relation: str
    object: str
    risk: KnowledgeRisk
    evidence_ids: tuple[str, ...]
    parent_claim_ids: tuple[str, ...]
    content_digest: str

    @classmethod
    def create(cls, *, claim_id: str, subject: str, relation: str, object: str,
               risk: KnowledgeRisk = KnowledgeRisk.STANDARD, evidence_ids: tuple[str, ...] = (),
               parent_claim_ids: tuple[str, ...] = ()) -> "KnowledgeClaim":
        fields = {
            "claim_id": str(claim_id).strip(), "subject": str(subject).strip(),
            "relation": str(relation).strip(), "object": str(object).strip(),
        }
        if any(not value for value in fields.values()):
            raise ValueError("knowledge claim identity and proposition fields must be explicit")
        evidence_ids = _uniq(tuple(evidence_ids), "evidence_ids")
        parent_claim_ids = _uniq(tuple(parent_claim_ids), "parent_claim_ids")
        if fields["claim_id"] in parent_claim_ids:
            raise ValueError("knowledge claim cannot depend on itself")
        payload = {
            **fields, "risk": KnowledgeRisk(risk).value,
            "evidence_ids": list(evidence_ids), "parent_claim_ids": list(parent_claim_ids),
        }
        return cls(
            fields["claim_id"], fields["subject"], fields["relation"], fields["object"],
            KnowledgeRisk(risk), evidence_ids, parent_claim_ids, truth_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id, "subject": self.subject, "relation": self.relation,
            "object": self.object, "risk": self.risk.value, "evidence_ids": list(self.evidence_ids),
            "parent_claim_ids": list(self.parent_claim_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "content_digest": self.content_digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "KnowledgeClaim":
        row = cls.create(
            claim_id=str(state["claim_id"]), subject=str(state["subject"]),
            relation=str(state["relation"]), object=str(state["object"]),
            risk=KnowledgeRisk(str(state["risk"])),
            evidence_ids=tuple(str(x) for x in state.get("evidence_ids", ())),
            parent_claim_ids=tuple(str(x) for x in state.get("parent_claim_ids", ())),
        )
        if str(state["content_digest"]) != row.content_digest:
            raise ValueError("knowledge claim content digest mismatch")
        return row


class KnowledgeLedger:
    """Immutable proposition/derivation authority; does not decide epistemic truth."""

    def __init__(self) -> None:
        self._claims: dict[str, KnowledgeClaim] = {}

    def add(self, claim: KnowledgeClaim) -> KnowledgeClaim:
        previous = self._claims.get(claim.claim_id)
        if previous is not None:
            if previous != claim:
                raise ValueError("knowledge claim id collision")
            return previous
        missing = tuple(parent for parent in claim.parent_claim_ids if parent not in self._claims)
        if missing:
            raise ValueError(f"unknown parent knowledge claim(s): {','.join(missing)}")
        self._claims[claim.claim_id] = claim
        return claim

    def get(self, claim_id: str) -> KnowledgeClaim:
        try:
            return self._claims[str(claim_id)]
        except KeyError as exc:
            raise KeyError(f"unknown knowledge claim: {claim_id}") from exc

    def claims(self) -> tuple[KnowledgeClaim, ...]:
        return tuple(self._claims[key] for key in sorted(self._claims))

    @property
    def digest(self) -> str:
        return truth_digest(self.to_state())

    def impacted_claim_ids(self, evidence: _EvidenceLedgerLike) -> tuple[str, ...]:
        impacted = {
            claim.claim_id for claim in self._claims.values()
            if any(not evidence.is_active(evidence_id) for evidence_id in claim.evidence_ids)
        }
        changed = True
        while changed:
            changed = False
            for claim in self._claims.values():
                if claim.claim_id not in impacted and any(parent in impacted for parent in claim.parent_claim_ids):
                    impacted.add(claim.claim_id)
                    changed = True
        return tuple(sorted(impacted))

    def to_state(self) -> dict[str, Any]:
        return {"protocol": "knowledge-ledger-v1", "claims": [row.to_state() for row in self.claims()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "KnowledgeLedger":
        ledger = cls()
        for value in state.get("claims", ()):
            ledger.add(KnowledgeClaim.from_state(value))
        return ledger


__all__ = ("KnowledgeRisk", "KnowledgeClaim", "KnowledgeLedger")
