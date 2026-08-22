import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import AgentStatus, EventKind


def _ids(runtime, agent_id):
    return {event.event_id for event in runtime.ledger.deliverable_for(agent_id)}


def test_direct_correction_is_same_authoritative_event_for_target_and_chief():
    runtime = OrganizationRuntime.first_generation()
    event = runtime.central.correct(
        target_agent_id='coding.backend.01',
        directive='do not mutate architecture authority',
        evidence_refs=('ev-central-1',),
    )
    assert event.kind is EventKind.CENTRAL_CORRECTION
    assert event.event_id in _ids(runtime, 'coding.backend.01')
    assert event.event_id in _ids(runtime, 'coding.chief')
    assert event.requires_ack


def test_pause_and_abort_are_explicit_state_changes():
    runtime = OrganizationRuntime.first_generation()
    runtime.central.pause(
        target_agent_id='coding.backend.01',
        directive='pause for architecture reconciliation',
        evidence_refs=('ev-central-2',),
    )
    assert runtime.registry.get('coding.backend.01').status is AgentStatus.PAUSED

    runtime.registry.set_status('coding.backend.01', AgentStatus.ACTIVE)
    runtime.tasks.add_task('T-central-abort', title='unsafe implementation', plan_node_id='P-abort')
    runtime.tasks.lease('T-central-abort', 'coding.backend.01')
    event = runtime.central.abort(
        target_agent_id='coding.backend.01',
        directive='abort unsafe implementation',
        evidence_refs=('ev-central-3',),
    )
    task = runtime.tasks.get('T-central-abort')
    assert event.kind is EventKind.CENTRAL_ABORT
    assert task.aborted_by == 'nolane.central'
    assert task.leased_to is None
    assert runtime.registry.get('coding.backend.01').current_task is None
    assert runtime.registry.get('coding.backend.01').status is AgentStatus.PAUSED


def test_state_changing_central_actions_require_evidence():
    runtime = OrganizationRuntime.first_generation()
    with pytest.raises(ValueError):
        runtime.central.correct(
            target_agent_id='coding.backend.01',
            directive='missing evidence',
            evidence_refs=(),
        )
    with pytest.raises(ValueError):
        runtime.central.pause(
            target_agent_id='coding.backend.01',
            directive='missing evidence',
            evidence_refs=(),
        )


def test_central_direct_work_requires_real_artifact_and_evidence():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-central-work', title='bounded architecture audit', plan_node_id='P-central')
    runtime.tasks.lease('T-central-work', 'nolane.central')

    artifact = runtime.artifacts.put(
        kind='analysis',
        producer_agent_id='nolane.central',
        content='bounded result with explicit acceptance evidence',
        evidence_refs=('ev-work-1',),
    )

    with pytest.raises(ValueError):
        runtime.central.complete_direct_work(
            task_id='T-central-work',
            artifact_ids=(artifact.artifact_id,),
            evidence_refs=(),
        )

    receipt = runtime.central.complete_direct_work(
        task_id='T-central-work',
        artifact_ids=(artifact.artifact_id,),
        evidence_refs=('ev-work-1',),
    )
    assert receipt.task_id == 'T-central-work'
    assert receipt.producer_agent_id == 'nolane.central'
    assert receipt.artifact_ids == (artifact.artifact_id,)
    assert runtime.tasks.get('T-central-work').completed_by == 'nolane.central'
    direct_events = [e for e in runtime.ledger.deliverable_for('nolane.central') if e.kind is EventKind.CENTRAL_DIRECT_WORK]
    assert direct_events


def test_conflict_resolution_does_not_erase_independent_block():
    runtime = OrganizationRuntime.first_generation()
    block = runtime.authority.record_block(
        'architecture-graph',
        'verification.chief',
        reason='fresh verification found incompatible interface',
    )
    packet = runtime.central.open_conflict(
        submitted_by=('coding.chief', 'architecture.chief'),
        regions=('core-coding', 'architecture-system'),
        object_refs=('architecture-graph',),
        claims=(
            ('coding.chief', 'ship interface', ('ev-conflict-1',)),
            ('architecture.chief', 'freeze interface', ('ev-conflict-2',)),
        ),
        severity=90,
    )
    runtime.central.resolve_conflict(
        packet.conflict_id,
        decision='freeze interface',
        rationale='verification evidence dominates',
        evidence_refs=('ev-conflict-resolution',),
    )
    assert runtime.authority.blocks_for('architecture-graph') == (block,)
    assert not runtime.authority.can_write('nolane.central', 'architecture-graph')
