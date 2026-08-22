from cogcoder.organization.reliability_operations import FailureScenarioKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot


def test_operations_state_round_trips_exactly_through_organization_snapshot():
    runtime = OrganizationRuntime.first_generation()
    forward = runtime.artifacts.put(kind='migration-forward', producer_agent_id='data.schema-migration.01', content='forward')
    rollback = runtime.artifacts.put(kind='migration-rollback', producer_agent_id='data.schema-migration.01', content='rollback')
    migration = runtime.operations.data.register_migration(
        migration_id='MIG-SNAPSHOT', producer_agent_id='data.schema-migration.01',
        from_schema_version='v1', to_schema_version='v2',
        forward_artifact_id=forward.artifact_id, rollback_artifact_id=rollback.artifact_id,
        compatibility_evidence_refs=('EV-COMPAT',), validation_evidence_refs=('EV-VALIDATE',),
        online=True, idempotent=True,
    )
    runtime.operations.data.assess_migration(migration.migration_id)
    runtime.operations.reliability.record_failure_exercise(
        exercise_id='EX-SNAPSHOT', producer_agent_id='reliability.recovery.01',
        scenario=FailureScenarioKind.NETWORK_TIMEOUT, workload_digest='workload', environment_digest='env',
        injection_artifact_refs=('artifact-timeout',), recovery_strategies=('retry', 'circuit-breaker'),
        recovered=True, data_loss_count=0, duplicate_side_effect_count=0, evidence_refs=('EV-RECOVERY',),
    )
    first = OrganizationSnapshot.capture(runtime)
    restored = OrganizationSnapshot.from_json(first.to_json()).restore()
    second = OrganizationSnapshot.capture(restored)
    assert second.to_json() == first.to_json()
    assert restored.operations.to_state() == runtime.operations.to_state()


def test_operational_context_is_region_scoped_and_private():
    runtime = OrganizationRuntime.first_generation()
    data = runtime.context.compile('data.persistence.01')
    infra = runtime.context.compile('infrastructure.deployment.01')
    reliability = runtime.context.compile('reliability.recovery.01')
    coding = runtime.context.compile('coding.backend.01')

    assert ('data-state', runtime.operations.data.digest) in data.authoritative_artifacts
    assert not any(name in {'infrastructure-state', 'reliability-state'} for name, _ in data.authoritative_artifacts)

    assert ('infrastructure-state', runtime.operations.infrastructure.digest) in infra.authoritative_artifacts
    assert not any(name in {'data-state', 'reliability-state'} for name, _ in infra.authoritative_artifacts)

    assert ('reliability-state', runtime.operations.reliability.digest) in reliability.authoritative_artifacts
    assert not any(name in {'data-state', 'infrastructure-state'} for name, _ in reliability.authoritative_artifacts)

    assert not any(name in {'data-state', 'infrastructure-state', 'reliability-state'} for name, _ in coding.authoritative_artifacts)
