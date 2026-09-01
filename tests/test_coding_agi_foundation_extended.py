import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord, EventKind, MemoryScope, MemoryStatus


def test_identity_tracks_specialization_authority_checkpoint_and_self_model_versions():
    runtime = OrganizationRuntime.first_generation()
    row = runtime.registry.get('coding.backend.01')
    assert row.specialization_version
    assert row.authority_scope
    assert row.self_model_version
    assert row.checkpoint_id is None

    runtime.checkpoint_agent(row.agent_id)
    assert runtime.registry.get(row.agent_id).checkpoint_id is not None


def test_external_cores_are_owned_by_regions_and_not_implicitly_owned_by_central():
    runtime = OrganizationRuntime.first_generation()
    trace = runtime.external_cores.get('runtime-tracer')
    assert trace.owner_agent_or_region == 'debugging-failure'
    assert 'runtime-tracer' in runtime.registry.get('debug.runtime-trace.01').external_core_bindings
    assert 'runtime-tracer' not in runtime.registry.get('nolane.central').external_core_bindings
    assert trace.verification_hooks
    assert trace.failure_modes


def test_artifact_store_is_content_addressed_and_keeps_provenance():
    runtime = OrganizationRuntime.first_generation()
    first = runtime.artifacts.put(
        kind='trace',
        producer_agent_id='debug.runtime-trace.01',
        content='frame-a -> frame-b',
        evidence_refs=('EV-9',),
    )
    duplicate = runtime.artifacts.put(
        kind='trace',
        producer_agent_id='debug.runtime-trace.01',
        content='frame-a -> frame-b',
        evidence_refs=('EV-9',),
    )
    changed = runtime.artifacts.put(
        kind='trace',
        producer_agent_id='debug.runtime-trace.01',
        content='frame-a -> frame-c',
        evidence_refs=('EV-9',),
    )
    assert first.artifact_id == duplicate.artifact_id
    assert changed.artifact_id != first.artifact_id
    assert runtime.artifacts.get(first.artifact_id).producer_agent_id == 'debug.runtime-trace.01'


def test_memory_lifecycle_excludes_contradicted_entries_from_normal_retrieval_but_preserves_history():
    runtime = OrganizationRuntime.first_generation()
    row = runtime.memory.write(MemoryScope.PERSONAL, 'old assumption', owner_agent_id='coding.backend.01')
    runtime.memory.set_status(row.memory_id, MemoryStatus.CONTRADICTED, reason='fresh trace disproved assumption')
    normal = runtime.memory.retrieve(agent_id='coding.backend.01', region='core-coding')
    historical = runtime.memory.retrieve(agent_id='coding.backend.01', region='core-coding', include_inactive=True)
    assert all(entry.memory_id != row.memory_id for entry in normal)
    assert any(entry.memory_id == row.memory_id and entry.status is MemoryStatus.CONTRADICTED for entry in historical)


def test_self_model_can_only_improve_from_valid_external_evidence():
    runtime = OrganizationRuntime.first_generation()
    agent_id = 'debug.runtime-trace.01'
    before = runtime.self_models.get(agent_id)

    bad = EvidenceRecord('EV-BAD', 'debug.runtime-trace.01', passed=False, notes='self assertion only')
    with pytest.raises(PermissionError):
        runtime.self_models.update_competence(agent_id, domain='runtime-debugging', score=0.8, evidence=bad)

    good = EvidenceRecord('EV-GOOD', 'verification.integration-e2e.01', passed=True, notes='fresh heldout verification')
    authority = runtime.learning_substrate.learning_authority
    lease = authority.issue(
        subject_kind='self_model',
        subject_id=agent_id,
        operation_class='self_model.update_competence',
        producer_agent_id=agent_id,
        evidence=good,
        subject_digest=runtime.self_models.competence_subject_digest(
            agent_id, domain='runtime-debugging', score=0.8,
        ),
    )
    after = runtime.self_models.update_competence(
        agent_id, domain='runtime-debugging', score=0.8, evidence=good,
        authority_lease_id=lease.lease_id,
    )
    assert after.version != before.version
    assert dict(after.domain_competence)['runtime-debugging'] == 0.8
    assert 'EV-GOOD' in after.evidence_ids


def test_part_i_event_vocabulary_contains_architecture_bug_evidence_and_explicit_central_actions():
    required = {
        'TASK_ASSIGNED',
        'TASK_PROGRESS',
        'ARCHITECTURE_CONCERN',
        'BUG_DISCOVERED',
        'HYPOTHESIS_PROPOSED',
        'EVIDENCE_ADDED',
        'TEST_PASSED',
        'SKILL_CANDIDATE',
        'SKILL_REJECTED',
        'MEMORY_CONFLICT',
        'CENTRAL_QUESTION',
        'CENTRAL_CORRECTION',
        'CENTRAL_REDIRECT',
        'CENTRAL_PAUSE',
        'CENTRAL_ABORT',
        'CENTRAL_REQUEST_EVIDENCE',
        'AGENT_CHECKPOINTED',
    }
    assert required <= set(EventKind.__members__)
