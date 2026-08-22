from cogcoder.organization.assurance_evidence import AssuranceEvidence
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.operations import OperationalReadinessDisposition
from cogcoder.organization.reliability_operations import FailureScenarioKind
from cogcoder.organization.runtime import OrganizationRuntime


def _verified_assurance(runtime, subject_id='OPS-ASSURANCE'):
    artifact = runtime.artifacts.put(kind='ops-assurance-target', producer_agent_id='coding.backend.01', content=subject_id)
    subject = runtime.assurance.register_subject(
        subject_id=subject_id, artifact_id=artifact.artifact_id, producer_agent_id='coding.backend.01',
        subject_version='v1', policy_class='code-change', evidence_refs=('EV-SUBJECT',),
    )
    rows = (
        AssuranceEvidence(
            evidence_id=subject_id + '-U', subject_id=subject.subject_id, subject_version='v1',
            verifier_agent_id='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY,
            passed=True, sandbox_digest='sandbox-u', observed_epoch=runtime.assurance.evidence.current_epoch,
            evidence_refs=('EV-U',),
        ),
        AssuranceEvidence(
            evidence_id=subject_id + '-E', subject_id=subject.subject_id, subject_version='v1',
            verifier_agent_id='verification.integration-e2e.01', domain=AssuranceDomain.INTEGRATION_E2E,
            passed=True, sandbox_digest='sandbox-e', observed_epoch=runtime.assurance.evidence.current_epoch,
            evidence_refs=('EV-E',),
        ),
        AssuranceEvidence(
            evidence_id=subject_id + '-F', subject_id=subject.subject_id, subject_version='v1',
            verifier_agent_id='verification.fuzz-regression.01', domain=AssuranceDomain.FUZZ_REGRESSION,
            passed=True, sandbox_digest='sandbox-f', observed_epoch=runtime.assurance.evidence.current_epoch,
            evidence_refs=('EV-F',),
        ),
    )
    recorded = tuple(runtime.assurance.record_evidence(row) for row in rows)
    runtime.assurance.assess(subject.subject_id, evidence_ids=tuple(row.evidence_id for row in recorded))
    return subject


def _operational_chain(runtime):
    forward = runtime.artifacts.put(kind='migration-forward', producer_agent_id='data.chief', content='forward')
    rollback = runtime.artifacts.put(kind='migration-rollback', producer_agent_id='data.chief', content='rollback')
    migration = runtime.operations.data.register_migration(
        migration_id='MIG-READY', producer_agent_id='data.chief',
        from_schema_version='v1', to_schema_version='v2',
        forward_artifact_id=forward.artifact_id, rollback_artifact_id=rollback.artifact_id,
        compatibility_evidence_refs=('EV-COMPAT',), validation_evidence_refs=('EV-VALIDATE',),
        online=True, idempotent=True,
    )
    migration_receipt = runtime.operations.data.assess_migration(migration.migration_id)

    build_a_artifact = runtime.artifacts.put(kind='build-output', producer_agent_id='infrastructure.chief', content='binary')
    build_b_artifact = runtime.artifacts.put(kind='build-output', producer_agent_id='infrastructure.chief', content='binary')
    common = dict(
        producer_agent_id='infrastructure.chief', source_digest='src', dependency_lock_digest='deps',
        toolchain_digest='tool', environment_digest='env', build_command_digest='cmd', evidence_refs=('EV-BUILD',),
    )
    build_a = runtime.operations.infrastructure.register_build(build_id='BUILD-A', artifact_id=build_a_artifact.artifact_id, **common)
    build_b = runtime.operations.infrastructure.register_build(build_id='BUILD-B', artifact_id=build_b_artifact.artifact_id, **common)
    reproduction = runtime.operations.infrastructure.assess_reproducibility(build_a.build_id, build_b.build_id)
    package = runtime.artifacts.put(kind='release-package', producer_agent_id='infrastructure.chief', content='package')
    release_rollback = runtime.artifacts.put(kind='release-rollback', producer_agent_id='infrastructure.chief', content='rollback-package')
    obs = runtime.operations.infrastructure.register_observability(
        bundle_id='OBS-READY', producer_agent_id='infrastructure.chief',
        log_schema_digest='logs', metric_schema_digest='metrics', trace_schema_digest='traces',
        slo_refs=('SLO-1',), evidence_refs=('EV-OBS',),
    )
    release = runtime.operations.infrastructure.register_release(
        release_id='REL-READY', producer_agent_id='infrastructure.chief',
        build_reproduction_receipt_id=reproduction.receipt_id, package_artifact_id=package.artifact_id,
        config_digest='config', deployment_topology_digest='topology', rollback_artifact_id=release_rollback.artifact_id,
        observability_bundle_id=obs.bundle_id, evidence_refs=('EV-REL',),
    )
    release_receipt = runtime.operations.infrastructure.assess_release(release.release_id)

    exercises = []
    for index, scenario in enumerate(FailureScenarioKind):
        exercises.append(runtime.operations.reliability.record_failure_exercise(
            exercise_id=f'EX-R-{index}', producer_agent_id='reliability.chief', scenario=scenario,
            workload_digest='workload', environment_digest='runtime-env',
            injection_artifact_refs=(f'artifact-injection-{index}',),
            recovery_strategies=('retry', 'idempotency', 'checkpoint', 'deduplicate'),
            recovered=True, data_loss_count=0, duplicate_side_effect_count=0,
            evidence_refs=(f'EV-R-{index}',),
        ))
    matrix = runtime.operations.reliability.assess_matrix(tuple(row.exercise_id for row in exercises))
    return migration_receipt, release_receipt, matrix


def test_verified_assurance_plus_clean_operational_chain_is_ready():
    runtime = OrganizationRuntime.first_generation()
    subject = _verified_assurance(runtime)
    migration, release, matrix = _operational_chain(runtime)
    receipt = runtime.operations.assess_readiness(
        readiness_id='OPS-READY-1', migration_receipt_ids=(migration.receipt_id,),
        release_readiness_receipt_id=release.receipt_id, reliability_matrix_receipt_id=matrix.receipt_id,
        performance_claim_receipt_ids=(), assurance_subject_id=subject.subject_id,
    )
    assert receipt.disposition is OperationalReadinessDisposition.READY
    assert receipt.reasons == ()


def test_assurance_pending_or_rejected_blocks_operational_readiness():
    runtime = OrganizationRuntime.first_generation()
    artifact = runtime.artifacts.put(kind='pending-target', producer_agent_id='coding.backend.01', content='pending')
    subject = runtime.assurance.register_subject(
        subject_id='OPS-PENDING', artifact_id=artifact.artifact_id, producer_agent_id='coding.backend.01',
        subject_version='v1', policy_class='code-change', evidence_refs=('EV-PENDING',),
    )
    migration, release, matrix = _operational_chain(runtime)
    receipt = runtime.operations.assess_readiness(
        readiness_id='OPS-BLOCKED-1', migration_receipt_ids=(migration.receipt_id,),
        release_readiness_receipt_id=release.receipt_id, reliability_matrix_receipt_id=matrix.receipt_id,
        performance_claim_receipt_ids=(), assurance_subject_id=subject.subject_id,
    )
    assert receipt.disposition is OperationalReadinessDisposition.BLOCKED
    assert 'assurance_not_verified_or_overridden' in receipt.reasons


def test_central_assurance_override_is_preserved_as_ready_with_override_not_verified_ready():
    runtime = OrganizationRuntime.first_generation()
    artifact = runtime.artifacts.put(kind='override-target', producer_agent_id='nolane.central', content='override')
    subject = runtime.assurance.register_subject(
        subject_id='OPS-OVERRIDE', artifact_id=artifact.artifact_id, producer_agent_id='nolane.central',
        subject_version='v1', policy_class='security-sensitive', evidence_refs=('EV-OVERRIDE-SUBJECT',),
    )
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=())
    runtime.assurance.central_override(
        subject_id=subject.subject_id, decision_id=decision.decision_id,
        reason='controlled emergency rollout', evidence_ids=('EV-RISK-ACCEPT',),
    )
    migration, release, matrix = _operational_chain(runtime)
    receipt = runtime.operations.assess_readiness(
        readiness_id='OPS-OVERRIDE-READY', migration_receipt_ids=(migration.receipt_id,),
        release_readiness_receipt_id=release.receipt_id, reliability_matrix_receipt_id=matrix.receipt_id,
        performance_claim_receipt_ids=(), assurance_subject_id=subject.subject_id,
    )
    assert receipt.disposition is OperationalReadinessDisposition.READY_WITH_ASSURANCE_OVERRIDE
    assert runtime.assurance.effective_disposition(subject.subject_id).value == 'overridden'


def test_failed_operational_receipt_blocks_even_with_verified_assurance():
    runtime = OrganizationRuntime.first_generation()
    subject = _verified_assurance(runtime, 'OPS-ASSURANCE-FAILCHAIN')
    migration, release, _matrix = _operational_chain(runtime)
    incomplete = runtime.operations.reliability.assess_matrix(())
    receipt = runtime.operations.assess_readiness(
        readiness_id='OPS-BLOCKED-FAILCHAIN', migration_receipt_ids=(migration.receipt_id,),
        release_readiness_receipt_id=release.receipt_id, reliability_matrix_receipt_id=incomplete.receipt_id,
        performance_claim_receipt_ids=(), assurance_subject_id=subject.subject_id,
    )
    assert receipt.disposition is OperationalReadinessDisposition.BLOCKED
    assert 'reliability_matrix_not_ready' in receipt.reasons
