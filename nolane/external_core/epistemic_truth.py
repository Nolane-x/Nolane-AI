from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ._truth_digest import truth_digest
from .evidence_truth import EvidenceLedger, EvidencePolarity
from .knowledge import KnowledgeLedger

COMPONENT_ID = "external.epistemic.truth"
COMPONENT_VERSION = "0.1.0"


class EpistemicDisposition(str, Enum):
    UNKNOWN = "unknown"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True, slots=True)
class EpistemicAssessment:
    claim_id: str
    disposition: EpistemicDisposition
    support_evidence_ids: tuple[str, ...]
    refute_evidence_ids: tuple[str, ...]
    knowledge_digest: str
    evidence_digest: str
    digest: str

    @classmethod
    def create(cls, *, claim_id: str, disposition: EpistemicDisposition,
               support_evidence_ids: tuple[str, ...], refute_evidence_ids: tuple[str, ...],
               knowledge_digest: str, evidence_digest: str) -> "EpistemicAssessment":
        payload = {
            "claim_id": str(claim_id), "disposition": EpistemicDisposition(disposition).value,
            "support_evidence_ids": list(support_evidence_ids), "refute_evidence_ids": list(refute_evidence_ids),
            "knowledge_digest": str(knowledge_digest), "evidence_digest": str(evidence_digest),
        }
        return cls(
            str(claim_id), EpistemicDisposition(disposition), tuple(support_evidence_ids),
            tuple(refute_evidence_ids), str(knowledge_digest), str(evidence_digest), truth_digest(payload),
        )


@dataclass(frozen=True, slots=True)
class EpistemicDebt:
    debt_id: str
    claim_id: str
    critical: bool
    reason: str
    digest: str

    @classmethod
    def create(cls, debt_id: str, *, claim_id: str, critical: bool, reason: str) -> "EpistemicDebt":
        payload = {
            "debt_id": str(debt_id).strip(), "claim_id": str(claim_id).strip(),
            "critical": bool(critical), "reason": str(reason).strip(),
        }
        if not payload["debt_id"] or not payload["claim_id"] or not payload["reason"]:
            raise ValueError("epistemic debt identity, claim, and reason must be explicit")
        return cls(payload["debt_id"], payload["claim_id"], payload["critical"], payload["reason"], truth_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {
            "debt_id": self.debt_id, "claim_id": self.claim_id, "critical": self.critical,
            "reason": self.reason, "digest": self.digest,
        }


class EpistemicJudge:
    """Judges uncertainty/conflict without owning proposition or evidence storage."""

    def assess(self, claim_id: str, *, knowledge: KnowledgeLedger, evidence: EvidenceLedger) -> EpistemicAssessment:
        claim = knowledge.get(claim_id)
        if claim.claim_id in set(knowledge.impacted_claim_ids(evidence)):
            support: tuple[str, ...] = ()
            refute: tuple[str, ...] = ()
            disposition = EpistemicDisposition.UNKNOWN
        else:
            rows = tuple(evidence.get(eid) for eid in claim.evidence_ids if evidence.is_active(eid))
            support = tuple(sorted(row.evidence_id for row in rows if row.polarity is EvidencePolarity.SUPPORT))
            refute = tuple(sorted(row.evidence_id for row in rows if row.polarity is EvidencePolarity.REFUTE))
            if support and refute:
                disposition = EpistemicDisposition.CONTRADICTED
            elif support:
                disposition = EpistemicDisposition.SUPPORTED
            elif refute:
                disposition = EpistemicDisposition.REFUTED
            else:
                disposition = EpistemicDisposition.UNKNOWN
        return EpistemicAssessment.create(
            claim_id=claim.claim_id, disposition=disposition, support_evidence_ids=support,
            refute_evidence_ids=refute, knowledge_digest=knowledge.digest, evidence_digest=evidence.digest,
        )

    def audit(self, *, knowledge: KnowledgeLedger, evidence: EvidenceLedger) -> tuple[EpistemicDebt, ...]:
        debts = []
        for claim in knowledge.claims():
            assessment = self.assess(claim.claim_id, knowledge=knowledge, evidence=evidence)
            if assessment.disposition in {EpistemicDisposition.UNKNOWN, EpistemicDisposition.CONTRADICTED}:
                debts.append(EpistemicDebt.create(
                    f"epistemic-debt:{claim.claim_id}:{assessment.disposition.value}",
                    claim_id=claim.claim_id, critical=claim.risk.value == "critical",
                    reason=assessment.disposition.value,
                ))
        return tuple(debts)


__all__ = ("EpistemicDisposition", "EpistemicAssessment", "EpistemicDebt", "EpistemicJudge")
