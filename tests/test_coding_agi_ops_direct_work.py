from cogcoder.organization.reliability_operations import FailureScenarioKind
from cogcoder.organization.runtime import OrganizationRuntime


def test_data_chief_directly_builds_and_validates_migration_rollback_chain():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-DATA-CHIEF', title='Own reversible schema migration', plan_node_id='P-DATA-CHIEF')
    runtime.tasks.lease('T-DATA-CHIEF', 'data.chief')
    forward = runtime.artifacts.put(kind='migration-forward', producer_agent_id='data.chief', content='forward')
    rollback = runtime.artifacts.put(kind='migration-rollback', producer_agent_id='data.chief', content='rollback')
    plan = runtime.operations.data.register_migration(
        migration_id='MIG-DATA-CHIEF', producer_agent_id='data.chief',
        from_schema_version='v1', to_schema_version='v2',
        forward_artifact_id=forward.artifact_id, rollback_artifact_id=rollback.artifact_id,
        compatibility_evidence_refs=('EV-COMPAT',), validation_evidence_refs=('EV-VALIDATE',),
        online=True, idempotent=True,
    )
    receipt = runtime.operations.data.assess_migration(plan.migration_id)
    assert receipt.ready is True
    evidence_artifact = runtime.artifacts.put(kind='migration-readiness', producer_agent_id='data.chief', content=receipt.digest)
    completed = runtime.chief_direct_work('data.chief', 'T-DATA-CHIEF', output_artifact_ids=(evidence_artifact.artifact_id,))
    assert completed['chief_agent_id'] == 'data.chief'


def test_infrastructure_chief_directly_builds_reproducible_release_observability_chain():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-INFRA-CHIEF', title='Own reproducible release chain', plan_node_id='P-INFRA-CHIEF')
    runtime.tasks.lease('T-INFRA-CHIEF', 'infrastructure.chief')
    artifact = runtime.artifacts.put(kind='build-output', producer_agent_id='infrastructure.chief', content='binary')
    common = dict(
        producer_agent_id='infrastructure.chief', source_digest='src', dependency_lock_digest='deps',
        toolchain_digest='tool', environment_digest='env', build_command_digest='cmd',
        artifact_id=artifact.artifact_id, evidence_refs=('EV-BUILD',),
    )
    first = runtime.operations.infrastructure.register_build(build_id='BUILD-INFRA-A', **common)
    second = runtime.operations.infrastructure.register_build(build_id='BUILD-INFRA-B', **common)
    reproduction = runtime.operations.infrastructure.assess_reproducibility(first.build_id, second.build_id)
    obs = runtime.operations.infrastructure.register_observability(
        bundle_id='OBS-INFRA', producer_agent_id='infrastructure.chief',
        log_schema_digest='logs', metric_schema_digest='metrics', trace_schema_digest='traces',
        slo_refs=('SLO-1',), evidence_refs=('EV-OBS',),
    )
    package = runtime.artifacts.put(kind='release-package', producer_agent_id='infrastructure.chief', content='package')
    rollback = runtime.artifacts.put(kind='release-rollback', producer_agent_id='infrastructure.chief', content='rollback')
    release = runtime.operations.infrastructure.register_release(
        release_id='REL-INFRA', producer_agent_id='infrastructure.chief',
        build_reproduction_receipt_id=reproduction.receipt_id, package_artifact_id=package.artifact_id,
        config_digest='config', deployment_topology_digest='topology', rollback_artifact_id=rollback.artifact_id,
        observability_bundle_id=obs.bundle_id, evidence_refs=('EV-REL',),
    )
    release_receipt = runtime.operations.infrastructure.assess_release(release.release_id)
    assert reproduction.reproducible is True and release_receipt.ready is True
    out = runtime.artifacts.put(kind='release-readiness', producer_agent_id='infrastructure.chief', content=release_receipt.digest)
    completed = runtime.chief_direct_work('infrastructure.chief', 'T-INFRA-CHIEF', output_artifact_ids=(out.artifact_id,))
    assert completed['chief_agent_id'] == 'infrastructure.chief'


def test_reliability_chief_directly_exercises_adverse_recovery_and_measured_performance():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-RELIABILITY-CHIEF', title='Own restart recovery proof', plan_node_id='P-RELIABILITY-CHIEF')
    runtime.tasks.lease('T-RELIABILITY-CHIEF', 'reliability.chief')
    exercise = runtime.operations.reliability.record_failure_exercise(
        exercise_id='EX-CHIEF-RESTART', producer_agent_id='reliability.chief',
        scenario=FailureScenarioKind.RESTART, workload_digest='workload', environment_digest='env',
        injection_artifact_refs=('artifact-process-restart',),
        recovery_strategies=('checkpoint', 'idempotency', 'deduplicate'),
        recovered=True, data_loss_count=0, duplicate_side_effect_count=0,
        evidence_refs=('EV-RECOVERY',),
    )
    measurement = runtime.operations.reliability.record_performance_measurement(
        measurement_id='PERF-CHIEF', producer_agent_id='reliability.chief',
        baseline_workload_digest='workload', candidate_workload_digest='workload',
        baseline_environment_digest='env', candidate_environment_digest='env',
        metric_name='recovery_time', unit='ms', baseline_value=300.0, candidate_value=180.0,
        lower_is_better=True, baseline_samples=10, candidate_samples=10, evidence_refs=('EV-PERF',),
    )
    performance = runtime.operations.reliability.assess_performance(measurement.measurement_id)
    assert exercise.recovered is True and performance.valid is True
    out = runtime.artifacts.put(kind='reliability-evidence', producer_agent_id='reliability.chief', content=exercise.digest + performance.digest)
    completed = runtime.chief_direct_work('reliability.chief', 'T-RELIABILITY-CHIEF', output_artifact_ids=(out.artifact_id,))
    assert completed['chief_agent_id'] == 'reliability.chief'
