from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationSemanticsRegistry
from .epistemic_defeasible_truth import (
    DEFEASIBLE_BINDING_MODE,
    DefeasibleEpistemicJudge,
    DefeasibleTruthScope,
)
from .epistemic_truth import EpistemicDisposition
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceLedger
from .knowledge_justification_truth import KnowledgeJustificationRegistry
from .knowledge_temporal_truth import TemporalKnowledgeView
from .knowledge_truth import KnowledgeLedger, KnowledgeRisk
from .knowledge_undercutter_truth import JustificationUndercutterRegistry
from .temporal_truth import TemporalContext
from .verification_defeasible_truth import DefeasibleTruthVerificationLedger


PARENT_COMPONENT_ID = "external.assurance"
TRUTH_PROTOCOL = "truth-assurance-defeasible-justification-provenance-lineage-temporal-v7"

_REQUIREMENTS = {
    KnowledgeRisk.LOW: (1, 1),
    KnowledgeRisk.STANDARD: (1, 1),
    KnowledgeRisk.HIGH: (2, 2),
    KnowledgeRisk.CRITICAL: (3, 3),
}
_RELATION_AMBIGUITY_REASON = "relation_semantics_unspecified_for_multiple_values"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be explicit and unique")
    return rows


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class DefeasibleTruthClosureCertificate:
    certificate_id: str
    claim_id: str
    risk: KnowledgeRisk
    scope_digest: str
    verification_scope_digest: str
    temporal_context_digest: str
    as_of: str
    verification_receipt_ids: tuple[str, ...]
    epistemic_debt_ids: tuple[str, ...]
    closed: bool
    reasons: tuple[str, ...]
    digest: str
    binding_mode: str = DEFEASIBLE_BINDING_MODE

    @classmethod
    def create(
        cls,
        *,
        claim_id: str,
        risk: KnowledgeRisk,
        scope_digest: str,
        verification_scope_digest: str,
        temporal_context_digest: str,
        as_of: str,
        verification_receipt_ids: tuple[str, ...],
        epistemic_debt_ids: tuple[str, ...],
        closed: bool,
        reasons: tuple[str, ...],
    ) -> "DefeasibleTruthClosureCertificate":
        claim_id = _explicit(claim_id, "defeasible closure claim id")
        scope_digest = _explicit(scope_digest, "defeasible closure scope digest")
        verification_scope_digest = _explicit(
            verification_scope_digest,
            "defeasible verification projection digest",
        )
        temporal_context_digest = _explicit(
            temporal_context_digest,
            "defeasible closure temporal context digest",
        )
        context = TemporalContext.create(as_of=as_of)
        if context.digest != temporal_context_digest:
            raise ValueError("defeasible closure temporal context digest mismatch")
        verification_receipt_ids = _ids(
            tuple(verification_receipt_ids),
            "defeasible verification receipt ids",
        )
        epistemic_debt_ids = _ids(
            tuple(epistemic_debt_ids),
            "defeasible epistemic debt ids",
        )
        reasons = tuple(sorted(str(value).strip() for value in reasons))
        if any(not value for value in reasons) or len(set(reasons)) != len(reasons):
            raise ValueError("defeasible closure reasons must be explicit and unique")
        closed = bool(closed)
        if closed != (not reasons):
            raise ValueError("defeasible closure decision and reasons are inconsistent")
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": DEFEASIBLE_BINDING_MODE,
            "claim_id": claim_id,
            "risk": KnowledgeRisk(risk).value,
            "scope_digest": scope_digest,
            "verification_scope_digest": verification_scope_digest,
            "temporal_context_digest": temporal_context_digest,
            "as_of": context.as_of,
            "verification_receipt_ids": list(verification_receipt_ids),
            "epistemic_debt_ids": list(epistemic_debt_ids),
            "closed": closed,
            "reasons": list(reasons),
        }
        digest = canonical_digest(payload)
        return cls(
            f"truth-defeasible-closure-{digest[:24]}",
            claim_id,
            KnowledgeRisk(risk),
            scope_digest,
            verification_scope_digest,
            temporal_context_digest,
            context.as_of,
            verification_receipt_ids,
            epistemic_debt_ids,
            closed,
            reasons,
            digest,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": self.binding_mode,
            "claim_id": self.claim_id,
            "risk": self.risk.value,
            "scope_digest": self.scope_digest,
            "verification_scope_digest": self.verification_scope_digest,
            "temporal_context_digest": self.temporal_context_digest,
            "as_of": self.as_of,
            "verification_receipt_ids": list(self.verification_receipt_ids),
            "epistemic_debt_ids": list(self.epistemic_debt_ids),
            "closed": self.closed,
            "reasons": list(self.reasons),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DefeasibleTruthClosureCertificate":
        _unexpected(
            state,
            {
                "certificate_id",
                "protocol",
                "binding_mode",
                "claim_id",
                "risk",
                "scope_digest",
                "verification_scope_digest",
                "temporal_context_digest",
                "as_of",
                "verification_receipt_ids",
                "epistemic_debt_ids",
                "closed",
                "reasons",
                "digest",
            },
            "defeasible assurance certificate",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported defeasible assurance protocol")
        if str(state.get("binding_mode", "")) != DEFEASIBLE_BINDING_MODE:
            raise ValueError("unsupported defeasible assurance binding mode")
        row = cls.create(
            claim_id=str(state["claim_id"]),
            risk=KnowledgeRisk(str(state["risk"])),
            scope_digest=str(state["scope_digest"]),
            verification_scope_digest=str(state["verification_scope_digest"]),
            temporal_context_digest=str(state["temporal_context_digest"]),
            as_of=str(state["as_of"]),
            verification_receipt_ids=tuple(
                str(value) for value in state.get("verification_receipt_ids", ())
            ),
            epistemic_debt_ids=tuple(
                str(value) for value in state.get("epistemic_debt_ids", ())
            ),
            closed=bool(state["closed"]),
            reasons=tuple(str(value) for value in state.get("reasons", ())),
        )
        if (
            str(state["certificate_id"]) != row.certificate_id
            or str(state["digest"]) != row.digest
        ):
            raise ValueError("defeasible assurance certificate digest mismatch")
        return row


class DefeasibleTruthAssuranceGate:
    """Risk-sensitive A13 closure over complete live v7 defeasible truth state."""

    @staticmethod
    def _supporting_lineage_claim_ids(scope: DefeasibleTruthScope) -> frozenset[str]:
        by_claim: dict[str, list[Any]] = {}
        for status in scope.justification_statuses:
            by_claim.setdefault(status.claim_id, []).append(status)

        seen: set[str] = set()

        def visit(claim_id: str) -> None:
            if claim_id in seen:
                return
            seen.add(claim_id)
            for status in by_claim.get(claim_id, ()):
                if status.status != "supported":
                    continue
                for parent_id in status.parent_claim_ids:
                    visit(parent_id)

        visit(scope.target_claim_id)
        return frozenset(seen)

    @staticmethod
    def _relation_target_conflict(scope: DefeasibleTruthScope, claim_id: str) -> bool:
        return any(str(claim_id) in row.claim_ids for row in scope.contradictions)

    @classmethod
    def _relation_lineage_conflict(cls, scope: DefeasibleTruthScope, claim_id: str) -> bool:
        lineage = set(cls._supporting_lineage_claim_ids(scope))
        lineage.discard(str(claim_id))
        return any(set(row.claim_ids) & lineage for row in scope.contradictions)

    def close(
        self,
        *,
        claim_id: str,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
        source_provenance: SourceProvenanceRegistry,
        justifications: KnowledgeJustificationRegistry,
        undercutters: JustificationUndercutterRegistry,
        verification: DefeasibleTruthVerificationLedger,
    ) -> DefeasibleTruthClosureCertificate:
        if not isinstance(justifications, KnowledgeJustificationRegistry):
            raise TypeError("defeasible assurance requires KnowledgeJustificationRegistry")
        if not isinstance(undercutters, JustificationUndercutterRegistry):
            raise TypeError("defeasible assurance requires JustificationUndercutterRegistry")
        if not isinstance(verification, DefeasibleTruthVerificationLedger):
            raise TypeError("defeasible assurance requires v7 verification ledger")

        scope = DefeasibleEpistemicJudge().relation_aware_temporal_scope(
            str(claim_id),
            temporal_context=temporal_context,
            knowledge=knowledge,
            evidence=evidence,
            relation_semantics=relation_semantics,
            knowledge_temporal=knowledge_temporal,
            evidence_temporal=evidence_temporal,
            source_provenance=source_provenance,
            justifications=justifications,
            undercutters=undercutters,
        )
        claim = knowledge.get(str(claim_id))
        target = scope.assessment(claim.claim_id)
        coverage = verification.coverage(
            claim.claim_id,
            scope=scope,
            temporal_context=temporal_context,
            evidence=evidence,
            evidence_temporal=evidence_temporal,
            source_provenance=source_provenance,
        )
        supporting_lineage = set(self._supporting_lineage_claim_ids(scope))

        reasons: set[str] = set()
        if target.disposition is not EpistemicDisposition.SUPPORTED:
            reasons.add("epistemic_claim_not_supported")
        if target.disposition is EpistemicDisposition.CONTRADICTED:
            reasons.add("epistemic_claim_conflicted")
        if self._relation_target_conflict(scope, claim.claim_id):
            reasons.add("epistemic_claim_conflicted")
        if self._relation_lineage_conflict(scope, claim.claim_id):
            reasons.add("epistemic_lineage_conflicted")

        for debt in scope.debts:
            if debt.reason == _RELATION_AMBIGUITY_REASON:
                if debt.claim_id == claim.claim_id:
                    reasons.add("relation_semantics_ambiguous")
                elif debt.claim_id in supporting_lineage:
                    reasons.add("relation_semantics_lineage_ambiguous")
            if debt.critical and debt.claim_id in supporting_lineage:
                reasons.add("critical_epistemic_debt")

        for lineage_claim_id in sorted(supporting_lineage):
            if lineage_claim_id == claim.claim_id:
                continue
            disposition = scope.assessment(lineage_claim_id).disposition
            if disposition is EpistemicDisposition.CONTRADICTED:
                reasons.add("epistemic_lineage_conflicted")
            if disposition is not EpistemicDisposition.SUPPORTED:
                reasons.add("epistemic_lineage_not_supported")

        if any(source_provenance.current(source_id) is None for source_id in scope.source_ids):
            reasons.add("source_provenance_incomplete")
        if coverage.invalid_receipt_ids or coverage.issues:
            reasons.add("verification_provenance_invalid")
        if coverage.negative_receipt_ids:
            reasons.add("negative_verification")

        required_sources, required_channels = _REQUIREMENTS[claim.risk]
        if coverage.independent_source_count < required_sources:
            reasons.add("insufficient_independent_verification")
        if coverage.channel_count < required_channels:
            reasons.add("insufficient_verification_channel_diversity")

        valid_ids = set(coverage.valid_receipt_ids)
        passing_ids = tuple(
            sorted(
                row.receipt_id
                for row in coverage.receipts
                if row.receipt_id in valid_ids and row.passed
            )
        )
        verification_scope_digest = verification.scoped_digest(
            claim.claim_id,
            scope=scope,
            temporal_context=temporal_context,
        )
        return DefeasibleTruthClosureCertificate.create(
            claim_id=claim.claim_id,
            risk=claim.risk,
            scope_digest=scope.digest,
            verification_scope_digest=verification_scope_digest,
            temporal_context_digest=temporal_context.digest,
            as_of=temporal_context.as_of,
            verification_receipt_ids=passing_ids,
            epistemic_debt_ids=tuple(row.debt_id for row in scope.debts),
            closed=not reasons,
            reasons=tuple(reasons),
        )

    def validate_certificate(
        self,
        certificate: DefeasibleTruthClosureCertificate,
        *,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
        source_provenance: SourceProvenanceRegistry,
        justifications: KnowledgeJustificationRegistry,
        undercutters: JustificationUndercutterRegistry,
        verification: DefeasibleTruthVerificationLedger,
    ) -> bool:
        if not isinstance(certificate, DefeasibleTruthClosureCertificate):
            return False
        if certificate.binding_mode != DEFEASIBLE_BINDING_MODE:
            return False
        if (
            certificate.temporal_context_digest != temporal_context.digest
            or certificate.as_of != temporal_context.as_of
        ):
            return False
        try:
            canonical = self.close(
                claim_id=certificate.claim_id,
                temporal_context=temporal_context,
                knowledge=knowledge,
                evidence=evidence,
                relation_semantics=relation_semantics,
                knowledge_temporal=knowledge_temporal,
                evidence_temporal=evidence_temporal,
                source_provenance=source_provenance,
                justifications=justifications,
                undercutters=undercutters,
                verification=verification,
            )
        except (KeyError, TypeError, ValueError):
            return False
        return canonical == certificate


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "DefeasibleTruthClosureCertificate",
    "DefeasibleTruthAssuranceGate",
)
