from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationSemanticsRegistry
from .epistemic_context_truth import ContextEpistemicJudge, ContextTruthScope
from .epistemic_truth import EpistemicDebt, EpistemicDisposition, TruthScopeAssessment
from .evidence_context_truth import EvidenceContextBindingRegistry
from .evidence_dependence_truth import SourceDependenceRegistry
from .evidence_observation_truth import ObservationOutcome, ObservationResultLedger
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceLedger
from .knowledge_context_truth import ClaimContextBindingRegistry, TruthContext
from .knowledge_justification_truth import KnowledgeJustificationRegistry
from .knowledge_observation_truth import ObservationRequirement, ObservationRequirementRegistry
from .knowledge_temporal_truth import TemporalKnowledgeView
from .knowledge_truth import KnowledgeLedger
from .knowledge_undercutter_truth import JustificationUndercutterRegistry
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.epistemic"
TRUTH_PROTOCOL = (
    "truth-observation-context-dependence-defeasible-justification-provenance-"
    "lineage-temporal-scope-v10"
)
OBSERVATION_BINDING_MODE = (
    "observation-context-dependence-defeasible-justification-provenance-"
    "lineage-temporal-v10"
)

_OUTCOME_REASON = {
    ObservationOutcome.MISSING: "required_observation_missing",
    ObservationOutcome.CENSORED: "required_observation_censored",
    ObservationOutcome.UNAVAILABLE: "required_observation_unavailable",
    ObservationOutcome.TIMEOUT: "required_observation_timeout",
    ObservationOutcome.INTERFERED: "required_observation_interfered",
}


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


def _observation_debt(requirement: ObservationRequirement, reason: str) -> EpistemicDebt:
    payload = {
        "claim_id": requirement.claim_id,
        "observation_id": requirement.observation_id,
        "requirement_digest": requirement.digest,
        "reason": reason,
    }
    digest = canonical_digest(payload)
    return EpistemicDebt.create(
        f"observation-debt-{digest[:24]}",
        claim_id=requirement.claim_id,
        critical=True,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class ObservationTruthScope:
    audit_context_scope: ContextTruthScope
    observation_requirement_digest: str
    observation_result_digest: str
    requirement_digests: tuple[str, ...]
    observation_ids: tuple[str, ...]
    incomplete_observation_ids: tuple[str, ...]
    unrecorded_observation_ids: tuple[str, ...]
    missing_observation_ids: tuple[str, ...]
    censored_observation_ids: tuple[str, ...]
    unavailable_observation_ids: tuple[str, ...]
    timeout_observation_ids: tuple[str, ...]
    interfered_observation_ids: tuple[str, ...]
    assessments: tuple[TruthScopeAssessment, ...]
    observation_debts: tuple[EpistemicDebt, ...]
    debts: tuple[EpistemicDebt, ...]
    digest: str
    binding_mode: str = OBSERVATION_BINDING_MODE

    @classmethod
    def create(
        cls,
        *,
        audit_context_scope: ContextTruthScope,
        observation_requirement_digest: str,
        observation_result_digest: str,
        requirement_digests: tuple[str, ...],
        observation_ids: tuple[str, ...],
        unrecorded_observation_ids: tuple[str, ...] = (),
        missing_observation_ids: tuple[str, ...] = (),
        censored_observation_ids: tuple[str, ...] = (),
        unavailable_observation_ids: tuple[str, ...] = (),
        timeout_observation_ids: tuple[str, ...] = (),
        interfered_observation_ids: tuple[str, ...] = (),
        assessments: tuple[TruthScopeAssessment, ...],
        observation_debts: tuple[EpistemicDebt, ...],
    ) -> "ObservationTruthScope":
        if not isinstance(audit_context_scope, ContextTruthScope):
            raise TypeError("observation scope requires exact v9 context audit scope")
        requirement_digest = _explicit(
            observation_requirement_digest,
            "observation requirement projection digest",
        )
        result_digest = _explicit(
            observation_result_digest,
            "observation result projection digest",
        )
        requirement_digests = _ids(tuple(requirement_digests), "observation requirement digests")
        observation_ids = _ids(tuple(observation_ids), "observation ids")
        unrecorded = _ids(tuple(unrecorded_observation_ids), "unrecorded observation ids")
        missing = _ids(tuple(missing_observation_ids), "missing observation ids")
        censored = _ids(tuple(censored_observation_ids), "censored observation ids")
        unavailable = _ids(tuple(unavailable_observation_ids), "unavailable observation ids")
        timeout = _ids(tuple(timeout_observation_ids), "timeout observation ids")
        interfered = _ids(tuple(interfered_observation_ids), "interfered observation ids")

        partitions = (unrecorded, missing, censored, unavailable, timeout, interfered)
        flattened = tuple(value for rows in partitions for value in rows)
        if len(set(flattened)) != len(flattened):
            raise ValueError("incomplete observation partitions must be disjoint")
        incomplete = tuple(sorted(flattened))
        if not set(incomplete).issubset(set(observation_ids)):
            raise ValueError("incomplete observations must belong to observation scope")

        assessments = tuple(sorted(tuple(assessments), key=lambda row: row.claim_id))
        if (
            len(assessments) != len(audit_context_scope.scope_claim_ids)
            or {row.claim_id for row in assessments} != set(audit_context_scope.scope_claim_ids)
        ):
            raise ValueError("observation assessments must cover exact v9 scope claims")

        observation_debts = tuple(sorted(tuple(observation_debts), key=lambda row: row.debt_id))
        if any(row.claim_id not in audit_context_scope.lineage_claim_ids for row in observation_debts):
            raise ValueError("observation debt must belong to exact target lineage")
        debt_ids = [row.debt_id for row in observation_debts]
        if len(set(debt_ids)) != len(debt_ids):
            raise ValueError("observation debt ids must be unique")
        merged_by_id = {row.debt_id: row for row in audit_context_scope.debts}
        for row in observation_debts:
            old = merged_by_id.get(row.debt_id)
            if old is not None and old != row:
                raise ValueError("observation debt id collision")
            merged_by_id[row.debt_id] = row
        debts = tuple(sorted(merged_by_id.values(), key=lambda row: row.debt_id))

        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": OBSERVATION_BINDING_MODE,
            "audit_context_scope": audit_context_scope.to_state(),
            "observation_requirement_digest": requirement_digest,
            "observation_result_digest": result_digest,
            "requirement_digests": list(requirement_digests),
            "observation_ids": list(observation_ids),
            "incomplete_observation_ids": list(incomplete),
            "unrecorded_observation_ids": list(unrecorded),
            "missing_observation_ids": list(missing),
            "censored_observation_ids": list(censored),
            "unavailable_observation_ids": list(unavailable),
            "timeout_observation_ids": list(timeout),
            "interfered_observation_ids": list(interfered),
            "assessments": [row.to_state() for row in assessments],
            "observation_debts": [row.to_state() for row in observation_debts],
            "debts": [row.to_state() for row in debts],
        }
        return cls(
            audit_context_scope,
            requirement_digest,
            result_digest,
            requirement_digests,
            observation_ids,
            incomplete,
            unrecorded,
            missing,
            censored,
            unavailable,
            timeout,
            interfered,
            assessments,
            observation_debts,
            debts,
            canonical_digest(payload),
        )

    @property
    def target_claim_id(self) -> str:
        return self.audit_context_scope.target_claim_id

    @property
    def lineage_claim_ids(self) -> tuple[str, ...]:
        return self.audit_context_scope.lineage_claim_ids

    @property
    def scope_claim_ids(self) -> tuple[str, ...]:
        return self.audit_context_scope.scope_claim_ids

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return self.audit_context_scope.evidence_ids

    @property
    def relation_ids(self) -> tuple[str, ...]:
        return self.audit_context_scope.relation_ids

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.audit_context_scope.source_ids

    @property
    def decision_source_ids(self) -> tuple[str, ...]:
        return self.audit_context_scope.decision_source_ids

    @property
    def source_provenance_digest(self) -> str:
        return self.audit_context_scope.source_provenance_digest

    @property
    def source_dependence_digest(self) -> str:
        return self.audit_context_scope.source_dependence_digest

    @property
    def claim_context_digest(self) -> str:
        return self.audit_context_scope.claim_context_digest

    @property
    def evidence_context_digest(self) -> str:
        return self.audit_context_scope.evidence_context_digest

    @property
    def truth_context(self) -> TruthContext:
        return self.audit_context_scope.truth_context

    @property
    def temporal_context_digest(self) -> str:
        return self.audit_context_scope.temporal_context_digest

    @property
    def as_of(self) -> str:
        return self.audit_context_scope.as_of

    @property
    def justification_statuses(self):
        return self.audit_context_scope.justification_statuses

    @property
    def undercutter_statuses(self):
        return self.audit_context_scope.undercutter_statuses

    @property
    def contradictions(self):
        return self.audit_context_scope.contradictions

    @property
    def context_mismatch_claim_ids(self) -> tuple[str, ...]:
        return self.audit_context_scope.context_mismatch_claim_ids

    @property
    def context_mismatch_evidence_ids(self) -> tuple[str, ...]:
        return self.audit_context_scope.context_mismatch_evidence_ids

    def assessment(self, claim_id: str) -> TruthScopeAssessment:
        for row in self.assessments:
            if row.claim_id == str(claim_id):
                return row
        raise KeyError(f"claim missing from observation scope: {claim_id}")

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": self.binding_mode,
            "audit_context_scope": self.audit_context_scope.to_state(),
            "observation_requirement_digest": self.observation_requirement_digest,
            "observation_result_digest": self.observation_result_digest,
            "requirement_digests": list(self.requirement_digests),
            "observation_ids": list(self.observation_ids),
            "incomplete_observation_ids": list(self.incomplete_observation_ids),
            "unrecorded_observation_ids": list(self.unrecorded_observation_ids),
            "missing_observation_ids": list(self.missing_observation_ids),
            "censored_observation_ids": list(self.censored_observation_ids),
            "unavailable_observation_ids": list(self.unavailable_observation_ids),
            "timeout_observation_ids": list(self.timeout_observation_ids),
            "interfered_observation_ids": list(self.interfered_observation_ids),
            "assessments": [row.to_state() for row in self.assessments],
            "observation_debts": [row.to_state() for row in self.observation_debts],
            "debts": [row.to_state() for row in self.debts],
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ObservationTruthScope":
        allowed = {
            "protocol",
            "binding_mode",
            "audit_context_scope",
            "observation_requirement_digest",
            "observation_result_digest",
            "requirement_digests",
            "observation_ids",
            "incomplete_observation_ids",
            "unrecorded_observation_ids",
            "missing_observation_ids",
            "censored_observation_ids",
            "unavailable_observation_ids",
            "timeout_observation_ids",
            "interfered_observation_ids",
            "assessments",
            "observation_debts",
            "debts",
            "digest",
        }
        _unexpected(state, allowed, "observation epistemic scope")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported observation epistemic scope protocol")
        if str(state.get("binding_mode", "")) != OBSERVATION_BINDING_MODE:
            raise ValueError("unsupported observation epistemic binding mode")

        row = cls.create(
            audit_context_scope=ContextTruthScope.from_state(state["audit_context_scope"]),
            observation_requirement_digest=str(state["observation_requirement_digest"]),
            observation_result_digest=str(state["observation_result_digest"]),
            requirement_digests=tuple(str(value) for value in state.get("requirement_digests", ())),
            observation_ids=tuple(str(value) for value in state.get("observation_ids", ())),
            unrecorded_observation_ids=tuple(
                str(value) for value in state.get("unrecorded_observation_ids", ())
            ),
            missing_observation_ids=tuple(
                str(value) for value in state.get("missing_observation_ids", ())
            ),
            censored_observation_ids=tuple(
                str(value) for value in state.get("censored_observation_ids", ())
            ),
            unavailable_observation_ids=tuple(
                str(value) for value in state.get("unavailable_observation_ids", ())
            ),
            timeout_observation_ids=tuple(
                str(value) for value in state.get("timeout_observation_ids", ())
            ),
            interfered_observation_ids=tuple(
                str(value) for value in state.get("interfered_observation_ids", ())
            ),
            assessments=tuple(
                TruthScopeAssessment.from_state(value) for value in state.get("assessments", ())
            ),
            observation_debts=tuple(
                EpistemicDebt.from_state(value) for value in state.get("observation_debts", ())
            ),
        )
        if tuple(row.incomplete_observation_ids) != tuple(
            str(value) for value in state.get("incomplete_observation_ids", ())
        ):
            raise ValueError("observation incomplete partition mismatch")
        if [item.to_state() for item in row.debts] != list(state.get("debts", ())):
            raise ValueError("observation merged debt state mismatch")
        if str(state["digest"]) != row.digest:
            raise ValueError("observation epistemic scope digest mismatch")
        return row


class ObservationEpistemicJudge:
    """A16 observation-completeness truth over the exact accepted A15 audit scope."""

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
        observation_requirements: ObservationRequirementRegistry,
        observation_results: ObservationResultLedger,
    ) -> ObservationTruthScope:
        if not isinstance(observation_requirements, ObservationRequirementRegistry):
            raise TypeError("observation epistemic judge requires ObservationRequirementRegistry")
        if not isinstance(observation_results, ObservationResultLedger):
            raise TypeError("observation epistemic judge requires ObservationResultLedger")

        audit = ContextEpistemicJudge().relation_aware_temporal_scope(
            str(claim_id),
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

        requirement_rows = tuple(
            sorted(
                (
                    requirement
                    for lineage_claim_id in audit.lineage_claim_ids
                    for requirement in observation_requirements.requirements(lineage_claim_id)
                ),
                key=lambda row: (row.observation_id, row.digest),
            )
        )
        if len({row.digest for row in requirement_rows}) != len(requirement_rows):
            raise ValueError("observation requirement digest collision in target lineage")
        if len({row.observation_id for row in requirement_rows}) != len(requirement_rows):
            raise ValueError("observation ids must be unique across exact target lineage")

        unrecorded: list[str] = []
        missing: list[str] = []
        censored: list[str] = []
        unavailable: list[str] = []
        timeout: list[str] = []
        interfered: list[str] = []
        observation_debts: list[EpistemicDebt] = []

        partitions = {
            ObservationOutcome.MISSING: missing,
            ObservationOutcome.CENSORED: censored,
            ObservationOutcome.UNAVAILABLE: unavailable,
            ObservationOutcome.TIMEOUT: timeout,
            ObservationOutcome.INTERFERED: interfered,
        }
        for requirement in requirement_rows:
            result = observation_results.current(requirement.digest)
            if result is None:
                unrecorded.append(requirement.observation_id)
                observation_debts.append(
                    _observation_debt(requirement, "required_observation_unrecorded")
                )
                continue
            if result.requirement != requirement:
                raise ValueError("observation result requirement snapshot mismatch")
            if result.outcome is ObservationOutcome.OBSERVED:
                continue
            partitions[result.outcome].append(requirement.observation_id)
            observation_debts.append(_observation_debt(requirement, _OUTCOME_REASON[result.outcome]))

        incomplete = bool(observation_debts)
        target_assessment = audit.assessment(audit.target_claim_id)
        assessments: list[TruthScopeAssessment] = []
        for row in audit.assessments:
            if (
                row.claim_id == audit.target_claim_id
                and row.disposition is EpistemicDisposition.SUPPORTED
                and incomplete
            ):
                assessments.append(
                    TruthScopeAssessment.create(
                        claim_id=row.claim_id,
                        disposition=EpistemicDisposition.UNKNOWN,
                        support_evidence_ids=row.support_evidence_ids,
                        refute_evidence_ids=row.refute_evidence_ids,
                    )
                )
            else:
                assessments.append(row)
        if target_assessment.disposition is not EpistemicDisposition.SUPPORTED:
            # Observation completeness never upgrades an already unsupported v9 target.
            assert next(row for row in assessments if row.claim_id == audit.target_claim_id) == target_assessment

        return ObservationTruthScope.create(
            audit_context_scope=audit,
            observation_requirement_digest=observation_requirements.projection_digest(
                audit.lineage_claim_ids
            ),
            observation_result_digest=observation_results.projection_digest(requirement_rows),
            requirement_digests=tuple(row.digest for row in requirement_rows),
            observation_ids=tuple(row.observation_id for row in requirement_rows),
            unrecorded_observation_ids=tuple(unrecorded),
            missing_observation_ids=tuple(missing),
            censored_observation_ids=tuple(censored),
            unavailable_observation_ids=tuple(unavailable),
            timeout_observation_ids=tuple(timeout),
            interfered_observation_ids=tuple(interfered),
            assessments=tuple(assessments),
            observation_debts=tuple(observation_debts),
        )

    def validate_scope(
        self,
        scope: ObservationTruthScope,
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
        observation_requirements: ObservationRequirementRegistry,
        observation_results: ObservationResultLedger,
    ) -> bool:
        if not isinstance(scope, ObservationTruthScope):
            return False
        try:
            current = self.relation_aware_temporal_scope(
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
                observation_requirements=observation_requirements,
                observation_results=observation_results,
            )
        except (KeyError, TypeError, ValueError):
            return False
        return current == scope


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "OBSERVATION_BINDING_MODE",
    "ObservationTruthScope",
    "ObservationEpistemicJudge",
)
