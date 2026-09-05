from __future__ import annotations

import pytest

from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.integration_evolution import (
    ComponentEvolutionDelta,
    IntegrationImpactClosure,
    IntegrationImpactReason,
    qualify_component_evolution,
)
from nolane.external_core.integration_revalidation import (
    ComponentRevalidationRequirement,
    RevalidationDisposition,
    RevalidationEvidenceBinding,
    RevalidationPlan,
    assess_revalidation,
)


def _manifest(component_id: str = "external.integration", version: str = "0.0.1") -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version=version,
        family=ExternalCoreFamily.D,
        protocol_versions={"integration": "1"},
        consumes_contracts=("candidate",),
        produces_contracts=("integrated",),
        authority_capabilities=("integrate",),
        forbidden_authorities=("assure", "execute", "promote"),
        mutable_resources=("integration.graph",),
        evidence_inputs=("verification",),
        evidence_outputs=("integration-revalidation",),
        restore_protocol="exact-revalidation",
        compatibility_floor="0.0.1",
        compatibility_ceiling=version,
    )


def test_adversarial_direct_constructor_delta_forgery_fails_at_semantic_consumer() -> None:
    valid = ComponentEvolutionDelta.create(_manifest(), _manifest(version="0.0.2"))
    forged = ComponentEvolutionDelta(
        component_id=valid.component_id,
        old_manifest=valid.old_manifest,
        new_manifest=valid.new_manifest,
        changed_fields=valid.changed_fields,
        delta_id="forged",
    )
    with pytest.raises(ValueError, match="integrity"):
        qualify_component_evolution(forged)


def test_adversarial_same_component_identity_cannot_be_rebound_between_manifests() -> None:
    with pytest.raises(ValueError, match="component identity"):
        ComponentEvolutionDelta.create(
            _manifest("external.integration"),
            _manifest("external.planning", "0.0.2"),
        )


def test_adversarial_non_string_impact_identity_is_rejected() -> None:
    with pytest.raises(ValueError):
        IntegrationImpactReason.create(7, "external.planning", "depends", "integrated")  # type: ignore[arg-type]


def test_adversarial_forged_impact_reason_cannot_enter_closure() -> None:
    valid = IntegrationImpactReason.create(
        "external.integration",
        "external.planning",
        "depends",
        "integrated",
    )
    forged = IntegrationImpactReason(
        source_id=valid.source_id,
        target_id=valid.target_id,
        relation=valid.relation,
        contract_kind=valid.contract_kind,
        digest="forged",
    )
    with pytest.raises(ValueError, match="integrity"):
        IntegrationImpactClosure.create(
            changed_component_ids=("external.integration",),
            impacted_component_ids=("external.integration", "external.planning"),
            reasons=(forged,),
            authority_graph_digest="graph-digest",
        )


def test_adversarial_component_cannot_self_certify_revalidation_evidence() -> None:
    evidence = EvidenceRecord(
        evidence_id="ev-self",
        verifier_agent_id="external.integration",
        passed=True,
        false_accepts=0,
        regressions=0,
    )
    with pytest.raises(ValueError, match="self-certify"):
        RevalidationEvidenceBinding.create(
            component_id="external.integration",
            evidence_kind="regression",
            evidence=evidence,
        )


def test_adversarial_empty_evidence_cannot_turn_required_plan_current() -> None:
    requirement = ComponentRevalidationRequirement.create(
        component_id="external.integration",
        required_evidence_kinds=("regression",),
        basis_codes=("COMPONENT_VERSION_CHANGED",),
    )
    plan = RevalidationPlan.create(
        delta_id="delta-id",
        impact_closure_id="closure-id",
        authority_graph_digest="graph-digest",
        disposition=RevalidationDisposition.REVALIDATION_REQUIRED,
        blocker_reason_codes=(),
        requirements=(requirement,),
    )
    assessment = assess_revalidation(plan, ())
    assert assessment.disposition is RevalidationDisposition.REVALIDATION_REQUIRED
    assert assessment.missing_requirements


def test_adversarial_direct_constructor_plan_forgery_fails_before_assessment() -> None:
    requirement = ComponentRevalidationRequirement.create(
        component_id="external.integration",
        required_evidence_kinds=("restore",),
        basis_codes=("COMPONENT_VERSION_CHANGED",),
    )
    valid = RevalidationPlan.create(
        delta_id="delta-id",
        impact_closure_id="closure-id",
        authority_graph_digest="graph-digest",
        disposition=RevalidationDisposition.REVALIDATION_REQUIRED,
        blocker_reason_codes=(),
        requirements=(requirement,),
    )
    forged = RevalidationPlan(
        delta_id=valid.delta_id,
        impact_closure_id=valid.impact_closure_id,
        authority_graph_digest=valid.authority_graph_digest,
        disposition=valid.disposition,
        blocker_reason_codes=valid.blocker_reason_codes,
        requirements=valid.requirements,
        plan_id="forged",
    )
    with pytest.raises(ValueError, match="revalidation"):
        assess_revalidation(forged, ())
