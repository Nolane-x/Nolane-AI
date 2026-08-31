from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationSemanticsRegistry
from .epistemic_defeasible_truth import (
    DefeasibleEpistemicJudge,
    DefeasibleJustificationStatus,
    UndercutterStatus,
)
from .epistemic_dependence_truth import DependenceEpistemicJudge, DependenceTruthScope
from .epistemic_truth import EpistemicContradiction, EpistemicDebt, TruthScopeAssessment
from .evidence_context_truth import EvidenceContextBindingRegistry
from .evidence_dependence_truth import SourceDependenceRegistry
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceLedger
from .knowledge_context_truth import ClaimContextBindingRegistry, TruthContext
from .knowledge_justification_truth import KnowledgeJustificationRegistry
from .knowledge_temporal_truth import TemporalKnowledgeView
from .knowledge_truth import KnowledgeLedger
from .knowledge_undercutter_truth import JustificationUndercutterRegistry
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.epistemic"
TRUTH_PROTOCOL = (
    "truth-context-dependence-defeasible-justification-provenance-lineage-temporal-scope-v9"
)
CONTEXT_BINDING_MODE = (
    "context-dependence-defeasible-justification-provenance-lineage-temporal-v9"
)


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


class _ContextKnowledgeTemporalView:
    def __init__(
        self,
        base: TemporalKnowledgeView,
        *,
        truth_context: TruthContext,
        claim_context: ClaimContextBindingRegistry,
    ) -> None:
        self._base = base
        self._truth_context = truth_context
        self._claim_context = claim_context

    def state_at(self, claim_id: str, **kwargs):
        state = self._base.state_at(claim_id, **kwargs)
        if state == "active" and not self._claim_context.applies(
            str(claim_id), self._truth_context
        ):
            return "context_mismatch"
        return state

    def projection_digest(self, *args, **kwargs):
        return self._base.projection_digest(*args, **kwargs)


class _ContextEvidenceTemporalView:
    def __init__(
        self,
        base: TemporalEvidenceView,
        *,
        truth_context: TruthContext,
        evidence_context: EvidenceContextBindingRegistry,
    ) -> None:
        self._base = base
        self._truth_context = truth_context
        self._evidence_context = evidence_context

    def state_at(self, evidence_id: str, **kwargs):
        state = self._base.state_at(evidence_id, **kwargs)
        if state == "active" and not self._evidence_context.applies(
            str(evidence_id), self._truth_context
        ):
            return "context_mismatch"
        return state

    def projection_digest(self, *args, **kwargs):
        return self._base.projection_digest(*args, **kwargs)


@dataclass(frozen=True, slots=True)
class ContextTruthScope:
    audit_dependence_scope: DependenceTruthScope
    truth_context: TruthContext
    target_claim_id: str
    lineage_claim_ids: tuple[str, ...]
    scope_claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    decision_source_ids: tuple[str, ...]
    source_provenance_digest: str
    source_dependence_digest: str
    claim_context_digest: str
    evidence_context_digest: str
    assessments: tuple[TruthScopeAssessment, ...]
    justification_statuses: tuple[DefeasibleJustificationStatus, ...]
    undercutter_statuses: tuple[UndercutterStatus, ...]
    contradictions: tuple[EpistemicContradiction, ...]
    debts: tuple[EpistemicDebt, ...]
    context_mismatch_claim_ids: tuple[str, ...]
    context_mismatch_evidence_ids: tuple[str, ...]
    digest: str
    binding_mode: str = CONTEXT_BINDING_MODE

    @classmethod
    def create(
        cls,
        *,
        audit_dependence_scope: DependenceTruthScope,
        truth_context: TruthContext,
        target_claim_id: str,
        lineage_claim_ids: tuple[str, ...],
        scope_claim_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        relation_ids: tuple[str, ...],
        source_ids: tuple[str, ...],
        decision_source_ids: tuple[str, ...],
        source_provenance_digest: str,
        source_dependence_digest: str,
        claim_context_digest: str,
        evidence_context_digest: str,
        assessments: tuple[TruthScopeAssessment, ...],
        justification_statuses: tuple[DefeasibleJustificationStatus, ...],
        undercutter_statuses: tuple[UndercutterStatus, ...],
        contradictions: tuple[EpistemicContradiction, ...],
        debts: tuple[EpistemicDebt, ...],
        context_mismatch_claim_ids: tuple[str, ...] = (),
        context_mismatch_evidence_ids: tuple[str, ...] = (),
    ) -> "ContextTruthScope":
        if not isinstance(audit_dependence_scope, DependenceTruthScope):
            raise TypeError("context scope requires exact v8 dependence audit scope")
        if not isinstance(truth_context, TruthContext):
            raise TypeError("context scope requires exact TruthContext")
        target = _explicit(target_claim_id, "context scope target claim")
        lineage = _ids(tuple(lineage_claim_ids), "context scope lineage claim ids")
        scope = _ids(tuple(scope_claim_ids), "context scope claim ids")
        evidence = _ids(tuple(evidence_ids), "context scope evidence ids")
        relations = _ids(tuple(relation_ids), "context scope relation ids")
        sources = _ids(tuple(source_ids), "context scope source ids")
        decision_sources = _ids(tuple(decision_source_ids), "context decision source ids")
        mismatch_claims = _ids(
            tuple(context_mismatch_claim_ids),
            "context mismatch claim ids",
        )
        mismatch_evidence = _ids(
            tuple(context_mismatch_evidence_ids),
            "context mismatch evidence ids",
        )
        if target not in lineage or not set(lineage).issubset(set(scope)):
            raise ValueError("context scope lineage is inconsistent")
        if not set(decision_sources).issubset(set(sources)):
            raise ValueError("context decision sources must belong to context source scope")
        if not set(mismatch_claims).issubset(set(scope)):
            raise ValueError("context mismatch claims must belong to context scope")
        if not set(mismatch_evidence).issubset(set(evidence)):
            raise ValueError("context mismatch evidence must belong to context scope")

        assessments = tuple(sorted(assessments, key=lambda row: row.claim_id))
        statuses = tuple(sorted(justification_statuses, key=lambda row: row.justification_id))
        attacks = tuple(sorted(undercutter_statuses, key=lambda row: row.undercutter_id))
        contradictions = tuple(sorted(contradictions, key=lambda row: row.contradiction_id))
        debts = tuple(sorted(debts, key=lambda row: row.debt_id))
        if {row.claim_id for row in assessments} != set(scope) or len(assessments) != len(scope):
            raise ValueError("context assessments must cover exactly context scope claims")

        source_provenance_digest = _explicit(
            source_provenance_digest,
            "context scope source provenance digest",
        )
        source_dependence_digest = _explicit(
            source_dependence_digest,
            "context scope source dependence digest",
        )
        claim_context_digest = _explicit(claim_context_digest, "claim context projection digest")
        evidence_context_digest = _explicit(
            evidence_context_digest,
            "evidence context projection digest",
        )
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": CONTEXT_BINDING_MODE,
            "audit_dependence_scope": audit_dependence_scope.to_state(),
            "truth_context": truth_context.to_state(),
            "target_claim_id": target,
            "lineage_claim_ids": list(lineage),
            "scope_claim_ids": list(scope),
            "evidence_ids": list(evidence),
            "relation_ids": list(relations),
            "source_ids": list(sources),
            "decision_source_ids": list(decision_sources),
            "source_provenance_digest": source_provenance_digest,
            "source_dependence_digest": source_dependence_digest,
            "claim_context_digest": claim_context_digest,
            "evidence_context_digest": evidence_context_digest,
            "assessments": [row.to_state() for row in assessments],
            "justification_statuses": [row.to_state() for row in statuses],
            "undercutter_statuses": [row.to_state() for row in attacks],
            "contradictions": [row.to_state() for row in contradictions],
            "debts": [row.to_state() for row in debts],
            "context_mismatch_claim_ids": list(mismatch_claims),
            "context_mismatch_evidence_ids": list(mismatch_evidence),
        }
        return cls(
            audit_dependence_scope,
            truth_context,
            target,
            lineage,
            scope,
            evidence,
            relations,
            sources,
            decision_sources,
            source_provenance_digest,
            source_dependence_digest,
            claim_context_digest,
            evidence_context_digest,
            assessments,
            statuses,
            attacks,
            contradictions,
            debts,
            mismatch_claims,
            mismatch_evidence,
            canonical_digest(payload),
        )

    @property
    def temporal_context_digest(self) -> str:
        return self.audit_dependence_scope.temporal_context_digest

    @property
    def as_of(self) -> str:
        return self.audit_dependence_scope.as_of

    def assessment(self, claim_id: str) -> TruthScopeAssessment:
        for row in self.assessments:
            if row.claim_id == str(claim_id):
                return row
        raise KeyError(f"claim missing from context scope: {claim_id}")

    def justification_status(self, justification_id: str) -> DefeasibleJustificationStatus:
        for row in self.justification_statuses:
            if row.justification_id == str(justification_id):
                return row
        raise KeyError(f"justification missing from context scope: {justification_id}")

    def undercutter_status(self, undercutter_id: str) -> UndercutterStatus:
        for row in self.undercutter_statuses:
            if row.undercutter_id == str(undercutter_id):
                return row
        raise KeyError(f"undercutter missing from context scope: {undercutter_id}")

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": self.binding_mode,
            "audit_dependence_scope": self.audit_dependence_scope.to_state(),
            "truth_context": self.truth_context.to_state(),
            "target_claim_id": self.target_claim_id,
            "lineage_claim_ids": list(self.lineage_claim_ids),
            "scope_claim_ids": list(self.scope_claim_ids),
            "evidence_ids": list(self.evidence_ids),
            "relation_ids": list(self.relation_ids),
            "source_ids": list(self.source_ids),
            "decision_source_ids": list(self.decision_source_ids),
            "source_provenance_digest": self.source_provenance_digest,
            "source_dependence_digest": self.source_dependence_digest,
            "claim_context_digest": self.claim_context_digest,
            "evidence_context_digest": self.evidence_context_digest,
            "assessments": [row.to_state() for row in self.assessments],
            "justification_statuses": [row.to_state() for row in self.justification_statuses],
            "undercutter_statuses": [row.to_state() for row in self.undercutter_statuses],
            "contradictions": [row.to_state() for row in self.contradictions],
            "debts": [row.to_state() for row in self.debts],
            "context_mismatch_claim_ids": list(self.context_mismatch_claim_ids),
            "context_mismatch_evidence_ids": list(self.context_mismatch_evidence_ids),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ContextTruthScope":
        allowed = {
            "protocol",
            "binding_mode",
            "audit_dependence_scope",
            "truth_context",
            "target_claim_id",
            "lineage_claim_ids",
            "scope_claim_ids",
            "evidence_ids",
            "relation_ids",
            "source_ids",
            "decision_source_ids",
            "source_provenance_digest",
            "source_dependence_digest",
            "claim_context_digest",
            "evidence_context_digest",
            "assessments",
            "justification_statuses",
            "undercutter_statuses",
            "contradictions",
            "debts",
            "context_mismatch_claim_ids",
            "context_mismatch_evidence_ids",
            "digest",
        }
        _unexpected(state, allowed, "context epistemic scope")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported context epistemic scope protocol")
        if str(state.get("binding_mode", "")) != CONTEXT_BINDING_MODE:
            raise ValueError("unsupported context epistemic binding mode")
        row = cls.create(
            audit_dependence_scope=DependenceTruthScope.from_state(state["audit_dependence_scope"]),
            truth_context=TruthContext.from_state(state["truth_context"]),
            target_claim_id=str(state["target_claim_id"]),
            lineage_claim_ids=tuple(str(value) for value in state.get("lineage_claim_ids", ())),
            scope_claim_ids=tuple(str(value) for value in state.get("scope_claim_ids", ())),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            relation_ids=tuple(str(value) for value in state.get("relation_ids", ())),
            source_ids=tuple(str(value) for value in state.get("source_ids", ())),
            decision_source_ids=tuple(str(value) for value in state.get("decision_source_ids", ())),
            source_provenance_digest=str(state["source_provenance_digest"]),
            source_dependence_digest=str(state["source_dependence_digest"]),
            claim_context_digest=str(state["claim_context_digest"]),
            evidence_context_digest=str(state["evidence_context_digest"]),
            assessments=tuple(
                TruthScopeAssessment.from_state(value) for value in state.get("assessments", ())
            ),
            justification_statuses=tuple(
                DefeasibleJustificationStatus.from_state(value)
                for value in state.get("justification_statuses", ())
            ),
            undercutter_statuses=tuple(
                UndercutterStatus.from_state(value)
                for value in state.get("undercutter_statuses", ())
            ),
            contradictions=tuple(
                EpistemicContradiction.from_state(value)
                for value in state.get("contradictions", ())
            ),
            debts=tuple(EpistemicDebt.from_state(value) for value in state.get("debts", ())),
            context_mismatch_claim_ids=tuple(
                str(value) for value in state.get("context_mismatch_claim_ids", ())
            ),
            context_mismatch_evidence_ids=tuple(
                str(value) for value in state.get("context_mismatch_evidence_ids", ())
            ),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("context epistemic scope digest mismatch")
        return row


class ContextEpistemicJudge:
    """A15 applicability-qualified truth over the exact accepted A14 audit state."""

    @staticmethod
    def _context_mismatch_evidence_ids(
        evidence_ids: tuple[str, ...],
        *,
        truth_context: TruthContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        claim_context: ClaimContextBindingRegistry,
        evidence_context: EvidenceContextBindingRegistry,
    ) -> tuple[str, ...]:
        mismatches: set[str] = set()
        for evidence_id in evidence_ids:
            if evidence_context.applies(evidence_id, truth_context):
                continue
            try:
                item = evidence.get(evidence_id)
            except KeyError:
                continue
            try:
                knowledge.get(item.subject_id)
            except KeyError:
                subject_applicable = True
            else:
                subject_applicable = claim_context.applies(item.subject_id, truth_context)
            if subject_applicable:
                mismatches.add(evidence_id)
        return tuple(sorted(mismatches))

    def relation_aware_temporal_scope(
        self,
        claim_id: str,
        *,
        truth_context: TruthContext,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
        source_provenance: SourceProvenanceRegistry,
        source_dependence: SourceDependenceRegistry,
        justifications: KnowledgeJustificationRegistry,
        undercutters: JustificationUndercutterRegistry,
        claim_context: ClaimContextBindingRegistry,
        evidence_context: EvidenceContextBindingRegistry,
    ) -> ContextTruthScope:
        if not isinstance(truth_context, TruthContext):
            raise TypeError("context epistemic judge requires TruthContext")
        if not isinstance(claim_context, ClaimContextBindingRegistry):
            raise TypeError("context epistemic judge requires ClaimContextBindingRegistry")
        if not isinstance(evidence_context, EvidenceContextBindingRegistry):
            raise TypeError("context epistemic judge requires EvidenceContextBindingRegistry")
        if not isinstance(source_dependence, SourceDependenceRegistry):
            raise TypeError("context epistemic judge requires SourceDependenceRegistry")

        target = str(claim_id)
        audit = DependenceEpistemicJudge().relation_aware_temporal_scope(
            target,
            temporal_context=temporal_context,
            knowledge=knowledge,
            evidence=evidence,
            relation_semantics=relation_semantics,
            knowledge_temporal=knowledge_temporal,
            evidence_temporal=evidence_temporal,
            source_provenance=source_provenance,
            source_dependence=source_dependence,
            justifications=justifications,
            undercutters=undercutters,
        )

        context_knowledge_temporal = _ContextKnowledgeTemporalView(
            knowledge_temporal,
            truth_context=truth_context,
            claim_context=claim_context,
        )
        context_evidence_temporal = _ContextEvidenceTemporalView(
            evidence_temporal,
            truth_context=truth_context,
            evidence_context=evidence_context,
        )
        qualified = DefeasibleEpistemicJudge().relation_aware_temporal_scope(
            target,
            temporal_context=temporal_context,
            knowledge=knowledge,
            evidence=evidence,
            relation_semantics=relation_semantics,
            knowledge_temporal=context_knowledge_temporal,  # type: ignore[arg-type]
            evidence_temporal=context_evidence_temporal,  # type: ignore[arg-type]
            source_provenance=source_provenance,
            justifications=justifications,
            undercutters=undercutters,
        )

        mismatch_claims = tuple(
            sorted(
                claim
                for claim in qualified.scope_claim_ids
                if not claim_context.applies(claim, truth_context)
            )
        )
        mismatch_evidence = self._context_mismatch_evidence_ids(
            qualified.evidence_ids,
            truth_context=truth_context,
            knowledge=knowledge,
            evidence=evidence,
            claim_context=claim_context,
            evidence_context=evidence_context,
        )
        return ContextTruthScope.create(
            audit_dependence_scope=audit,
            truth_context=truth_context,
            target_claim_id=target,
            lineage_claim_ids=qualified.lineage_claim_ids,
            scope_claim_ids=qualified.scope_claim_ids,
            evidence_ids=qualified.evidence_ids,
            relation_ids=qualified.relation_ids,
            source_ids=qualified.source_ids,
            decision_source_ids=qualified.decision_source_ids,
            source_provenance_digest=source_provenance.projection_digest(qualified.source_ids),
            source_dependence_digest=source_dependence.projection_digest(qualified.source_ids),
            claim_context_digest=claim_context.projection_digest(qualified.scope_claim_ids),
            evidence_context_digest=evidence_context.projection_digest(qualified.evidence_ids),
            assessments=qualified.assessments,
            justification_statuses=qualified.justification_statuses,
            undercutter_statuses=qualified.undercutter_statuses,
            contradictions=qualified.contradictions,
            debts=qualified.debts,
            context_mismatch_claim_ids=mismatch_claims,
            context_mismatch_evidence_ids=mismatch_evidence,
        )

    def validate_scope(
        self,
        scope: ContextTruthScope,
        *,
        truth_context: TruthContext,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
        source_provenance: SourceProvenanceRegistry,
        source_dependence: SourceDependenceRegistry,
        justifications: KnowledgeJustificationRegistry,
        undercutters: JustificationUndercutterRegistry,
        claim_context: ClaimContextBindingRegistry,
        evidence_context: EvidenceContextBindingRegistry,
    ) -> bool:
        if not isinstance(scope, ContextTruthScope):
            return False
        if scope.binding_mode != CONTEXT_BINDING_MODE:
            return False
        if scope.truth_context != truth_context:
            return False
        if (
            scope.temporal_context_digest != temporal_context.digest
            or scope.as_of != temporal_context.as_of
        ):
            return False
        try:
            canonical = self.relation_aware_temporal_scope(
                scope.target_claim_id,
                truth_context=truth_context,
                temporal_context=temporal_context,
                knowledge=knowledge,
                evidence=evidence,
                relation_semantics=relation_semantics,
                knowledge_temporal=knowledge_temporal,
                evidence_temporal=evidence_temporal,
                source_provenance=source_provenance,
                source_dependence=source_dependence,
                justifications=justifications,
                undercutters=undercutters,
                claim_context=claim_context,
                evidence_context=evidence_context,
            )
        except (KeyError, TypeError, ValueError):
            return False
        return canonical == scope


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "CONTEXT_BINDING_MODE",
    "ContextTruthScope",
    "ContextEpistemicJudge",
)
