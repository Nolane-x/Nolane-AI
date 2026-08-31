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
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceLedger, EvidencePolarity
from .knowledge_justification_truth import (
    KnowledgeJustificationBasis,
    KnowledgeJustificationRegistry,
)
from .knowledge_temporal_truth import TemporalKnowledgeView
from .knowledge_truth import KnowledgeLedger, KnowledgeRisk
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.epistemic"
TRUTH_PROTOCOL = "truth-justification-provenance-lineage-temporal-scope-v6"
JUSTIFICATION_BINDING_MODE = "justification-provenance-lineage-temporal-v6"
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
class JustificationStatus:
    justification_id: str
    claim_id: str
    kind: str
    status: str
    reason: str
    evidence_ids: tuple[str, ...]
    parent_claim_ids: tuple[str, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        justification_id: str,
        claim_id: str,
        kind: str,
        status: str,
        reason: str,
        evidence_ids: tuple[str, ...],
        parent_claim_ids: tuple[str, ...],
    ) -> "JustificationStatus":
        justification_id = _explicit(justification_id, "justification status id")
        claim_id = _explicit(claim_id, "justification status claim id")
        kind = _explicit(kind, "justification status kind")
        if kind not in {"legacy", "explicit"}:
            raise ValueError("unsupported justification status kind")
        status = _explicit(status, "justification status")
        if status not in {"supported", "refuted", "contradicted", "unknown", "dead"}:
            raise ValueError("unsupported justification status")
        reason = _explicit(reason, "justification status reason")
        evidence_ids = _ids(tuple(evidence_ids), "justification status evidence ids")
        parent_claim_ids = _ids(tuple(parent_claim_ids), "justification status parent claim ids")
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "justification_id": justification_id,
            "claim_id": claim_id,
            "kind": kind,
            "status": status,
            "reason": reason,
            "evidence_ids": list(evidence_ids),
            "parent_claim_ids": list(parent_claim_ids),
        }
        return cls(
            justification_id,
            claim_id,
            kind,
            status,
            reason,
            evidence_ids,
            parent_claim_ids,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "justification_id": self.justification_id,
            "claim_id": self.claim_id,
            "kind": self.kind,
            "status": self.status,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "parent_claim_ids": list(self.parent_claim_ids),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "JustificationStatus":
        _unexpected(
            state,
            {
                "protocol",
                "justification_id",
                "claim_id",
                "kind",
                "status",
                "reason",
                "evidence_ids",
                "parent_claim_ids",
                "digest",
            },
            "justification status",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported justification status protocol")
        row = cls.create(
            justification_id=str(state["justification_id"]),
            claim_id=str(state["claim_id"]),
            kind=str(state["kind"]),
            status=str(state["status"]),
            reason=str(state["reason"]),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            parent_claim_ids=tuple(str(value) for value in state.get("parent_claim_ids", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("justification status digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class JustificationTruthScope:
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
    justification_digest: str
    source_ids: tuple[str, ...]
    supporting_source_ids: tuple[str, ...]
    source_provenance_digest: str
    temporal_context_digest: str
    as_of: str
    assessments: tuple[TruthScopeAssessment, ...]
    justification_statuses: tuple[JustificationStatus, ...]
    contradictions: tuple[EpistemicContradiction, ...]
    debts: tuple[EpistemicDebt, ...]
    digest: str
    binding_mode: str = JUSTIFICATION_BINDING_MODE

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
        justification_digest: str,
        source_ids: tuple[str, ...],
        supporting_source_ids: tuple[str, ...],
        source_provenance_digest: str,
        temporal_context_digest: str,
        as_of: str,
        assessments: tuple[TruthScopeAssessment, ...],
        justification_statuses: tuple[JustificationStatus, ...],
        contradictions: tuple[EpistemicContradiction, ...],
        debts: tuple[EpistemicDebt, ...],
    ) -> "JustificationTruthScope":
        target = _explicit(target_claim_id, "justification scope target claim")
        lineage = _ids(tuple(lineage_claim_ids), "justification scope lineage ids")
        scope = _ids(tuple(scope_claim_ids), "justification scope claim ids")
        evidence = _ids(tuple(evidence_ids), "justification scope evidence ids")
        relations = _ids(tuple(relation_ids), "justification scope relation ids")
        sources = _ids(tuple(source_ids), "justification scope source ids")
        supporting_sources = _ids(
            tuple(supporting_source_ids),
            "justification scope supporting source ids",
        )
        if target not in lineage or not set(lineage).issubset(set(scope)):
            raise ValueError("justification scope lineage is inconsistent")
        if not set(supporting_sources).issubset(set(sources)):
            raise ValueError("supporting sources must belong to justification source scope")
        context = TemporalContext.create(as_of=as_of)
        temporal_context_digest = _explicit(
            temporal_context_digest,
            "justification temporal context digest",
        )
        if context.digest != temporal_context_digest:
            raise ValueError("justification scope temporal context digest mismatch")
        knowledge_digest = _explicit(knowledge_digest, "justification scoped knowledge digest")
        evidence_digest = _explicit(evidence_digest, "justification scoped evidence digest")
        relation_semantics_digest = _explicit(
            relation_semantics_digest,
            "justification relation semantics digest",
        )
        knowledge_temporal_digest = _explicit(
            knowledge_temporal_digest,
            "justification knowledge temporal digest",
        )
        evidence_temporal_digest = _explicit(
            evidence_temporal_digest,
            "justification evidence temporal digest",
        )
        justification_digest = _explicit(justification_digest, "justification projection digest")
        source_provenance_digest = _explicit(
            source_provenance_digest,
            "justification source provenance digest",
        )

        assessments = tuple(sorted(assessments, key=lambda row: row.claim_id))
        statuses = tuple(sorted(justification_statuses, key=lambda row: row.justification_id))
        contradictions = tuple(sorted(contradictions, key=lambda row: row.contradiction_id))
        debts = tuple(sorted(debts, key=lambda row: row.debt_id))
        if {row.claim_id for row in assessments} != set(scope) or len(assessments) != len(scope):
            raise ValueError("justification assessments must cover exactly scope claims")
        if len({row.justification_id for row in statuses}) != len(statuses):
            raise ValueError("justification status ids must be unique")
        if any(row.claim_id not in set(scope) for row in statuses):
            raise ValueError("justification status references claim outside scope")
        if len({row.contradiction_id for row in contradictions}) != len(contradictions):
            raise ValueError("justification contradiction ids must be unique")
        if len({row.debt_id for row in debts}) != len(debts):
            raise ValueError("justification debt ids must be unique")

        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": JUSTIFICATION_BINDING_MODE,
            "target_claim_id": target,
            "lineage_claim_ids": list(lineage),
            "scope_claim_ids": list(scope),
            "evidence_ids": list(evidence),
            "relation_ids": list(relations),
            "knowledge_digest": knowledge_digest,
            "evidence_digest": evidence_digest,
            "relation_semantics_digest": relation_semantics_digest,
            "knowledge_temporal_digest": knowledge_temporal_digest,
            "evidence_temporal_digest": evidence_temporal_digest,
            "justification_digest": justification_digest,
            "source_ids": list(sources),
            "supporting_source_ids": list(supporting_sources),
            "source_provenance_digest": source_provenance_digest,
            "temporal_context_digest": temporal_context_digest,
            "as_of": context.as_of,
            "assessments": [row.to_state() for row in assessments],
            "justification_statuses": [row.to_state() for row in statuses],
            "contradictions": [row.to_state() for row in contradictions],
            "debts": [row.to_state() for row in debts],
        }
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
            justification_digest,
            sources,
            supporting_sources,
            source_provenance_digest,
            temporal_context_digest,
            context.as_of,
            assessments,
            statuses,
            contradictions,
            debts,
            canonical_digest(payload),
        )

    def assessment(self, claim_id: str) -> TruthScopeAssessment:
        for row in self.assessments:
            if row.claim_id == str(claim_id):
                return row
        raise KeyError(f"claim missing from justification scope: {claim_id}")

    def justification_status(self, justification_id: str) -> JustificationStatus:
        for row in self.justification_statuses:
            if row.justification_id == str(justification_id):
                return row
        raise KeyError(f"justification missing from scope: {justification_id}")

    def legacy_justification_id(self, claim_id: str) -> str:
        rows = [
            row.justification_id
            for row in self.justification_statuses
            if row.claim_id == str(claim_id) and row.kind == "legacy"
        ]
        if len(rows) != 1:
            raise KeyError(f"legacy justification missing from scope: {claim_id}")
        return rows[0]

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": self.binding_mode,
            "target_claim_id": self.target_claim_id,
            "lineage_claim_ids": list(self.lineage_claim_ids),
            "scope_claim_ids": list(self.scope_claim_ids),
            "evidence_ids": list(self.evidence_ids),
            "relation_ids": list(self.relation_ids),
            "knowledge_digest": self.knowledge_digest,
            "evidence_digest": self.evidence_digest,
            "relation_semantics_digest": self.relation_semantics_digest,
            "knowledge_temporal_digest": self.knowledge_temporal_digest,
            "evidence_temporal_digest": self.evidence_temporal_digest,
            "justification_digest": self.justification_digest,
            "source_ids": list(self.source_ids),
            "supporting_source_ids": list(self.supporting_source_ids),
            "source_provenance_digest": self.source_provenance_digest,
            "temporal_context_digest": self.temporal_context_digest,
            "as_of": self.as_of,
            "assessments": [row.to_state() for row in self.assessments],
            "justification_statuses": [row.to_state() for row in self.justification_statuses],
            "contradictions": [row.to_state() for row in self.contradictions],
            "debts": [row.to_state() for row in self.debts],
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "JustificationTruthScope":
        allowed = {
            "protocol",
            "binding_mode",
            "target_claim_id",
            "lineage_claim_ids",
            "scope_claim_ids",
            "evidence_ids",
            "relation_ids",
            "knowledge_digest",
            "evidence_digest",
            "relation_semantics_digest",
            "knowledge_temporal_digest",
            "evidence_temporal_digest",
            "justification_digest",
            "source_ids",
            "supporting_source_ids",
            "source_provenance_digest",
            "temporal_context_digest",
            "as_of",
            "assessments",
            "justification_statuses",
            "contradictions",
            "debts",
            "digest",
        }
        _unexpected(state, allowed, "justification epistemic scope")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported justification epistemic scope protocol")
        if str(state.get("binding_mode", "")) != JUSTIFICATION_BINDING_MODE:
            raise ValueError("unsupported justification epistemic binding mode")
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
            justification_digest=str(state["justification_digest"]),
            source_ids=tuple(str(value) for value in state.get("source_ids", ())),
            supporting_source_ids=tuple(
                str(value) for value in state.get("supporting_source_ids", ())
            ),
            source_provenance_digest=str(state["source_provenance_digest"]),
            temporal_context_digest=str(state["temporal_context_digest"]),
            as_of=str(state["as_of"]),
            assessments=tuple(
                TruthScopeAssessment.from_state(value) for value in state.get("assessments", ())
            ),
            justification_statuses=tuple(
                JustificationStatus.from_state(value)
                for value in state.get("justification_statuses", ())
            ),
            contradictions=tuple(
                EpistemicContradiction.from_state(value)
                for value in state.get("contradictions", ())
            ),
            debts=tuple(EpistemicDebt.from_state(value) for value in state.get("debts", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("justification epistemic scope digest mismatch")
        return row


class JustificationEpistemicJudge:
    """A12 OR-of-AND truth maintenance over A9/A10 temporal semantics and A11 provenance."""

    @staticmethod
    def _debt(claim_id: str, reason: str, *, critical: bool, suffix: str = "") -> EpistemicDebt:
        tail = f":{suffix}" if suffix else ""
        return EpistemicDebt.create(
            f"epistemic-debt:{claim_id}:justification:{reason}{tail}",
            claim_id=claim_id,
            critical=critical,
            reason=reason,
        )

    @staticmethod
    def _dead_status(basis: KnowledgeJustificationBasis, reason: str) -> JustificationStatus:
        return JustificationStatus.create(
            justification_id=basis.justification_id,
            claim_id=basis.claim_id,
            kind=basis.kind,
            status="dead",
            reason=reason,
            evidence_ids=basis.evidence_ids,
            parent_claim_ids=basis.parent_claim_ids,
        )

    def _scope_claim_ids(
        self,
        claim_id: str,
        *,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        justifications: KnowledgeJustificationRegistry,
    ) -> tuple[str, ...]:
        scope = set(justifications.lineage_claim_ids(str(claim_id), knowledge=knowledge))
        changed = True
        while changed:
            changed = False
            competitors: set[str] = set()
            for current in tuple(scope):
                if knowledge_temporal.state_at(
                    current,
                    knowledge=knowledge,
                    temporal_context=temporal_context,
                ) != "active":
                    continue
                claim = knowledge.get(current)
                if relation_semantics.cardinality(claim.relation) is RelationCardinality.MULTI_VALUED:
                    continue
                for row in knowledge.claims():
                    if (
                        row.claim_id != claim.claim_id
                        and row.subject == claim.subject
                        and row.relation == claim.relation
                        and row.object != claim.object
                        and knowledge_temporal.state_at(
                            row.claim_id,
                            knowledge=knowledge,
                            temporal_context=temporal_context,
                        ) == "active"
                    ):
                        competitors.add(row.claim_id)
            expanded = set(scope)
            for competitor in competitors:
                expanded.update(
                    justifications.lineage_claim_ids(competitor, knowledge=knowledge)
                )
            if expanded != scope:
                scope = expanded
                changed = True
        return tuple(sorted(scope))

    def _assess(
        self,
        claim_id: str,
        *,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
        justifications: KnowledgeJustificationRegistry,
        memo: dict[str, TruthScopeAssessment],
        status_map: dict[str, JustificationStatus],
        debt_map: dict[str, EpistemicDebt],
    ) -> TruthScopeAssessment:
        if claim_id in memo:
            return memo[claim_id]
        claim = knowledge.get(claim_id)
        critical = claim.risk is KnowledgeRisk.CRITICAL
        bases = justifications.effective_justifications(claim.claim_id, knowledge=knowledge)
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
            debt_map[debt.debt_id] = debt
            for basis in bases:
                status_map[basis.justification_id] = self._dead_status(basis, reason)
            row = TruthScopeAssessment.create(
                claim_id=claim.claim_id,
                disposition=EpistemicDisposition.UNKNOWN,
                support_evidence_ids=(),
                refute_evidence_ids=(),
            )
            memo[claim.claim_id] = row
            return row

        for basis in bases:
            dead_reason = ""
            for parent_id in basis.parent_claim_ids:
                parent_state = knowledge_temporal.state_at(
                    parent_id,
                    knowledge=knowledge,
                    temporal_context=temporal_context,
                )
                parent = self._assess(
                    parent_id,
                    temporal_context=temporal_context,
                    knowledge=knowledge,
                    evidence=evidence,
                    knowledge_temporal=knowledge_temporal,
                    evidence_temporal=evidence_temporal,
                    justifications=justifications,
                    memo=memo,
                    status_map=status_map,
                    debt_map=debt_map,
                )
                if parent_state != "active":
                    dead_reason = "parent_not_applicable"
                    break
                if parent.disposition is not EpistemicDisposition.SUPPORTED:
                    dead_reason = "parent_not_supported"
                    break
            active_rows = []
            if not dead_reason:
                for evidence_id in basis.evidence_ids:
                    evidence_state = evidence_temporal.state_at(
                        evidence_id,
                        evidence=evidence,
                        temporal_context=temporal_context,
                    )
                    if evidence_state != "active":
                        dead_reason = {
                            "missing": "evidence_missing",
                            "revoked": "evidence_revoked",
                            "not_yet_valid": "evidence_not_yet_valid",
                            "expired": "evidence_expired",
                            "binding_mismatch": "evidence_binding_mismatch",
                        }.get(evidence_state, "evidence_not_applicable")
                        break
                    item = evidence.get(evidence_id)
                    if item.subject_id != claim.claim_id:
                        dead_reason = "evidence_subject_mismatch"
                        break
                    active_rows.append(item)
            if dead_reason:
                status_map[basis.justification_id] = self._dead_status(basis, dead_reason)
                continue

            support = tuple(sorted(
                row.evidence_id for row in active_rows
                if row.polarity is EvidencePolarity.SUPPORT
            ))
            refute = tuple(sorted(
                row.evidence_id for row in active_rows
                if row.polarity is EvidencePolarity.REFUTE
            ))
            if support and refute:
                status, reason = "contradicted", "support_and_refute"
            elif support:
                status, reason = "supported", "supporting_evidence_live"
            elif refute:
                status, reason = "refuted", "refuting_evidence_live"
            else:
                status, reason = "unknown", "no_decisive_evidence"
            status_map[basis.justification_id] = JustificationStatus.create(
                justification_id=basis.justification_id,
                claim_id=basis.claim_id,
                kind=basis.kind,
                status=status,
                reason=reason,
                evidence_ids=basis.evidence_ids,
                parent_claim_ids=basis.parent_claim_ids,
            )

        own_statuses = tuple(status_map[basis.justification_id] for basis in bases)
        supported = tuple(row for row in own_statuses if row.status == "supported")
        refuted = tuple(row for row in own_statuses if row.status == "refuted")
        contradicted = tuple(row for row in own_statuses if row.status == "contradicted")
        support_ids: set[str] = set()
        refute_ids: set[str] = set()
        for status in supported + contradicted:
            for evidence_id in status.evidence_ids:
                try:
                    item = evidence.get(evidence_id)
                except KeyError:
                    continue
                if item.polarity is EvidencePolarity.SUPPORT:
                    support_ids.add(evidence_id)
        for status in refuted + contradicted:
            for evidence_id in status.evidence_ids:
                try:
                    item = evidence.get(evidence_id)
                except KeyError:
                    continue
                if item.polarity is EvidencePolarity.REFUTE:
                    refute_ids.add(evidence_id)

        if contradicted or (supported and refuted):
            disposition = EpistemicDisposition.CONTRADICTED
        elif supported:
            disposition = EpistemicDisposition.SUPPORTED
        elif refuted:
            disposition = EpistemicDisposition.REFUTED
        else:
            disposition = EpistemicDisposition.UNKNOWN
        row = TruthScopeAssessment.create(
            claim_id=claim.claim_id,
            disposition=disposition,
            support_evidence_ids=tuple(support_ids),
            refute_evidence_ids=tuple(refute_ids),
        )
        memo[claim.claim_id] = row
        return row

    @staticmethod
    def _contributing_support_evidence_ids(
        target_claim_id: str,
        *,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        justifications: KnowledgeJustificationRegistry,
        status_map: Mapping[str, JustificationStatus],
    ) -> tuple[str, ...]:
        """Trace only supported proof paths reachable from the target.

        The full v6 lineage remains audit-relevant, but a supported parent that is
        reachable only through a dead target justification is not an origin of the
        target's live support and therefore must not reduce verifier independence.
        """
        support_ids: set[str] = set()
        visited_claims: set[str] = set()

        def visit(claim_id: str) -> None:
            if claim_id in visited_claims:
                return
            visited_claims.add(claim_id)
            knowledge.get(claim_id)
            for basis in justifications.effective_justifications(claim_id, knowledge=knowledge):
                status = status_map.get(basis.justification_id)
                if status is None or status.status != "supported":
                    continue
                for evidence_id in basis.evidence_ids:
                    try:
                        item = evidence.get(evidence_id)
                    except KeyError:
                        continue
                    if item.polarity is EvidencePolarity.SUPPORT:
                        support_ids.add(evidence_id)
                for parent_id in basis.parent_claim_ids:
                    visit(parent_id)

        visit(str(target_claim_id))
        return tuple(sorted(support_ids))

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
        justifications: KnowledgeJustificationRegistry,
    ) -> JustificationTruthScope:
        if not isinstance(temporal_context, TemporalContext):
            raise TypeError("justification epistemic scope requires TemporalContext")
        if not isinstance(relation_semantics, RelationSemanticsRegistry):
            raise TypeError("justification epistemic scope requires RelationSemanticsRegistry")
        if not isinstance(knowledge_temporal, TemporalKnowledgeView):
            raise TypeError("justification epistemic scope requires TemporalKnowledgeView")
        if not isinstance(evidence_temporal, TemporalEvidenceView):
            raise TypeError("justification epistemic scope requires TemporalEvidenceView")
        if not isinstance(source_provenance, SourceProvenanceRegistry):
            raise TypeError("justification epistemic scope requires SourceProvenanceRegistry")
        if not isinstance(justifications, KnowledgeJustificationRegistry):
            raise TypeError("justification epistemic scope requires KnowledgeJustificationRegistry")

        target = str(claim_id)
        lineage = justifications.lineage_claim_ids(target, knowledge=knowledge)
        scope_claim_ids = self._scope_claim_ids(
            target,
            temporal_context=temporal_context,
            knowledge=knowledge,
            relation_semantics=relation_semantics,
            knowledge_temporal=knowledge_temporal,
            justifications=justifications,
        )
        evidence_ids = justifications.evidence_ids_for_claims(
            scope_claim_ids,
            knowledge=knowledge,
        )
        relation_ids = knowledge.relations_for_claims(scope_claim_ids)

        memo: dict[str, TruthScopeAssessment] = {}
        status_map: dict[str, JustificationStatus] = {}
        debt_map: dict[str, EpistemicDebt] = {}
        assessments = tuple(
            self._assess(
                current,
                temporal_context=temporal_context,
                knowledge=knowledge,
                evidence=evidence,
                knowledge_temporal=knowledge_temporal,
                evidence_temporal=evidence_temporal,
                justifications=justifications,
                memo=memo,
                status_map=status_map,
                debt_map=debt_map,
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
                ambiguity_key = canonical_digest(
                    {
                        "subject": subject,
                        "relation": relation,
                        "claim_ids": sorted(claim_ids),
                        "objects": sorted(objects),
                        "as_of": temporal_context.as_of,
                    }
                )[:24]
                for current in sorted(claim_ids):
                    claim = knowledge.get(current)
                    debt = self._debt(
                        current,
                        _RELATION_AMBIGUITY_REASON,
                        critical=claim.risk is KnowledgeRisk.CRITICAL,
                        suffix=ambiguity_key,
                    )
                    debt_map[debt.debt_id] = debt

        source_ids: set[str] = set()
        for evidence_id in evidence_ids:
            try:
                source_ids.add(evidence.get(evidence_id).source_id)
            except KeyError:
                continue
        supporting_evidence_ids = self._contributing_support_evidence_ids(
            target,
            knowledge=knowledge,
            evidence=evidence,
            justifications=justifications,
            status_map=status_map,
        )
        supporting_source_ids: set[str] = set()
        for evidence_id in supporting_evidence_ids:
            try:
                supporting_source_ids.add(evidence.get(evidence_id).source_id)
            except KeyError:
                continue

        sources = tuple(sorted(source_ids))
        supporting_sources = tuple(sorted(supporting_source_ids))
        return JustificationTruthScope.create(
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
            justification_digest=justifications.projection_digest(
                scope_claim_ids,
                knowledge=knowledge,
            ),
            source_ids=sources,
            supporting_source_ids=supporting_sources,
            source_provenance_digest=source_provenance.projection_digest(sources),
            temporal_context_digest=temporal_context.digest,
            as_of=temporal_context.as_of,
            assessments=assessments,
            justification_statuses=tuple(status_map.values()),
            contradictions=tuple(contradictions),
            debts=tuple(debt_map.values()),
        )

    def validate_scope(
        self,
        scope: JustificationTruthScope,
        *,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
        source_provenance: SourceProvenanceRegistry,
        justifications: KnowledgeJustificationRegistry,
    ) -> bool:
        if not isinstance(scope, JustificationTruthScope):
            return False
        if scope.binding_mode != JUSTIFICATION_BINDING_MODE:
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
                justifications=justifications,
            )
        except (KeyError, TypeError, ValueError):
            return False
        return canonical == scope


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "JUSTIFICATION_BINDING_MODE",
    "JustificationStatus",
    "JustificationTruthScope",
    "JustificationEpistemicJudge",
)
