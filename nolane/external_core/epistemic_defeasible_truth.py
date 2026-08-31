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
from .knowledge_undercutter_truth import (
    JustificationUndercutterRegistry,
    JustificationUndercutterRevision,
)
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.epistemic"
TRUTH_PROTOCOL = "truth-defeasible-justification-provenance-lineage-temporal-scope-v7"
DEFEASIBLE_BINDING_MODE = "defeasible-justification-provenance-lineage-temporal-v7"
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
class UndercutterStatus:
    undercutter_id: str
    target_claim_id: str
    target_justification_id: str
    status: str
    reason: str
    evidence_ids: tuple[str, ...]
    parent_claim_ids: tuple[str, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        undercutter_id: str,
        target_claim_id: str,
        target_justification_id: str,
        status: str,
        reason: str,
        evidence_ids: tuple[str, ...],
        parent_claim_ids: tuple[str, ...],
    ) -> "UndercutterStatus":
        undercutter_id = _explicit(undercutter_id, "undercutter status id")
        target_claim_id = _explicit(target_claim_id, "undercutter status target claim")
        target_justification_id = _explicit(
            target_justification_id, "undercutter status target justification"
        )
        status = _explicit(status, "undercutter status")
        if status not in {"supported", "refuted", "contradicted", "unknown", "dead"}:
            raise ValueError("unsupported undercutter status")
        reason = _explicit(reason, "undercutter status reason")
        evidence_ids = _ids(tuple(evidence_ids), "undercutter status evidence ids")
        parent_claim_ids = _ids(tuple(parent_claim_ids), "undercutter status parent claim ids")
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "undercutter_id": undercutter_id,
            "target_claim_id": target_claim_id,
            "target_justification_id": target_justification_id,
            "status": status,
            "reason": reason,
            "evidence_ids": list(evidence_ids),
            "parent_claim_ids": list(parent_claim_ids),
        }
        return cls(
            undercutter_id,
            target_claim_id,
            target_justification_id,
            status,
            reason,
            evidence_ids,
            parent_claim_ids,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "undercutter_id": self.undercutter_id,
            "target_claim_id": self.target_claim_id,
            "target_justification_id": self.target_justification_id,
            "status": self.status,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "parent_claim_ids": list(self.parent_claim_ids),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "UndercutterStatus":
        _unexpected(
            state,
            {
                "protocol",
                "undercutter_id",
                "target_claim_id",
                "target_justification_id",
                "status",
                "reason",
                "evidence_ids",
                "parent_claim_ids",
                "digest",
            },
            "undercutter status",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported undercutter status protocol")
        row = cls.create(
            undercutter_id=str(state["undercutter_id"]),
            target_claim_id=str(state["target_claim_id"]),
            target_justification_id=str(state["target_justification_id"]),
            status=str(state["status"]),
            reason=str(state["reason"]),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            parent_claim_ids=tuple(str(value) for value in state.get("parent_claim_ids", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("undercutter status digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class DefeasibleJustificationStatus:
    justification_id: str
    claim_id: str
    kind: str
    intrinsic_status: str
    status: str
    reason: str
    evidence_ids: tuple[str, ...]
    parent_claim_ids: tuple[str, ...]
    supported_undercutter_ids: tuple[str, ...]
    contested_undercutter_ids: tuple[str, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        justification_id: str,
        claim_id: str,
        kind: str,
        intrinsic_status: str,
        status: str,
        reason: str,
        evidence_ids: tuple[str, ...],
        parent_claim_ids: tuple[str, ...],
        supported_undercutter_ids: tuple[str, ...] = (),
        contested_undercutter_ids: tuple[str, ...] = (),
    ) -> "DefeasibleJustificationStatus":
        justification_id = _explicit(justification_id, "defeasible justification id")
        claim_id = _explicit(claim_id, "defeasible justification claim id")
        kind = _explicit(kind, "defeasible justification kind")
        if kind not in {"legacy", "explicit"}:
            raise ValueError("unsupported defeasible justification kind")
        intrinsic_status = _explicit(intrinsic_status, "intrinsic justification status")
        if intrinsic_status not in {"supported", "refuted", "contradicted", "unknown", "dead"}:
            raise ValueError("unsupported intrinsic justification status")
        status = _explicit(status, "defeasible justification status")
        if status not in {
            "supported",
            "refuted",
            "contradicted",
            "unknown",
            "dead",
            "defeated",
            "contested",
        }:
            raise ValueError("unsupported defeasible justification status")
        reason = _explicit(reason, "defeasible justification reason")
        evidence_ids = _ids(tuple(evidence_ids), "defeasible justification evidence ids")
        parent_claim_ids = _ids(tuple(parent_claim_ids), "defeasible justification parent ids")
        supported_undercutter_ids = _ids(
            tuple(supported_undercutter_ids), "supported undercutter ids"
        )
        contested_undercutter_ids = _ids(
            tuple(contested_undercutter_ids), "contested undercutter ids"
        )
        if set(supported_undercutter_ids) & set(contested_undercutter_ids):
            raise ValueError("undercutter cannot be both supported and contested")
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "justification_id": justification_id,
            "claim_id": claim_id,
            "kind": kind,
            "intrinsic_status": intrinsic_status,
            "status": status,
            "reason": reason,
            "evidence_ids": list(evidence_ids),
            "parent_claim_ids": list(parent_claim_ids),
            "supported_undercutter_ids": list(supported_undercutter_ids),
            "contested_undercutter_ids": list(contested_undercutter_ids),
        }
        return cls(
            justification_id,
            claim_id,
            kind,
            intrinsic_status,
            status,
            reason,
            evidence_ids,
            parent_claim_ids,
            supported_undercutter_ids,
            contested_undercutter_ids,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "justification_id": self.justification_id,
            "claim_id": self.claim_id,
            "kind": self.kind,
            "intrinsic_status": self.intrinsic_status,
            "status": self.status,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "parent_claim_ids": list(self.parent_claim_ids),
            "supported_undercutter_ids": list(self.supported_undercutter_ids),
            "contested_undercutter_ids": list(self.contested_undercutter_ids),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DefeasibleJustificationStatus":
        _unexpected(
            state,
            {
                "protocol",
                "justification_id",
                "claim_id",
                "kind",
                "intrinsic_status",
                "status",
                "reason",
                "evidence_ids",
                "parent_claim_ids",
                "supported_undercutter_ids",
                "contested_undercutter_ids",
                "digest",
            },
            "defeasible justification status",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported defeasible justification status protocol")
        row = cls.create(
            justification_id=str(state["justification_id"]),
            claim_id=str(state["claim_id"]),
            kind=str(state["kind"]),
            intrinsic_status=str(state["intrinsic_status"]),
            status=str(state["status"]),
            reason=str(state["reason"]),
            evidence_ids=tuple(str(value) for value in state.get("evidence_ids", ())),
            parent_claim_ids=tuple(str(value) for value in state.get("parent_claim_ids", ())),
            supported_undercutter_ids=tuple(
                str(value) for value in state.get("supported_undercutter_ids", ())
            ),
            contested_undercutter_ids=tuple(
                str(value) for value in state.get("contested_undercutter_ids", ())
            ),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("defeasible justification status digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class DefeasibleTruthScope:
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
    undercutter_digest: str
    source_ids: tuple[str, ...]
    decision_source_ids: tuple[str, ...]
    source_provenance_digest: str
    temporal_context_digest: str
    as_of: str
    assessments: tuple[TruthScopeAssessment, ...]
    justification_statuses: tuple[DefeasibleJustificationStatus, ...]
    undercutter_statuses: tuple[UndercutterStatus, ...]
    contradictions: tuple[EpistemicContradiction, ...]
    debts: tuple[EpistemicDebt, ...]
    digest: str
    binding_mode: str = DEFEASIBLE_BINDING_MODE

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
        undercutter_digest: str,
        source_ids: tuple[str, ...],
        decision_source_ids: tuple[str, ...],
        source_provenance_digest: str,
        temporal_context_digest: str,
        as_of: str,
        assessments: tuple[TruthScopeAssessment, ...],
        justification_statuses: tuple[DefeasibleJustificationStatus, ...],
        undercutter_statuses: tuple[UndercutterStatus, ...],
        contradictions: tuple[EpistemicContradiction, ...],
        debts: tuple[EpistemicDebt, ...],
    ) -> "DefeasibleTruthScope":
        target = _explicit(target_claim_id, "defeasible scope target claim")
        lineage = _ids(tuple(lineage_claim_ids), "defeasible scope lineage ids")
        scope = _ids(tuple(scope_claim_ids), "defeasible scope claim ids")
        evidence = _ids(tuple(evidence_ids), "defeasible scope evidence ids")
        relations = _ids(tuple(relation_ids), "defeasible scope relation ids")
        sources = _ids(tuple(source_ids), "defeasible scope source ids")
        decision_sources = _ids(tuple(decision_source_ids), "defeasible decision source ids")
        if target not in lineage or not set(lineage).issubset(set(scope)):
            raise ValueError("defeasible scope lineage is inconsistent")
        if not set(decision_sources).issubset(set(sources)):
            raise ValueError("defeasible decision sources must belong to audit source scope")
        context = TemporalContext.create(as_of=as_of)
        if context.digest != _explicit(
            temporal_context_digest, "defeasible temporal context digest"
        ):
            raise ValueError("defeasible scope temporal context digest mismatch")

        knowledge_digest = _explicit(knowledge_digest, "defeasible knowledge digest")
        evidence_digest = _explicit(evidence_digest, "defeasible evidence digest")
        relation_semantics_digest = _explicit(
            relation_semantics_digest, "defeasible relation semantics digest"
        )
        knowledge_temporal_digest = _explicit(
            knowledge_temporal_digest, "defeasible knowledge temporal digest"
        )
        evidence_temporal_digest = _explicit(
            evidence_temporal_digest, "defeasible evidence temporal digest"
        )
        justification_digest = _explicit(justification_digest, "defeasible justification digest")
        undercutter_digest = _explicit(undercutter_digest, "defeasible undercutter digest")
        source_provenance_digest = _explicit(
            source_provenance_digest, "defeasible source provenance digest"
        )

        assessments = tuple(sorted(assessments, key=lambda row: row.claim_id))
        statuses = tuple(sorted(justification_statuses, key=lambda row: row.justification_id))
        attacks = tuple(sorted(undercutter_statuses, key=lambda row: row.undercutter_id))
        contradictions = tuple(sorted(contradictions, key=lambda row: row.contradiction_id))
        debts = tuple(sorted(debts, key=lambda row: row.debt_id))
        if {row.claim_id for row in assessments} != set(scope) or len(assessments) != len(scope):
            raise ValueError("defeasible assessments must cover exactly scope claims")
        if len({row.justification_id for row in statuses}) != len(statuses):
            raise ValueError("defeasible justification status ids must be unique")
        if any(row.claim_id not in set(scope) for row in statuses):
            raise ValueError("defeasible justification status outside scope")
        if len({row.undercutter_id for row in attacks}) != len(attacks):
            raise ValueError("defeasible undercutter status ids must be unique")
        if any(row.target_claim_id not in set(scope) for row in attacks):
            raise ValueError("defeasible undercutter status outside scope")
        if len({row.contradiction_id for row in contradictions}) != len(contradictions):
            raise ValueError("defeasible contradiction ids must be unique")
        if len({row.debt_id for row in debts}) != len(debts):
            raise ValueError("defeasible debt ids must be unique")

        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": DEFEASIBLE_BINDING_MODE,
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
            "undercutter_digest": undercutter_digest,
            "source_ids": list(sources),
            "decision_source_ids": list(decision_sources),
            "source_provenance_digest": source_provenance_digest,
            "temporal_context_digest": context.digest,
            "as_of": context.as_of,
            "assessments": [row.to_state() for row in assessments],
            "justification_statuses": [row.to_state() for row in statuses],
            "undercutter_statuses": [row.to_state() for row in attacks],
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
            undercutter_digest,
            sources,
            decision_sources,
            source_provenance_digest,
            context.digest,
            context.as_of,
            assessments,
            statuses,
            attacks,
            contradictions,
            debts,
            canonical_digest(payload),
        )

    def assessment(self, claim_id: str) -> TruthScopeAssessment:
        for row in self.assessments:
            if row.claim_id == str(claim_id):
                return row
        raise KeyError(f"claim missing from defeasible scope: {claim_id}")

    def justification_status(self, justification_id: str) -> DefeasibleJustificationStatus:
        for row in self.justification_statuses:
            if row.justification_id == str(justification_id):
                return row
        raise KeyError(f"justification missing from defeasible scope: {justification_id}")

    def undercutter_status(self, undercutter_id: str) -> UndercutterStatus:
        for row in self.undercutter_statuses:
            if row.undercutter_id == str(undercutter_id):
                return row
        raise KeyError(f"undercutter missing from defeasible scope: {undercutter_id}")

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
            "undercutter_digest": self.undercutter_digest,
            "source_ids": list(self.source_ids),
            "decision_source_ids": list(self.decision_source_ids),
            "source_provenance_digest": self.source_provenance_digest,
            "temporal_context_digest": self.temporal_context_digest,
            "as_of": self.as_of,
            "assessments": [row.to_state() for row in self.assessments],
            "justification_statuses": [row.to_state() for row in self.justification_statuses],
            "undercutter_statuses": [row.to_state() for row in self.undercutter_statuses],
            "contradictions": [row.to_state() for row in self.contradictions],
            "debts": [row.to_state() for row in self.debts],
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "DefeasibleTruthScope":
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
            "undercutter_digest",
            "source_ids",
            "decision_source_ids",
            "source_provenance_digest",
            "temporal_context_digest",
            "as_of",
            "assessments",
            "justification_statuses",
            "undercutter_statuses",
            "contradictions",
            "debts",
            "digest",
        }
        _unexpected(state, allowed, "defeasible epistemic scope")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported defeasible epistemic scope protocol")
        if str(state.get("binding_mode", "")) != DEFEASIBLE_BINDING_MODE:
            raise ValueError("unsupported defeasible epistemic binding mode")
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
            undercutter_digest=str(state["undercutter_digest"]),
            source_ids=tuple(str(value) for value in state.get("source_ids", ())),
            decision_source_ids=tuple(
                str(value) for value in state.get("decision_source_ids", ())
            ),
            source_provenance_digest=str(state["source_provenance_digest"]),
            temporal_context_digest=str(state["temporal_context_digest"]),
            as_of=str(state["as_of"]),
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
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("defeasible epistemic scope digest mismatch")
        return row


class DefeasibleEpistemicJudge:
    """A13 non-monotonic undercutters over accepted A12 OR-of-AND truth maintenance."""

    @staticmethod
    def _debt(
        claim_id: str,
        reason: str,
        *,
        critical: bool,
        suffix: str = "",
    ) -> EpistemicDebt:
        tail = f":{suffix}" if suffix else ""
        return EpistemicDebt.create(
            f"epistemic-debt:{claim_id}:defeasible:{reason}{tail}",
            claim_id=claim_id,
            critical=critical,
            reason=reason,
        )

    def _dependency_lineage_claim_ids(
        self,
        claim_id: str,
        *,
        knowledge: KnowledgeLedger,
        justifications: KnowledgeJustificationRegistry,
        undercutters: JustificationUndercutterRegistry,
    ) -> tuple[str, ...]:
        seen: set[str] = set()
        pending = [str(claim_id)]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            knowledge.get(current)
            seen.add(current)
            for basis in justifications.effective_justifications(current, knowledge=knowledge):
                pending.extend(basis.parent_claim_ids)
                for attack in undercutters.targeting_basis(basis):
                    pending.extend(attack.parent_claim_ids)
        return tuple(sorted(seen))

    def _scope_claim_ids(
        self,
        claim_id: str,
        *,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        relation_semantics: RelationSemanticsRegistry,
        knowledge_temporal: TemporalKnowledgeView,
        justifications: KnowledgeJustificationRegistry,
        undercutters: JustificationUndercutterRegistry,
    ) -> tuple[str, ...]:
        scope = set(
            self._dependency_lineage_claim_ids(
                str(claim_id),
                knowledge=knowledge,
                justifications=justifications,
                undercutters=undercutters,
            )
        )
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
                    self._dependency_lineage_claim_ids(
                        competitor,
                        knowledge=knowledge,
                        justifications=justifications,
                        undercutters=undercutters,
                    )
                )
            if expanded != scope:
                scope = expanded
                changed = True
        return tuple(sorted(scope))

    def _evaluate_undercutter(
        self,
        attack: JustificationUndercutterRevision,
        *,
        temporal_context: TemporalContext,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        knowledge_temporal: TemporalKnowledgeView,
        evidence_temporal: TemporalEvidenceView,
        justifications: KnowledgeJustificationRegistry,
        undercutters: JustificationUndercutterRegistry,
        memo: dict[str, TruthScopeAssessment],
        status_map: dict[str, DefeasibleJustificationStatus],
        attack_map: dict[str, UndercutterStatus],
        debt_map: dict[str, EpistemicDebt],
    ) -> UndercutterStatus:
        old = attack_map.get(attack.undercutter_id)
        if old is not None:
            return old
        claim = knowledge.get(attack.target_claim_id)
        critical = claim.risk is KnowledgeRisk.CRITICAL
        dead_reason = ""
        for parent_id in attack.parent_claim_ids:
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
                undercutters=undercutters,
                memo=memo,
                status_map=status_map,
                attack_map=attack_map,
                debt_map=debt_map,
            )
            if parent_state != "active":
                dead_reason = "undercutter_parent_not_applicable"
                break
            if parent.disposition is not EpistemicDisposition.SUPPORTED:
                dead_reason = "undercutter_parent_not_supported"
                break

        active_rows = []
        if not dead_reason:
            for evidence_id in attack.evidence_ids:
                evidence_state = evidence_temporal.state_at(
                    evidence_id,
                    evidence=evidence,
                    temporal_context=temporal_context,
                )
                if evidence_state != "active":
                    dead_reason = {
                        "missing": "undercutter_evidence_missing",
                        "revoked": "undercutter_evidence_revoked",
                        "not_yet_valid": "undercutter_evidence_not_yet_valid",
                        "expired": "undercutter_evidence_expired",
                        "binding_mismatch": "undercutter_evidence_binding_mismatch",
                    }.get(evidence_state, "undercutter_evidence_not_applicable")
                    break
                item = evidence.get(evidence_id)
                if item.subject_id != attack.undercutter_id:
                    dead_reason = "undercutter_evidence_subject_mismatch"
                    break
                active_rows.append(item)

        if dead_reason:
            row = UndercutterStatus.create(
                undercutter_id=attack.undercutter_id,
                target_claim_id=attack.target_claim_id,
                target_justification_id=attack.target_justification_id,
                status="dead",
                reason=dead_reason,
                evidence_ids=attack.evidence_ids,
                parent_claim_ids=attack.parent_claim_ids,
            )
            attack_map[row.undercutter_id] = row
            return row

        support = tuple(
            sorted(
                row.evidence_id
                for row in active_rows
                if row.polarity is EvidencePolarity.SUPPORT
            )
        )
        refute = tuple(
            sorted(
                row.evidence_id
                for row in active_rows
                if row.polarity is EvidencePolarity.REFUTE
            )
        )
        if support and refute:
            status, reason = "contradicted", "undercutter_support_and_refute"
        elif support:
            status, reason = "supported", "undercutter_supporting_evidence_live"
        elif refute:
            status, reason = "refuted", "undercutter_refuting_evidence_live"
        else:
            status, reason = "unknown", "undercutter_no_decisive_evidence"
        row = UndercutterStatus.create(
            undercutter_id=attack.undercutter_id,
            target_claim_id=attack.target_claim_id,
            target_justification_id=attack.target_justification_id,
            status=status,
            reason=reason,
            evidence_ids=attack.evidence_ids,
            parent_claim_ids=attack.parent_claim_ids,
        )
        attack_map[row.undercutter_id] = row
        if status in {"unknown", "contradicted"}:
            debt = self._debt(
                claim.claim_id,
                f"undercutter_{status}",
                critical=critical,
                suffix=attack.undercutter_id,
            )
            debt_map[debt.debt_id] = debt
        return row

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
        undercutters: JustificationUndercutterRegistry,
        memo: dict[str, TruthScopeAssessment],
        status_map: dict[str, DefeasibleJustificationStatus],
        attack_map: dict[str, UndercutterStatus],
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
                status_map[basis.justification_id] = DefeasibleJustificationStatus.create(
                    justification_id=basis.justification_id,
                    claim_id=basis.claim_id,
                    kind=basis.kind,
                    intrinsic_status="dead",
                    status="dead",
                    reason=reason,
                    evidence_ids=basis.evidence_ids,
                    parent_claim_ids=basis.parent_claim_ids,
                )
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
                    undercutters=undercutters,
                    memo=memo,
                    status_map=status_map,
                    attack_map=attack_map,
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
                intrinsic_status, intrinsic_reason = "dead", dead_reason
            else:
                support = tuple(
                    sorted(
                        row.evidence_id
                        for row in active_rows
                        if row.polarity is EvidencePolarity.SUPPORT
                    )
                )
                refute = tuple(
                    sorted(
                        row.evidence_id
                        for row in active_rows
                        if row.polarity is EvidencePolarity.REFUTE
                    )
                )
                if support and refute:
                    intrinsic_status, intrinsic_reason = "contradicted", "support_and_refute"
                elif support:
                    intrinsic_status, intrinsic_reason = "supported", "supporting_evidence_live"
                elif refute:
                    intrinsic_status, intrinsic_reason = "refuted", "refuting_evidence_live"
                else:
                    intrinsic_status, intrinsic_reason = "unknown", "no_decisive_evidence"

            attack_statuses = tuple(
                self._evaluate_undercutter(
                    attack,
                    temporal_context=temporal_context,
                    knowledge=knowledge,
                    evidence=evidence,
                    knowledge_temporal=knowledge_temporal,
                    evidence_temporal=evidence_temporal,
                    justifications=justifications,
                    undercutters=undercutters,
                    memo=memo,
                    status_map=status_map,
                    attack_map=attack_map,
                    debt_map=debt_map,
                )
                for attack in undercutters.targeting_basis(basis)
            )
            supported_attacks = tuple(
                sorted(row.undercutter_id for row in attack_statuses if row.status == "supported")
            )
            contested_attacks = tuple(
                sorted(row.undercutter_id for row in attack_statuses if row.status == "contradicted")
            )

            if intrinsic_status == "dead":
                final_status, reason = "dead", intrinsic_reason
            elif supported_attacks:
                final_status, reason = "defeated", "supported_undercutter"
            elif contested_attacks:
                final_status, reason = "contested", "contradicted_undercutter"
            else:
                final_status, reason = intrinsic_status, intrinsic_reason

            status_map[basis.justification_id] = DefeasibleJustificationStatus.create(
                justification_id=basis.justification_id,
                claim_id=basis.claim_id,
                kind=basis.kind,
                intrinsic_status=intrinsic_status,
                status=final_status,
                reason=reason,
                evidence_ids=basis.evidence_ids,
                parent_claim_ids=basis.parent_claim_ids,
                supported_undercutter_ids=supported_attacks,
                contested_undercutter_ids=contested_attacks,
            )

        own_statuses = tuple(status_map[basis.justification_id] for basis in bases)
        supported = tuple(row for row in own_statuses if row.status == "supported")
        refuted = tuple(row for row in own_statuses if row.status == "refuted")
        contradicted = tuple(row for row in own_statuses if row.status == "contradicted")
        contested = tuple(row for row in own_statuses if row.status == "contested")

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

        if supported and (refuted or contradicted):
            disposition = EpistemicDisposition.CONTRADICTED
        elif supported:
            disposition = EpistemicDisposition.SUPPORTED
        elif contradicted:
            disposition = EpistemicDisposition.CONTRADICTED
        elif refuted and contested:
            disposition = EpistemicDisposition.CONTRADICTED
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
    def _decision_evidence_ids(
        target_claim_id: str,
        *,
        knowledge: KnowledgeLedger,
        evidence: EvidenceLedger,
        justifications: KnowledgeJustificationRegistry,
        undercutters: JustificationUndercutterRegistry,
        status_map: Mapping[str, DefeasibleJustificationStatus],
        attack_map: Mapping[str, UndercutterStatus],
    ) -> tuple[str, ...]:
        ids: set[str] = set()
        visited: set[str] = set()

        def add_attack_evidence(undercutter_id: str) -> None:
            status = attack_map.get(undercutter_id)
            if status is None:
                return
            for evidence_id in status.evidence_ids:
                try:
                    item = evidence.get(evidence_id)
                except KeyError:
                    continue
                if item.polarity in {EvidencePolarity.SUPPORT, EvidencePolarity.REFUTE}:
                    ids.add(evidence_id)

        def visit(claim_id: str) -> None:
            if claim_id in visited:
                return
            visited.add(claim_id)
            bases = justifications.effective_justifications(claim_id, knowledge=knowledge)
            for basis in bases:
                status = status_map.get(basis.justification_id)
                if status is None:
                    continue
                if status.status == "supported":
                    for evidence_id in basis.evidence_ids:
                        try:
                            item = evidence.get(evidence_id)
                        except KeyError:
                            continue
                        if item.polarity is EvidencePolarity.SUPPORT:
                            ids.add(evidence_id)
                    for attack in undercutters.targeting_basis(basis):
                        attack_status = attack_map.get(attack.undercutter_id)
                        if attack_status is not None and attack_status.status == "refuted":
                            add_attack_evidence(attack.undercutter_id)
                    for parent_id in basis.parent_claim_ids:
                        visit(parent_id)
                elif status.status in {"defeated", "contested"} and status.intrinsic_status in {
                    "refuted",
                    "contradicted",
                }:
                    for undercutter_id in (
                        status.supported_undercutter_ids + status.contested_undercutter_ids
                    ):
                        add_attack_evidence(undercutter_id)

        visit(str(target_claim_id))
        return tuple(sorted(ids))

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
        undercutters: JustificationUndercutterRegistry,
    ) -> DefeasibleTruthScope:
        if not isinstance(temporal_context, TemporalContext):
            raise TypeError("defeasible epistemic scope requires TemporalContext")
        if not isinstance(relation_semantics, RelationSemanticsRegistry):
            raise TypeError("defeasible epistemic scope requires RelationSemanticsRegistry")
        if not isinstance(justifications, KnowledgeJustificationRegistry):
            raise TypeError("defeasible epistemic scope requires KnowledgeJustificationRegistry")
        if not isinstance(undercutters, JustificationUndercutterRegistry):
            raise TypeError("defeasible epistemic scope requires JustificationUndercutterRegistry")

        target = str(claim_id)
        knowledge.get(target)
        lineage = self._dependency_lineage_claim_ids(
            target,
            knowledge=knowledge,
            justifications=justifications,
            undercutters=undercutters,
        )
        scope_claim_ids = self._scope_claim_ids(
            target,
            temporal_context=temporal_context,
            knowledge=knowledge,
            relation_semantics=relation_semantics,
            knowledge_temporal=knowledge_temporal,
            justifications=justifications,
            undercutters=undercutters,
        )
        justification_evidence_ids = justifications.evidence_ids_for_claims(
            scope_claim_ids,
            knowledge=knowledge,
        )
        undercutter_evidence_ids = undercutters.evidence_ids_for_claims(scope_claim_ids)
        evidence_ids = tuple(sorted(set(justification_evidence_ids) | set(undercutter_evidence_ids)))
        relation_ids = knowledge.relations_for_claims(scope_claim_ids)

        memo: dict[str, TruthScopeAssessment] = {}
        status_map: dict[str, DefeasibleJustificationStatus] = {}
        attack_map: dict[str, UndercutterStatus] = {}
        debt_map: dict[str, EpistemicDebt] = {}
        for current in scope_claim_ids:
            self._assess(
                current,
                temporal_context=temporal_context,
                knowledge=knowledge,
                evidence=evidence,
                knowledge_temporal=knowledge_temporal,
                evidence_temporal=evidence_temporal,
                justifications=justifications,
                undercutters=undercutters,
                memo=memo,
                status_map=status_map,
                attack_map=attack_map,
                debt_map=debt_map,
            )
        assessments = tuple(memo[current] for current in scope_claim_ids)

        for assessment in assessments:
            if assessment.disposition in {
                EpistemicDisposition.UNKNOWN,
                EpistemicDisposition.CONTRADICTED,
            }:
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
        decision_evidence_ids = self._decision_evidence_ids(
            target,
            knowledge=knowledge,
            evidence=evidence,
            justifications=justifications,
            undercutters=undercutters,
            status_map=status_map,
            attack_map=attack_map,
        )
        decision_source_ids: set[str] = set()
        for evidence_id in decision_evidence_ids:
            try:
                decision_source_ids.add(evidence.get(evidence_id).source_id)
            except KeyError:
                continue

        sources = tuple(sorted(source_ids))
        decision_sources = tuple(sorted(decision_source_ids))
        return DefeasibleTruthScope.create(
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
            undercutter_digest=undercutters.projection_digest(
                scope_claim_ids,
                knowledge=knowledge,
            ),
            source_ids=sources,
            decision_source_ids=decision_sources,
            source_provenance_digest=source_provenance.projection_digest(sources),
            temporal_context_digest=temporal_context.digest,
            as_of=temporal_context.as_of,
            assessments=assessments,
            justification_statuses=tuple(status_map.values()),
            undercutter_statuses=tuple(attack_map.values()),
            contradictions=tuple(contradictions),
            debts=tuple(debt_map.values()),
        )

    def validate_scope(
        self,
        scope: DefeasibleTruthScope,
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
    ) -> bool:
        if not isinstance(scope, DefeasibleTruthScope):
            return False
        if scope.binding_mode != DEFEASIBLE_BINDING_MODE:
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
                undercutters=undercutters,
            )
        except (KeyError, TypeError, ValueError):
            return False
        return canonical == scope


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "DEFEASIBLE_BINDING_MODE",
    "UndercutterStatus",
    "DefeasibleJustificationStatus",
    "DefeasibleTruthScope",
    "DefeasibleEpistemicJudge",
)
