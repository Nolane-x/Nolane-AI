import pytest

from cogcoder.organization.architecture import (
    ArchitectureComponent,
    ArchitectureEdge,
    ComponentKind,
    EdgeKind,
    InterfaceClass,
    InterfaceContract,
    InterfaceStability,
)
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind


def _component(component_id: str, *, deps=(), requirement_refs=()):
    return ArchitectureComponent(
        component_id=component_id,
        title=f'Component {component_id}',
        kind=ComponentKind.MODULE,
        owner_region='core-coding',
        trust_zone='internal',
        requirement_refs=tuple(requirement_refs),
    )


def test_architecture_revision_is_owner_evidence_gated_and_atomic():
    runtime = OrganizationRuntime.first_generation()
    api = InterfaceContract(
        interface_id='IF-A', producer_component_id='A',
        interface_class=InterfaceClass.API, semantic_version='1.0.0',
        signature_digest='sig-v1', stability=InterfaceStability.INTERNAL,
    )
    rev = runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief', reason='establish boundary',
        evidence_refs=('EV-A-1',),
        upsert_components=(_component('A'), _component('B')),
        upsert_interfaces=(api,),
        upsert_edges=(ArchitectureEdge('E-B-A', 'B', 'A', EdgeKind.DEPENDS_ON),),
    )
    assert rev.version == 1
    before = runtime.architecture.to_state()

    with pytest.raises(PermissionError):
        runtime.architecture.apply_revision(
            actor_agent_id='coding.backend.01', reason='silent rewrite', evidence_refs=('EV-A-2',),
            upsert_components=(_component('C'),),
        )
    assert runtime.architecture.to_state() == before

    with pytest.raises(ValueError, match='cycle'):
        runtime.architecture.apply_revision(
            actor_agent_id='architecture.chief', reason='bad cycle', evidence_refs=('EV-A-3',),
            upsert_edges=(ArchitectureEdge('E-A-B', 'A', 'B', EdgeKind.DEPENDS_ON),),
        )
    assert runtime.architecture.to_state() == before


def test_worker_architecture_concern_does_not_mutate_graph():
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief', reason='seed', evidence_refs=('EV-A-4',),
        upsert_components=(_component('A'),),
    )
    before = runtime.architecture.to_state()
    event = runtime.architecture.propose_concern(
        source_agent_id='coding.backend.01',
        component_refs=('A',),
        observation='new direct database call violates intended boundary',
        alternatives=('repository-interface', 'event-boundary'),
        evidence_refs=('EV-A-5',),
        severity=80,
    )
    assert event.kind is EventKind.ARCHITECTURE_CONCERN
    assert event.target_agent_id == 'architecture.chief'
    assert runtime.architecture.to_state() == before
