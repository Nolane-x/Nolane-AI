from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.integration_evolution import (
    ComponentEvolutionDelta,
    EvolutionCompatibilityDisposition,
    EvolutionCompatibilityQualification,
    IntegrationImpactClosure,
    qualify_component_evolution,
)


REVALIDATION_REQUIREMENT_PROTOCOL = "integration-revalidation-requirement-v1"
REVALIDATION_PLAN_PROTOCOL = "integration-revalidation-plan-v1"
REVALIDATION_EVIDENCE_PROTOCOL = "integration-revalidation-evidence-binding-v1"
REVALIDATION_ASSESSMENT_PROTOCOL = "integration-revalidation-assessment-v1"


class RevalidationDisposition(str, Enum):
    CURRENT = "CURRENT"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ComponentRevalidationRequirement:
    component_id: str
    required_evidence_kinds: tuple[str, ...]
    basis_codes: tuple[str, ...]
    requirement_id: str

    @classmethod
    def create(
        cls,
        *,
        component_id: str,
        required_evidence_kinds: tuple[str, ...],
        basis_codes: tuple[str, ...],
    ) -> "ComponentRevalidationRequirement":
        component = _explicit(component_id, "revalidation component")
        kinds = _sorted_unique(required_evidence_kinds, "revalidation evidence kind")
        basis = _sorted_unique(basis_codes, "revalidation basis code")
        if not kinds:
            raise ValueError("revalidation requirement needs at least one evidence kind")
        if not basis:
            raise ValueError("revalidation requirement needs at least one basis code")
        payload = {
            "protocol": REVALIDATION_REQUIREMENT_PROTOCOL,
            "component_id": component,
            "required_evidence_kinds": list(kinds),
            "basis_codes": list(basis),
        }
        return cls(
            component_id=component,
            required_evidence_kinds=kinds,
            basis_codes=basis,
            requirement_id="integration-revalidation-requirement-v1-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": REVALIDATION_REQUIREMENT_PROTOCOL,
            "component_id": self.component_id,
            "required_evidence_kinds": list(self.required_evidence_kinds),
            "basis_codes": list(self.basis_codes),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "requirement_id": self.requirement_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ComponentRevalidationRequirement":
        if state.get("protocol") != REVALIDATION_REQUIREMENT_PROTOCOL:
            raise ValueError("revalidation requirement protocol mismatch")
        kinds = state.get("required_evidence_kinds")
        basis = state.get("basis_codes")
        if not isinstance(kinds, list) or not isinstance(basis, list):
            raise ValueError("revalidation requirement state shape is invalid")
        expected = cls.create(
            component_id=state.get("component_id"),
            required_evidence_kinds=tuple(kinds),
            basis_codes=tuple(basis),
        )
        if state.get("requirement_id") != expected.requirement_id or dict(state) != expected.to_state():
            raise ValueError("revalidation requirement integrity mismatch")
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("revalidation requirement integrity validation failed") from exc
        if restored != self:
            raise ValueError("revalidation requirement integrity validation failed")


@dataclass(frozen=True, slots=True)
class RevalidationPlan:
    delta_id: str
    impact_closure_id: str
    authority_graph_digest: str
    disposition: RevalidationDisposition
    blocker_reason_codes: tuple[str, ...]
    requirements: tuple[ComponentRevalidationRequirement, ...]
    plan_id: str

    @classmethod
    def create(
        cls,
        *,
        delta_id: str,
        impact_closure_id: str,
        authority_graph_digest: str,
        disposition: RevalidationDisposition,
        blocker_reason_codes: tuple[str, ...],
        requirements: tuple[ComponentRevalidationRequirement, ...],
    ) -> "RevalidationPlan":
        delta = _explicit(delta_id, "revalidation delta")
        closure = _explicit(impact_closure_id, "revalidation impact closure")
        graph_digest = _explicit(authority_graph_digest, "revalidation authority graph digest")
        state = RevalidationDisposition(disposition)
        blockers = _sorted_unique(blocker_reason_codes, "revalidation blocker reason")
        canonical_requirements: list[ComponentRevalidationRequirement] = []
        for row in requirements:
            if not isinstance(row, ComponentRevalidationRequirement):
                raise ValueError("revalidation plan requirements must be canonical")
            row.validate_integrity()
            canonical_requirements.append(row)
        ordered_requirements = tuple(sorted(canonical_requirements, key=lambda row: row.component_id))
        if len({row.component_id for row in ordered_requirements}) != len(ordered_requirements):
            raise ValueError("revalidation plan cannot contain duplicate component requirements")
        if state is RevalidationDisposition.BLOCKED and not blockers:
            raise ValueError("blocked revalidation plan requires blocker reasons")
        if state is RevalidationDisposition.REVALIDATION_REQUIRED and not ordered_requirements:
            raise ValueError("revalidation-required plan needs component requirements")
        if state is RevalidationDisposition.CURRENT and (blockers or ordered_requirements):
            raise ValueError("current revalidation plan must not carry blockers or requirements")
        payload = {
            "protocol": REVALIDATION_PLAN_PROTOCOL,
            "delta_id": delta,
            "impact_closure_id": closure,
            "authority_graph_digest": graph_digest,
            "disposition": state.value,
            "blocker_reason_codes": list(blockers),
            "requirements": [row.to_state() for row in ordered_requirements],
        }
        return cls(
            delta_id=delta,
            impact_closure_id=closure,
            authority_graph_digest=graph_digest,
            disposition=state,
            blocker_reason_codes=blockers,
            requirements=ordered_requirements,
            plan_id="integration-revalidation-plan-v1-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": REVALIDATION_PLAN_PROTOCOL,
            "delta_id": self.delta_id,
            "impact_closure_id": self.impact_closure_id,
            "authority_graph_digest": self.authority_graph_digest,
            "disposition": self.disposition.value,
            "blocker_reason_codes": list(self.blocker_reason_codes),
            "requirements": [row.to_state() for row in self.requirements],
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "plan_id": self.plan_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RevalidationPlan":
        if state.get("protocol") != REVALIDATION_PLAN_PROTOCOL:
            raise ValueError("revalidation plan protocol mismatch")
        raw_requirements = state.get("requirements")
        raw_blockers = state.get("blocker_reason_codes")
        if not isinstance(raw_requirements, list) or not isinstance(raw_blockers, list):
            raise ValueError("revalidation plan state shape is invalid")
        requirements: list[ComponentRevalidationRequirement] = []
        for row in raw_requirements:
            if not isinstance(row, Mapping):
                raise ValueError("revalidation requirement state must be an object")
            requirements.append(ComponentRevalidationRequirement.from_state(row))
        try:
            disposition = RevalidationDisposition(state.get("disposition"))
        except (TypeError, ValueError) as exc:
            raise ValueError("revalidation plan disposition is invalid") from exc
        expected = cls.create(
            delta_id=state.get("delta_id"),
            impact_closure_id=state.get("impact_closure_id"),
            authority_graph_digest=state.get("authority_graph_digest"),
            disposition=disposition,
            blocker_reason_codes=tuple(raw_blockers),
            requirements=tuple(requirements),
        )
        if state.get("plan_id") != expected.plan_id or dict(state) != expected.to_state():
            raise ValueError("revalidation plan integrity mismatch")
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("revalidation plan integrity validation failed") from exc
        if restored != self:
            raise ValueError("revalidation plan integrity validation failed")


@dataclass(frozen=True, slots=True)
class RevalidationEvidenceBinding:
    component_id: str
    evidence_kind: str
    evidence: EvidenceRecord
    binding_id: str

    @classmethod
    def create(
        cls,
        *,
        component_id: str,
        evidence_kind: str,
        evidence: EvidenceRecord,
    ) -> "RevalidationEvidenceBinding":
        component = _explicit(component_id, "revalidation evidence component")
        kind = _explicit(evidence_kind, "revalidation evidence kind")
        if not isinstance(evidence, EvidenceRecord):
            raise ValueError("revalidation evidence binding requires an EvidenceRecord")
        if evidence.verifier_agent_id == component:
            raise ValueError("revalidation evidence cannot self-certify its component")
        payload = {
            "protocol": REVALIDATION_EVIDENCE_PROTOCOL,
            "component_id": component,
            "evidence_kind": kind,
            "evidence": evidence.to_state(),
        }
        return cls(component, kind, evidence, "integration-revalidation-evidence-v1-" + canonical_digest(payload))

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": REVALIDATION_EVIDENCE_PROTOCOL,
            "component_id": self.component_id,
            "evidence_kind": self.evidence_kind,
            "evidence": self.evidence.to_state(),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "binding_id": self.binding_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RevalidationEvidenceBinding":
        if state.get("protocol") != REVALIDATION_EVIDENCE_PROTOCOL:
            raise ValueError("revalidation evidence protocol mismatch")
        evidence_state = state.get("evidence")
        if not isinstance(evidence_state, Mapping):
            raise ValueError("revalidation evidence state must be an object")
        expected = cls.create(
            component_id=state.get("component_id"),
            evidence_kind=state.get("evidence_kind"),
            evidence=EvidenceRecord.from_state(evidence_state),
        )
        if state.get("binding_id") != expected.binding_id or dict(state) != expected.to_state():
            raise ValueError("revalidation evidence binding integrity mismatch")
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("revalidation evidence binding integrity validation failed") from exc
        if restored != self:
            raise ValueError("revalidation evidence binding integrity validation failed")


@dataclass(frozen=True, slots=True)
class RevalidationAssessment:
    plan_id: str
    disposition: RevalidationDisposition
    missing_requirements: tuple[str, ...]
    reason_codes: tuple[str, ...]
    evidence_binding_ids: tuple[str, ...]
    assessment_id: str

    @classmethod
    def create(
        cls,
        *,
        plan_id: str,
        disposition: RevalidationDisposition,
        missing_requirements: tuple[str, ...],
        reason_codes: tuple[str, ...],
        evidence_binding_ids: tuple[str, ...],
    ) -> "RevalidationAssessment":
        plan = _explicit(plan_id, "revalidation assessment plan")
        state = RevalidationDisposition(disposition)
        missing = _sorted_unique(missing_requirements, "revalidation missing requirement")
        reasons = _sorted_unique(reason_codes, "revalidation assessment reason")
        bindings = _sorted_unique(evidence_binding_ids, "revalidation evidence binding id")
        payload = {
            "protocol": REVALIDATION_ASSESSMENT_PROTOCOL,
            "plan_id": plan,
            "disposition": state.value,
            "missing_requirements": list(missing),
            "reason_codes": list(reasons),
            "evidence_binding_ids": list(bindings),
        }
        return cls(plan, state, missing, reasons, bindings, "integration-revalidation-assessment-v1-" + canonical_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": REVALIDATION_ASSESSMENT_PROTOCOL,
            "plan_id": self.plan_id,
            "disposition": self.disposition.value,
            "missing_requirements": list(self.missing_requirements),
            "reason_codes": list(self.reason_codes),
            "evidence_binding_ids": list(self.evidence_binding_ids),
            "assessment_id": self.assessment_id,
        }


def build_revalidation_plan(
    *,
    delta: ComponentEvolutionDelta,
    qualification: EvolutionCompatibilityQualification,
    impact_closure: IntegrationImpactClosure,
) -> RevalidationPlan:
    try:
        delta.validate_integrity()
        impact_closure.validate_integrity()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("revalidation inputs failed integrity validation") from exc
    canonical_qualification = qualify_component_evolution(delta)
    if qualification != canonical_qualification:
        raise ValueError("revalidation qualification does not match canonical evolution delta")
    if delta.component_id not in impact_closure.changed_component_ids:
        raise ValueError("revalidation impact closure does not contain evolved component")

    if qualification.disposition is EvolutionCompatibilityDisposition.COMPATIBLE:
        return RevalidationPlan.create(
            delta_id=delta.delta_id,
            impact_closure_id=impact_closure.closure_id,
            authority_graph_digest=impact_closure.authority_graph_digest,
            disposition=RevalidationDisposition.CURRENT,
            blocker_reason_codes=(),
            requirements=(),
        )

    if qualification.disposition in {
        EvolutionCompatibilityDisposition.INCOMPATIBLE,
        EvolutionCompatibilityDisposition.UNKNOWN,
    }:
        blockers = qualification.reason_codes or ("EVOLUTION_COMPATIBILITY_UNKNOWN",)
        return RevalidationPlan.create(
            delta_id=delta.delta_id,
            impact_closure_id=impact_closure.closure_id,
            authority_graph_digest=impact_closure.authority_graph_digest,
            disposition=RevalidationDisposition.BLOCKED,
            blocker_reason_codes=tuple("EVOLUTION:" + code for code in blockers),
            requirements=(),
        )

    requirements: list[ComponentRevalidationRequirement] = []
    changed = set(impact_closure.changed_component_ids)
    for component_id in impact_closure.impacted_component_ids:
        if component_id in changed:
            kinds = ("component_contract", "regression", "restore")
            basis = tuple("EVOLUTION:" + code for code in qualification.reason_codes)
        else:
            kinds = ("integration_compatibility", "regression")
            impact_basis = tuple(
                "IMPACT:" + row.source_id + "->" + row.target_id + ":" + row.relation + ":" + row.contract_kind
                for row in impact_closure.reasons
                if row.target_id == component_id
            )
            basis = impact_basis or ("IMPACT:TRANSITIVE_DEPENDENCY",)
        requirements.append(
            ComponentRevalidationRequirement.create(
                component_id=component_id,
                required_evidence_kinds=kinds,
                basis_codes=basis,
            )
        )
    return RevalidationPlan.create(
        delta_id=delta.delta_id,
        impact_closure_id=impact_closure.closure_id,
        authority_graph_digest=impact_closure.authority_graph_digest,
        disposition=RevalidationDisposition.REVALIDATION_REQUIRED,
        blocker_reason_codes=(),
        requirements=tuple(requirements),
    )


def assess_revalidation(
    plan: RevalidationPlan,
    evidence_bindings: tuple[RevalidationEvidenceBinding, ...],
) -> RevalidationAssessment:
    if not isinstance(plan, RevalidationPlan):
        raise ValueError("revalidation assessment requires a canonical plan")
    plan.validate_integrity()

    if plan.disposition is RevalidationDisposition.BLOCKED:
        return RevalidationAssessment.create(
            plan_id=plan.plan_id,
            disposition=RevalidationDisposition.BLOCKED,
            missing_requirements=(),
            reason_codes=plan.blocker_reason_codes,
            evidence_binding_ids=(),
        )

    required_pairs = {
        (row.component_id, kind)
        for row in plan.requirements
        for kind in row.required_evidence_kinds
    }
    bindings_by_pair: dict[tuple[str, str], RevalidationEvidenceBinding] = {}
    binding_ids: list[str] = []
    reasons: list[str] = []
    for binding in evidence_bindings:
        if not isinstance(binding, RevalidationEvidenceBinding):
            raise ValueError("revalidation assessment evidence must use canonical bindings")
        binding.validate_integrity()
        pair = (binding.component_id, binding.evidence_kind)
        if pair not in required_pairs:
            reasons.append("UNEXPECTED_EVIDENCE_BINDING")
            continue
        if pair in bindings_by_pair:
            reasons.append("DUPLICATE_EVIDENCE_BINDING")
            continue
        bindings_by_pair[pair] = binding
        binding_ids.append(binding.binding_id)
        if not binding.evidence.passed or binding.evidence.false_accepts or binding.evidence.regressions:
            reasons.append("EVIDENCE_NOT_CLEAN")

    missing = tuple(sorted(f"{component_id}:{kind}" for component_id, kind in required_pairs - set(bindings_by_pair)))
    if reasons:
        disposition = RevalidationDisposition.BLOCKED
    elif missing:
        disposition = RevalidationDisposition.REVALIDATION_REQUIRED
        reasons = ["MISSING_REQUIRED_EVIDENCE"]
    else:
        disposition = RevalidationDisposition.CURRENT
        reasons = []
    return RevalidationAssessment.create(
        plan_id=plan.plan_id,
        disposition=disposition,
        missing_requirements=missing,
        reason_codes=tuple(reasons),
        evidence_binding_ids=tuple(binding_ids),
    )


def _sorted_unique(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    normalized = tuple(_explicit(value, label) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(normalized))


def _explicit(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an explicit string")
    return value


__all__ = (
    "ComponentRevalidationRequirement",
    "RevalidationAssessment",
    "RevalidationDisposition",
    "RevalidationEvidenceBinding",
    "RevalidationPlan",
    "assess_revalidation",
    "build_revalidation_plan",
)
