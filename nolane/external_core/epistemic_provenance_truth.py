from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationSemanticsRegistry
from .epistemic_temporal_truth import TemporalEpistemicJudge
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceLedger
from .knowledge_temporal_truth import TemporalKnowledgeView
from .knowledge_truth import KnowledgeLedger
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.epistemic"
TRUTH_PROTOCOL = "truth-provenance-lineage-temporal-scope-v5"
PROVENANCE_BINDING_MODE = "provenance-lineage-temporal-v5"


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
class ProvenanceTruthScope:
    target_claim_id: str
    temporal_scope_digest: str
    temporal_context_digest: str
    as_of: str
    source_ids: tuple[str, ...]
    source_provenance_digest: str
    digest: str
    binding_mode: str = PROVENANCE_BINDING_MODE

    @classmethod
    def create(
        cls,
        *,
        target_claim_id: str,
        temporal_scope_digest: str,
        temporal_context_digest: str,
        as_of: str,
        source_ids: tuple[str, ...],
        source_provenance_digest: str,
    ) -> "ProvenanceTruthScope":
        target = _explicit(target_claim_id, "provenance scope target claim")
        temporal_scope_digest = _explicit(temporal_scope_digest, "provenance temporal scope digest")
        temporal_context_digest = _explicit(temporal_context_digest, "provenance temporal context digest")
        context = TemporalContext.create(as_of=as_of)
        if context.digest != temporal_context_digest:
            raise ValueError("provenance scope temporal context digest mismatch")
        source_ids = _ids(tuple(source_ids), "provenance scope source ids")
        source_provenance_digest = _explicit(
            source_provenance_digest,
            "provenance scope source provenance digest",
        )
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": PROVENANCE_BINDING_MODE,
            "target_claim_id": target,
            "temporal_scope_digest": temporal_scope_digest,
            "temporal_context_digest": temporal_context_digest,
            "as_of": context.as_of,
            "source_ids": list(source_ids),
            "source_provenance_digest": source_provenance_digest,
        }
        return cls(
            target,
            temporal_scope_digest,
            temporal_context_digest,
            context.as_of,
            source_ids,
            source_provenance_digest,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": self.binding_mode,
            "target_claim_id": self.target_claim_id,
            "temporal_scope_digest": self.temporal_scope_digest,
            "temporal_context_digest": self.temporal_context_digest,
            "as_of": self.as_of,
            "source_ids": list(self.source_ids),
            "source_provenance_digest": self.source_provenance_digest,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ProvenanceTruthScope":
        _unexpected(
            state,
            {
                "protocol",
                "binding_mode",
                "target_claim_id",
                "temporal_scope_digest",
                "temporal_context_digest",
                "as_of",
                "source_ids",
                "source_provenance_digest",
                "digest",
            },
            "provenance epistemic scope",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported provenance epistemic scope protocol")
        if str(state.get("binding_mode", "")) != PROVENANCE_BINDING_MODE:
            raise ValueError("unsupported provenance epistemic binding mode")
        row = cls.create(
            target_claim_id=str(state["target_claim_id"]),
            temporal_scope_digest=str(state["temporal_scope_digest"]),
            temporal_context_digest=str(state["temporal_context_digest"]),
            as_of=str(state["as_of"]),
            source_ids=tuple(str(value) for value in state.get("source_ids", ())),
            source_provenance_digest=str(state["source_provenance_digest"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("provenance epistemic scope digest mismatch")
        return row


class ProvenanceEpistemicJudge:
    """A11 wrapper over the exact A9 temporal/relation-aware epistemic scope."""

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
    ) -> ProvenanceTruthScope:
        if not isinstance(source_provenance, SourceProvenanceRegistry):
            raise TypeError("provenance epistemic scope requires SourceProvenanceRegistry")
        temporal_scope = TemporalEpistemicJudge().relation_aware_dependency_scope(
            str(claim_id),
            temporal_context=temporal_context,
            knowledge=knowledge,
            evidence=evidence,
            relation_semantics=relation_semantics,
            knowledge_temporal=knowledge_temporal,
            evidence_temporal=evidence_temporal,
        )
        source_ids: set[str] = set()
        for evidence_id in temporal_scope.evidence_ids:
            try:
                item = evidence.get(evidence_id)
            except KeyError:
                continue
            source_ids.add(item.source_id)
        sources = tuple(sorted(source_ids))
        return ProvenanceTruthScope.create(
            target_claim_id=temporal_scope.target_claim_id,
            temporal_scope_digest=temporal_scope.digest,
            temporal_context_digest=temporal_context.digest,
            as_of=temporal_context.as_of,
            source_ids=sources,
            source_provenance_digest=source_provenance.projection_digest(sources),
        )

    def validate_scope(
        self,
        scope: ProvenanceTruthScope,
        *,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
        source_provenance: SourceProvenanceRegistry,
    ) -> bool:
        if not isinstance(scope, ProvenanceTruthScope):
            return False
        if (
            scope.binding_mode != PROVENANCE_BINDING_MODE
            or scope.temporal_context_digest != temporal_context.digest
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
            )
        except (KeyError, TypeError, ValueError):
            return False
        return canonical == scope


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROVENANCE_BINDING_MODE",
    "ProvenanceTruthScope",
    "ProvenanceEpistemicJudge",
)
