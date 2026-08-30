from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .epistemic_truth import EpistemicDebt, EpistemicDisposition, EpistemicJudge, EpistemicSnapshot
from .evidence_truth import EvidenceLedger
from .knowledge_truth import KnowledgeLedger, KnowledgeRisk
from .verification_truth import TruthVerificationLedger

PARENT_COMPONENT_ID = "external.assurance"
TRUTH_PROTOCOL = "truth-assurance-v1"

_REQUIREMENTS = {
    KnowledgeRisk.LOW: (1, 1), KnowledgeRisk.STANDARD: (1, 1),
    KnowledgeRisk.HIGH: (2, 2), KnowledgeRisk.CRITICAL: (3, 3),
}


@dataclass(frozen=True, slots=True)
class TruthClosureCertificate:
    certificate_id: str
    claim_id: str
    risk: KnowledgeRisk
    knowledge_digest: str
    evidence_digest: str
    epistemic_digest: str
    verification_digest: str
    verification_receipt_ids: tuple[str, ...]
    epistemic_debt_ids: tuple[str, ...]
    closed: bool
    reasons: tuple[str, ...]
    digest: str

    @classmethod
    def create(cls, *, claim_id: str, risk: KnowledgeRisk, knowledge_digest: str, evidence_digest: str,
               epistemic_digest: str, verification_digest: str, verification_receipt_ids: tuple[str, ...],
               epistemic_debt_ids: tuple[str, ...], closed: bool, reasons: tuple[str, ...]) -> "TruthClosureCertificate":
        payload = {"protocol": TRUTH_PROTOCOL, "claim_id": str(claim_id), "risk": KnowledgeRisk(risk).value,
                   "knowledge_digest": str(knowledge_digest), "evidence_digest": str(evidence_digest),
                   "epistemic_digest": str(epistemic_digest), "verification_digest": str(verification_digest),
                   "verification_receipt_ids": list(verification_receipt_ids),
                   "epistemic_debt_ids": list(epistemic_debt_ids), "closed": bool(closed), "reasons": list(reasons)}
        digest = canonical_digest(payload)
        return cls(f"truth-closure-{digest[:24]}", str(claim_id), KnowledgeRisk(risk), str(knowledge_digest),
                   str(evidence_digest), str(epistemic_digest), str(verification_digest),
                   tuple(verification_receipt_ids), tuple(epistemic_debt_ids), bool(closed), tuple(reasons), digest)

    def payload(self) -> dict[str, Any]:
        return {"protocol": TRUTH_PROTOCOL, "claim_id": self.claim_id, "risk": self.risk.value,
                "knowledge_digest": self.knowledge_digest, "evidence_digest": self.evidence_digest,
                "epistemic_digest": self.epistemic_digest, "verification_digest": self.verification_digest,
                "verification_receipt_ids": list(self.verification_receipt_ids),
                "epistemic_debt_ids": list(self.epistemic_debt_ids), "closed": self.closed,
                "reasons": list(self.reasons)}

    def to_state(self) -> dict[str, Any]:
        return {"certificate_id": self.certificate_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthClosureCertificate":
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported truth assurance protocol")
        row = cls.create(claim_id=str(state["claim_id"]), risk=KnowledgeRisk(str(state["risk"])),
                         knowledge_digest=str(state["knowledge_digest"]), evidence_digest=str(state["evidence_digest"]),
                         epistemic_digest=str(state["epistemic_digest"]),
                         verification_digest=str(state["verification_digest"]),
                         verification_receipt_ids=tuple(str(x) for x in state.get("verification_receipt_ids", ())),
                         epistemic_debt_ids=tuple(str(x) for x in state.get("epistemic_debt_ids", ())),
                         closed=bool(state["closed"]), reasons=tuple(str(x) for x in state.get("reasons", ())))
        if str(state["certificate_id"]) != row.certificate_id or str(state["digest"]) != row.digest:
            raise ValueError("truth closure certificate digest mismatch")
        return row


class TruthAssuranceGate:
    """Truth-closure protocol under the canonical ``external.assurance`` authority.

    ``close_snapshot`` and ``close_live`` are the only strict paths. The legacy digest-only
    ``close`` surface is deliberately retained only as a fail-closed diagnostic compatibility path:
    caller-asserted digests or debt can never manufacture an accepted truth certificate.
    """

    @staticmethod
    def _strict_verification(*, claim_id: str, risk: KnowledgeRisk, knowledge_digest: str,
                             epistemic_digest: str, verification: TruthVerificationLedger,
                             evidence: EvidenceLedger):
        coverage = verification.coverage(
            claim_id, knowledge_digest=knowledge_digest, epistemic_digest=epistemic_digest, evidence=evidence,
        )
        reasons: list[str] = list(coverage.issues)
        if coverage.negative_receipt_ids:
            reasons.append("negative_verification")
        required_sources, required_channels = _REQUIREMENTS[risk]
        if coverage.independent_source_count < required_sources:
            reasons.append("insufficient_independent_verification")
        if coverage.channel_count < required_channels:
            reasons.append("insufficient_verification_channel_diversity")
        return coverage.receipts, reasons

    def close(self, *, claim_id: str, risk: KnowledgeRisk, knowledge_digest: str, epistemic_digest: str,
              verification: TruthVerificationLedger, debts: tuple[EpistemicDebt, ...] = ()) -> TruthClosureCertificate:
        """Compatibility-only unbound path. It intentionally cannot return ``closed=True``."""
        risk = KnowledgeRisk(risk)
        rows = verification.bound_receipts(
            str(claim_id), knowledge_digest=str(knowledge_digest), epistemic_digest=str(epistemic_digest),
        )
        claim_debts = tuple(sorted((row for row in debts if row.claim_id == str(claim_id)), key=lambda row: row.debt_id))
        reasons = ["noncanonical_closure_path"]
        if any(not row.passed for row in rows):
            reasons.append("negative_verification")
        if any(row.critical for row in claim_debts):
            reasons.append("critical_epistemic_debt")
        return TruthClosureCertificate.create(
            claim_id=str(claim_id), risk=risk, knowledge_digest=str(knowledge_digest), evidence_digest="unbound",
            epistemic_digest=str(epistemic_digest), verification_digest=verification.digest,
            verification_receipt_ids=tuple(row.receipt_id for row in rows),
            epistemic_debt_ids=tuple(row.debt_id for row in claim_debts),
            closed=False, reasons=tuple(dict.fromkeys(reasons)),
        )

    def close_snapshot(self, *, claim_id: str, knowledge: KnowledgeLedger, evidence: EvidenceLedger,
                       epistemic: EpistemicSnapshot, verification: TruthVerificationLedger) -> TruthClosureCertificate:
        if epistemic.knowledge_digest != knowledge.digest:
            raise ValueError("epistemic snapshot is bound to a different knowledge state")
        if epistemic.evidence_digest != evidence.digest:
            raise ValueError("epistemic snapshot is bound to a different evidence state")

        canonical = EpistemicJudge().snapshot(knowledge=knowledge, evidence=evidence)
        if canonical.digest != epistemic.digest:
            raise ValueError("noncanonical epistemic snapshot")

        claim = knowledge.get(claim_id)
        assessment = canonical.assessment(claim.claim_id)
        rows, reasons = self._strict_verification(
            claim_id=claim.claim_id, risk=claim.risk, knowledge_digest=knowledge.digest,
            epistemic_digest=canonical.digest, verification=verification, evidence=evidence,
        )
        claim_debts = tuple(row for row in canonical.debts if row.claim_id == claim.claim_id)
        if assessment.disposition is not EpistemicDisposition.SUPPORTED:
            reasons.insert(0, "epistemic_claim_not_supported")
        if any(claim.claim_id in row.claim_ids for row in canonical.contradictions):
            reasons.insert(0, "epistemic_claim_conflicted")
        if any(row.critical for row in claim_debts):
            reasons.insert(0, "critical_epistemic_debt")
        reasons = list(dict.fromkeys(reasons))
        return TruthClosureCertificate.create(
            claim_id=claim.claim_id, risk=claim.risk, knowledge_digest=knowledge.digest,
            evidence_digest=evidence.digest, epistemic_digest=canonical.digest, verification_digest=verification.digest,
            verification_receipt_ids=tuple(row.receipt_id for row in rows),
            epistemic_debt_ids=tuple(sorted(row.debt_id for row in claim_debts)),
            closed=not reasons, reasons=tuple(reasons),
        )

    def close_live(self, *, claim_id: str, knowledge: KnowledgeLedger, evidence: EvidenceLedger,
                   verification: TruthVerificationLedger) -> TruthClosureCertificate:
        """Compute canonical epistemic state from live ledgers and attempt strict closure."""
        snapshot = EpistemicJudge().snapshot(knowledge=knowledge, evidence=evidence)
        return self.close_snapshot(
            claim_id=claim_id, knowledge=knowledge, evidence=evidence,
            epistemic=snapshot, verification=verification,
        )


__all__ = (
    "PARENT_COMPONENT_ID", "TRUTH_PROTOCOL", "TruthClosureCertificate", "TruthAssuranceGate",
)
