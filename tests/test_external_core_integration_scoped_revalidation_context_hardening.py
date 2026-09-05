from __future__ import annotations

import pytest

from nolane.external_core.authority_graph import AuthorityEdge, AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.evidence import ScopedEvidenceRecord
from nolane.external_core.integration_evolution import ComponentEvolutionDelta, build_integration_impact_closure, qualify_component_evolution
from nolane.external_core.integration_revalidation import RevalidationDisposition, build_revalidation_plan
from nolane.external_core.integration_scoped_revalidation import (
    RevalidationChallenge,
    RevalidationCompletionReceipt,
    RevalidationScope,
    ScopedRevalidationAssessment,
    ScopedRevalidationEvidenceBinding,
    assess_scoped_revalidation,
    build_revalidation_challenges,
    build_revalidation_scope,
    challenge_subject_digest,
)


def _manifest(component_id: str, version: str, *, consumes: tuple[str, ...] = (), produces: tuple[str, ...] = ()) -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version=version,
        family=ExternalCoreFamily.D,
        protocol_versions={"integration": "2"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=("integrate",) if component_id == "external.integration" else ("plan",),
        forbidden_authorities=("assure", "execute", "promote"),
        mutable_resources=(f"state:{component_id}",),
        evidence_inputs=("scoped-evidence-v2",),
        evidence_outputs=("integration-revalidation-v2",),
        restore_protocol="exact-revalidation-v2",
        compatibility_floor="0.0.1",
        compatibility_ceiling=version,
    )


def _case():
    old = _manifest("external.integration", "0.0.2", produces=("integrated",))
    new = _manifest("external.integration", "0.0.3", produces=("integrated",))
    planning = _manifest("external.planning", "0.0.1", consumes=("integrated",))
    graph = ExternalAuthorityGraph(
        (new, planning),
        (
            AuthorityEdge.create(
                source_component_id="external.integration",
                target_component_id="external.planning",
                relation=AuthorityRelation.PROPOSES_TO,
                contract_kind="integrated",
            ),
        ),
    )
    delta = ComponentEvolutionDelta.create(old, new)
    closure = build_integration_impact_closure(("external.integration",), graph)
    plan = build_revalidation_plan(delta=delta, qualification=qualify_component_evolution(delta), impact_closure=closure)
    scope = build_revalidation_scope(delta=delta, impact_closure=closure, plan=plan)
    challenges = build_revalidation_challenges(scope=scope, plan=plan, authority_graph=graph)
    return graph, delta, closure, plan, scope, challenges


def _binding(challenge: RevalidationChallenge, suffix: str) -> ScopedRevalidationEvidenceBinding:
    evidence = ScopedEvidenceRecord.create(
        evidence_id=f"context-{suffix}",
        subject_id=challenge.component_id,
        subject_version=challenge.target_component_version,
        subject_digest=challenge_subject_digest(challenge),
        scope_digest=challenge.scope_id,
        verifier_agent_id=f"verification.agent.{suffix}",
        observed_epoch=10,
        passed=True,
        evidence_refs=(f"artifact:{suffix}",),
    )
    return ScopedRevalidationEvidenceBinding.create(challenge=challenge, evidence=evidence)


def test_assessment_recomputes_scope_from_canonical_transition_context() -> None:
    graph, delta, closure, plan, scope, _ = _case()
    forged_scope = RevalidationScope.create(
        delta_id="forged-delta",
        component_id=scope.component_id,
        old_manifest_digest="forged-old-manifest",
        new_manifest_digest=scope.new_manifest_digest,
        old_component_version=scope.old_component_version,
        new_component_version=scope.new_component_version,
        impact_closure_id=scope.impact_closure_id,
        authority_graph_digest=scope.authority_graph_digest,
        plan_id=scope.plan_id,
    )
    forged_challenges = build_revalidation_challenges(scope=forged_scope, plan=plan, authority_graph=graph)
    forged_bindings = tuple(_binding(row, str(index)) for index, row in enumerate(forged_challenges))

    with pytest.raises(ValueError, match="canonical|scope|transition"):
        assess_scoped_revalidation(
            delta=delta,
            impact_closure=closure,
            authority_graph=graph,
            scope=forged_scope,
            plan=plan,
            challenges=forged_challenges,
            evidence_bindings=forged_bindings,
            minimum_observed_epoch=0,
        )


def test_assessment_recomputes_challenges_instead_of_trusting_rehashed_metadata() -> None:
    graph, delta, closure, plan, scope, challenges = _case()
    canonical = challenges[0]
    forged = RevalidationChallenge.create(
        scope_id=canonical.scope_id,
        plan_id=canonical.plan_id,
        requirement_id=canonical.requirement_id,
        component_id=canonical.component_id,
        evidence_kind=canonical.evidence_kind,
        basis_codes=canonical.basis_codes,
        target_component_version="9.9.9",
    )
    substituted = (forged,) + challenges[1:]
    bindings = tuple(_binding(row, str(index)) for index, row in enumerate(substituted))

    with pytest.raises(ValueError, match="canonical|challenge|version"):
        assess_scoped_revalidation(
            delta=delta,
            impact_closure=closure,
            authority_graph=graph,
            scope=scope,
            plan=plan,
            challenges=substituted,
            evidence_bindings=bindings,
            minimum_observed_epoch=0,
        )


def test_completion_recomputes_current_assessment_before_minting_receipt() -> None:
    graph, delta, closure, plan, scope, challenges = _case()
    bindings = tuple(_binding(row, str(index)) for index, row in enumerate(challenges))
    assessment = assess_scoped_revalidation(
        delta=delta,
        impact_closure=closure,
        authority_graph=graph,
        scope=scope,
        plan=plan,
        challenges=challenges,
        evidence_bindings=bindings,
        minimum_observed_epoch=0,
    )
    assert assessment.disposition is RevalidationDisposition.CURRENT

    forged_assessment = ScopedRevalidationAssessment.create(
        scope_id=scope.scope_id,
        plan_id=plan.plan_id,
        disposition=RevalidationDisposition.CURRENT,
        missing_challenge_ids=(),
        reason_codes=(),
        challenge_ids=assessment.challenge_ids,
        evidence_binding_ids=(),
    )
    with pytest.raises(ValueError, match="canonical|assessment|CURRENT|binding"):
        RevalidationCompletionReceipt.create(
            delta=delta,
            impact_closure=closure,
            authority_graph=graph,
            scope=scope,
            plan=plan,
            assessment=forged_assessment,
            challenges=challenges,
            evidence_bindings=bindings,
            minimum_observed_epoch=0,
        )
