from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ._truth_digest import truth_digest
from .epistemic_truth import EpistemicDebt
from .knowledge import KnowledgeRisk
from .verification_truth import TruthVerificationLedger

COMPONENT_ID = "external.assurance.truth"
COMPONENT_VERSION = "0.1.0"

_REQUIREMENTS = {
    KnowledgeRisk.LOW: (1, 1),
    KnowledgeRisk.STANDARD: (1, 1),
    KnowledgeRisk.HIGH: (2, 2),
    KnowledgeRisk.CRITICAL: (3, 3),
}


@dataclass(frozen=True, slots=True)
class TruthClosureCertificate:
    certificate_id: str
    claim_id: str
    risk: KnowledgeRisk
    knowledge_digest: str
    epistemic_digest: str
    verification_digest: str
    verification_receipt_ids: tuple[str, ...]
    epistemic_debt_ids: tuple[str, ...]
    closed: bool
    reasons: tuple[str, ...]
    digest: str

    @classmethod
    def create(cls, *, claim_id: str, risk: KnowledgeRisk, knowledge_digest: str, epistemic_digest: str,
               verification_digest: str, verification_receipt_ids: tuple[str, ...],
               epistemic_debt_ids: tuple[str, ...], closed: bool, reasons: tuple[str, ...]) -> "TruthClosureCertificate":
        payload = {
            "claim_id": str(claim_id), "risk": KnowledgeRisk(risk).value,
            "knowledge_digest": str(knowledge_digest), "epistemic_digest": str(epistemic_digest),
            "verification_digest": str(verification_digest),
            "verification_receipt_ids": list(verification_receipt_ids),
            "epistemic_debt_ids": list(epistemic_debt_ids), "closed": bool(closed), "reasons": list(reasons),
        }
        digest = truth_digest(payload)
        return cls(
            f"truth-closure-{digest[:24]}", str(claim_id), KnowledgeRisk(risk), str(knowledge_digest),
            str(epistemic_digest), str(verification_digest), tuple(verification_receipt_ids),
            tuple(epistemic_debt_ids), bool(closed), tuple(reasons), digest,
        )

    def payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id, "risk": self.risk.value, "knowledge_digest": self.knowledge_digest,
            "epistemic_digest": self.epistemic_digest, "verification_digest": self.verification_digest,
            "verification_receipt_ids": list(self.verification_receipt_ids),
            "epistemic_debt_ids": list(self.epistemic_debt_ids), "closed": self.closed,
            "reasons": list(self.reasons),
        }

    def to_state(self) -> dict[str, Any]:
        return {"certificate_id": self.certificate_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthClosureCertificate":
        row = cls.create(
            claim_id=str(state["claim_id"]), risk=KnowledgeRisk(str(state["risk"])),
            knowledge_digest=str(state["knowledge_digest"]), epistemic_digest=str(state["epistemic_digest"]),
            verification_digest=str(state["verification_digest"]),
            verification_receipt_ids=tuple(str(x) for x in state.get("verification_receipt_ids", ())),
            epistemic_debt_ids=tuple(str(x) for x in state.get("epistemic_debt_ids", ())),
            closed=bool(state["closed"]), reasons=tuple(str(x) for x in state.get("reasons", ())),
        )
        if str(state["certificate_id"]) != row.certificate_id or str(state["digest"]) != row.digest:
            raise ValueError("truth closure certificate digest mismatch")
        return row


class TruthAssuranceGate:
    """Final closure only; it cannot create evidence, knowledge, or verification receipts."""

    def close(self, *, claim_id: str, risk: KnowledgeRisk, knowledge_digest: str, epistemic_digest: str,
              verification: TruthVerificationLedger, debts: tuple[EpistemicDebt, ...] = ()) -> TruthClosureCertificate:
        risk = KnowledgeRisk(risk)
        rows = verification.bound_receipts(
            claim_id, knowledge_digest=knowledge_digest, epistemic_digest=epistemic_digest,
        )
        reasons: list[str] = []
        claim_debts = tuple(sorted(
            (row for row in debts if row.claim_id == str(claim_id)), key=lambda row: row.debt_id,
        ))
        if any(row.critical for row in claim_debts):
            reasons.append("critical_epistemic_debt")
        if any(not row.passed for row in rows):
            reasons.append("negative_verification")
        required_sources, required_channels = _REQUIREMENTS[risk]
        passing_sources = {row.source_family for row in rows if row.passed}
        passing_channels = {row.channel for row in rows if row.passed}
        if len(passing_sources) < required_sources:
            reasons.append("insufficient_independent_verification")
        if len(passing_channels) < required_channels:
            reasons.append("insufficient_verification_channel_diversity")
        reasons = list(dict.fromkeys(reasons))
        return TruthClosureCertificate.create(
            claim_id=str(claim_id), risk=risk, knowledge_digest=str(knowledge_digest),
            epistemic_digest=str(epistemic_digest), verification_digest=verification.digest,
            verification_receipt_ids=tuple(row.receipt_id for row in rows),
            epistemic_debt_ids=tuple(row.debt_id for row in claim_debts), closed=not reasons,
            reasons=tuple(reasons),
        )


__all__ = ("TruthClosureCertificate", "TruthAssuranceGate")
