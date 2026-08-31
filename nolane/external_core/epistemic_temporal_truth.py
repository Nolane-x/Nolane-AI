from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationCardinality, RelationSemanticsRegistry
from .epistemic_truth import (
    EpistemicContradiction,
    EpistemicDebt,
    EpistemicDisposition,
    TruthScopeAssessment,
)
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceLedger, EvidencePolarity
from .knowledge_temporal_truth import TemporalKnowledgeView
from .knowledge_truth import KnowledgeLedger, KnowledgeRisk
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.epistemic"
TRUTH_PROTOCOL = "truth-relation-aware-temporal-scope-v4"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _unique(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be explicit and unique")
    return rows


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} state field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class TemporalTruthRelationAwareScope:
    target_claim_id: str
    lineage_claim_ids: tuple[str, ...]
    scope_claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    knowledge_digest: str
    evidence_digest: str
    relation_semantics_digest: str
    knowledge_temporal_digest: str
    evidence_temporal_digest: str
    temporal_context_digest: str
    as_of: str
    assessments: tuple[TruthScopeAssessment, ...]
    contradictions: tuple[EpistemicContradiction, ...]
    debts: tuple[EpistemicDebt, ...]
    digest: str

    @staticmethod
    def _payload(
        *,
        target_claim_id: str,
        lineage_claim_ids: tuple[str, ...],
        scope_claim_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        relation_ids: tuple[str, ...],
        knowledge_digest: str,
        evidence_digest: str,
        relation_semantics_digest: str,
        knowledge_temporal_digest: str,
        evidence_temporal_digest: str,
        temporal_context_digest: str,
        as_of: str,
        assessments: tuple[TruthScopeAssessment, ...],
        contradictions: tuple[EpistemicContradiction, ...],
        debts: tuple[EpistemicDebt, ...],
    ) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "target_claim_id": target_claim_id,
            "lineage_claim_ids": list(lineage_claim_ids),
            "scope_claim_ids": list(scope_claim_ids),
            "evidence_ids": list(evidence_ids),
            "relation_ids": list(relation_ids),
            "knowledge_digest": knowledge_digest,
            "evidence_digest": evidence_digest,
            "relation_semantics_digest": relation_semantics_digest,
            "knowledge_temporal_digest": knowledge_temporal_digest,
            "evidence_temporal_digest": evidence_temporal_digest,
            "temporal_context_digest": temporal_context_digest,
            "as_of": as_of,
            "assessments": [row.to_state() for row in assessments],
            "contradictions": [row.to_state() for row in contradictions],
            "debts": [row.to_state() for row in debts],
        }

    @classmethod
    def create(
        cls,
        *,
        target_claim_id: str,
        lineage_claim_ids: tuple[str, ...],
        scope_claim_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        relation_ids: tuple[str, ...],
        knowledge_digest: str,
        evidence_digest: str,
        relation_semantics_digest: str,
        knowledge_temporal_digest: str,
        evidence_temporal_digest: str,
        temporal_context_digest: str,
        as_of: str,
        assessments: tuple[TruthScopeAssessment, ...],
        contradictions: tuple[EpistemicContradiction, ...],
        debts: tuple[EpistemicDebt, ...],
    ) -> "TemporalTruthRelationAwareScope":
        target = _explicit(target_claim_id, "temporal scope target_claim_id")
        lineage = _unique(tuple(lineage_claim_ids), "temporal lineage_claim_ids")
        scope = _unique(tuple(scope_claim_ids), "temporal scope_claim_ids")
        evidence = _unique(tuple(evidence_ids), "temporal evidence_ids")
        relations = _unique(tuple(relation_ids), "temporal relation_ids")
        knowledge_digest = _explicit(knowledge_digest, "temporal knowledge_digest")
        evidence_digest = _explicit(evidence_digest, "temporal evidence_digest")
        relation_semantics_digest = _explicit(relation_semantics_digest, "temporal relation_semantics_digest")
        knowledge_temporal_digest = _explicit(knowledge_temporal_digest, "knowledge temporal projection digest")
        evidence_temporal_digest = _explicit(evidence_temporal_digest, "evidence temporal projection digest")
        temporal_context_digest = _explicit(temporal_context_digest, "temporal context digest")
        context = TemporalContext.create(as_of=as_of)
        if context.digest != temporal_context_digest:
            raise ValueError("temporal scope context digest mismatch")
        if target not in lineage:
            raise ValueError("temporal scope target must belong to lineage")
        if not set(lineage).issubset(set(scope)):
            raise ValueError("temporal scope lineage must be contained in scope")

        assessments = tuple(sorted(assessments, key=lambda row: row.claim_id))
        contradictions = tuple(sorted(contradictions, key=lambda row: row.contradiction_id))
        debts = tuple(sorted(debts, key=lambda row: row.debt_id))
        assessment_ids = tuple(row.claim_id for row in assessments)
        if len(set(assessment_ids)) != len(assessment_ids) or set(assessment_ids) != set(scope):
            raise ValueError("temporal scope assessments must cover exactly the scope claims")
        if len({row.contradiction_id for row in contradictions}) != len(contradictions):
            raise ValueError("temporal scope contradiction ids must be unique")
        if len({row.debt_id for row in debts}) != len(debts):
            raise ValueError("temporal scope debt ids must be unique")
        scope_set = set(scope)
        if any(set(row.claim_ids) - scope_set for row in contradictions):
            raise ValueError("temporal contradiction references claim outside scope")
        if any(row.claim_id not in scope_set for row in debts):
            raise ValueError("temporal debt references claim outside scope")

        payload = cls._payload(
            target_claim_id=target,
            lineage_claim_ids=lineage,
            scope_claim_ids=scope,
            evidence_ids=evidence,
            relation_ids=relations,
            knowledge_digest=knowledge_digest,
            evidence_digest=evidence_digest,
            relation_semantics_digest=relation_semantics_digest,
            knowledge_temporal_digest=knowledge_temporal_digest,
            evidence_temporal_digest=evidence_temporal_digest,
            temporal_context_digest=temporal_context_digest,
            as_of=context.as_of,
            assessments=assessments,
            contradictions=contradictions,
            debts=debts,
        )
        return cls(
            target,
            lineage,
            scope,
            evidence,
            relations,
            knowledge_digest,
            evidence_digest,
            relation_semantics_digest,
            knowledge_temporal_digest,
            evidence_temporal_digest,
            temporal_context_digest,
            context.as_of,
            assessments,
            contradictions,
            debts,
            canonical_digest(payload),
        )

    def assessment(self, claim_id: str) -> TruthScopeAssessment:
        for row in self.assessments:
            if row.claim_id == str(claim_id):
                return row
        raise KeyError(f"claim missing from temporal relation-aware scope: {claim_id}")

    def to_state(self) -> dict[str, Any]:
        return {
            **self._payload(
                target_claim_id=self.target_claim_id,
                lineage_claim_ids=self.lineage_claim_ids,
                scope_claim_ids=self.scope_claim_ids,
                evidence_ids=self.evidence_ids,
                relation_ids=self.relation_ids,
                knowledge_digest=self.knowledge_digest,
                evidence_digest=self.evidence_digest,
                relation_semantics_digest=self.relation_semantics_digest,
                knowledge_temporal_digest=self.knowledge_temporal_digest,
                evidence_temporal_digest=self.evidence_temporal_digest,
                temporal_context_digest=self.temporal_context_digest,
                as_of=self.as_of,
                assessments=self.assessments,
                contradictions=self.contradictions,
                debts=self.debts,
            ),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TemporalTruthRelationAwareScope":
        allowed = {
            "protocol", "target_claim_id", "lineage_claim_ids", "scope_claim_ids", "evidence_ids",
            "relation_ids", "knowledge_digest", "evidence_digest", "relation_semantics_digest",
            "knowledge_temporal_digest", "evidence_temporal_digest", "temporal_context_digest",
            "as_of", "assessments", "contradictions", "debts", "digest",
        }
        _unexpected(state, allowed, "temporal epistemic scope")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported temporal epistemic scope protocol")
        row = cls.create(
            target_claim_id=str(state["target_claim_id"]),
            lineage_claim_ids=tuple(str(value) for value in state.get("lineage_claim_ids", ())),
            scope_claim_ids=tuple(str(value) for value in state.get("scope_claim_ids", ())),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            relation_ids=tuple(str(value) for value in state.get("relation_ids", ())),
            knowledge_digest=str(state["knowledge_digest"]),
            evidence_digest=str(state["evidence_digest"]),
            relation_semantics_digest=str(state["relation_semantics_digest"]),
            knowledge_temporal_digest=str(state["knowledge_temporal_digest"]),
            evidence_temporal_digest=str(state["evidence_temporal_digest"]),
            temporal_context_digest=str(state["temporal_context_digest"]),
            as_of=str(state["as_of"]),
            assessments=tuple(TruthScopeAssessment.from_state(value) for value in state.get("assessments", ())),
            contradictions=tuple(EpistemicContradiction.from_state(value) for value in state.get("contradictions", ())),
            debts=tuple(EpistemicDebt.from_state(value) for value in state.get("debts", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("temporal epistemic scope digest mismatch")
        return row


class TemporalEpistemicJudge:
    """Explicit-as-of, relation-aware Truth judgment without a wall-clock authority."""

    @staticmethod
    def _debt(claim_id: str, reason: str, *, critical: bool, suffix: str = "") -> EpistemicDebt:
        tail = f":{suffix}" if suffix else ""
        return EpistemicDebt.create(
            f"epistemic-debt:{claim_id}:temporal:{reason}{tail}",
            claim_id=claim_id,
            critical=critical,
            reason=reason,
        )

    def _assess(
        self,
        claim_id: str,
        *,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        temporal_context: TemporalContext,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
        memo: dict[str, TruthScopeAssessment],
        debts: dict[str, EpistemicDebt],
    ) -> TruthScopeAssessment:
        if claim_id in memo:
            return memo[claim_id]
        claim = knowledge.get(claim_id)
        critical = claim.risk is KnowledgeRisk.CRITICAL
        claim_state = knowledge_temporal.state_at(
            claim.claim_id,
            knowledge=knowledge,
            temporal_context=temporal_context,
        )
        if claim_state != "active":
            reason = {
                "not_yet_valid": "claim_not_yet_valid",
                "expired": "claim_expired",
                "binding_mismatch": "claim_temporal_binding_mismatch",
                "missing": "claim_missing",
            }.get(claim_state, "claim_not_applicable")
            debt = self._debt(claim.claim_id, reason, critical=critical)
            debts[debt.debt_id] = debt
            row = TruthScopeAssessment.create(
                claim_id=claim.claim_id,
                disposition=EpistemicDisposition.UNKNOWN,
                support_evidence_ids=(),
                refute_evidence_ids=(),
            )
            memo[claim.claim_id] = row
            return row

        parent_rows: list[TruthScopeAssessment] = []
        parent_not_applicable = False
        for parent_id in claim.parent_claim_ids:
            parent_state = knowledge_temporal.state_at(
                parent_id,
                knowledge=knowledge,
                temporal_context=temporal_context,
            )
            parent_row = self._assess(
                parent_id,
                knowledge=knowledge,
                evidence=evidence,
                temporal_context=temporal_context,
                knowledge_temporal=knowledge_temporal,
                evidence_temporal=evidence_temporal,
                memo=memo,
                debts=debts,
            )
            parent_rows.append(parent_row)
            if parent_state != "active":
                parent_not_applicable = True
        if parent_not_applicable:
            debt = self._debt(claim.claim_id, "parent_not_applicable", critical=critical)
            debts[debt.debt_id] = debt
            disposition = EpistemicDisposition.UNKNOWN
            support: tuple[str, ...] = ()
            refute: tuple[str, ...] = ()
        elif any(row.disposition is not EpistemicDisposition.SUPPORTED for row in parent_rows):
            disposition, support, refute = EpistemicDisposition.UNKNOWN, (), ()
        else:
            active_rows = []
            invalid = False
            for evidence_id in claim.evidence_ids:
                state = evidence_temporal.state_at(
                    evidence_id,
                    evidence=evidence,
                    temporal_context=temporal_context,
                )
                if state != "active":
                    reason = {
                        "missing": "evidence_missing",
                        "revoked": "evidence_revoked",
                        "not_yet_valid": "evidence_not_yet_valid",
                        "expired": "evidence_expired",
                        "binding_mismatch": "evidence_binding_mismatch",
                    }.get(state, "evidence_not_applicable")
                    debt = self._debt(claim.claim_id, reason, critical=critical, suffix=evidence_id)
                    debts[debt.debt_id] = debt
                    invalid = True
                    continue
                item = evidence.get(evidence_id)
                if item.subject_id != claim.claim_id:
                    debt = self._debt(
                        claim.claim_id,
                        "evidence_subject_mismatch",
                        critical=critical,
                        suffix=evidence_id,
                    )
                    debts[debt.debt_id] = debt
                    invalid = True
                    continue
                active_rows.append(item)
            if invalid:
                disposition, support, refute = EpistemicDisposition.UNKNOWN, (), ()
            else:
                support = tuple(sorted(
                    row.evidence_id for row in active_rows
                    if row.polarity is EvidencePolarity.SUPPORT
                ))
                refute = tuple(sorted(
                    row.evidence_id for row in active_rows
                    if row.polarity is EvidencePolarity.REFUTE
                ))
                disposition = (
                    EpistemicDisposition.CONTRADICTED if support and refute
                    else EpistemicDisposition.SUPPORTED if support
                    else EpistemicDisposition.REFUTED if refute
                    else EpistemicDisposition.UNKNOWN
                )

        row = TruthScopeAssessment.create(
            claim_id=claim.claim_id,
            disposition=disposition,
            support_evidence_ids=support,
            refute_evidence_ids=refute,
        )
        memo[claim.claim_id] = row
        return row

    def relation_aware_dependency_scope(
        self,
        claim_id: str,
        *,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
    ) -> TemporalTruthRelationAwareScope:
        if not isinstance(temporal_context, TemporalContext):
            raise TypeError("temporal epistemic scope requires canonical TemporalContext")
        if not isinstance(relation_semantics, RelationSemanticsRegistry):
            raise TypeError("temporal epistemic scope requires canonical relation semantics registry")
        if not isinstance(knowledge_temporal, TemporalKnowledgeView):
            raise TypeError("temporal epistemic scope requires TemporalKnowledgeView")
        if not isinstance(evidence_temporal, TemporalEvidenceView):
            raise TypeError("temporal epistemic scope requires TemporalEvidenceView")

        target = str(claim_id)
        lineage = knowledge.lineage_claim_ids(target)
        scope_claim_ids = knowledge_temporal.truth_scope_claim_ids_v4(
            target,
            knowledge=knowledge,
            relation_semantics=relation_semantics,
            temporal_context=temporal_context,
        )
        evidence_ids = knowledge.evidence_ids_for_claims(scope_claim_ids)
        relation_ids = knowledge.relations_for_claims(scope_claim_ids)

        memo: dict[str, TruthScopeAssessment] = {}
        debt_map: dict[str, EpistemicDebt] = {}
        assessments = tuple(
            self._assess(
                current,
                knowledge=knowledge,
                evidence=evidence,
                temporal_context=temporal_context,
                knowledge_temporal=knowledge_temporal,
                evidence_temporal=evidence_temporal,
                memo=memo,
                debts=debt_map,
            )
            for current in scope_claim_ids
        )

        for assessment in assessments:
            if assessment.disposition in {EpistemicDisposition.UNKNOWN, EpistemicDisposition.CONTRADICTED}:
                claim = knowledge.get(assessment.claim_id)
                debt = self._debt(
                    claim.claim_id,
                    assessment.disposition.value,
                    critical=claim.risk is KnowledgeRisk.CRITICAL,
                )
                debt_map[debt.debt_id] = debt

        groups: dict[tuple[str, str], list[str]] = {}
        for assessment in assessments:
            if assessment.disposition is not EpistemicDisposition.SUPPORTED:
                continue
            if knowledge_temporal.state_at(
                assessment.claim_id,
                knowledge=knowledge,
                temporal_context=temporal_context,
            ) != "active":
                continue
            claim = knowledge.get(assessment.claim_id)
            groups.setdefault((claim.subject, claim.relation), []).append(claim.claim_id)

        contradictions: list[EpistemicContradiction] = []
        for (subject, relation), claim_ids in sorted(groups.items()):
            objects = {knowledge.get(current).object for current in claim_ids}
            if len(objects) <= 1:
                continue
            cardinality = relation_semantics.cardinality(relation)
            if cardinality is RelationCardinality.EXCLUSIVE:
                conflict = EpistemicContradiction.create(
                    subject=subject,
                    relation=relation,
                    claim_ids=tuple(claim_ids),
                    object_values=tuple(objects),
                )
                contradictions.append(conflict)
                for current in conflict.claim_ids:
                    claim = knowledge.get(current)
                    debt = self._debt(
                        current,
                        "competing_supported_propositions",
                        critical=claim.risk is KnowledgeRisk.CRITICAL,
                        suffix=conflict.contradiction_id,
                    )
                    debt_map[debt.debt_id] = debt
            elif cardinality is RelationCardinality.UNSPECIFIED:
                ambiguity_key = canonical_digest({
                    "subject": subject,
                    "relation": relation,
                    "claim_ids": sorted(claim_ids),
                    "objects": sorted(objects),
                    "as_of": temporal_context.as_of,
                })[:24]
                for current in sorted(claim_ids):
                    claim = knowledge.get(current)
                    debt = self._debt(
                        current,
                        "relation_semantics_unspecified_for_multiple_values",
                        critical=claim.risk is KnowledgeRisk.CRITICAL,
                        suffix=ambiguity_key,
                    )
                    debt_map[debt.debt_id] = debt

        return TemporalTruthRelationAwareScope.create(
            target_claim_id=target,
            lineage_claim_ids=lineage,
            scope_claim_ids=scope_claim_ids,
            evidence_ids=evidence_ids,
            relation_ids=relation_ids,
            knowledge_digest=knowledge.scoped_digest(scope_claim_ids),
            evidence_digest=evidence.scoped_digest(evidence_ids),
            relation_semantics_digest=relation_semantics.projection_digest(relation_ids),
            knowledge_temporal_digest=knowledge_temporal.projection_digest(
                scope_claim_ids,
                knowledge=knowledge,
                temporal_context=temporal_context,
            ),
            evidence_temporal_digest=evidence_temporal.projection_digest(
                evidence_ids,
                evidence=evidence,
                temporal_context=temporal_context,
            ),
            temporal_context_digest=temporal_context.digest,
            as_of=temporal_context.as_of,
            assessments=assessments,
            contradictions=tuple(contradictions),
            debts=tuple(debt_map.values()),
        )

    def validate_relation_aware_scope(
        self,
        scope: TemporalTruthRelationAwareScope,
        *,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
    ) -> bool:
        if not isinstance(scope, TemporalTruthRelationAwareScope):
            return False
        try:
            canonical = self.relation_aware_dependency_scope(
                scope.target_claim_id,
                temporal_context=temporal_context,
                knowledge=knowledge,
                evidence=evidence,
                relation_semantics=relation_semantics,
                knowledge_temporal=knowledge_temporal,
                evidence_temporal=evidence_temporal,
            )
        except (KeyError, TypeError, ValueError):
            return False
        return canonical == scope


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "TemporalTruthRelationAwareScope",
    "TemporalEpistemicJudge",
)
