from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from .epistemic_observation_fitness_truth import FITNESS_BINDING_MODE, ObservationFitnessTruthScope
from .evidence_context_truth import EvidenceContextBindingRegistry
from .evidence_dependence_truth import SourceDependenceRegistry
from .evidence_observation_fitness_truth import ObservationFitnessAssessmentLedger
from .evidence_observation_truth import ObservationResultLedger
from .evidence_provenance_truth import SourceProvenanceRegistry
from .evidence_temporal_truth import TemporalEvidenceView
from .evidence_truth import EvidenceChannel, EvidenceLedger
from .knowledge_context_truth import ClaimContextBindingRegistry, TruthContext
from .knowledge_observation_fitness_truth import ObservationFitnessRequirementRegistry
from .knowledge_observation_truth import ObservationRequirement, ObservationRequirementRegistry
from .temporal_truth import TemporalContext
from .verification_observation_truth import (
    ObservationTruthVerificationLedger,
    ObservationTruthVerificationReceipt,
)

PARENT_COMPONENT_ID = "external.verification"
TRUTH_PROTOCOL = "truth-verification-fitness-observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v11"
PROJECTION_PROTOCOL = "truth-verification-fitness-observation-projection-v11"


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
class ObservationFitnessTruthVerificationReceipt:
    receipt_id: str
    claim_id: str
    verifier_id: str
    channel: EvidenceChannel
    passed: bool
    scope_digest: str
    truth_context_digest: str
    temporal_context_digest: str
    as_of: str
    observation_requirement_digest: str
    observation_result_digest: str
    fitness_requirement_digest: str
    fitness_assessment_digest: str
    evidence_ids: tuple[str, ...]
    source_provenance_digest: str
    source_dependence_digest: str
    evidence_context_digest: str
    digest: str
    binding_mode: str = FITNESS_BINDING_MODE

    @classmethod
    def create(cls, *, receipt_id: str, claim_id: str, verifier_id: str,
               channel: EvidenceChannel, passed: bool, scope_digest: str,
               truth_context_digest: str, temporal_context_digest: str, as_of: str,
               observation_requirement_digest: str, observation_result_digest: str,
               fitness_requirement_digest: str, fitness_assessment_digest: str,
               evidence_ids: tuple[str, ...], source_provenance_digest: str,
               source_dependence_digest: str, evidence_context_digest: str) -> "ObservationFitnessTruthVerificationReceipt":
        temporal = TemporalContext.create(as_of=as_of)
        if temporal.digest != _explicit(temporal_context_digest, "fitness verification temporal-context digest"):
            raise ValueError("fitness verification temporal context digest mismatch")
        channel = EvidenceChannel(channel)
        evidence_ids = _ids(tuple(evidence_ids), "fitness verification evidence ids")
        payload = {
            "protocol": TRUTH_PROTOCOL, "binding_mode": FITNESS_BINDING_MODE,
            "receipt_id": _explicit(receipt_id, "fitness verification receipt id"),
            "claim_id": _explicit(claim_id, "fitness verification claim id"),
            "verifier_id": _explicit(verifier_id, "fitness verifier id"),
            "channel": channel.value, "passed": bool(passed),
            "scope_digest": _explicit(scope_digest, "fitness verification scope digest"),
            "truth_context_digest": _explicit(truth_context_digest, "fitness verification truth-context digest"),
            "temporal_context_digest": temporal.digest, "as_of": temporal.as_of,
            "observation_requirement_digest": _explicit(observation_requirement_digest, "observation requirement digest"),
            "observation_result_digest": _explicit(observation_result_digest, "observation result digest"),
            "fitness_requirement_digest": _explicit(fitness_requirement_digest, "fitness requirement digest"),
            "fitness_assessment_digest": _explicit(fitness_assessment_digest, "fitness assessment digest"),
            "evidence_ids": list(evidence_ids),
            "source_provenance_digest": _explicit(source_provenance_digest, "fitness verifier provenance digest"),
            "source_dependence_digest": _explicit(source_dependence_digest, "fitness verifier dependence digest"),
            "evidence_context_digest": _explicit(evidence_context_digest, "fitness verifier evidence-context digest"),
        }
        return cls(payload["receipt_id"], payload["claim_id"], payload["verifier_id"], channel,
                   bool(passed), payload["scope_digest"], payload["truth_context_digest"], temporal.digest,
                   temporal.as_of, payload["observation_requirement_digest"], payload["observation_result_digest"],
                   payload["fitness_requirement_digest"], payload["fitness_assessment_digest"], evidence_ids,
                   payload["source_provenance_digest"], payload["source_dependence_digest"],
                   payload["evidence_context_digest"], canonical_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {"protocol": TRUTH_PROTOCOL, "binding_mode": self.binding_mode, "receipt_id": self.receipt_id,
                "claim_id": self.claim_id, "verifier_id": self.verifier_id, "channel": self.channel.value,
                "passed": self.passed, "scope_digest": self.scope_digest,
                "truth_context_digest": self.truth_context_digest, "temporal_context_digest": self.temporal_context_digest,
                "as_of": self.as_of, "observation_requirement_digest": self.observation_requirement_digest,
                "observation_result_digest": self.observation_result_digest,
                "fitness_requirement_digest": self.fitness_requirement_digest,
                "fitness_assessment_digest": self.fitness_assessment_digest, "evidence_ids": list(self.evidence_ids),
                "source_provenance_digest": self.source_provenance_digest,
                "source_dependence_digest": self.source_dependence_digest,
                "evidence_context_digest": self.evidence_context_digest, "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ObservationFitnessTruthVerificationReceipt":
        allowed = {"protocol","binding_mode","receipt_id","claim_id","verifier_id","channel","passed","scope_digest",
                   "truth_context_digest","temporal_context_digest","as_of","observation_requirement_digest",
                   "observation_result_digest","fitness_requirement_digest","fitness_assessment_digest","evidence_ids",
                   "source_provenance_digest","source_dependence_digest","evidence_context_digest","digest"}
        _unexpected(state, allowed, "fitness verification receipt")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported fitness verification protocol")
        if str(state.get("binding_mode", "")) != FITNESS_BINDING_MODE:
            raise ValueError("unsupported fitness verification binding mode")
        row = cls.create(receipt_id=str(state["receipt_id"]), claim_id=str(state["claim_id"]),
                         verifier_id=str(state["verifier_id"]), channel=EvidenceChannel(str(state["channel"])),
                         passed=bool(state["passed"]), scope_digest=str(state["scope_digest"]),
                         truth_context_digest=str(state["truth_context_digest"]),
                         temporal_context_digest=str(state["temporal_context_digest"]), as_of=str(state["as_of"]),
                         observation_requirement_digest=str(state["observation_requirement_digest"]),
                         observation_result_digest=str(state["observation_result_digest"]),
                         fitness_requirement_digest=str(state["fitness_requirement_digest"]),
                         fitness_assessment_digest=str(state["fitness_assessment_digest"]),
                         evidence_ids=tuple(str(v) for v in state.get("evidence_ids", ())),
                         source_provenance_digest=str(state["source_provenance_digest"]),
                         source_dependence_digest=str(state["source_dependence_digest"]),
                         evidence_context_digest=str(state["evidence_context_digest"]))
        if str(state["digest"]) != row.digest:
            raise ValueError("fitness verification receipt digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class ObservationFitnessTruthVerificationCoverage:
    receipts: tuple[ObservationFitnessTruthVerificationReceipt, ...]
    valid_receipt_ids: tuple[str, ...]
    invalid_receipt_ids: tuple[str, ...]
    negative_receipt_ids: tuple[str, ...]
    non_independent_receipt_ids: tuple[str, ...]
    passing_independence_keys: tuple[str, ...]
    passing_channels: tuple[EvidenceChannel, ...]
    issues: tuple[str, ...]
    @property
    def independent_source_count(self) -> int: return len(self.passing_independence_keys)
    @property
    def channel_count(self) -> int: return len(self.passing_channels)


class ObservationFitnessTruthVerificationLedger:
    def __init__(self) -> None:
        self._receipts: dict[str, ObservationFitnessTruthVerificationReceipt] = {}

    def record(self, row: ObservationFitnessTruthVerificationReceipt) -> ObservationFitnessTruthVerificationReceipt:
        if not isinstance(row, ObservationFitnessTruthVerificationReceipt):
            raise TypeError("fitness verification ledger accepts v11 receipts only")
        old = self._receipts.get(row.receipt_id)
        if old is not None and old != row:
            raise ValueError("fitness verification receipt id collision")
        self._receipts[row.receipt_id] = row
        return row

    def receipts(self, claim_id: str | None = None) -> tuple[ObservationFitnessTruthVerificationReceipt, ...]:
        rows = tuple(self._receipts.values())
        if claim_id is not None: rows = tuple(row for row in rows if row.claim_id == str(claim_id))
        return tuple(sorted(rows, key=lambda row: row.receipt_id))

    @staticmethod
    def receipt_is_current(row: ObservationFitnessTruthVerificationReceipt, *, scope: ObservationFitnessTruthScope,
                           truth_context: TruthContext, temporal_context: TemporalContext) -> bool:
        return isinstance(row, ObservationFitnessTruthVerificationReceipt) and isinstance(scope, ObservationFitnessTruthScope) and (
            row.binding_mode == FITNESS_BINDING_MODE and scope.binding_mode == FITNESS_BINDING_MODE and
            row.claim_id == scope.target_claim_id and row.scope_digest == scope.digest and
            scope.truth_context == truth_context and row.truth_context_digest == truth_context.digest and
            row.temporal_context_digest == temporal_context.digest == scope.temporal_context_digest and
            row.as_of == temporal_context.as_of == scope.as_of and
            row.observation_requirement_digest == scope.observation_requirement_digest and
            row.observation_result_digest == scope.observation_result_digest and
            row.fitness_requirement_digest == scope.fitness_requirement_digest and
            row.fitness_assessment_digest == scope.fitness_assessment_digest)

    def current_receipts(self, claim_id: str, *, scope: ObservationFitnessTruthScope,
                         truth_context: TruthContext, temporal_context: TemporalContext) -> tuple[ObservationFitnessTruthVerificationReceipt, ...]:
        return tuple(row for row in self.receipts(claim_id) if self.receipt_is_current(row, scope=scope,
                     truth_context=truth_context, temporal_context=temporal_context))

    @staticmethod
    def _observation_rows(scope: ObservationFitnessTruthScope, registry: ObservationRequirementRegistry) -> tuple[ObservationRequirement, ...]:
        return tuple(sorted((r for cid in scope.lineage_claim_ids for r in registry.requirements(cid)),
                            key=lambda r: (r.observation_id, r.digest)))

    @classmethod
    def _fitness_issue(cls, scope: ObservationFitnessTruthScope, *, observation_requirements: ObservationRequirementRegistry,
                       observation_results: ObservationResultLedger, fitness_requirements: ObservationFitnessRequirementRegistry,
                       fitness_assessments: ObservationFitnessAssessmentLedger, evidence: EvidenceLedger) -> str | None:
        observations = cls._observation_rows(scope, observation_requirements)
        if scope.fitness_requirement_digest != fitness_requirements.projection_digest(observations):
            return "verification_fitness_requirements_stale"
        constrained = tuple(sorted((r for o in observations for r in (fitness_requirements.constraint(o),) if r is not None),
                                   key=lambda r: (r.observation_id, r.digest)))
        if scope.fitness_requirement_digests != tuple(sorted(r.digest for r in constrained)):
            return "verification_fitness_requirements_stale"
        digest = fitness_assessments.projection_digest(constrained, observation_results=observation_results, evidence=evidence)
        if scope.fitness_assessment_digest != digest:
            return "verification_fitness_assessments_stale"
        return None

    @staticmethod
    def _to_v10(row: ObservationFitnessTruthVerificationReceipt, scope: ObservationFitnessTruthScope) -> ObservationTruthVerificationReceipt:
        audit = scope.audit_observation_scope
        return ObservationTruthVerificationReceipt.create(
            receipt_id=row.receipt_id, claim_id=row.claim_id, verifier_id=row.verifier_id, channel=row.channel,
            passed=row.passed, scope_digest=audit.digest, truth_context_digest=row.truth_context_digest,
            temporal_context_digest=row.temporal_context_digest, as_of=row.as_of,
            observation_requirement_digest=audit.observation_requirement_digest,
            observation_result_digest=audit.observation_result_digest, evidence_ids=row.evidence_ids,
            source_provenance_digest=row.source_provenance_digest, source_dependence_digest=row.source_dependence_digest,
            evidence_context_digest=row.evidence_context_digest)

    def as_v10_ledger(self, *, scope: ObservationFitnessTruthScope, truth_context: TruthContext,
                      temporal_context: TemporalContext) -> ObservationTruthVerificationLedger:
        ledger = ObservationTruthVerificationLedger()
        for row in self.current_receipts(scope.target_claim_id, scope=scope, truth_context=truth_context,
                                         temporal_context=temporal_context):
            ledger.record(self._to_v10(row, scope))
        return ledger

    def coverage(self, claim_id: str, *, scope: ObservationFitnessTruthScope, truth_context: TruthContext,
                 temporal_context: TemporalContext, evidence: EvidenceLedger, evidence_temporal: TemporalEvidenceView,
                 source_provenance: SourceProvenanceRegistry, source_dependence: SourceDependenceRegistry,
                 claim_context: ClaimContextBindingRegistry, evidence_context: EvidenceContextBindingRegistry,
                 observation_requirements: ObservationRequirementRegistry, observation_results: ObservationResultLedger,
                 fitness_requirements: ObservationFitnessRequirementRegistry,
                 fitness_assessments: ObservationFitnessAssessmentLedger) -> ObservationFitnessTruthVerificationCoverage:
        rows = self.current_receipts(claim_id, scope=scope, truth_context=truth_context, temporal_context=temporal_context)
        issue = self._fitness_issue(scope, observation_requirements=observation_requirements,
                                    observation_results=observation_results, fitness_requirements=fitness_requirements,
                                    fitness_assessments=fitness_assessments, evidence=evidence)
        if issue is not None:
            return ObservationFitnessTruthVerificationCoverage(rows, (), tuple(r.receipt_id for r in rows), (), (), (), (), (issue,))
        base = self.as_v10_ledger(scope=scope, truth_context=truth_context, temporal_context=temporal_context).coverage(
            claim_id, scope=scope.audit_observation_scope, truth_context=truth_context, temporal_context=temporal_context,
            evidence=evidence, evidence_temporal=evidence_temporal, source_provenance=source_provenance,
            source_dependence=source_dependence, claim_context=claim_context, evidence_context=evidence_context,
            observation_requirements=observation_requirements, observation_results=observation_results)
        return ObservationFitnessTruthVerificationCoverage(rows, base.valid_receipt_ids, base.invalid_receipt_ids,
            base.negative_receipt_ids, base.non_independent_receipt_ids, base.passing_independence_keys,
            base.passing_channels, base.issues)

    def scoped_digest(self, claim_id: str, *, scope: ObservationFitnessTruthScope,
                      truth_context: TruthContext, temporal_context: TemporalContext) -> str:
        rows = self.current_receipts(claim_id, scope=scope, truth_context=truth_context, temporal_context=temporal_context)
        return canonical_digest({"protocol": PROJECTION_PROTOCOL, "binding_mode": FITNESS_BINDING_MODE,
            "claim_id": str(claim_id), "scope_digest": scope.digest, "truth_context_digest": truth_context.digest,
            "temporal_context_digest": temporal_context.digest, "as_of": temporal_context.as_of,
            "observation_requirement_digest": scope.observation_requirement_digest,
            "observation_result_digest": scope.observation_result_digest,
            "fitness_requirement_digest": scope.fitness_requirement_digest,
            "fitness_assessment_digest": scope.fitness_assessment_digest,
            "receipts": [r.to_state() for r in rows]})

    def to_state(self) -> dict[str, Any]:
        return {"protocol": TRUTH_PROTOCOL, "receipts": [r.to_state() for r in self.receipts()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ObservationFitnessTruthVerificationLedger":
        _unexpected(state, {"protocol","receipts"}, "fitness verification ledger")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL: raise ValueError("unsupported fitness verification protocol")
        ledger, seen = cls(), set()
        for value in state.get("receipts", ()):
            row = ObservationFitnessTruthVerificationReceipt.from_state(value)
            if row.receipt_id in seen: raise ValueError("duplicate serialized fitness verification receipt")
            seen.add(row.receipt_id); ledger.record(row)
        return ledger


__all__ = ("PARENT_COMPONENT_ID","TRUTH_PROTOCOL","PROJECTION_PROTOCOL",
           "ObservationFitnessTruthVerificationReceipt","ObservationFitnessTruthVerificationCoverage",
           "ObservationFitnessTruthVerificationLedger")
