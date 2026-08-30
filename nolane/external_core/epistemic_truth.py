from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .evidence_truth import EvidenceLedger, EvidencePolarity
from .knowledge_truth import KnowledgeLedger, KnowledgeRisk

PARENT_COMPONENT_ID = "external.epistemic"
TRUTH_PROTOCOL = "truth-epistemic-snapshot-v1"
DEPENDENCY_SCOPE_PROTOCOL = "truth-dependency-scope-v2"


class EpistemicDisposition(str, Enum):
    UNKNOWN = "unknown"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    CONTRADICTED = "contradicted"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _unique(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    normalized = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in normalized):
        raise ValueError(f"{field} entries must be explicit")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} entries must be unique")
    return normalized


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
    def create(cls, *, claim_id: str, disposition: EpistemicDisposition, support_evidence_ids: tuple[str, ...],
               refute_evidence_ids: tuple[str, ...], knowledge_digest: str, evidence_digest: str) -> "EpistemicAssessment":
        claim_id = _explicit(claim_id, "claim_id")
        knowledge_digest = _explicit(knowledge_digest, "knowledge_digest")
        evidence_digest = _explicit(evidence_digest, "evidence_digest")
        support_evidence_ids = _unique(tuple(support_evidence_ids), "support_evidence_ids")
        refute_evidence_ids = _unique(tuple(refute_evidence_ids), "refute_evidence_ids")
        if set(support_evidence_ids) & set(refute_evidence_ids):
            raise ValueError("epistemic evidence cannot be both support and refute")
        payload = {"claim_id": claim_id, "disposition": EpistemicDisposition(disposition).value,
                   "support_evidence_ids": list(support_evidence_ids), "refute_evidence_ids": list(refute_evidence_ids),
                   "knowledge_digest": knowledge_digest, "evidence_digest": evidence_digest}
        return cls(claim_id, EpistemicDisposition(disposition), support_evidence_ids, refute_evidence_ids,
                   knowledge_digest, evidence_digest, canonical_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, "disposition": self.disposition.value,
                "support_evidence_ids": list(self.support_evidence_ids), "refute_evidence_ids": list(self.refute_evidence_ids),
                "knowledge_digest": self.knowledge_digest, "evidence_digest": self.evidence_digest, "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EpistemicAssessment":
        row = cls.create(
            claim_id=str(state["claim_id"]),
            disposition=EpistemicDisposition(str(state["disposition"])),
            support_evidence_ids=tuple(str(value) for value in state.get("support_evidence_ids", ())),
            refute_evidence_ids=tuple(str(value) for value in state.get("refute_evidence_ids", ())),
            knowledge_digest=str(state["knowledge_digest"]),
            evidence_digest=str(state["evidence_digest"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("epistemic assessment digest mismatch")
        return row


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
        return cls(payload["debt_id"], payload["claim_id"], payload["critical"], payload["reason"], canonical_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {"debt_id": self.debt_id, "claim_id": self.claim_id, "critical": self.critical,
                "reason": self.reason, "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EpistemicDebt":
        row = cls.create(
            str(state["debt_id"]), claim_id=str(state["claim_id"]),
            critical=bool(state["critical"]), reason=str(state["reason"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("epistemic debt digest mismatch")
        return row


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
        subject = _explicit(subject, "contradiction subject")
        relation = _explicit(relation, "contradiction relation")
        claim_ids = _unique(tuple(claim_ids), "contradiction claim_ids")
        object_values = _unique(tuple(object_values), "contradiction object_values")
        if len(claim_ids) < 2 or len(object_values) < 2:
            raise ValueError("epistemic contradiction requires competing claims and values")
        payload = {"subject": subject, "relation": relation, "claim_ids": list(claim_ids), "object_values": list(object_values)}
        digest = canonical_digest(payload)
        return cls(f"epistemic-contradiction-{digest[:24]}", subject, relation, claim_ids, object_values, digest)

    def to_state(self) -> dict[str, Any]:
        return {"contradiction_id": self.contradiction_id, "subject": self.subject, "relation": self.relation,
                "claim_ids": list(self.claim_ids), "object_values": list(self.object_values), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EpistemicContradiction":
        row = cls.create(
            subject=str(state["subject"]), relation=str(state["relation"]),
            claim_ids=tuple(str(value) for value in state.get("claim_ids", ())),
            object_values=tuple(str(value) for value in state.get("object_values", ())),
        )
        if str(state["contradiction_id"]) != row.contradiction_id or str(state["digest"]) != row.digest:
            raise ValueError("epistemic contradiction digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EpistemicSnapshot:
    knowledge_digest: str
    evidence_digest: str
    assessments: tuple[EpistemicAssessment, ...]
    contradictions: tuple[EpistemicContradiction, ...]
    debts: tuple[EpistemicDebt, ...]
    digest: str

    @staticmethod
    def _payload(*, knowledge_digest: str, evidence_digest: str,
                 assessments: tuple[EpistemicAssessment, ...],
                 contradictions: tuple[EpistemicContradiction, ...], debts: tuple[EpistemicDebt, ...]) -> dict[str, Any]:
        return {"protocol": TRUTH_PROTOCOL, "knowledge_digest": knowledge_digest,
                "evidence_digest": evidence_digest, "assessments": [row.to_state() for row in assessments],
                "contradictions": [row.to_state() for row in contradictions], "debts": [row.to_state() for row in debts]}

    @classmethod
    def create(cls, *, knowledge_digest: str, evidence_digest: str, assessments: tuple[EpistemicAssessment, ...],
               contradictions: tuple[EpistemicContradiction, ...], debts: tuple[EpistemicDebt, ...]) -> "EpistemicSnapshot":
        knowledge_digest = _explicit(knowledge_digest, "knowledge_digest")
        evidence_digest = _explicit(evidence_digest, "evidence_digest")
        assessments = tuple(sorted(assessments, key=lambda row: row.claim_id))
        contradictions = tuple(sorted(contradictions, key=lambda row: row.contradiction_id))
        debts = tuple(sorted(debts, key=lambda row: row.debt_id))

        claim_ids = tuple(row.claim_id for row in assessments)
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("epistemic snapshot assessment ids must be unique")
        if len({row.contradiction_id for row in contradictions}) != len(contradictions):
            raise ValueError("epistemic snapshot contradiction ids must be unique")
        if len({row.debt_id for row in debts}) != len(debts):
            raise ValueError("epistemic snapshot debt ids must be unique")
        for row in assessments:
            if row.knowledge_digest != knowledge_digest or row.evidence_digest != evidence_digest:
                raise ValueError("epistemic assessment state binding mismatch")
        claim_id_set = set(claim_ids)
        if any(set(row.claim_ids) - claim_id_set for row in contradictions):
            raise ValueError("epistemic contradiction references unknown snapshot claim")
        if any(row.claim_id not in claim_id_set for row in debts):
            raise ValueError("epistemic debt references unknown snapshot claim")

        payload = cls._payload(
            knowledge_digest=knowledge_digest, evidence_digest=evidence_digest,
            assessments=assessments, contradictions=contradictions, debts=debts,
        )
        return cls(knowledge_digest, evidence_digest, assessments, contradictions, debts, canonical_digest(payload))

    def assessment(self, claim_id: str) -> EpistemicAssessment:
        for row in self.assessments:
            if row.claim_id == str(claim_id):
                return row
        raise KeyError(f"claim missing from epistemic snapshot: {claim_id}")

    def to_state(self) -> dict[str, Any]:
        return {**self._payload(
            knowledge_digest=self.knowledge_digest, evidence_digest=self.evidence_digest,
            assessments=self.assessments, contradictions=self.contradictions, debts=self.debts,
        ), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EpistemicSnapshot":
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported epistemic snapshot protocol")
        row = cls.create(
            knowledge_digest=str(state["knowledge_digest"]),
            evidence_digest=str(state["evidence_digest"]),
            assessments=tuple(EpistemicAssessment.from_state(value) for value in state.get("assessments", ())),
            contradictions=tuple(EpistemicContradiction.from_state(value) for value in state.get("contradictions", ())),
            debts=tuple(EpistemicDebt.from_state(value) for value in state.get("debts", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("epistemic snapshot digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class TruthScopeAssessment:
    claim_id: str
    disposition: EpistemicDisposition
    support_evidence_ids: tuple[str, ...]
    refute_evidence_ids: tuple[str, ...]
    digest: str

    @classmethod
    def create(cls, *, claim_id: str, disposition: EpistemicDisposition,
               support_evidence_ids: tuple[str, ...], refute_evidence_ids: tuple[str, ...]) -> "TruthScopeAssessment":
        claim_id = _explicit(claim_id, "scope assessment claim_id")
        support = _unique(tuple(support_evidence_ids), "scope support_evidence_ids")
        refute = _unique(tuple(refute_evidence_ids), "scope refute_evidence_ids")
        if set(support) & set(refute):
            raise ValueError("scope evidence cannot be both support and refute")
        payload = {
            "claim_id": claim_id,
            "disposition": EpistemicDisposition(disposition).value,
            "support_evidence_ids": list(support),
            "refute_evidence_ids": list(refute),
        }
        return cls(claim_id, EpistemicDisposition(disposition), support, refute, canonical_digest(payload))

    @classmethod
    def from_assessment(cls, row: EpistemicAssessment) -> "TruthScopeAssessment":
        return cls.create(
            claim_id=row.claim_id, disposition=row.disposition,
            support_evidence_ids=row.support_evidence_ids, refute_evidence_ids=row.refute_evidence_ids,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "disposition": self.disposition.value,
            "support_evidence_ids": list(self.support_evidence_ids),
            "refute_evidence_ids": list(self.refute_evidence_ids),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthScopeAssessment":
        row = cls.create(
            claim_id=str(state["claim_id"]),
            disposition=EpistemicDisposition(str(state["disposition"])),
            support_evidence_ids=tuple(str(value) for value in state.get("support_evidence_ids", ())),
            refute_evidence_ids=tuple(str(value) for value in state.get("refute_evidence_ids", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("scope assessment digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class TruthDependencyScope:
    target_claim_id: str
    lineage_claim_ids: tuple[str, ...]
    scope_claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    knowledge_digest: str
    evidence_digest: str
    assessments: tuple[TruthScopeAssessment, ...]
    contradictions: tuple[EpistemicContradiction, ...]
    debts: tuple[EpistemicDebt, ...]
    digest: str

    @staticmethod
    def _payload(*, target_claim_id: str, lineage_claim_ids: tuple[str, ...],
                 scope_claim_ids: tuple[str, ...], evidence_ids: tuple[str, ...],
                 knowledge_digest: str, evidence_digest: str,
                 assessments: tuple[TruthScopeAssessment, ...],
                 contradictions: tuple[EpistemicContradiction, ...],
                 debts: tuple[EpistemicDebt, ...]) -> dict[str, Any]:
        return {
            "protocol": DEPENDENCY_SCOPE_PROTOCOL,
            "target_claim_id": target_claim_id,
            "lineage_claim_ids": list(lineage_claim_ids),
            "scope_claim_ids": list(scope_claim_ids),
            "evidence_ids": list(evidence_ids),
            "knowledge_digest": knowledge_digest,
            "evidence_digest": evidence_digest,
            "assessments": [row.to_state() for row in assessments],
            "contradictions": [row.to_state() for row in contradictions],
            "debts": [row.to_state() for row in debts],
        }

    @classmethod
    def create(cls, *, target_claim_id: str, lineage_claim_ids: tuple[str, ...],
               scope_claim_ids: tuple[str, ...], evidence_ids: tuple[str, ...],
               knowledge_digest: str, evidence_digest: str,
               assessments: tuple[TruthScopeAssessment, ...],
               contradictions: tuple[EpistemicContradiction, ...],
               debts: tuple[EpistemicDebt, ...]) -> "TruthDependencyScope":
        target = _explicit(target_claim_id, "scope target_claim_id")
        lineage = _unique(tuple(lineage_claim_ids), "lineage_claim_ids")
        scope = _unique(tuple(scope_claim_ids), "scope_claim_ids")
        evidence = _unique(tuple(evidence_ids), "scope evidence_ids")
        knowledge_digest = _explicit(knowledge_digest, "scoped knowledge_digest")
        evidence_digest = _explicit(evidence_digest, "scoped evidence_digest")
        if target not in lineage:
            raise ValueError("scope target must belong to lineage")
        if not set(lineage).issubset(set(scope)):
            raise ValueError("scope lineage must be contained in scope claims")

        assessments = tuple(sorted(assessments, key=lambda row: row.claim_id))
        contradictions = tuple(sorted(contradictions, key=lambda row: row.contradiction_id))
        debts = tuple(sorted(debts, key=lambda row: row.debt_id))
        assessment_ids = tuple(row.claim_id for row in assessments)
        if len(set(assessment_ids)) != len(assessment_ids) or set(assessment_ids) != set(scope):
            raise ValueError("scope assessments must cover exactly the scope claims")
        if len({row.contradiction_id for row in contradictions}) != len(contradictions):
            raise ValueError("scope contradiction ids must be unique")
        if len({row.debt_id for row in debts}) != len(debts):
            raise ValueError("scope debt ids must be unique")
        scope_set = set(scope)
        if any(set(row.claim_ids) - scope_set for row in contradictions):
            raise ValueError("scope contradiction references claim outside scope")
        if any(row.claim_id not in scope_set for row in debts):
            raise ValueError("scope debt references claim outside scope")

        payload = cls._payload(
            target_claim_id=target, lineage_claim_ids=lineage, scope_claim_ids=scope,
            evidence_ids=evidence, knowledge_digest=knowledge_digest, evidence_digest=evidence_digest,
            assessments=assessments, contradictions=contradictions, debts=debts,
        )
        return cls(
            target, lineage, scope, evidence, knowledge_digest, evidence_digest,
            assessments, contradictions, debts, canonical_digest(payload),
        )

    @classmethod
    def create_from_state_payload(cls, state: Mapping[str, Any]) -> "TruthDependencyScope":
        if str(state.get("protocol", "")) != DEPENDENCY_SCOPE_PROTOCOL:
            raise ValueError("unsupported dependency scope protocol")
        return cls.create(
            target_claim_id=str(state["target_claim_id"]),
            lineage_claim_ids=tuple(str(value) for value in state.get("lineage_claim_ids", ())),
            scope_claim_ids=tuple(str(value) for value in state.get("scope_claim_ids", ())),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            knowledge_digest=str(state["knowledge_digest"]),
            evidence_digest=str(state["evidence_digest"]),
            assessments=tuple(TruthScopeAssessment.from_state(value) for value in state.get("assessments", ())),
            contradictions=tuple(EpistemicContradiction.from_state(value) for value in state.get("contradictions", ())),
            debts=tuple(EpistemicDebt.from_state(value) for value in state.get("debts", ())),
        )

    def assessment(self, claim_id: str) -> TruthScopeAssessment:
        for row in self.assessments:
            if row.claim_id == str(claim_id):
                return row
        raise KeyError(f"claim missing from dependency scope: {claim_id}")

    def to_state(self) -> dict[str, Any]:
        return {**self._payload(
            target_claim_id=self.target_claim_id, lineage_claim_ids=self.lineage_claim_ids,
            scope_claim_ids=self.scope_claim_ids, evidence_ids=self.evidence_ids,
            knowledge_digest=self.knowledge_digest, evidence_digest=self.evidence_digest,
            assessments=self.assessments, contradictions=self.contradictions, debts=self.debts,
        ), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthDependencyScope":
        row = cls.create_from_state_payload(state)
        if str(state["digest"]) != row.digest:
            raise ValueError("dependency scope digest mismatch")
        return row


class EpistemicJudge:
    """Truth-closure uncertainty/conflict protocol under ``external.epistemic``."""

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
                if any(row.subject_id != claim.claim_id for row in rows):
                    disposition, support, refute = EpistemicDisposition.UNKNOWN, (), ()
                else:
                    support = tuple(sorted(row.evidence_id for row in rows if row.polarity is EvidencePolarity.SUPPORT))
                    refute = tuple(sorted(row.evidence_id for row in rows if row.polarity is EvidencePolarity.REFUTE))
                    disposition = (EpistemicDisposition.CONTRADICTED if support and refute else
                                   EpistemicDisposition.SUPPORTED if support else
                                   EpistemicDisposition.REFUTED if refute else EpistemicDisposition.UNKNOWN)
        result = EpistemicAssessment.create(claim_id=claim.claim_id, disposition=disposition,
                                            support_evidence_ids=support, refute_evidence_ids=refute,
                                            knowledge_digest=knowledge.digest, evidence_digest=evidence.digest)
        memo[claim_id] = result
        return result

    def assess(self, claim_id: str, *, knowledge: KnowledgeLedger, evidence: EvidenceLedger) -> EpistemicAssessment:
        return self._assess(str(claim_id), knowledge=knowledge, evidence=evidence, memo={})

    @staticmethod
    def _lineage_debts(*, knowledge: KnowledgeLedger, evidence: EvidenceLedger) -> tuple[EpistemicDebt, ...]:
        debts: list[EpistemicDebt] = []
        for claim in knowledge.claims():
            critical = claim.risk is KnowledgeRisk.CRITICAL
            for evidence_id in claim.evidence_ids:
                try:
                    row = evidence.get(evidence_id)
                except KeyError:
                    debts.append(EpistemicDebt.create(
                        f"epistemic-debt:{claim.claim_id}:missing-evidence:{evidence_id}",
                        claim_id=claim.claim_id, critical=critical, reason="missing_evidence_reference",
                    ))
                    continue
                if not evidence.is_active(evidence_id):
                    debts.append(EpistemicDebt.create(
                        f"epistemic-debt:{claim.claim_id}:revoked-evidence:{evidence_id}",
                        claim_id=claim.claim_id, critical=critical, reason="revoked_evidence_reference",
                    ))
                elif row.subject_id != claim.claim_id:
                    debts.append(EpistemicDebt.create(
                        f"epistemic-debt:{claim.claim_id}:subject-mismatch:{evidence_id}",
                        claim_id=claim.claim_id, critical=critical, reason="evidence_subject_mismatch",
                    ))
        return tuple(debts)

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
        debts = list(self._lineage_debts(knowledge=knowledge, evidence=evidence))
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

    def dependency_scope(self, claim_id: str, *, knowledge: KnowledgeLedger,
                         evidence: EvidenceLedger) -> TruthDependencyScope:
        target = str(claim_id)
        lineage = knowledge.lineage_claim_ids(target)
        scope_claim_ids = knowledge.truth_scope_claim_ids(target)
        evidence_ids = knowledge.evidence_ids_for_claims(scope_claim_ids)
        snapshot = self.snapshot(knowledge=knowledge, evidence=evidence)
        scope_set = set(scope_claim_ids)
        assessments = tuple(
            TruthScopeAssessment.from_assessment(snapshot.assessment(current))
            for current in scope_claim_ids
        )
        contradictions = tuple(
            row for row in snapshot.contradictions
            if set(row.claim_ids) & scope_set
        )
        debts = tuple(row for row in snapshot.debts if row.claim_id in scope_set)
        return TruthDependencyScope.create(
            target_claim_id=target,
            lineage_claim_ids=lineage,
            scope_claim_ids=scope_claim_ids,
            evidence_ids=evidence_ids,
            knowledge_digest=knowledge.scoped_digest(scope_claim_ids),
            evidence_digest=evidence.scoped_digest(evidence_ids),
            assessments=assessments,
            contradictions=contradictions,
            debts=debts,
        )

    def validate_dependency_scope(self, scope: TruthDependencyScope, *, knowledge: KnowledgeLedger,
                                  evidence: EvidenceLedger) -> bool:
        if not isinstance(scope, TruthDependencyScope):
            return False
        try:
            canonical = self.dependency_scope(
                scope.target_claim_id, knowledge=knowledge, evidence=evidence,
            )
        except (KeyError, TypeError, ValueError):
            return False
        return canonical == scope

    def audit(self, *, knowledge: KnowledgeLedger, evidence: EvidenceLedger) -> tuple[EpistemicDebt, ...]:
        return self.snapshot(knowledge=knowledge, evidence=evidence).debts


__all__ = (
    "PARENT_COMPONENT_ID", "TRUTH_PROTOCOL", "DEPENDENCY_SCOPE_PROTOCOL", "EpistemicDisposition",
    "EpistemicAssessment", "EpistemicDebt", "EpistemicContradiction", "EpistemicSnapshot",
    "TruthScopeAssessment", "TruthDependencyScope", "EpistemicJudge",
)
