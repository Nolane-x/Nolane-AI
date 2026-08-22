from cogcoder.organization.artifacts import ArtifactStore
from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.infrastructure_operations import InfrastructureOperationsLedger
from cogcoder.organization.registry import AgentRegistry


def _ledger():
    return InfrastructureOperationsLedger(
        registry=AgentRegistry(build_first_generation_blueprint()), artifacts=ArtifactStore(),
    )


def _build(ledger, build_id, artifact_content, **overrides):
    artifact = ledger.artifacts.put(
        kind='build-output', producer_agent_id='infrastructure.ci-env.01', content=artifact_content,
    )
    args = dict(
        build_id=build_id, producer_agent_id='infrastructure.ci-env.01',
        source_digest='src-1', dependency_lock_digest='deps-1', toolchain_digest='toolchain-1',
        environment_digest='env-1', build_command_digest='cmd-1', artifact_id=artifact.artifact_id,
        evidence_refs=(f'EV-{build_id}',),
    )
    args.update(overrides)
    return ledger.register_build(**args)


def test_build_reproduction_requires_identical_basis_and_artifact_digest():
    ledger = _ledger()
    original = _build(ledger, 'BUILD-1', 'binary-A')
    exact = _build(ledger, 'BUILD-2', 'binary-A')
    exact_receipt = ledger.assess_reproducibility(original.build_id, exact.build_id)
    assert exact_receipt.reproducible is True
    assert exact_receipt.reasons == ()

    changed_basis = _build(ledger, 'BUILD-3', 'binary-A', environment_digest='env-2')
    basis_receipt = ledger.assess_reproducibility(original.build_id, changed_basis.build_id)
    assert basis_receipt.reproducible is False
    assert 'build_basis_mismatch' in basis_receipt.reasons

    changed_output = _build(ledger, 'BUILD-4', 'binary-B')
    output_receipt = ledger.assess_reproducibility(original.build_id, changed_output.build_id)
    assert output_receipt.reproducible is False
    assert 'artifact_digest_mismatch' in output_receipt.reasons


def test_release_readiness_requires_reproducible_build_rollback_and_observability():
    ledger = _ledger()
    original = _build(ledger, 'BUILD-R1', 'release-binary')
    replay = _build(ledger, 'BUILD-R2', 'release-binary')
    reproduction = ledger.assess_reproducibility(original.build_id, replay.build_id)
    package = ledger.artifacts.put(kind='release-package', producer_agent_id='infrastructure.chief', content='package')
    rollback = ledger.artifacts.put(kind='rollback-package', producer_agent_id='infrastructure.chief', content='rollback')
    observability = ledger.register_observability(
        bundle_id='OBS-1', producer_agent_id='infrastructure.observability-release.01',
        log_schema_digest='logs-1', metric_schema_digest='metrics-1', trace_schema_digest='traces-1',
        slo_refs=('SLO-AVAILABILITY',), evidence_refs=('EV-OBS',),
    )
    release = ledger.register_release(
        release_id='REL-1', producer_agent_id='infrastructure.chief',
        build_reproduction_receipt_id=reproduction.receipt_id, package_artifact_id=package.artifact_id,
        config_digest='config-1', deployment_topology_digest='topology-1',
        rollback_artifact_id=rollback.artifact_id, observability_bundle_id=observability.bundle_id,
        evidence_refs=('EV-RELEASE',),
    )
    ready = ledger.assess_release(release.release_id)
    assert ready.ready is True

    missing = ledger.register_release(
        release_id='REL-MISSING', producer_agent_id='infrastructure.chief',
        build_reproduction_receipt_id=reproduction.receipt_id, package_artifact_id=package.artifact_id,
        config_digest='config-1', deployment_topology_digest='topology-1',
        rollback_artifact_id='', observability_bundle_id='', evidence_refs=('EV-MISSING',),
    )
    denied = ledger.assess_release(missing.release_id)
    assert denied.ready is False
    assert 'missing_rollback_artifact' in denied.reasons
    assert 'missing_observability_bundle' in denied.reasons


def test_infrastructure_state_round_trips_exactly():
    ledger = _ledger()
    original = _build(ledger, 'BUILD-S1', 'snapshot-binary')
    replay = _build(ledger, 'BUILD-S2', 'snapshot-binary')
    ledger.assess_reproducibility(original.build_id, replay.build_id)
    state = ledger.to_state()
    restored = InfrastructureOperationsLedger.from_state(registry=ledger.registry, artifacts=ledger.artifacts, state=state)
    assert restored.to_state() == state
