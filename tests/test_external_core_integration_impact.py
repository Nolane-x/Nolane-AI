from __future__ import annotations

import pytest

from nolane.external_core.authority_graph import AuthorityEdge, AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.integration_evolution import IntegrationImpactClosure, build_integration_impact_closure


def _manifest(
    component_id: str,
    *,
    consumes: tuple[str, ...] = (),
    produces: tuple[str, ...] = (),
) -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version="0.0.1",
        family=ExternalCoreFamily.D,
        protocol_versions={"core": "1"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=("integrate",) if component_id == "external.integration" else ("plan",),
        forbidden_authorities=("assure", "execute"),
        mutable_resources=(f"state:{component_id}",),
        evidence_inputs=(),
        evidence_outputs=(),
        restore_protocol="exact-revalidation",
        compatibility_floor="0.0.1",
        compatibility_ceiling="0.0.1",
    )


def _graph() -> ExternalAuthorityGraph:
    integration = _manifest("external.integration", produces=("integrated",))
    planning = _manifest("external.planning", consumes=("integrated",), produces=("plan",))
    execution = _manifest("external.execution", consumes=("plan",))
    return ExternalAuthorityGraph(
        (integration, planning, execution),
        (
            AuthorityEdge.create(
                source_component_id="external.integration",
                target_component_id="external.planning",
                relation=AuthorityRelation.PROPOSES_TO,
                contract_kind="integrated",
            ),
            AuthorityEdge.create(
                source_component_id="external.planning",
                target_component_id="external.execution",
                relation=AuthorityRelation.PROPOSES_TO,
                contract_kind="plan",
            ),
        ),
    )


def test_impact_closure_propagates_downstream_across_declared_contract_edge() -> None:
    closure = build_integration_impact_closure(("external.integration",), _graph())
    assert closure.changed_component_ids == ("external.integration",)
    assert closure.impacted_component_ids == (
        "external.execution",
        "external.integration",
        "external.planning",
    )
    assert any(row.source_id == "external.integration" and row.target_id == "external.planning" for row in closure.reasons)
    assert any(row.source_id == "external.planning" and row.target_id == "external.execution" for row in closure.reasons)


def test_impact_closure_rejects_unknown_changed_component() -> None:
    graph = ExternalAuthorityGraph((_manifest("external.integration"),), ())
    with pytest.raises(ValueError, match="unknown"):
        build_integration_impact_closure(("external.unknown",), graph)


def test_impact_closure_exact_restore_is_canonical() -> None:
    closure = build_integration_impact_closure(("external.integration",), _graph())
    assert IntegrationImpactClosure.from_state(closure.to_state()) == closure


def test_impact_closure_restore_rejects_tampering() -> None:
    closure = build_integration_impact_closure(("external.integration",), _graph())
    state = closure.to_state()
    state["closure_id"] = "forged"
    with pytest.raises(ValueError, match="impact"):
        IntegrationImpactClosure.from_state(state)


def test_direct_constructor_forged_impact_closure_fails_integrity() -> None:
    closure = build_integration_impact_closure(("external.integration",), _graph())
    forged = IntegrationImpactClosure(
        changed_component_ids=closure.changed_component_ids,
        impacted_component_ids=closure.impacted_component_ids,
        reasons=closure.reasons,
        authority_graph_digest=closure.authority_graph_digest,
        closure_id="forged",
    )
    with pytest.raises(ValueError, match="impact"):
        forged.validate_integrity()
