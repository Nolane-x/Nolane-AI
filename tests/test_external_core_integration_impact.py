from __future__ import annotations

from nolane.external_core.authority_graph import AuthorityEdge, AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.integration_evolution import build_integration_impact_closure


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


def test_impact_closure_propagates_downstream_across_declared_contract_edge() -> None:
    integration = _manifest("external.integration", produces=("integrated",))
    planning = _manifest("external.planning", consumes=("integrated",), produces=("plan",))
    execution = _manifest("external.execution", consumes=("plan",))
    graph = ExternalAuthorityGraph(
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
    closure = build_integration_impact_closure(("external.integration",), graph)
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
    try:
        build_integration_impact_closure(("external.unknown",), graph)
    except ValueError as exc:
        assert "unknown" in str(exc).lower()
    else:
        raise AssertionError("unknown changed component was accepted")
