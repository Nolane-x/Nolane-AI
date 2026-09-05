from __future__ import annotations

import pytest

from nolane.external_core.authority_graph import AuthorityEdge, AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.integration import COMPONENT_VERSION as INTEGRATION_COMPONENT_VERSION
from nolane.external_core.integration_evolution import (
    ComponentEvolutionDelta,
    EvolutionCompatibilityDisposition,
    build_integration_impact_closure,
    qualify_component_evolution,
)
from nolane.external_core.integration_revalidation import (
    RevalidationDisposition,
    RevalidationEvidenceBinding,
    RevalidationPlan,
    assess_revalidation,
    build_revalidation_plan,
)
from nolane.metadata.component_versions import component_version


def _manifest(component_id: str, version: str, *, consumes: tuple[str, ...] = (), produces: tuple[str, ...] = ()) -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version=version,
        family=ExternalCoreFamily.D,
        protocol_versions={"core": "1"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=("integrate",) if component_id == "external.integration" else ("plan",),
        forbidden_authorities=("assure", "execute", "promote"),
        mutable_resources=(f"state:{component_id}",),
        evidence_inputs=("verification",),
        evidence_outputs=("integration-revalidation",),
        restore_protocol="exact-revalidation",
        compatibility_floor="0.0.1",
        compatibility_ceiling=version,
    )


def _graph() -> ExternalAuthorityGraph:
    integration = _manifest("external.integration", "0.0.2", produces=("integrated",))
    planning = _manifest("external.planning", "0.0.1", consumes=("integrated",))
    return ExternalAuthorityGraph(
        (integration, planning),
        (
            AuthorityEdge.create(
                source_component_id="external.integration",
                target_component_id="external.planning",
                relation=AuthorityRelation.PROPOSES_TO,
                contract_kind="integrated",
            ),
        ),
    )


def _plan() -> RevalidationPlan:
    old = _manifest("external.integration", "0.0.1", produces=("integrated",))
    new = _manifest("external.integration", "0.0.2", produces=("integrated",))
    delta = ComponentEvolutionDelta.create(old, new)
    qualification = qualify_component_evolution(delta)
    assert qualification.disposition is EvolutionCompatibilityDisposition.REVALIDATION_REQUIRED
    closure = build_integration_impact_closure(("external.integration",), _graph())
    return build_revalidation_plan(delta=delta, qualification=qualification, impact_closure=closure)


def _binding(component_id: str, kind: str, suffix: str) -> RevalidationEvidenceBinding:
    record = EvidenceRecord(
        evidence_id=f"ev-{suffix}",
        verifier_agent_id=f"verification.agent.{suffix}",
        passed=True,
        false_accepts=0,
        regressions=0,
    )
    return RevalidationEvidenceBinding.create(component_id=component_id, evidence_kind=kind, evidence=record)


def test_integration_component_advances_exactly_to_v002() -> None:
    assert INTEGRATION_COMPONENT_VERSION == "0.0.2"
    assert str(component_version("external.integration")) == "0.0.2"


def test_revalidation_plan_is_exactly_scoped_to_impact_closure() -> None:
    plan = _plan()
    assert plan.disposition is RevalidationDisposition.REVALIDATION_REQUIRED
    assert tuple(row.component_id for row in plan.requirements) == ("external.integration", "external.planning")
    integration = next(row for row in plan.requirements if row.component_id == "external.integration")
    planning = next(row for row in plan.requirements if row.component_id == "external.planning")
    assert integration.required_evidence_kinds == ("component_contract", "regression", "restore")
    assert planning.required_evidence_kinds == ("integration_compatibility", "regression")


def test_missing_required_evidence_cannot_be_current() -> None:
    assessment = assess_revalidation(_plan(), ())
    assert assessment.disposition is RevalidationDisposition.REVALIDATION_REQUIRED
    assert assessment.missing_requirements


def test_all_required_external_evidence_can_make_plan_current() -> None:
    plan = _plan()
    bindings = tuple(
        _binding(row.component_id, kind, f"{index}-{kind}")
        for index, row in enumerate(plan.requirements)
        for kind in row.required_evidence_kinds
    )
    assessment = assess_revalidation(plan, bindings)
    assert assessment.disposition is RevalidationDisposition.CURRENT
    assert assessment.missing_requirements == ()


def test_failed_or_regressing_evidence_blocks_revalidation() -> None:
    plan = _plan()
    row = plan.requirements[0]
    bad = RevalidationEvidenceBinding.create(
        component_id=row.component_id,
        evidence_kind=row.required_evidence_kinds[0],
        evidence=EvidenceRecord("ev-bad", "verification.agent.bad", False, regressions=1),
    )
    assessment = assess_revalidation(plan, (bad,))
    assert assessment.disposition is RevalidationDisposition.BLOCKED
    assert "EVIDENCE_NOT_CLEAN" in assessment.reason_codes


def test_revalidation_plan_exact_restore_rejects_tampering() -> None:
    plan = _plan()
    assert RevalidationPlan.from_state(plan.to_state()) == plan
    state = plan.to_state()
    state["plan_id"] = "forged"
    with pytest.raises(ValueError, match="revalidation"):
        RevalidationPlan.from_state(state)


def test_direct_constructor_forged_plan_fails_before_assessment() -> None:
    plan = _plan()
    forged = RevalidationPlan(
        delta_id=plan.delta_id,
        impact_closure_id=plan.impact_closure_id,
        authority_graph_digest=plan.authority_graph_digest,
        disposition=plan.disposition,
        blocker_reason_codes=plan.blocker_reason_codes,
        requirements=plan.requirements,
        plan_id="forged",
    )
    with pytest.raises(ValueError, match="revalidation"):
        assess_revalidation(forged, ())


def test_incompatible_evolution_is_blocked_not_revalidated_away() -> None:
    old = _manifest("external.integration", "0.0.1", produces=("integrated",))
    new = _manifest("external.integration", "0.0.2", produces=())
    delta = ComponentEvolutionDelta.create(old, new)
    qualification = qualify_component_evolution(delta)
    assert qualification.disposition is EvolutionCompatibilityDisposition.INCOMPATIBLE
    closure = build_integration_impact_closure(("external.integration",), _graph())
    plan = build_revalidation_plan(delta=delta, qualification=qualification, impact_closure=closure)
    assert plan.disposition is RevalidationDisposition.BLOCKED
    assessment = assess_revalidation(plan, ())
    assert assessment.disposition is RevalidationDisposition.BLOCKED


def test_revalidation_surface_has_no_authorize_execute_or_promote_methods() -> None:
    forbidden = ("authorize", "execute", "promote", "deploy", "repair")
    for name in forbidden:
        assert not hasattr(RevalidationPlan, name)
        assert not hasattr(RevalidationEvidenceBinding, name)
