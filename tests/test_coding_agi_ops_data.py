import pytest

from cogcoder.organization.artifacts import ArtifactStore
from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.data_operations import DataOperationsLedger
from cogcoder.organization.registry import AgentRegistry


def _ledger():
    return DataOperationsLedger(
        registry=AgentRegistry(build_first_generation_blueprint()),
        artifacts=ArtifactStore(),
    )


def _artifact(ledger, producer, content):
    return ledger.artifacts.put(kind='migration-artifact', producer_agent_id=producer, content=content)


def test_migration_id_is_immutable_and_ready_requires_distinct_rollback_compatibility_validation():
    ledger = _ledger()
    forward = _artifact(ledger, 'data.schema-migration.01', 'ALTER TABLE example ADD COLUMN value TEXT')
    rollback = _artifact(ledger, 'data.schema-migration.01', 'ALTER TABLE example DROP COLUMN value')
    plan = ledger.register_migration(
        migration_id='MIG-1', producer_agent_id='data.schema-migration.01',
        from_schema_version='v1', to_schema_version='v2',
        forward_artifact_id=forward.artifact_id, rollback_artifact_id=rollback.artifact_id,
        compatibility_evidence_refs=('EV-COMPAT',), validation_evidence_refs=('EV-VALIDATE',),
        online=True, idempotent=True,
    )
    assert ledger.assess_migration(plan.migration_id).ready is True
    with pytest.raises(ValueError):
        ledger.register_migration(
            migration_id='MIG-1', producer_agent_id='data.schema-migration.01',
            from_schema_version='v1', to_schema_version='v3',
            forward_artifact_id=forward.artifact_id, rollback_artifact_id=rollback.artifact_id,
            compatibility_evidence_refs=('EV-OTHER',), validation_evidence_refs=('EV-OTHER',),
            online=False, idempotent=False,
        )


def test_migration_readiness_fails_closed_for_missing_rollback_or_evidence():
    ledger = _ledger()
    forward = _artifact(ledger, 'data.chief', 'forward-v2')
    missing = ledger.register_migration(
        migration_id='MIG-MISSING', producer_agent_id='data.chief',
        from_schema_version='v1', to_schema_version='v2',
        forward_artifact_id=forward.artifact_id, rollback_artifact_id='',
        compatibility_evidence_refs=(), validation_evidence_refs=(), online=True, idempotent=False,
    )
    receipt = ledger.assess_migration(missing.migration_id)
    assert receipt.ready is False
    assert 'missing_rollback_artifact' in receipt.reasons
    assert 'missing_compatibility_evidence' in receipt.reasons
    assert 'missing_validation_evidence' in receipt.reasons

    same = ledger.register_migration(
        migration_id='MIG-SAME', producer_agent_id='data.chief',
        from_schema_version='v1', to_schema_version='v2',
        forward_artifact_id=forward.artifact_id, rollback_artifact_id=forward.artifact_id,
        compatibility_evidence_refs=('EV-C',), validation_evidence_refs=('EV-V',), online=False, idempotent=True,
    )
    same_receipt = ledger.assess_migration(same.migration_id)
    assert same_receipt.ready is False
    assert 'rollback_matches_forward' in same_receipt.reasons


def test_non_data_identity_cannot_author_data_operational_records():
    ledger = _ledger()
    forward = _artifact(ledger, 'coding.backend.01', 'forward')
    rollback = _artifact(ledger, 'coding.backend.01', 'rollback')
    with pytest.raises(PermissionError):
        ledger.register_migration(
            migration_id='MIG-BAD-AUTH', producer_agent_id='coding.backend.01',
            from_schema_version='v1', to_schema_version='v2',
            forward_artifact_id=forward.artifact_id, rollback_artifact_id=rollback.artifact_id,
            compatibility_evidence_refs=('EV-C',), validation_evidence_refs=('EV-V',), online=False, idempotent=False,
        )


def test_persistence_and_cache_consistency_records_are_evidence_grounded_and_round_trip():
    ledger = _ledger()
    invariant = ledger.record_persistence_invariant(
        invariant_id='INV-1', producer_agent_id='data.persistence.01',
        name='committed writes survive restart', statement='a committed transaction is durable after restart',
        evidence_refs=('EV-DURABILITY',),
    )
    exercise = ledger.record_consistency_exercise(
        exercise_id='CONS-1', producer_agent_id='data.cache-consistency.01',
        source_version='db-v12', cache_version='cache-v12',
        operation_sequence=('write:key=7', 'invalidate:key', 'read:key'),
        observed_result='7', expected_result='7', evidence_refs=('EV-CONSISTENCY',),
    )
    assert invariant.digest and exercise.consistent is True
    state = ledger.to_state()
    restored = DataOperationsLedger.from_state(registry=ledger.registry, artifacts=ledger.artifacts, state=state)
    assert restored.to_state() == state
