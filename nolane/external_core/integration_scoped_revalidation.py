from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.authority_graph import ExternalAuthorityGraph
from nolane.external_core.evidence import ScopedEvidenceRecord
from nolane.external_core.integration_evolution import (
    ComponentEvolutionDelta,
    IntegrationImpactClosure,
    build_integration_impact_closure,
    qualify_component_evolution,
)
from nolane.external_core.integration_revalidation import (
    ComponentRevalidationRequirement,
    RevalidationDisposition,
    RevalidationPlan,
    build_revalidation_plan,
)


REVALIDATION_SCOPE_PROTOCOL = "integration-revalidation-scope-v2"
REVALIDATION_CHALLENGE_PROTOCOL = "integration-revalidation-challenge-v2"
REVALIDATION_BINDING_PROTOCOL = "integration-revalidation-evidence-binding-v2"
REVALIDATION_ASSESSMENT_V2_PROTOCOL = "integration-revalidation-assessment-v2"
REVALIDATION_COMPLETION_PROTOCOL = "integration-revalidation-completion-v2"
REVALIDATION_SUBJECT_PROTOCOL = "integration-revalidation-challenge-subject-v2"


@dataclass(frozen=True, slots=True)
class RevalidationScope:
    delta_id: str
    component_id: str
    old_manifest_digest: str
    new_manifest_digest: str
    old_component_version: str
    new_component_version: str
    impact_closure_id: str
    authority_graph_digest: str
    plan_id: str
    scope_id: str

    @classmethod
    def create(
        cls,
        *,
        delta_id: str,
        component_id: str,
        old_manifest_digest: str,
        new_manifest_digest: str,
        old_component_version: str,
        new_component_version: str,
        impact_closure_id: str,
        authority_graph_digest: str,
        plan_id: str,
    ) -> "RevalidationScope":
        payload = {
            "protocol": REVALIDATION_SCOPE_PROTOCOL,
            "delta_id": _explicit(delta_id, "revalidation scope delta"),
            "component_id": _explicit(component_id, "revalidation scope component"),
            "old_manifest_digest": _explicit(old_manifest_digest, "revalidation old manifest digest"),
            "new_manifest_digest": _explicit(new_manifest_digest, "revalidation new manifest digest"),
            "old_component_version": _explicit(old_component_version, "revalidation old component version"),
            "new_component_version": _explicit(new_component_version, "revalidation new component version"),
            "impact_closure_id": _explicit(impact_closure_id, "revalidation impact closure"),
            "authority_graph_digest": _explicit(authority_graph_digest, "revalidation authority graph digest"),
            "plan_id": _explicit(plan_id, "revalidation plan"),
        }
        return cls(
            delta_id=payload["delta_id"],
            component_id=payload["component_id"],
            old_manifest_digest=payload["old_manifest_digest"],
            new_manifest_digest=payload["new_manifest_digest"],
            old_component_version=payload["old_component_version"],
            new_component_version=payload["new_component_version"],
            impact_closure_id=payload["impact_closure_id"],
            authority_graph_digest=payload["authority_graph_digest"],
            plan_id=payload["plan_id"],
            scope_id="integration-revalidation-scope-v2-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": REVALIDATION_SCOPE_PROTOCOL,
            "delta_id": self.delta_id,
            "component_id": self.component_id,
            "old_manifest_digest": self.old_manifest_digest,
            "new_manifest_digest": self.new_manifest_digest,
            "old_component_version": self.old_component_version,
            "new_component_version": self.new_component_version,
            "impact_closure_id": self.impact_closure_id,
            "authority_graph_digest": self.authority_graph_digest,
            "plan_id": self.plan_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "scope_id": self.scope_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RevalidationScope":
        if not isinstance(state, Mapping) or state.get("protocol") != REVALIDATION_SCOPE_PROTOCOL:
            raise ValueError("revalidation scope protocol mismatch")
        expected = cls.create(
            delta_id=state.get("delta_id"),
            component_id=state.get("component_id"),
            old_manifest_digest=state.get("old_manifest_digest"),
            new_manifest_digest=state.get("new_manifest_digest"),
            old_component_version=state.get("old_component_version"),
            new_component_version=state.get("new_component_version"),
            impact_closure_id=state.get("impact_closure_id"),
            authority_graph_digest=state.get("authority_graph_digest"),
            plan_id=state.get("plan_id"),
        )
        if state.get("scope_id") != expected.scope_id or dict(state) != expected.to_state():
            raise ValueError("revalidation scope integrity mismatch or non-canonical state")
        return expected

    def validate_integrity(self) -> None:
        _validate_round_trip(self, type(self).from_state, "revalidation scope")


@dataclass(frozen=True, slots=True)
class RevalidationChallenge:
    scope_id: str
    plan_id: str
    requirement_id: str
    component_id: str
    evidence_kind: str
    basis_codes: tuple[str, ...]
    target_component_version: str
    challenge_id: str

    @classmethod
    def create(
        cls,
        *,
        scope_id: str,
        plan_id: str,
        requirement_id: str,
        component_id: str,
        evidence_kind: str,
        basis_codes: tuple[str, ...],
        target_component_version: str,
    ) -> "RevalidationChallenge":
        basis = _sorted_unique_strings(
            basis_codes,
            "revalidation challenge basis",
            require_non_empty=True,
        )
        payload = {
            "protocol": REVALIDATION_CHALLENGE_PROTOCOL,
            "scope_id": _explicit(scope_id, "revalidation challenge scope"),
            "plan_id": _explicit(plan_id, "revalidation challenge plan"),
            "requirement_id": _explicit(requirement_id, "revalidation challenge requirement"),
            "component_id": _explicit(component_id, "revalidation challenge component"),
            "evidence_kind": _explicit(evidence_kind, "revalidation challenge evidence kind"),
            "basis_codes": list(basis),
            "target_component_version": _explicit(
                target_component_version,
                "revalidation challenge target version",
            ),
        }
        return cls(
            scope_id=payload["scope_id"],
            plan_id=payload["plan_id"],
            requirement_id=payload["requirement_id"],
            component_id=payload["component_id"],
            evidence_kind=payload["evidence_kind"],
            basis_codes=basis,
            target_component_version=payload["target_component_version"],
            challenge_id="integration-revalidation-challenge-v2-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": REVALIDATION_CHALLENGE_PROTOCOL,
            "scope_id": self.scope_id,
            "plan_id": self.plan_id,
            "requirement_id": self.requirement_id,
            "component_id": self.component_id,
            "evidence_kind": self.evidence_kind,
            "basis_codes": list(self.basis_codes),
            "target_component_version": self.target_component_version,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "challenge_id": self.challenge_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RevalidationChallenge":
        if not isinstance(state, Mapping) or state.get("protocol") != REVALIDATION_CHALLENGE_PROTOCOL:
            raise ValueError("revalidation challenge protocol mismatch")
        raw_basis = state.get("basis_codes")
        if not isinstance(raw_basis, list):
            raise ValueError("revalidation challenge basis must be a list")
        expected = cls.create(
            scope_id=state.get("scope_id"),
            plan_id=state.get("plan_id"),
            requirement_id=state.get("requirement_id"),
            component_id=state.get("component_id"),
            evidence_kind=state.get("evidence_kind"),
            basis_codes=tuple(raw_basis),
            target_component_version=state.get("target_component_version"),
        )
        if state.get("challenge_id") != expected.challenge_id or dict(state) != expected.to_state():
            raise ValueError("revalidation challenge integrity mismatch or non-canonical state")
        return expected

    def validate_integrity(self) -> None:
        _validate_round_trip(self, type(self).from_state, "revalidation challenge")


@dataclass(frozen=True, slots=True)
class ScopedRevalidationEvidenceBinding:
    challenge: RevalidationChallenge
    evidence: ScopedEvidenceRecord
    binding_id: str

    @property
    def challenge_id(self) -> str:
        return self.challenge.challenge_id

    @property
    def scope_id(self) -> str:
        return self.challenge.scope_id

    @property
    def component_id(self) -> str:
        return self.challenge.component_id

    @property
    def evidence_kind(self) -> str:
        return self.challenge.evidence_kind

    @classmethod
    def create(
        cls,
        *,
        challenge: RevalidationChallenge,
        evidence: ScopedEvidenceRecord,
    ) -> "ScopedRevalidationEvidenceBinding":
        if not isinstance(challenge, RevalidationChallenge):
            raise ValueError("scoped revalidation binding requires a canonical challenge")
        challenge.validate_integrity()
        if not isinstance(evidence, ScopedEvidenceRecord):
            raise ValueError("scoped revalidation binding requires scoped evidence v2")
        evidence.validate_integrity()
        if evidence.subject_id != challenge.component_id:
            raise ValueError("scoped evidence subject does not match revalidation challenge")
        if evidence.subject_version != challenge.target_component_version:
            raise ValueError("scoped evidence subject version does not match revalidation challenge")
        if evidence.scope_digest != challenge.scope_id:
            raise ValueError("scoped evidence scope does not match revalidation challenge")
        if evidence.subject_digest != challenge_subject_digest(challenge):
            raise ValueError("scoped evidence subject digest does not match revalidation challenge")
        if evidence.verifier_agent_id == challenge.component_id:
            raise ValueError("scoped revalidation evidence cannot self-certify its component")
        payload = {
            "protocol": REVALIDATION_BINDING_PROTOCOL,
            "challenge": challenge.to_state(),
            "evidence": evidence.to_state(),
        }
        return cls(
            challenge=challenge,
            evidence=evidence,
            binding_id="integration-revalidation-evidence-v2-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": REVALIDATION_BINDING_PROTOCOL,
            "challenge": self.challenge.to_state(),
            "evidence": self.evidence.to_state(),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "binding_id": self.binding_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ScopedRevalidationEvidenceBinding":
        if not isinstance(state, Mapping) or state.get("protocol") != REVALIDATION_BINDING_PROTOCOL:
            raise ValueError("scoped revalidation binding protocol mismatch")
        raw_challenge = state.get("challenge")
        raw_evidence = state.get("evidence")
        if not isinstance(raw_challenge, Mapping) or not isinstance(raw_evidence, Mapping):
            raise ValueError("scoped revalidation binding state shape is invalid")
        expected = cls.create(
            challenge=RevalidationChallenge.from_state(raw_challenge),
            evidence=ScopedEvidenceRecord.from_state(raw_evidence),
        )
        if state.get("binding_id") != expected.binding_id or dict(state) != expected.to_state():
            raise ValueError("scoped revalidation binding integrity mismatch or non-canonical state")
        return expected

    def validate_integrity(self) -> None:
        _validate_round_trip(self, type(self).from_state, "scoped revalidation binding")


@dataclass(frozen=True, slots=True)
class ScopedRevalidationAssessment:
    scope_id: str
    plan_id: str
    disposition: RevalidationDisposition
    missing_challenge_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    challenge_ids: tuple[str, ...]
    evidence_binding_ids: tuple[str, ...]
    assessment_id: str

    @classmethod
    def create(
        cls,
        *,
        scope_id: str,
        plan_id: str,
        disposition: RevalidationDisposition,
        missing_challenge_ids: tuple[str, ...],
        reason_codes: tuple[str, ...],
        challenge_ids: tuple[str, ...],
        evidence_binding_ids: tuple[str, ...],
    ) -> "ScopedRevalidationAssessment":
        state = RevalidationDisposition(disposition)
        missing = _sorted_unique_strings(
            missing_challenge_ids,
            "scoped revalidation missing challenge",
            require_non_empty=False,
        )
        reasons = _sorted_unique_strings(
            reason_codes,
            "scoped revalidation reason",
            require_non_empty=False,
        )
        challenges = _sorted_unique_strings(
            challenge_ids,
            "scoped revalidation challenge id",
            require_non_empty=False,
        )
        bindings = _sorted_unique_strings(
            evidence_binding_ids,
            "scoped revalidation binding id",
            require_non_empty=False,
        )
        if state is RevalidationDisposition.CURRENT and (missing or reasons):
            raise ValueError("CURRENT scoped revalidation assessment cannot carry missing challenges or reasons")
        if state is RevalidationDisposition.REVALIDATION_REQUIRED and not missing:
            raise ValueError("revalidation-required scoped assessment needs missing challenges")
        if state is RevalidationDisposition.BLOCKED and not reasons:
            raise ValueError("blocked scoped revalidation assessment needs reasons")
        payload = {
            "protocol": REVALIDATION_ASSESSMENT_V2_PROTOCOL,
            "scope_id": _explicit(scope_id, "scoped assessment scope"),
            "plan_id": _explicit(plan_id, "scoped assessment plan"),
            "disposition": state.value,
            "missing_challenge_ids": list(missing),
            "reason_codes": list(reasons),
            "challenge_ids": list(challenges),
            "evidence_binding_ids": list(bindings),
        }
        return cls(
            scope_id=payload["scope_id"],
            plan_id=payload["plan_id"],
            disposition=state,
            missing_challenge_ids=missing,
            reason_codes=reasons,
            challenge_ids=challenges,
            evidence_binding_ids=bindings,
            assessment_id="integration-revalidation-assessment-v2-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": REVALIDATION_ASSESSMENT_V2_PROTOCOL,
            "scope_id": self.scope_id,
            "plan_id": self.plan_id,
            "disposition": self.disposition.value,
            "missing_challenge_ids": list(self.missing_challenge_ids),
            "reason_codes": list(self.reason_codes),
            "challenge_ids": list(self.challenge_ids),
            "evidence_binding_ids": list(self.evidence_binding_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "assessment_id": self.assessment_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ScopedRevalidationAssessment":
        if not isinstance(state, Mapping) or state.get("protocol") != REVALIDATION_ASSESSMENT_V2_PROTOCOL:
            raise ValueError("scoped revalidation assessment protocol mismatch")
        raw_missing = state.get("missing_challenge_ids")
        raw_reasons = state.get("reason_codes")
        raw_challenges = state.get("challenge_ids")
        raw_bindings = state.get("evidence_binding_ids")
        if not all(
            isinstance(value, list)
            for value in (raw_missing, raw_reasons, raw_challenges, raw_bindings)
        ):
            raise ValueError("scoped revalidation assessment state shape is invalid")
        try:
            disposition = RevalidationDisposition(state.get("disposition"))
        except (TypeError, ValueError) as exc:
            raise ValueError("scoped revalidation assessment disposition is invalid") from exc
        expected = cls.create(
            scope_id=state.get("scope_id"),
            plan_id=state.get("plan_id"),
            disposition=disposition,
            missing_challenge_ids=tuple(raw_missing),
            reason_codes=tuple(raw_reasons),
            challenge_ids=tuple(raw_challenges),
            evidence_binding_ids=tuple(raw_bindings),
        )
        if state.get("assessment_id") != expected.assessment_id or dict(state) != expected.to_state():
            raise ValueError("scoped revalidation assessment integrity mismatch or non-canonical state")
        return expected

    def validate_integrity(self) -> None:
        _validate_round_trip(self, type(self).from_state, "scoped revalidation assessment")


@dataclass(frozen=True, slots=True)
class RevalidationCompletionReceipt:
    scope_id: str
    plan_id: str
    assessment_id: str
    challenge_ids: tuple[str, ...]
    evidence_binding_ids: tuple[str, ...]
    receipt_id: str

    @classmethod
    def create(
        cls,
        *,
        delta: ComponentEvolutionDelta,
        impact_closure: IntegrationImpactClosure,
        authority_graph: ExternalAuthorityGraph,
        scope: RevalidationScope,
        plan: RevalidationPlan,
        assessment: ScopedRevalidationAssessment,
        challenges: tuple[RevalidationChallenge, ...],
        evidence_bindings: tuple[ScopedRevalidationEvidenceBinding, ...],
        minimum_observed_epoch: int = 0,
    ) -> "RevalidationCompletionReceipt":
        if not isinstance(assessment, ScopedRevalidationAssessment):
            raise ValueError("completion receipt requires a canonical scoped assessment")
        assessment.validate_integrity()
        canonical_assessment = assess_scoped_revalidation(
            delta=delta,
            impact_closure=impact_closure,
            authority_graph=authority_graph,
            scope=scope,
            plan=plan,
            challenges=challenges,
            evidence_bindings=evidence_bindings,
            minimum_observed_epoch=minimum_observed_epoch,
        )
        if assessment != canonical_assessment:
            raise ValueError("completion assessment does not match canonical transition assessment")
        if canonical_assessment.disposition is not RevalidationDisposition.CURRENT:
            raise ValueError("completion receipt requires a canonical CURRENT scoped assessment")
        return cls._from_values(
            scope_id=canonical_assessment.scope_id,
            plan_id=canonical_assessment.plan_id,
            assessment_id=canonical_assessment.assessment_id,
            challenge_ids=canonical_assessment.challenge_ids,
            evidence_binding_ids=canonical_assessment.evidence_binding_ids,
        )

    @classmethod
    def _from_values(
        cls,
        *,
        scope_id: str,
        plan_id: str,
        assessment_id: str,
        challenge_ids: tuple[str, ...],
        evidence_binding_ids: tuple[str, ...],
    ) -> "RevalidationCompletionReceipt":
        challenge_rows = _sorted_unique_strings(
            challenge_ids,
            "completion challenge id",
            require_non_empty=False,
        )
        binding_rows = _sorted_unique_strings(
            evidence_binding_ids,
            "completion binding id",
            require_non_empty=False,
        )
        payload = {
            "protocol": REVALIDATION_COMPLETION_PROTOCOL,
            "scope_id": _explicit(scope_id, "completion scope"),
            "plan_id": _explicit(plan_id, "completion plan"),
            "assessment_id": _explicit(assessment_id, "completion assessment"),
            "challenge_ids": list(challenge_rows),
            "evidence_binding_ids": list(binding_rows),
        }
        return cls(
            scope_id=payload["scope_id"],
            plan_id=payload["plan_id"],
            assessment_id=payload["assessment_id"],
            challenge_ids=challenge_rows,
            evidence_binding_ids=binding_rows,
            receipt_id="integration-revalidation-completion-v2-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": REVALIDATION_COMPLETION_PROTOCOL,
            "scope_id": self.scope_id,
            "plan_id": self.plan_id,
            "assessment_id": self.assessment_id,
            "challenge_ids": list(self.challenge_ids),
            "evidence_binding_ids": list(self.evidence_binding_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": self.receipt_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "RevalidationCompletionReceipt":
        if not isinstance(state, Mapping) or state.get("protocol") != REVALIDATION_COMPLETION_PROTOCOL:
            raise ValueError("completion receipt protocol mismatch")
        raw_challenges = state.get("challenge_ids")
        raw_bindings = state.get("evidence_binding_ids")
        if not isinstance(raw_challenges, list) or not isinstance(raw_bindings, list):
            raise ValueError("completion receipt state shape is invalid")
        expected = cls._from_values(
            scope_id=state.get("scope_id"),
            plan_id=state.get("plan_id"),
            assessment_id=state.get("assessment_id"),
            challenge_ids=tuple(raw_challenges),
            evidence_binding_ids=tuple(raw_bindings),
        )
        if state.get("receipt_id") != expected.receipt_id or dict(state) != expected.to_state():
            raise ValueError("completion receipt integrity mismatch or non-canonical state")
        return expected

    def validate_integrity(self) -> None:
        _validate_round_trip(self, type(self).from_state, "completion receipt")


def build_revalidation_scope(
    *,
    delta: ComponentEvolutionDelta,
    impact_closure: IntegrationImpactClosure,
    plan: RevalidationPlan,
) -> RevalidationScope:
    if not isinstance(delta, ComponentEvolutionDelta):
        raise ValueError("revalidation scope requires a canonical evolution delta")
    if not isinstance(impact_closure, IntegrationImpactClosure):
        raise ValueError("revalidation scope requires a canonical impact closure")
    if not isinstance(plan, RevalidationPlan):
        raise ValueError("revalidation scope requires a canonical revalidation plan")
    delta.validate_integrity()
    impact_closure.validate_integrity()
    plan.validate_integrity()
    if plan.delta_id != delta.delta_id:
        raise ValueError("revalidation scope plan/delta mismatch")
    if plan.impact_closure_id != impact_closure.closure_id:
        raise ValueError("revalidation scope plan/impact closure mismatch")
    if plan.authority_graph_digest != impact_closure.authority_graph_digest:
        raise ValueError("revalidation scope plan/authority graph mismatch")
    if delta.component_id not in impact_closure.changed_component_ids:
        raise ValueError("revalidation scope evolved component is outside changed component set")
    return RevalidationScope.create(
        delta_id=delta.delta_id,
        component_id=delta.component_id,
        old_manifest_digest=delta.old_manifest.manifest_digest,
        new_manifest_digest=delta.new_manifest.manifest_digest,
        old_component_version=delta.old_manifest.component_version,
        new_component_version=delta.new_manifest.component_version,
        impact_closure_id=impact_closure.closure_id,
        authority_graph_digest=impact_closure.authority_graph_digest,
        plan_id=plan.plan_id,
    )


def build_revalidation_challenges(
    *,
    scope: RevalidationScope,
    plan: RevalidationPlan,
    authority_graph: ExternalAuthorityGraph,
) -> tuple[RevalidationChallenge, ...]:
    if not isinstance(scope, RevalidationScope):
        raise ValueError("challenge derivation requires a canonical revalidation scope")
    scope.validate_integrity()
    if not isinstance(plan, RevalidationPlan):
        raise ValueError("challenge derivation requires a canonical revalidation plan")
    plan.validate_integrity()
    canonical_graph = _canonical_authority_graph(authority_graph)
    if plan.plan_id != scope.plan_id:
        raise ValueError("challenge derivation plan does not match exact scope")
    if plan.authority_graph_digest != scope.authority_graph_digest:
        raise ValueError("challenge derivation plan graph does not match exact scope")
    if canonical_graph.digest != scope.authority_graph_digest:
        raise ValueError("challenge derivation authority graph drift")
    try:
        evolved_manifest = canonical_graph.manifest(scope.component_id)
    except KeyError as exc:
        raise ValueError("evolved component is missing from challenge authority graph") from exc
    if evolved_manifest.component_version != scope.new_component_version:
        raise ValueError("evolved component version drift in challenge authority graph")

    rows: list[RevalidationChallenge] = []
    for requirement in plan.requirements:
        if not isinstance(requirement, ComponentRevalidationRequirement):
            raise ValueError("challenge derivation requires canonical plan requirements")
        requirement.validate_integrity()
        try:
            manifest = canonical_graph.manifest(requirement.component_id)
        except KeyError as exc:
            raise ValueError("revalidation requirement component missing from authority graph") from exc
        target_version = (
            scope.new_component_version
            if requirement.component_id == scope.component_id
            else manifest.component_version
        )
        for evidence_kind in requirement.required_evidence_kinds:
            rows.append(
                RevalidationChallenge.create(
                    scope_id=scope.scope_id,
                    plan_id=plan.plan_id,
                    requirement_id=requirement.requirement_id,
                    component_id=requirement.component_id,
                    evidence_kind=evidence_kind,
                    basis_codes=requirement.basis_codes,
                    target_component_version=target_version,
                )
            )
    return tuple(
        sorted(rows, key=lambda row: (row.component_id, row.evidence_kind, row.challenge_id))
    )


def challenge_subject_digest(challenge: RevalidationChallenge) -> str:
    if not isinstance(challenge, RevalidationChallenge):
        raise ValueError("challenge subject digest requires a canonical challenge")
    challenge.validate_integrity()
    payload = {
        "protocol": REVALIDATION_SUBJECT_PROTOCOL,
        "scope_id": challenge.scope_id,
        "challenge_id": challenge.challenge_id,
        "component_id": challenge.component_id,
        "target_component_version": challenge.target_component_version,
        "evidence_kind": challenge.evidence_kind,
        "basis_codes": list(challenge.basis_codes),
    }
    return "integration-revalidation-subject-v2-" + canonical_digest(payload)


def assess_scoped_revalidation(
    *,
    delta: ComponentEvolutionDelta,
    impact_closure: IntegrationImpactClosure,
    authority_graph: ExternalAuthorityGraph,
    scope: RevalidationScope,
    plan: RevalidationPlan,
    challenges: tuple[RevalidationChallenge, ...],
    evidence_bindings: tuple[ScopedRevalidationEvidenceBinding, ...],
    minimum_observed_epoch: int = 0,
) -> ScopedRevalidationAssessment:
    canonical_scope, canonical_plan, canonical_challenges = _canonical_transition_context(
        delta=delta,
        impact_closure=impact_closure,
        authority_graph=authority_graph,
        scope=scope,
        plan=plan,
        challenges=challenges,
    )
    minimum_epoch = _strict_non_negative_int(
        minimum_observed_epoch,
        "minimum observed epoch",
    )

    if canonical_plan.disposition is RevalidationDisposition.BLOCKED:
        return ScopedRevalidationAssessment.create(
            scope_id=canonical_scope.scope_id,
            plan_id=canonical_plan.plan_id,
            disposition=RevalidationDisposition.BLOCKED,
            missing_challenge_ids=(),
            reason_codes=tuple("PLAN:" + code for code in canonical_plan.blocker_reason_codes),
            challenge_ids=(),
            evidence_binding_ids=(),
        )
    if canonical_plan.disposition is RevalidationDisposition.UNKNOWN:
        return ScopedRevalidationAssessment.create(
            scope_id=canonical_scope.scope_id,
            plan_id=canonical_plan.plan_id,
            disposition=RevalidationDisposition.UNKNOWN,
            missing_challenge_ids=(),
            reason_codes=(),
            challenge_ids=(),
            evidence_binding_ids=(),
        )

    challenges_by_id = {row.challenge_id: row for row in canonical_challenges}
    reasons: list[str] = []
    bindings_by_challenge: dict[str, ScopedRevalidationEvidenceBinding] = {}
    accepted_binding_ids: list[str] = []

    for binding in evidence_bindings:
        if not isinstance(binding, ScopedRevalidationEvidenceBinding):
            raise ValueError("scoped revalidation evidence must use canonical v2 bindings")
        binding.validate_integrity()
        if binding.scope_id != canonical_scope.scope_id:
            reasons.append("SCOPE_MISMATCH")
            continue
        expected_challenge = challenges_by_id.get(binding.challenge_id)
        if expected_challenge is None:
            reasons.append("UNEXPECTED_EVIDENCE_BINDING")
            continue
        if binding.challenge != expected_challenge:
            reasons.append("CHALLENGE_MISMATCH")
            continue
        if binding.challenge_id in bindings_by_challenge:
            reasons.append("DUPLICATE_EVIDENCE_BINDING")
            continue
        bindings_by_challenge[binding.challenge_id] = binding
        accepted_binding_ids.append(binding.binding_id)
        if binding.evidence.observed_epoch < minimum_epoch:
            reasons.append("EVIDENCE_STALE")
        if not binding.evidence.passed or binding.evidence.false_accepts or binding.evidence.regressions:
            reasons.append("EVIDENCE_NOT_CLEAN")

    missing = tuple(
        sorted(
            challenge_id
            for challenge_id in challenges_by_id
            if challenge_id not in bindings_by_challenge
        )
    )
    unique_reasons = tuple(sorted(set(reasons)))
    if unique_reasons:
        disposition = RevalidationDisposition.BLOCKED
    elif missing:
        disposition = RevalidationDisposition.REVALIDATION_REQUIRED
    else:
        disposition = RevalidationDisposition.CURRENT

    return ScopedRevalidationAssessment.create(
        scope_id=canonical_scope.scope_id,
        plan_id=canonical_plan.plan_id,
        disposition=disposition,
        missing_challenge_ids=missing,
        reason_codes=unique_reasons,
        challenge_ids=tuple(challenges_by_id),
        evidence_binding_ids=tuple(accepted_binding_ids),
    )


def _canonical_transition_context(
    *,
    delta: ComponentEvolutionDelta,
    impact_closure: IntegrationImpactClosure,
    authority_graph: ExternalAuthorityGraph,
    scope: RevalidationScope,
    plan: RevalidationPlan,
    challenges: tuple[RevalidationChallenge, ...],
) -> tuple[RevalidationScope, RevalidationPlan, tuple[RevalidationChallenge, ...]]:
    if not isinstance(delta, ComponentEvolutionDelta):
        raise ValueError("canonical transition requires a component evolution delta")
    if not isinstance(impact_closure, IntegrationImpactClosure):
        raise ValueError("canonical transition requires an integration impact closure")
    if not isinstance(scope, RevalidationScope):
        raise ValueError("canonical transition requires a revalidation scope")
    if not isinstance(plan, RevalidationPlan):
        raise ValueError("canonical transition requires a revalidation plan")
    try:
        delta.validate_integrity()
        impact_closure.validate_integrity()
        scope.validate_integrity()
        plan.validate_integrity()
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("canonical transition input integrity validation failed") from exc

    canonical_graph = _canonical_authority_graph(authority_graph)
    try:
        graph_new_manifest = canonical_graph.manifest(delta.component_id)
    except KeyError as exc:
        raise ValueError("canonical transition evolved component is absent from authority graph") from exc
    if graph_new_manifest.to_state() != delta.new_manifest.to_state():
        raise ValueError("canonical transition new manifest does not match authority graph")

    canonical_closure = build_integration_impact_closure(
        (delta.component_id,),
        canonical_graph,
    )
    if impact_closure != canonical_closure:
        raise ValueError("impact closure does not match canonical transition authority graph")

    canonical_plan = build_revalidation_plan(
        delta=delta,
        qualification=qualify_component_evolution(delta),
        impact_closure=canonical_closure,
    )
    if plan != canonical_plan:
        raise ValueError("revalidation plan does not match canonical transition")

    canonical_scope = build_revalidation_scope(
        delta=delta,
        impact_closure=canonical_closure,
        plan=canonical_plan,
    )
    if scope != canonical_scope:
        raise ValueError("revalidation scope does not match canonical transition")

    canonical_challenges = build_revalidation_challenges(
        scope=canonical_scope,
        plan=canonical_plan,
        authority_graph=canonical_graph,
    )
    if challenges != canonical_challenges:
        raise ValueError("revalidation challenges do not match canonical transition")
    return canonical_scope, canonical_plan, canonical_challenges


def _canonical_authority_graph(authority_graph: ExternalAuthorityGraph) -> ExternalAuthorityGraph:
    if not isinstance(authority_graph, ExternalAuthorityGraph):
        raise ValueError("canonical transition requires an ExternalAuthorityGraph")
    try:
        state = authority_graph.to_state()
        restored = ExternalAuthorityGraph.from_state(state)
        restored.validate()
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("canonical transition authority graph integrity validation failed") from exc
    if restored.to_state() != state:
        raise ValueError("canonical transition authority graph is non-canonical")
    return restored


def _validate_round_trip(value: Any, restore: Any, label: str) -> None:
    try:
        restored = restore(value.to_state())
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{label} integrity validation failed") from exc
    if restored != value:
        raise ValueError(f"{label} integrity validation failed")


def _explicit(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an explicit string")
    return value


def _strict_non_negative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _sorted_unique_strings(
    values: object,
    label: str,
    *,
    require_non_empty: bool,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{label} must be a tuple")
    normalized = tuple(_explicit(value, label) for value in values)
    if require_non_empty and not normalized:
        raise ValueError(f"{label} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(normalized))


__all__ = (
    "RevalidationChallenge",
    "RevalidationCompletionReceipt",
    "RevalidationScope",
    "ScopedRevalidationAssessment",
    "ScopedRevalidationEvidenceBinding",
    "assess_scoped_revalidation",
    "build_revalidation_challenges",
    "build_revalidation_scope",
    "challenge_subject_digest",
)
