from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.knowledge import RelationSemanticsRegistry
from .assurance_observation_truth import ObservationTruthAssuranceGate
from .epistemic_observation_fitness_truth import (
    FITNESS_BINDING_MODE,
    ObservationFitnessEpistemicJudge,
    ObservationFitnessTruthScope,
)
from .epistemic_truth import EpistemicDisposition
from .evidence_context_truth import EvidenceContextBindingRegistry
from .evidence_dependence_truth import SourceDependenceRegistry
from .evidence_observation_fitness_truth import ObservationFitnessAssessmentLedger
from .evidence_observation_truth import ObservationResultLedger
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceLedger
from .knowledge_context_truth import ClaimContextBindingRegistry, TruthContext
from .knowledge_justification_truth import KnowledgeJustificationRegistry
from .knowledge_observation_fitness_truth import ObservationFitnessRequirementRegistry
from .knowledge_observation_truth import ObservationRequirementRegistry
from .knowledge_temporal_truth import TemporalKnowledgeView
from .knowledge_truth import KnowledgeLedger, KnowledgeRisk
from .knowledge_undercutter_truth import JustificationUndercutterRegistry
from .temporal_truth import TemporalContext
from .verification_observation_fitness_truth import ObservationFitnessTruthVerificationLedger

PARENT_COMPONENT_ID = "external.assurance"
TRUTH_PROTOCOL = "truth-assurance-fitness-observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v11"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value: raise ValueError(f"{field} must be explicit")
    return value


def _ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    rows = tuple(sorted(str(v).strip() for v in values))
    if any(not v for v in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be explicit and unique")
    return rows


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra: raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class ObservationFitnessTruthClosureCertificate:
    certificate_id: str
    claim_id: str
    risk: KnowledgeRisk
    scope_digest: str
    verification_scope_digest: str
    truth_context_digest: str
    temporal_context_digest: str
    as_of: str
    observation_requirement_digest: str
    observation_result_digest: str
    fitness_requirement_digest: str
    fitness_assessment_digest: str
    verification_receipt_ids: tuple[str, ...]
    epistemic_debt_ids: tuple[str, ...]
    closed: bool
    reasons: tuple[str, ...]
    digest: str
    binding_mode: str = FITNESS_BINDING_MODE

    @classmethod
    def create(cls, *, claim_id: str, risk: KnowledgeRisk, scope_digest: str,
               verification_scope_digest: str, truth_context_digest: str,
               temporal_context_digest: str, as_of: str,
               observation_requirement_digest: str, observation_result_digest: str,
               fitness_requirement_digest: str, fitness_assessment_digest: str,
               verification_receipt_ids: tuple[str, ...], epistemic_debt_ids: tuple[str, ...],
               closed: bool, reasons: tuple[str, ...]) -> "ObservationFitnessTruthClosureCertificate":
        temporal = TemporalContext.create(as_of=as_of)
        if temporal.digest != _explicit(temporal_context_digest, "fitness closure temporal-context digest"):
            raise ValueError("fitness closure temporal context digest mismatch")
        receipt_ids = _ids(tuple(verification_receipt_ids), "fitness verification receipt ids")
        debt_ids = _ids(tuple(epistemic_debt_ids), "fitness epistemic debt ids")
        reasons = tuple(sorted(str(v).strip() for v in reasons))
        if any(not v for v in reasons) or len(set(reasons)) != len(reasons):
            raise ValueError("fitness closure reasons must be explicit and unique")
        if bool(closed) != (not reasons):
            raise ValueError("fitness closure decision and reasons are inconsistent")
        risk = KnowledgeRisk(risk)
        payload = {"protocol": TRUTH_PROTOCOL, "binding_mode": FITNESS_BINDING_MODE,
            "claim_id": _explicit(claim_id, "fitness closure claim id"), "risk": risk.value,
            "scope_digest": _explicit(scope_digest, "fitness closure scope digest"),
            "verification_scope_digest": _explicit(verification_scope_digest, "fitness verification projection digest"),
            "truth_context_digest": _explicit(truth_context_digest, "fitness closure truth-context digest"),
            "temporal_context_digest": temporal.digest, "as_of": temporal.as_of,
            "observation_requirement_digest": _explicit(observation_requirement_digest, "observation requirement digest"),
            "observation_result_digest": _explicit(observation_result_digest, "observation result digest"),
            "fitness_requirement_digest": _explicit(fitness_requirement_digest, "fitness requirement digest"),
            "fitness_assessment_digest": _explicit(fitness_assessment_digest, "fitness assessment digest"),
            "verification_receipt_ids": list(receipt_ids), "epistemic_debt_ids": list(debt_ids),
            "closed": bool(closed), "reasons": list(reasons)}
        digest = canonical_digest(payload)
        return cls(f"truth-fitness-closure-{digest[:24]}", payload["claim_id"], risk, payload["scope_digest"],
                   payload["verification_scope_digest"], payload["truth_context_digest"], temporal.digest, temporal.as_of,
                   payload["observation_requirement_digest"], payload["observation_result_digest"],
                   payload["fitness_requirement_digest"], payload["fitness_assessment_digest"], receipt_ids, debt_ids,
                   bool(closed), reasons, digest)

    def to_state(self) -> dict[str, Any]:
        return {"certificate_id": self.certificate_id, "protocol": TRUTH_PROTOCOL, "binding_mode": self.binding_mode,
                "claim_id": self.claim_id, "risk": self.risk.value, "scope_digest": self.scope_digest,
                "verification_scope_digest": self.verification_scope_digest,
                "truth_context_digest": self.truth_context_digest, "temporal_context_digest": self.temporal_context_digest,
                "as_of": self.as_of, "observation_requirement_digest": self.observation_requirement_digest,
                "observation_result_digest": self.observation_result_digest,
                "fitness_requirement_digest": self.fitness_requirement_digest,
                "fitness_assessment_digest": self.fitness_assessment_digest,
                "verification_receipt_ids": list(self.verification_receipt_ids),
                "epistemic_debt_ids": list(self.epistemic_debt_ids), "closed": self.closed,
                "reasons": list(self.reasons), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ObservationFitnessTruthClosureCertificate":
        allowed = {"certificate_id","protocol","binding_mode","claim_id","risk","scope_digest","verification_scope_digest",
                   "truth_context_digest","temporal_context_digest","as_of","observation_requirement_digest",
                   "observation_result_digest","fitness_requirement_digest","fitness_assessment_digest",
                   "verification_receipt_ids","epistemic_debt_ids","closed","reasons","digest"}
        _unexpected(state, allowed, "fitness assurance certificate")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL: raise ValueError("unsupported fitness assurance protocol")
        if str(state.get("binding_mode", "")) != FITNESS_BINDING_MODE: raise ValueError("unsupported fitness assurance binding mode")
        row = cls.create(claim_id=str(state["claim_id"]), risk=KnowledgeRisk(str(state["risk"])),
            scope_digest=str(state["scope_digest"]), verification_scope_digest=str(state["verification_scope_digest"]),
            truth_context_digest=str(state["truth_context_digest"]), temporal_context_digest=str(state["temporal_context_digest"]),
            as_of=str(state["as_of"]), observation_requirement_digest=str(state["observation_requirement_digest"]),
            observation_result_digest=str(state["observation_result_digest"]),
            fitness_requirement_digest=str(state["fitness_requirement_digest"]),
            fitness_assessment_digest=str(state["fitness_assessment_digest"]),
            verification_receipt_ids=tuple(str(v) for v in state.get("verification_receipt_ids", ())),
            epistemic_debt_ids=tuple(str(v) for v in state.get("epistemic_debt_ids", ())),
            closed=bool(state["closed"]), reasons=tuple(str(v) for v in state.get("reasons", ())))
        if str(state["certificate_id"]) != row.certificate_id or str(state["digest"]) != row.digest:
            raise ValueError("fitness assurance certificate digest mismatch")
        return row


class ObservationFitnessTruthAssuranceGate:
    """A17 live closure: exact fitness state plus inherited A16 risk/independence law."""

    def _scope(self, claim_id: str, **kwargs: Any) -> ObservationFitnessTruthScope:
        return ObservationFitnessEpistemicJudge().relation_aware_temporal_scope(str(claim_id), **kwargs)

    def close(self, *, claim_id: str, truth_context: TruthContext, temporal_context: TemporalContext,
              knowledge: KnowledgeLedger, evidence: EvidenceLedger, relation_semantics: RelationSemanticsRegistry,
              knowledge_temporal: TemporalKnowledgeView, evidence_temporal: TemporalEvidenceView,
              source_provenance: SourceProvenanceRegistry, source_dependence: SourceDependenceRegistry,
              justifications: KnowledgeJustificationRegistry, undercutters: JustificationUndercutterRegistry,
              claim_context: ClaimContextBindingRegistry, evidence_context: EvidenceContextBindingRegistry,
              observation_requirements: ObservationRequirementRegistry, observation_results: ObservationResultLedger,
              fitness_requirements: ObservationFitnessRequirementRegistry,
              fitness_assessments: ObservationFitnessAssessmentLedger,
              verification: ObservationFitnessTruthVerificationLedger) -> ObservationFitnessTruthClosureCertificate:
        if not isinstance(verification, ObservationFitnessTruthVerificationLedger):
            raise TypeError("fitness assurance requires v11 verification ledger")
        scope_kwargs = dict(truth_context=truth_context, temporal_context=temporal_context, knowledge=knowledge,
            evidence=evidence, relation_semantics=relation_semantics, knowledge_temporal=knowledge_temporal,
            evidence_temporal=evidence_temporal, source_provenance=source_provenance, source_dependence=source_dependence,
            justifications=justifications, undercutters=undercutters, claim_context=claim_context,
            evidence_context=evidence_context, observation_requirements=observation_requirements,
            observation_results=observation_results, fitness_requirements=fitness_requirements,
            fitness_assessments=fitness_assessments)
        scope = self._scope(claim_id, **scope_kwargs)
        base_verification = verification.as_v10_ledger(scope=scope, truth_context=truth_context, temporal_context=temporal_context)
        base = ObservationTruthAssuranceGate().close(
            claim_id=str(claim_id), truth_context=truth_context, temporal_context=temporal_context, knowledge=knowledge,
            evidence=evidence, relation_semantics=relation_semantics, knowledge_temporal=knowledge_temporal,
            evidence_temporal=evidence_temporal, source_provenance=source_provenance, source_dependence=source_dependence,
            justifications=justifications, undercutters=undercutters, claim_context=claim_context,
            evidence_context=evidence_context, observation_requirements=observation_requirements,
            observation_results=observation_results, verification=base_verification)
        reasons = set(base.reasons)
        target = scope.assessment(scope.target_claim_id)
        if target.disposition is not EpistemicDisposition.SUPPORTED: reasons.add("epistemic_claim_not_supported")
        if scope.unfit_fitness_observation_ids: reasons.add("observation_fitness_invalid")
        if any(d.critical for d in scope.fitness_debts): reasons.add("critical_fitness_debt")
        coverage = verification.coverage(scope.target_claim_id, scope=scope, truth_context=truth_context,
            temporal_context=temporal_context, evidence=evidence, evidence_temporal=evidence_temporal,
            source_provenance=source_provenance, source_dependence=source_dependence, claim_context=claim_context,
            evidence_context=evidence_context, observation_requirements=observation_requirements,
            observation_results=observation_results, fitness_requirements=fitness_requirements,
            fitness_assessments=fitness_assessments)
        if any("fitness" in issue for issue in coverage.issues): reasons.add("verification_fitness_invalid")
        valid = set(coverage.valid_receipt_ids)
        passing_ids = tuple(sorted(r.receipt_id for r in coverage.receipts if r.receipt_id in valid and r.passed))
        projection = verification.scoped_digest(scope.target_claim_id, scope=scope, truth_context=truth_context,
                                                temporal_context=temporal_context)
        claim = knowledge.get(scope.target_claim_id)
        return ObservationFitnessTruthClosureCertificate.create(
            claim_id=claim.claim_id, risk=claim.risk, scope_digest=scope.digest, verification_scope_digest=projection,
            truth_context_digest=truth_context.digest, temporal_context_digest=temporal_context.digest,
            as_of=temporal_context.as_of, observation_requirement_digest=scope.observation_requirement_digest,
            observation_result_digest=scope.observation_result_digest, fitness_requirement_digest=scope.fitness_requirement_digest,
            fitness_assessment_digest=scope.fitness_assessment_digest, verification_receipt_ids=passing_ids,
            epistemic_debt_ids=tuple(d.debt_id for d in scope.debts), closed=not reasons, reasons=tuple(reasons))

    def validate_certificate(self, certificate: ObservationFitnessTruthClosureCertificate, **kwargs: Any) -> bool:
        if not isinstance(certificate, ObservationFitnessTruthClosureCertificate): return False
        try: rebuilt = self.close(claim_id=certificate.claim_id, **kwargs)
        except (KeyError, TypeError, ValueError): return False
        return rebuilt == certificate


__all__ = ("PARENT_COMPONENT_ID","TRUTH_PROTOCOL","ObservationFitnessTruthClosureCertificate",
           "ObservationFitnessTruthAssuranceGate")
