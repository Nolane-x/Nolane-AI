from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ._truth_digest import truth_digest
from .evidence_truth import EvidenceLedger, EvidencePolarity
from .knowledge import KnowledgeLedger, KnowledgeRisk

COMPONENT_ID = "external.epistemic.truth"
COMPONENT_VERSION = "0.2.0"


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
        payload = {"claim_id": str(claim_id), "disposition": EpistemicDisposition(disposition).value,
                   "support_evidence_ids": list(support_evidence_ids), "refute_evidence_ids": list(refute_evidence_ids),
                   "knowledge_digest": str(knowledge_digest), "evidence_digest": str(evidence_digest)}
        return cls(str(claim_id), EpistemicDisposition(disposition), tuple(support_evidence_ids), tuple(refute_evidence_ids),
                   str(knowledge_digest), str(evidence_digest), truth_digest(payload))


@dataclass(frozen=True, slots=True)
class EpistemicDebt:
    debt_id: str
    claim_id: str
    critical: bool
    reason: str
    digest: str

    @classmethod
    def create(cls, debt_id: str, *, claim_id: str, critical: bool, reason: str) -> "EpistemicDebt":
        payload = {"debt_id": str(debt_id).strip(), "claim_id": str(claim_id).strip(),
                   "critical": bool(critical), "reason": str(reason).strip()}
        if not payload["debt_id"] or not payload["claim_id"] or not payload["reason"]:
            raise ValueError("epistemic debt identity, claim, and reason must be explicit")
        return cls(payload["debt_id"], payload["claim_id"], payload["critical"], payload["reason"], truth_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {"debt_id": self.debt_id, "claim_id": self.claim_id, "critical": self.critical,
                "reason": self.reason, "digest": self.digest}


@dataclass(frozen=True, slots=True)
class EpistemicContradiction:
    contradiction_id: str
    subject: str
    relation: str
    claim_ids: tuple[str, ...]
    object_values: tuple[str, ...]
    digest: str

    @classmethod
    def create(cls, *, subject: str, relation: str, claim_ids: tuple[str, ...], object_values: tuple[str, ...]) -> "EpistemicContradiction":
        claim_ids, object_values = tuple(sorted(map(str, claim_ids))), tuple(sorted(map(str, object_values)))
        payload = {"subject": str(subject), "relation": str(relation), "claim_ids": list(claim_ids), "object_values": list(object_values)}
        digest = truth_digest(payload)
        return cls(f"epistemic-contradiction-{digest[:24]}", str(subject), str(relation), claim_ids, object_values, digest)

    def to_state(self) -> dict[str, Any]:
        return {"contradiction_id": self.contradiction_id, "subject": self.subject, "relation": self.relation,
                "claim_ids": list(self.claim_ids), "object_values": list(self.object_values), "digest": self.digest}


@dataclass(frozen=True, slots=True)
class EpistemicSnapshot:
    knowledge_digest: str
    evidence_digest: str
    assessments: tuple[EpistemicAssessment, ...]
    contradictions: tuple[EpistemicContradiction, ...]
    debts: tuple[EpistemicDebt, ...]
    digest: str

    @classmethod
    def create(cls, *, knowledge_digest: str, evidence_digest: str, assessments: tuple[EpistemicAssessment, ...],
               contradictions: tuple[EpistemicContradiction, ...], debts: tuple[EpistemicDebt, ...]) -> "EpistemicSnapshot":
        assessments = tuple(sorted(assessments, key=lambda row: row.claim_id))
        contradictions = tuple(sorted(contradictions, key=lambda row: row.contradiction_id))
        debts = tuple(sorted(debts, key=lambda row: row.debt_id))
        state = {"protocol": "epistemic-snapshot-v1", "knowledge_digest": str(knowledge_digest),
                 "evidence_digest": str(evidence_digest),
                 "assessments": [vars(row) | {"disposition": row.disposition.value} for row in assessments],
                 "contradictions": [row.to_state() for row in contradictions],
                 "debts": [row.to_state() for row in debts]}
        return cls(str(knowledge_digest), str(evidence_digest), assessments, contradictions, debts, truth_digest(state))

    def assessment(self, claim_id: str) -> EpistemicAssessment:
        for row in self.assessments:
            if row.claim_id == str(claim_id):
                return row
        raise KeyError(f"claim missing from epistemic snapshot: {claim_id}")


class EpistemicJudge:
    """Uncertainty/conflict authority. Evidence and proposition storage remain separate."""

    def _assess(self, claim_id: str, *, knowledge: KnowledgeLedger, evidence: EvidenceLedger,
                memo: dict[str, EpistemicAssessment]) -> EpistemicAssessment:
        if claim_id in memo:
            return memo[claim_id]
        claim = knowledge.get(claim_id)
        if claim.claim_id in set(knowledge.impacted_claim_ids(evidence)):
            disposition, support, refute = EpistemicDisposition.UNKNOWN, (), ()
        else:
            parents = tuple(self._assess(parent, knowledge=knowledge, evidence=evidence, memo=memo) for parent in claim.parent_claim_ids)
            if any(row.disposition is not EpistemicDisposition.SUPPORTED for row in parents):
                disposition, support, refute = EpistemicDisposition.UNKNOWN, (), ()
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
        row = EpistemicAssessment.create(claim_id=claim.claim_id, disposition=disposition,
                                         support_evidence_ids=support, refute_evidence_ids=refute,
                                         knowledge_digest=knowledge.digest, evidence_digest=evidence.digest)
        memo[claim_id] = row
        return row

    def assess(self, claim_id: str, *, knowledge: KnowledgeLedger, evidence: EvidenceLedger) -> EpistemicAssessment:
        return self._assess(str(claim_id), knowledge=knowledge, evidence=evidence, memo={})

    def snapshot(self, *, knowledge: KnowledgeLedger, evidence: EvidenceLedger) -> EpistemicSnapshot:
        memo: dict[str, EpistemicAssessment] = {}
        assessments = tuple(self._assess(row.claim_id, knowledge=knowledge, evidence=evidence, memo=memo) for row in knowledge.claims())
        groups: dict[tuple[str, str], list[str]] = {}
        for row in assessments:
            if row.disposition is EpistemicDisposition.SUPPORTED:
                claim = knowledge.get(row.claim_id)
                groups.setdefault((claim.subject, claim.relation), []).append(claim.claim_id)
        contradictions = []
        for (subject, relation), claim_ids in sorted(groups.items()):
            objects = {knowledge.get(cid).object for cid in claim_ids}
            if len(objects) > 1:
                contradictions.append(EpistemicContradiction.create(subject=subject, relation=relation,
                                                                     claim_ids=tuple(claim_ids), object_values=tuple(objects)))
        debts = []
        for row in assessments:
            claim = knowledge.get(row.claim_id)
            if row.disposition in {EpistemicDisposition.UNKNOWN, EpistemicDisposition.CONTRADICTED}:
                debts.append(EpistemicDebt.create(f"epistemic-debt:{claim.claim_id}:{row.disposition.value}",
                                                  claim_id=claim.claim_id, critical=claim.risk is KnowledgeRisk.CRITICAL,
                                                  reason=row.disposition.value))
        for conflict in contradictions:
            for claim_id in conflict.claim_ids:
                claim = knowledge.get(claim_id)
                debts.append(EpistemicDebt.create(f"epistemic-debt:{claim_id}:{conflict.contradiction_id}",
                                                  claim_id=claim_id, critical=claim.risk is KnowledgeRisk.CRITICAL,
                                                  reason="competing_supported_propositions"))
        return EpistemicSnapshot.create(knowledge_digest=knowledge.digest, evidence_digest=evidence.digest,
                                        assessments=assessments, contradictions=tuple(contradictions), debts=tuple(debts))

    def audit(self, *, knowledge: KnowledgeLedger, evidence: EvidenceLedger) -> tuple[EpistemicDebt, ...]:
        return self.snapshot(knowledge=knowledge, evidence=evidence).debts


__all__ = ("EpistemicDisposition", "EpistemicAssessment", "EpistemicDebt", "EpistemicContradiction", "EpistemicSnapshot", "EpistemicJudge")
