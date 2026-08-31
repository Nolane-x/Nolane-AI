from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationSemanticsRegistry
from .epistemic_defeasible_truth import (
    DefeasibleEpistemicJudge,
    DefeasibleTruthScope,
)
from .evidence_dependence_truth import SourceDependenceRegistry
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceLedger
from .knowledge_justification_truth import KnowledgeJustificationRegistry
from .knowledge_temporal_truth import TemporalKnowledgeView
from .knowledge_truth import KnowledgeLedger
from .knowledge_undercutter_truth import JustificationUndercutterRegistry
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.epistemic"
TRUTH_PROTOCOL = "truth-dependence-defeasible-justification-provenance-lineage-temporal-scope-v8"
DEPENDENCE_BINDING_MODE = "dependence-defeasible-justification-provenance-lineage-temporal-v8"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class DependenceTruthScope:
    defeasible_scope: DefeasibleTruthScope
    source_dependence_digest: str
    digest: str
    binding_mode: str = DEPENDENCE_BINDING_MODE

    @classmethod
    def create(
        cls,
        *,
        defeasible_scope: DefeasibleTruthScope,
        source_dependence_digest: str,
    ) -> "DependenceTruthScope":
        if not isinstance(defeasible_scope, DefeasibleTruthScope):
            raise TypeError("dependence scope requires exact v7 defeasible scope")
        source_dependence_digest = _explicit(
            source_dependence_digest,
            "dependence scope source dependence digest",
        )
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": DEPENDENCE_BINDING_MODE,
            "defeasible_scope": defeasible_scope.to_state(),
            "source_dependence_digest": source_dependence_digest,
        }
        return cls(
            defeasible_scope,
            source_dependence_digest,
            canonical_digest(payload),
        )

    @property
    def target_claim_id(self) -> str:
        return self.defeasible_scope.target_claim_id

    @property
    def lineage_claim_ids(self) -> tuple[str, ...]:
        return self.defeasible_scope.lineage_claim_ids

    @property
    def scope_claim_ids(self) -> tuple[str, ...]:
        return self.defeasible_scope.scope_claim_ids

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return self.defeasible_scope.evidence_ids

    @property
    def relation_ids(self) -> tuple[str, ...]:
        return self.defeasible_scope.relation_ids

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.defeasible_scope.source_ids

    @property
    def decision_source_ids(self) -> tuple[str, ...]:
        return self.defeasible_scope.decision_source_ids

    @property
    def temporal_context_digest(self) -> str:
        return self.defeasible_scope.temporal_context_digest

    @property
    def as_of(self) -> str:
        return self.defeasible_scope.as_of

    @property
    def assessments(self):
        return self.defeasible_scope.assessments

    @property
    def justification_statuses(self):
        return self.defeasible_scope.justification_statuses

    @property
    def undercutter_statuses(self):
        return self.defeasible_scope.undercutter_statuses

    @property
    def contradictions(self):
        return self.defeasible_scope.contradictions

    @property
    def debts(self):
        return self.defeasible_scope.debts

    def assessment(self, claim_id: str):
        return self.defeasible_scope.assessment(claim_id)

    def justification_status(self, justification_id: str):
        return self.defeasible_scope.justification_status(justification_id)

    def undercutter_status(self, undercutter_id: str):
        return self.defeasible_scope.undercutter_status(undercutter_id)

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": self.binding_mode,
            "defeasible_scope": self.defeasible_scope.to_state(),
            "source_dependence_digest": self.source_dependence_digest,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DependenceTruthScope":
        _unexpected(
            state,
            {
                "protocol",
                "binding_mode",
                "defeasible_scope",
                "source_dependence_digest",
                "digest",
            },
            "dependence epistemic scope",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported dependence epistemic scope protocol")
        if str(state.get("binding_mode", "")) != DEPENDENCE_BINDING_MODE:
            raise ValueError("unsupported dependence epistemic binding mode")
        row = cls.create(
            defeasible_scope=DefeasibleTruthScope.from_state(state["defeasible_scope"]),
            source_dependence_digest=str(state["source_dependence_digest"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("dependence epistemic scope digest mismatch")
        return row


class DependenceEpistemicJudge:
    """A14 wrapper binding exact A13 truth to explicit common-basis dependence."""

    def relation_aware_temporal_scope(
        self,
        claim_id: str,
        *,
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
    ) -> DependenceTruthScope:
        if not isinstance(source_dependence, SourceDependenceRegistry):
            raise TypeError("dependence epistemic judge requires SourceDependenceRegistry")
        base = DefeasibleEpistemicJudge().relation_aware_temporal_scope(
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
        return DependenceTruthScope.create(
            defeasible_scope=base,
            source_dependence_digest=source_dependence.projection_digest(base.source_ids),
        )

    def validate_scope(
        self,
        scope: DependenceTruthScope,
        *,
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
    ) -> bool:
        if not isinstance(scope, DependenceTruthScope):
            return False
        if scope.binding_mode != DEPENDENCE_BINDING_MODE:
            return False
        if (
            scope.temporal_context_digest != temporal_context.digest
            or scope.as_of != temporal_context.as_of
        ):
            return False
        try:
            canonical = self.relation_aware_temporal_scope(
                scope.target_claim_id,
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
        except (KeyError, TypeError, ValueError):
            return False
        return canonical == scope


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "DEPENDENCE_BINDING_MODE",
    "DependenceTruthScope",
    "DependenceEpistemicJudge",
)
