from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationSemanticsRegistry
from .epistemic_truth import (
    EpistemicDebt,
    EpistemicDisposition,
    EpistemicJudge,
    EpistemicSnapshot,
    TruthDependencyScope,
    TruthRelationAwareScope,
)
from .evidence_truth import EvidenceLedger
from .knowledge_truth import KnowledgeLedger, KnowledgeRisk
from .verification_truth import (
    RELATION_SCOPED_BINDING_MODE,
    SCOPED_BINDING_MODE,
    TruthVerificationLedger,
)

PARENT_COMPONENT_ID = "external.assurance"
TRUTH_PROTOCOL = "truth-assurance-v1"

_REQUIREMENTS = {
    KnowledgeRisk.LOW: (1, 1), KnowledgeRisk.STANDARD: (1, 1),
    KnowledgeRisk.HIGH: (2, 2), KnowledgeRisk.CRITICAL: (3, 3),
}

_RELATION_AMBIGUITY_REASON = "relation_semantics_unspecified_for_multiple_values"


def _unique_ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows):
        raise ValueError(f"{field} must be explicit")
    if len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be unique")
    return rows


def _explicit_optional(value: str | None) -> str:
    return "" if value is None else str(value).strip()


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
    binding_mode: str = "global-v1"
    scope_digest: str = ""
    verification_scope_digest: str = ""

    @classmethod
    def create(cls, *, claim_id: str, risk: KnowledgeRisk,
               verification_receipt_ids: tuple[str, ...], epistemic_debt_ids: tuple[str, ...],
               closed: bool, reasons: tuple[str, ...], knowledge_digest: str | None = None,
               evidence_digest: str | None = None, epistemic_digest: str | None = None,
               verification_digest: str | None = None, binding_mode: str | None = None,
               scope_digest: str | None = None,
               verification_scope_digest: str | None = None) -> "TruthClosureCertificate":
        claim_id = str(claim_id).strip()
        if not claim_id:
            raise ValueError("truth closure claim identity must be explicit")
        risk = KnowledgeRisk(risk)
        verification_receipt_ids = _unique_ids(tuple(verification_receipt_ids), "verification receipt ids")
        epistemic_debt_ids = _unique_ids(tuple(epistemic_debt_ids), "epistemic debt ids")
        reasons = tuple(sorted(str(value).strip() for value in reasons))
        if any(not value for value in reasons):
            raise ValueError("closure reasons must be explicit")
        if len(set(reasons)) != len(reasons):
            raise ValueError("closure reasons must be unique")
        closed = bool(closed)
        if closed != (not reasons):
            raise ValueError("closure decision and reasons are inconsistent")

        mode = _explicit_optional(binding_mode)
        scope = _explicit_optional(scope_digest)
        verification_scope = _explicit_optional(verification_scope_digest)
        knowledge = _explicit_optional(knowledge_digest)
        evidence = _explicit_optional(evidence_digest)
        epistemic = _explicit_optional(epistemic_digest)
        verification = _explicit_optional(verification_digest)

        wants_scoped = bool(mode or scope or verification_scope)
        if wants_scoped:
            if mode not in {SCOPED_BINDING_MODE, RELATION_SCOPED_BINDING_MODE}:
                raise ValueError("unsupported truth closure binding mode")
            if not scope or not verification_scope:
                raise ValueError("scoped truth closure state bindings must be explicit")
            if any((knowledge, evidence, epistemic, verification)):
                raise ValueError("scoped truth closure cannot mix global state bindings")
            payload = {
                "protocol": TRUTH_PROTOCOL,
                "binding_mode": mode,
                "claim_id": claim_id,
                "risk": risk.value,
                "scope_digest": scope,
                "verification_scope_digest": verification_scope,
                "verification_receipt_ids": list(verification_receipt_ids),
                "epistemic_debt_ids": list(epistemic_debt_ids),
                "closed": closed,
                "reasons": list(reasons),
            }
            digest = canonical_digest(payload)
            return cls(
                f"truth-closure-{digest[:24]}", claim_id, risk,
                "", "", "", "", verification_receipt_ids, epistemic_debt_ids,
                closed, reasons, digest, mode, scope, verification_scope,
            )

        if not all((knowledge, evidence, epistemic, verification)):
            raise ValueError("truth closure identity and state bindings must be explicit")
        payload = {
            "protocol": TRUTH_PROTOCOL, "claim_id": claim_id, "risk": risk.value,
            "knowledge_digest": knowledge, "evidence_digest": evidence,
            "epistemic_digest": epistemic, "verification_digest": verification,
            "verification_receipt_ids": list(verification_receipt_ids),
            "epistemic_debt_ids": list(epistemic_debt_ids), "closed": closed, "reasons": list(reasons),
        }
        digest = canonical_digest(payload)
        return cls(
            f"truth-closure-{digest[:24]}", claim_id, risk, knowledge, evidence,
            epistemic, verification, verification_receipt_ids, epistemic_debt_ids,
            closed, reasons, digest,
        )

    @property
    def is_dependency_scoped(self) -> bool:
        return self.binding_mode == SCOPED_BINDING_MODE

    @property
    def is_relation_scoped(self) -> bool:
        return self.binding_mode == RELATION_SCOPED_BINDING_MODE

    @property
    def is_scoped(self) -> bool:
        return self.is_dependency_scoped or self.is_relation_scoped

    def payload(self) -> dict[str, Any]:
        if self.is_scoped:
            return {
                "protocol": TRUTH_PROTOCOL,
                "binding_mode": self.binding_mode,
                "claim_id": self.claim_id,
                "risk": self.risk.value,
                "scope_digest": self.scope_digest,
                "verification_scope_digest": self.verification_scope_digest,
                "verification_receipt_ids": list(self.verification_receipt_ids),
                "epistemic_debt_ids": list(self.epistemic_debt_ids),
                "closed": self.closed,
                "reasons": list(self.reasons),
            }
        return {
            "protocol": TRUTH_PROTOCOL, "claim_id": self.claim_id, "risk": self.risk.value,
            "knowledge_digest": self.knowledge_digest, "evidence_digest": self.evidence_digest,
            "epistemic_digest": self.epistemic_digest, "verification_digest": self.verification_digest,
            "verification_receipt_ids": list(self.verification_receipt_ids),
            "epistemic_debt_ids": list(self.epistemic_debt_ids), "closed": self.closed,
            "reasons": list(self.reasons),
        }

    def to_state(self) -> dict[str, Any]:
        return {"certificate_id": self.certificate_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthClosureCertificate":
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported truth assurance protocol")
        has_scoped_keys = any(key in state for key in ("binding_mode", "scope_digest", "verification_scope_digest"))
        if has_scoped_keys:
            mode = str(state.get("binding_mode", ""))
            if mode not in {SCOPED_BINDING_MODE, RELATION_SCOPED_BINDING_MODE}:
                raise ValueError("unsupported truth closure binding mode")
            forbidden = ("knowledge_digest", "evidence_digest", "epistemic_digest", "verification_digest")
            if any(key in state for key in forbidden):
                raise ValueError("scoped truth closure state cannot contain global bindings")
            row = cls.create(
                claim_id=str(state["claim_id"]), risk=KnowledgeRisk(str(state["risk"])),
                binding_mode=mode,
                scope_digest=str(state.get("scope_digest", "")),
                verification_scope_digest=str(state.get("verification_scope_digest", "")),
                verification_receipt_ids=tuple(str(x) for x in state.get("verification_receipt_ids", ())),
                epistemic_debt_ids=tuple(str(x) for x in state.get("epistemic_debt_ids", ())),
                closed=bool(state["closed"]), reasons=tuple(str(x) for x in state.get("reasons", ())),
            )
        else:
            row = cls.create(
                claim_id=str(state["claim_id"]), risk=KnowledgeRisk(str(state["risk"])),
                knowledge_digest=str(state["knowledge_digest"]), evidence_digest=str(state["evidence_digest"]),
                epistemic_digest=str(state["epistemic_digest"]),
                verification_digest=str(state["verification_digest"]),
                verification_receipt_ids=tuple(str(x) for x in state.get("verification_receipt_ids", ())),
                epistemic_debt_ids=tuple(str(x) for x in state.get("epistemic_debt_ids", ())),
                closed=bool(state["closed"]), reasons=tuple(str(x) for x in state.get("reasons", ())),
            )
        if str(state["certificate_id"]) != row.certificate_id or str(state["digest"]) != row.digest:
            raise ValueError("truth closure certificate digest mismatch")
        return row


class TruthAssuranceGate:
    """Truth closure under canonical ``external.assurance``.

    V1 is whole-ledger compatibility, A8 v2 is dependency-scoped, and A10 v3 is relation-aware.
    Mode selection and validation are exact: a newer history can never reinterpret or downgrade an
    older certificate. Certificates remain decision receipts and require live canonical revalidation.
    """

    @staticmethod
    def _coverage_reasons(*, risk: KnowledgeRisk, coverage) -> list[str]:
        reasons: list[str] = list(coverage.issues)
        if coverage.negative_receipt_ids:
            reasons.append("negative_verification")
        required_sources, required_channels = _REQUIREMENTS[risk]
        if coverage.independent_source_count < required_sources:
            reasons.append("insufficient_independent_verification")
        if coverage.channel_count < required_channels:
            reasons.append("insufficient_verification_channel_diversity")
        return reasons

    @classmethod
    def _strict_verification(cls, *, claim_id: str, risk: KnowledgeRisk, knowledge_digest: str,
                             epistemic_digest: str, verification: TruthVerificationLedger,
                             evidence: EvidenceLedger):
        coverage = verification.coverage(
            claim_id, knowledge_digest=knowledge_digest, epistemic_digest=epistemic_digest, evidence=evidence,
        )
        return coverage.receipts, cls._coverage_reasons(risk=risk, coverage=coverage)

    @classmethod
    def _strict_scoped_verification(cls, *, claim_id: str, risk: KnowledgeRisk,
                                    scope: TruthDependencyScope, verification: TruthVerificationLedger,
                                    evidence: EvidenceLedger):
        coverage = verification.coverage_scoped(
            claim_id, scope_digest=scope.digest, evidence=evidence,
        )
        return coverage.receipts, cls._coverage_reasons(risk=risk, coverage=coverage)

    @classmethod
    def _strict_relation_scoped_verification(cls, *, claim_id: str, risk: KnowledgeRisk,
                                             scope: TruthRelationAwareScope,
                                             verification: TruthVerificationLedger,
                                             evidence: EvidenceLedger):
        coverage = verification.coverage_relation_scoped(
            claim_id, scope_digest=scope.digest, evidence=evidence,
        )
        return coverage.receipts, cls._coverage_reasons(risk=risk, coverage=coverage)

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
        """Strict v1 whole-ledger compatibility issuance."""
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

    def _close_scoped(self, *, claim_id: str, knowledge: KnowledgeLedger, evidence: EvidenceLedger,
                      verification: TruthVerificationLedger, scope: TruthDependencyScope) -> TruthClosureCertificate:
        if not EpistemicJudge().validate_dependency_scope(scope, knowledge=knowledge, evidence=evidence):
            raise ValueError("noncanonical dependency scope")
        claim = knowledge.get(claim_id)
        assessment = scope.assessment(claim.claim_id)
        rows, reasons = self._strict_scoped_verification(
            claim_id=claim.claim_id, risk=claim.risk, scope=scope,
            verification=verification, evidence=evidence,
        )
        lineage = set(scope.lineage_claim_ids)
        target_conflicted = any(claim.claim_id in row.claim_ids for row in scope.contradictions)
        lineage_conflicted = any(
            bool((set(row.claim_ids) & lineage) - {claim.claim_id})
            for row in scope.contradictions
        )
        lineage_debts = tuple(row for row in scope.debts if row.claim_id in lineage)
        target_debts = tuple(row for row in lineage_debts if row.claim_id == claim.claim_id)
        ancestor_debts = tuple(row for row in lineage_debts if row.claim_id != claim.claim_id)

        if assessment.disposition is not EpistemicDisposition.SUPPORTED:
            reasons.insert(0, "epistemic_claim_not_supported")
        if target_conflicted:
            reasons.insert(0, "epistemic_claim_conflicted")
        if lineage_conflicted:
            reasons.insert(0, "epistemic_lineage_conflicted")
        if any(row.critical for row in target_debts):
            reasons.insert(0, "critical_epistemic_debt")
        if any(row.critical for row in ancestor_debts):
            reasons.insert(0, "critical_epistemic_lineage_debt")
        reasons = list(dict.fromkeys(reasons))
        return TruthClosureCertificate.create(
            claim_id=claim.claim_id, risk=claim.risk,
            binding_mode=SCOPED_BINDING_MODE,
            scope_digest=scope.digest,
            verification_scope_digest=verification.scoped_digest(claim.claim_id, scope_digest=scope.digest),
            verification_receipt_ids=tuple(row.receipt_id for row in rows),
            epistemic_debt_ids=tuple(sorted(row.debt_id for row in lineage_debts)),
            closed=not reasons, reasons=tuple(reasons),
        )

    def _close_relation_aware(self, *, claim_id: str, knowledge: KnowledgeLedger,
                              evidence: EvidenceLedger, verification: TruthVerificationLedger,
                              relation_semantics: RelationSemanticsRegistry,
                              scope: TruthRelationAwareScope) -> TruthClosureCertificate:
        judge = EpistemicJudge()
        if not judge.validate_relation_aware_scope(
            scope, knowledge=knowledge, evidence=evidence, relation_semantics=relation_semantics,
        ):
            raise ValueError("noncanonical relation-aware dependency scope")
        claim = knowledge.get(claim_id)
        assessment = scope.assessment(claim.claim_id)
        rows, reasons = self._strict_relation_scoped_verification(
            claim_id=claim.claim_id, risk=claim.risk, scope=scope,
            verification=verification, evidence=evidence,
        )
        lineage = set(scope.lineage_claim_ids)
        target_conflicted = any(claim.claim_id in row.claim_ids for row in scope.contradictions)
        lineage_conflicted = any(
            bool((set(row.claim_ids) & lineage) - {claim.claim_id})
            for row in scope.contradictions
        )
        lineage_debts = tuple(row for row in scope.debts if row.claim_id in lineage)
        target_debts = tuple(row for row in lineage_debts if row.claim_id == claim.claim_id)
        ancestor_debts = tuple(row for row in lineage_debts if row.claim_id != claim.claim_id)
        target_relation_ambiguity = any(
            row.reason == _RELATION_AMBIGUITY_REASON for row in target_debts
        )
        lineage_relation_ambiguity = any(
            row.reason == _RELATION_AMBIGUITY_REASON for row in ancestor_debts
        )

        if assessment.disposition is not EpistemicDisposition.SUPPORTED:
            reasons.insert(0, "epistemic_claim_not_supported")
        if target_conflicted:
            reasons.insert(0, "epistemic_claim_conflicted")
        if lineage_conflicted:
            reasons.insert(0, "epistemic_lineage_conflicted")
        if target_relation_ambiguity:
            reasons.insert(0, "relation_semantics_ambiguous")
        if lineage_relation_ambiguity:
            reasons.insert(0, "relation_semantics_lineage_ambiguous")
        if any(row.critical for row in target_debts):
            reasons.insert(0, "critical_epistemic_debt")
        if any(row.critical for row in ancestor_debts):
            reasons.insert(0, "critical_epistemic_lineage_debt")
        reasons = list(dict.fromkeys(reasons))
        return TruthClosureCertificate.create(
            claim_id=claim.claim_id,
            risk=claim.risk,
            binding_mode=RELATION_SCOPED_BINDING_MODE,
            scope_digest=scope.digest,
            verification_scope_digest=verification.relation_scoped_digest(
                claim.claim_id, scope_digest=scope.digest,
            ),
            verification_receipt_ids=tuple(row.receipt_id for row in rows),
            epistemic_debt_ids=tuple(sorted(row.debt_id for row in lineage_debts)),
            closed=not reasons,
            reasons=tuple(reasons),
        )

    def close_live(self, *, claim_id: str, knowledge: KnowledgeLedger, evidence: EvidenceLedger,
                   verification: TruthVerificationLedger,
                   relation_semantics: RelationSemanticsRegistry | None = None) -> TruthClosureCertificate:
        """Issue in the newest exact binding mode already established for the target."""
        claim_id = str(claim_id)
        judge = EpistemicJudge()
        receipts = verification.receipts(claim_id)
        has_relation_scoped_history = any(row.is_relation_scoped for row in receipts)
        if has_relation_scoped_history:
            if not isinstance(relation_semantics, RelationSemanticsRegistry):
                raise ValueError("relation-aware closure requires canonical relation semantics registry")
            scope_v3 = judge.relation_aware_dependency_scope(
                claim_id, knowledge=knowledge, evidence=evidence, relation_semantics=relation_semantics,
            )
            return self._close_relation_aware(
                claim_id=claim_id, knowledge=knowledge, evidence=evidence,
                verification=verification, relation_semantics=relation_semantics, scope=scope_v3,
            )

        has_dependency_scoped_history = any(row.is_dependency_scoped for row in receipts)
        if has_dependency_scoped_history:
            scope_v2 = judge.dependency_scope(claim_id, knowledge=knowledge, evidence=evidence)
            return self._close_scoped(
                claim_id=claim_id, knowledge=knowledge, evidence=evidence,
                verification=verification, scope=scope_v2,
            )

        snapshot = judge.snapshot(knowledge=knowledge, evidence=evidence)
        return self.close_snapshot(
            claim_id=claim_id, knowledge=knowledge, evidence=evidence,
            epistemic=snapshot, verification=verification,
        )

    def validate_certificate(self, certificate: TruthClosureCertificate, *, knowledge: KnowledgeLedger,
                             evidence: EvidenceLedger, verification: TruthVerificationLedger,
                             relation_semantics: RelationSemanticsRegistry | None = None) -> bool:
        """Re-derive a certificate in its exact historical binding mode from live authority state."""
        if not isinstance(certificate, TruthClosureCertificate) or not certificate.closed:
            return False
        judge = EpistemicJudge()
        try:
            if certificate.is_relation_scoped:
                if not isinstance(relation_semantics, RelationSemanticsRegistry):
                    return False
                scope_v3 = judge.relation_aware_dependency_scope(
                    certificate.claim_id,
                    knowledge=knowledge,
                    evidence=evidence,
                    relation_semantics=relation_semantics,
                )
                canonical = self._close_relation_aware(
                    claim_id=certificate.claim_id,
                    knowledge=knowledge,
                    evidence=evidence,
                    verification=verification,
                    relation_semantics=relation_semantics,
                    scope=scope_v3,
                )
            elif certificate.is_dependency_scoped:
                scope_v2 = judge.dependency_scope(
                    certificate.claim_id, knowledge=knowledge, evidence=evidence,
                )
                canonical = self._close_scoped(
                    claim_id=certificate.claim_id, knowledge=knowledge, evidence=evidence,
                    verification=verification, scope=scope_v2,
                )
            else:
                snapshot = judge.snapshot(knowledge=knowledge, evidence=evidence)
                canonical = self.close_snapshot(
                    claim_id=certificate.claim_id, knowledge=knowledge, evidence=evidence,
                    epistemic=snapshot, verification=verification,
                )
        except (KeyError, TypeError, ValueError):
            return False
        return bool(canonical.closed and canonical == certificate)


__all__ = (
    "PARENT_COMPONENT_ID", "TRUTH_PROTOCOL", "TruthClosureCertificate", "TruthAssuranceGate",
)
