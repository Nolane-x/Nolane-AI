from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationSemanticsRegistry
from .epistemic_observation_truth import ObservationEpistemicJudge, ObservationTruthScope
from .epistemic_truth import EpistemicDebt, EpistemicDisposition, TruthScopeAssessment
from .evidence_context_truth import EvidenceContextBindingRegistry
from .evidence_dependence_truth import SourceDependenceRegistry
from .evidence_observation_fitness_truth import ObservationFitnessAssessmentLedger
from .evidence_observation_truth import ObservationOutcome, ObservationResultLedger
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceLedger
from .knowledge_context_truth import ClaimContextBindingRegistry, TruthContext
from .knowledge_justification_truth import KnowledgeJustificationRegistry
from .knowledge_observation_fitness_truth import (
    ObservationFitnessRequirementRegistry,
    ObservationFitnessRequirementRevision,
)
from .knowledge_observation_truth import ObservationRequirement, ObservationRequirementRegistry
from .knowledge_temporal_truth import TemporalKnowledgeView
from .knowledge_truth import KnowledgeLedger
from .knowledge_undercutter_truth import JustificationUndercutterRegistry
from .temporal_truth import TemporalContext


PARENT_COMPONENT_ID = "external.epistemic"
TRUTH_PROTOCOL = (
    "truth-fitness-observation-context-dependence-defeasible-justification-provenance-"
    "lineage-temporal-scope-v11"
)
FITNESS_BINDING_MODE = (
    "fitness-observation-context-dependence-defeasible-justification-provenance-"
    "lineage-temporal-v11"
)


def _ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be explicit and unique")
    return rows


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


def _fitness_debt(
    requirement: ObservationFitnessRequirementRevision,
    reason: str,
) -> EpistemicDebt:
    payload = {
        "claim_id": requirement.claim_id,
        "observation_id": requirement.observation_id,
        "fitness_requirement_digest": requirement.digest,
        "reason": reason,
    }
    digest = canonical_digest(payload)
    return EpistemicDebt.create(
        f"fitness-debt-{digest[:24]}",
        claim_id=requirement.claim_id,
        critical=True,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class ObservationFitnessTruthScope:
    audit_observation_scope: ObservationTruthScope
    fitness_requirement_digest: str
    fitness_assessment_digest: str
    fitness_requirement_digests: tuple[str, ...]
    fitness_observation_ids: tuple[str, ...]
    unassessed_fitness_observation_ids: tuple[str, ...]
    failed_fitness_observation_ids: tuple[str, ...]
    indeterminate_fitness_observation_ids: tuple[str, ...]
    inactive_basis_fitness_observation_ids: tuple[str, ...]
    unfit_fitness_observation_ids: tuple[str, ...]
    assessments: tuple[TruthScopeAssessment, ...]
    fitness_debts: tuple[EpistemicDebt, ...]
    debts: tuple[EpistemicDebt, ...]
    digest: str
    binding_mode: str = FITNESS_BINDING_MODE

    @classmethod
    def create(
        cls,
        *,
        audit_observation_scope: ObservationTruthScope,
        fitness_requirement_digest: str,
        fitness_assessment_digest: str,
        fitness_requirement_digests: tuple[str, ...],
        fitness_observation_ids: tuple[str, ...],
        unassessed_fitness_observation_ids: tuple[str, ...] = (),
        failed_fitness_observation_ids: tuple[str, ...] = (),
        indeterminate_fitness_observation_ids: tuple[str, ...] = (),
        inactive_basis_fitness_observation_ids: tuple[str, ...] = (),
        assessments: tuple[TruthScopeAssessment, ...],
        fitness_debts: tuple[EpistemicDebt, ...],
    ) -> "ObservationFitnessTruthScope":
        if not isinstance(audit_observation_scope, ObservationTruthScope):
            raise TypeError("fitness scope requires exact v10 ObservationTruthScope")
        requirement_digest = _explicit(fitness_requirement_digest, "fitness requirement projection digest")
        assessment_digest = _explicit(fitness_assessment_digest, "fitness assessment projection digest")
        requirement_digests = _ids(tuple(fitness_requirement_digests), "fitness requirement digests")
        observation_ids = _ids(tuple(fitness_observation_ids), "fitness observation ids")
        unassessed = _ids(tuple(unassessed_fitness_observation_ids), "unassessed fitness observation ids")
        failed = _ids(tuple(failed_fitness_observation_ids), "failed fitness observation ids")
        indeterminate = _ids(
            tuple(indeterminate_fitness_observation_ids),
            "indeterminate fitness observation ids",
        )
        inactive_basis = _ids(
            tuple(inactive_basis_fitness_observation_ids),
            "inactive-basis fitness observation ids",
        )
        partitions = (unassessed, failed, indeterminate, inactive_basis)
        flattened = tuple(value for rows in partitions for value in rows)
        if len(set(flattened)) != len(flattened):
            raise ValueError("fitness debt partitions must be disjoint")
        unfit = tuple(sorted(flattened))
        if not set(unfit).issubset(set(observation_ids)):
            raise ValueError("unfit observations must belong to exact fitness scope")

        assessments = tuple(sorted(tuple(assessments), key=lambda row: row.claim_id))
        if (
            len(assessments) != len(audit_observation_scope.scope_claim_ids)
            or {row.claim_id for row in assessments} != set(audit_observation_scope.scope_claim_ids)
        ):
            raise ValueError("fitness assessments must cover exact v10 scope claims")

        fitness_debts = tuple(sorted(tuple(fitness_debts), key=lambda row: row.debt_id))
        if any(row.claim_id not in audit_observation_scope.lineage_claim_ids for row in fitness_debts):
            raise ValueError("fitness debt must belong to exact target lineage")
        if len({row.debt_id for row in fitness_debts}) != len(fitness_debts):
            raise ValueError("fitness debt ids must be unique")
        merged = {row.debt_id: row for row in audit_observation_scope.debts}
        for row in fitness_debts:
            old = merged.get(row.debt_id)
            if old is not None and old != row:
                raise ValueError("fitness debt id collision")
            merged[row.debt_id] = row
        debts = tuple(sorted(merged.values(), key=lambda row: row.debt_id))

        payload = {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": FITNESS_BINDING_MODE,
            "audit_observation_scope": audit_observation_scope.to_state(),
            "fitness_requirement_digest": requirement_digest,
            "fitness_assessment_digest": assessment_digest,
            "fitness_requirement_digests": list(requirement_digests),
            "fitness_observation_ids": list(observation_ids),
            "unassessed_fitness_observation_ids": list(unassessed),
            "failed_fitness_observation_ids": list(failed),
            "indeterminate_fitness_observation_ids": list(indeterminate),
            "inactive_basis_fitness_observation_ids": list(inactive_basis),
            "unfit_fitness_observation_ids": list(unfit),
            "assessments": [row.to_state() for row in assessments],
            "fitness_debts": [row.to_state() for row in fitness_debts],
            "debts": [row.to_state() for row in debts],
        }
        return cls(
            audit_observation_scope,
            requirement_digest,
            assessment_digest,
            requirement_digests,
            observation_ids,
            unassessed,
            failed,
            indeterminate,
            inactive_basis,
            unfit,
            assessments,
            fitness_debts,
            debts,
            canonical_digest(payload),
        )

    @property
    def target_claim_id(self) -> str:
        return self.audit_observation_scope.target_claim_id

    @property
    def lineage_claim_ids(self) -> tuple[str, ...]:
        return self.audit_observation_scope.lineage_claim_ids

    @property
    def scope_claim_ids(self) -> tuple[str, ...]:
        return self.audit_observation_scope.scope_claim_ids

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return self.audit_observation_scope.evidence_ids

    @property
    def relation_ids(self) -> tuple[str, ...]:
        return self.audit_observation_scope.relation_ids

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.audit_observation_scope.source_ids

    @property
    def decision_source_ids(self) -> tuple[str, ...]:
        return self.audit_observation_scope.decision_source_ids

    @property
    def truth_context(self) -> TruthContext:
        return self.audit_observation_scope.truth_context

    @property
    def temporal_context_digest(self) -> str:
        return self.audit_observation_scope.temporal_context_digest

    @property
    def as_of(self) -> str:
        return self.audit_observation_scope.as_of

    @property
    def observation_requirement_digest(self) -> str:
        return self.audit_observation_scope.observation_requirement_digest

    @property
    def observation_result_digest(self) -> str:
        return self.audit_observation_scope.observation_result_digest

    @property
    def contradictions(self):
        return self.audit_observation_scope.contradictions

    @property
    def justification_statuses(self):
        return self.audit_observation_scope.justification_statuses

    def assessment(self, claim_id: str) -> TruthScopeAssessment:
        for row in self.assessments:
            if row.claim_id == str(claim_id):
                return row
        raise KeyError(f"claim missing from fitness scope: {claim_id}")

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "binding_mode": self.binding_mode,
            "audit_observation_scope": self.audit_observation_scope.to_state(),
            "fitness_requirement_digest": self.fitness_requirement_digest,
            "fitness_assessment_digest": self.fitness_assessment_digest,
            "fitness_requirement_digests": list(self.fitness_requirement_digests),
            "fitness_observation_ids": list(self.fitness_observation_ids),
            "unassessed_fitness_observation_ids": list(self.unassessed_fitness_observation_ids),
            "failed_fitness_observation_ids": list(self.failed_fitness_observation_ids),
            "indeterminate_fitness_observation_ids": list(self.indeterminate_fitness_observation_ids),
            "inactive_basis_fitness_observation_ids": list(self.inactive_basis_fitness_observation_ids),
            "unfit_fitness_observation_ids": list(self.unfit_fitness_observation_ids),
            "assessments": [row.to_state() for row in self.assessments],
            "fitness_debts": [row.to_state() for row in self.fitness_debts],
            "debts": [row.to_state() for row in self.debts],
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ObservationFitnessTruthScope":
        _unexpected(
            state,
            {
                "protocol",
                "binding_mode",
                "audit_observation_scope",
                "fitness_requirement_digest",
                "fitness_assessment_digest",
                "fitness_requirement_digests",
                "fitness_observation_ids",
                "unassessed_fitness_observation_ids",
                "failed_fitness_observation_ids",
                "indeterminate_fitness_observation_ids",
                "inactive_basis_fitness_observation_ids",
                "unfit_fitness_observation_ids",
                "assessments",
                "fitness_debts",
                "debts",
                "digest",
            },
            "fitness epistemic scope",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported fitness epistemic scope protocol")
        if str(state.get("binding_mode", "")) != FITNESS_BINDING_MODE:
            raise ValueError("unsupported fitness epistemic binding mode")
        row = cls.create(
            audit_observation_scope=ObservationTruthScope.from_state(state["audit_observation_scope"]),
            fitness_requirement_digest=str(state["fitness_requirement_digest"]),
            fitness_assessment_digest=str(state["fitness_assessment_digest"]),
            fitness_requirement_digests=tuple(str(value) for value in state.get("fitness_requirement_digests", ())),
            fitness_observation_ids=tuple(str(value) for value in state.get("fitness_observation_ids", ())),
            unassessed_fitness_observation_ids=tuple(
                str(value) for value in state.get("unassessed_fitness_observation_ids", ())
            ),
            failed_fitness_observation_ids=tuple(
                str(value) for value in state.get("failed_fitness_observation_ids", ())
            ),
            indeterminate_fitness_observation_ids=tuple(
                str(value) for value in state.get("indeterminate_fitness_observation_ids", ())
            ),
            inactive_basis_fitness_observation_ids=tuple(
                str(value) for value in state.get("inactive_basis_fitness_observation_ids", ())
            ),
            assessments=tuple(
                TruthScopeAssessment.from_state(value) for value in state.get("assessments", ())
            ),
            fitness_debts=tuple(EpistemicDebt.from_state(value) for value in state.get("fitness_debts", ())),
        )
        if tuple(row.unfit_fitness_observation_ids) != tuple(
            str(value) for value in state.get("unfit_fitness_observation_ids", ())
        ):
            raise ValueError("fitness unfit partition mismatch")
        if [value.to_state() for value in row.debts] != list(state.get("debts", ())):
            raise ValueError("fitness merged debt state mismatch")
        if str(state["digest"]) != row.digest:
            raise ValueError("fitness epistemic scope digest mismatch")
        return row


class ObservationFitnessEpistemicJudge:
    """A17 measurement-fitness truth over exact accepted A16 observation truth."""

    @staticmethod
    def _lineage_observation_requirements(
        audit: ObservationTruthScope,
        observation_requirements: ObservationRequirementRegistry,
    ) -> tuple[ObservationRequirement, ...]:
        rows = tuple(
            sorted(
                (
                    requirement
                    for claim_id in audit.lineage_claim_ids
                    for requirement in observation_requirements.requirements(claim_id)
                ),
                key=lambda row: (row.observation_id, row.digest),
            )
        )
        if len({row.digest for row in rows}) != len(rows):
            raise ValueError("fitness scope observation requirement digest collision")
        return rows

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
        fitness_requirements: ObservationFitnessRequirementRegistry,
        fitness_assessments: ObservationFitnessAssessmentLedger,
    ) -> ObservationFitnessTruthScope:
        if not isinstance(fitness_requirements, ObservationFitnessRequirementRegistry):
            raise TypeError("fitness epistemic judge requires ObservationFitnessRequirementRegistry")
        if not isinstance(fitness_assessments, ObservationFitnessAssessmentLedger):
            raise TypeError("fitness epistemic judge requires ObservationFitnessAssessmentLedger")

        audit = ObservationEpistemicJudge().relation_aware_temporal_scope(
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
            observation_requirements=observation_requirements,
            observation_results=observation_results,
        )
        observation_rows = self._lineage_observation_requirements(audit, observation_requirements)
        fitness_rows = tuple(
            sorted(
                (
                    row
                    for requirement in observation_rows
                    for row in (fitness_requirements.constraint(requirement),)
                    if row is not None
                ),
                key=lambda row: (row.observation_id, row.digest),
            )
        )
        if len({row.observation_id for row in fitness_rows}) != len(fitness_rows):
            raise ValueError("fitness observation ids must be unique across target lineage")

        unassessed: list[str] = []
        failed: list[str] = []
        indeterminate: list[str] = []
        inactive_basis: list[str] = []
        debts: list[EpistemicDebt] = []
        for fitness_requirement in fitness_rows:
            result = observation_results.current(fitness_requirement.observation_requirement_digest)
            if result is None or result.outcome is not ObservationOutcome.OBSERVED:
                continue
            assessment = fitness_assessments.assessment_for(fitness_requirement, result)
            if assessment is None:
                unassessed.append(fitness_requirement.observation_id)
                debts.append(_fitness_debt(fitness_requirement, "required_observation_fitness_unassessed"))
                continue
            if not fitness_assessments.basis_is_active(assessment, evidence):
                inactive_basis.append(fitness_requirement.observation_id)
                debts.append(_fitness_debt(fitness_requirement, "required_observation_fitness_basis_inactive"))
                continue
            if assessment.has_failure:
                failed.append(fitness_requirement.observation_id)
                debts.append(_fitness_debt(fitness_requirement, "required_observation_fitness_failed"))
                continue
            if assessment.has_unknown:
                indeterminate.append(fitness_requirement.observation_id)
                debts.append(_fitness_debt(fitness_requirement, "required_observation_fitness_indeterminate"))

        has_fitness_debt = bool(debts)
        audit_target = audit.assessment(audit.target_claim_id)
        assessments: list[TruthScopeAssessment] = []
        for row in audit.assessments:
            if (
                row.claim_id == audit.target_claim_id
                and row.disposition is EpistemicDisposition.SUPPORTED
                and has_fitness_debt
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
        if audit_target.disposition is not EpistemicDisposition.SUPPORTED:
            assert next(row for row in assessments if row.claim_id == audit.target_claim_id) == audit_target

        return ObservationFitnessTruthScope.create(
            audit_observation_scope=audit,
            fitness_requirement_digest=fitness_requirements.projection_digest(observation_rows),
            fitness_assessment_digest=fitness_assessments.projection_digest(
                fitness_rows,
                observation_results=observation_results,
                evidence=evidence,
            ),
            fitness_requirement_digests=tuple(row.digest for row in fitness_rows),
            fitness_observation_ids=tuple(row.observation_id for row in fitness_rows),
            unassessed_fitness_observation_ids=tuple(unassessed),
            failed_fitness_observation_ids=tuple(failed),
            indeterminate_fitness_observation_ids=tuple(indeterminate),
            inactive_basis_fitness_observation_ids=tuple(inactive_basis),
            assessments=tuple(assessments),
            fitness_debts=tuple(debts),
        )

    def validate_scope(
        self,
        scope: ObservationFitnessTruthScope,
        **kwargs: Any,
    ) -> bool:
        if not isinstance(scope, ObservationFitnessTruthScope):
            return False
        try:
            current = self.relation_aware_temporal_scope(scope.target_claim_id, **kwargs)
        except (KeyError, TypeError, ValueError):
            return False
        return current == scope


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "FITNESS_BINDING_MODE",
    "ObservationFitnessTruthScope",
    "ObservationFitnessEpistemicJudge",
)
