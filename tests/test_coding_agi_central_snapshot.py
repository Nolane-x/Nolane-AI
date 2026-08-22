from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot
from cogcoder.organization.types import AgentRank


def test_central_state_survives_runtime_state_roundtrip_exactly():
    runtime = OrganizationRuntime.first_generation()
    runtime.central.capabilities.observe(
        agent_id='coding.chief', readiness=85, health=90,
        evidence_refs=('ev-s-cap',),
    )
    runtime.central.resources.allocate(
        beneficiary='coding.chief', resource='compute', amount=10,
        reason='bounded direct coding', evidence_refs=('ev-s-resource',),
    )
    lease = runtime.central.core_access.grant_lease(
        core_id='runtime-tracer', owner='debugging-failure', call_budget=2,
        expires_at_token=10, reason='cross-region incident', evidence_refs=('ev-s-core',),
    )
    runtime.central.core_access.consume(lease.lease_id, token=1)
    runtime.central.open_conflict(
        submitted_by=('coding.chief', 'architecture.chief'),
        regions=('core-coding', 'architecture-system'),
        object_refs=('architecture-graph',),
        claims=(
            ('coding.chief', 'ship', ('ev-s-c1',)),
            ('architecture.chief', 'freeze', ('ev-s-c2',)),
        ),
        severity=70,
    )

    before_world = runtime.central.world_state().digest
    restored = OrganizationRuntime.from_state(runtime.to_state())
    assert restored.central.to_state() == runtime.central.to_state()
    assert restored.central.world_state().digest == before_world


def test_organization_snapshot_preserves_central_world_digest():
    runtime = OrganizationRuntime.first_generation()
    runtime.central.capabilities.observe(
        agent_id='debug.chief', readiness=66, health=72,
        evidence_refs=('ev-snap-cap',),
    )
    snapshot = OrganizationSnapshot.capture(runtime)
    restored = OrganizationSnapshot.from_json(snapshot.to_json()).restore()
    assert restored.central.world_state().digest == runtime.central.world_state().digest


def test_first_generation_central_remains_bounded_and_direct_work_capable():
    runtime = OrganizationRuntime.first_generation()
    central = runtime.registry.get('nolane.central')
    assert central.rank is AgentRank.CENTRAL
    assert central.direct_work_capable
    assert central.learning_capable
    assert central.parameter_accounting.total_physical_parameters < 100_000_000
    assert runtime.central.core_access.can_invoke('global-project-graph', token=1)
    assert not runtime.central.core_access.can_invoke('runtime-tracer', token=1)


def test_central_uses_existing_self_model_and_evolution_authorities():
    runtime = OrganizationRuntime.first_generation()
    assert runtime.central.self_models is runtime.self_models
    assert runtime.central.evolution is runtime.evolution
    assert runtime.central.verification is runtime.verification
