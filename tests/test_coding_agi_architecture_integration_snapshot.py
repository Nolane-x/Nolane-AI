from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.adr import ADRStatus
from cogcoder.organization.compatibility import CompatibilityAssessment, CompatibilityClass
from cogcoder.organization.integration import ChangeCandidate
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot


def test_architecture_integration_and_adr_restore_exactly():
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief', reason='seed', evidence_refs=('EV-S-1',),
        upsert_components=(ArchitectureComponent('A','A',ComponentKind.MODULE,'core-coding','internal'),),
    )
    adr = runtime.adr.propose(
        source_agent_id='architecture.chief', title='Boundary', context='Need boundary',
        alternatives=('A','B'), decision='A', rationale='evidence',
        architecture_refs=('A',), evidence_refs=('EV-S-2',),
    )
    runtime.adr.accept(adr.adr_id, actor_agent_id='architecture.chief', evidence_refs=('EV-S-3',))
    assessment = CompatibilityAssessment('CA-1', CompatibilityClass.COMPATIBLE, True, 'same contract', ('EV-S-4',), 'digest-ca-1')
    candidate = ChangeCandidate(
        candidate_id='C-1', producer_agent_id='coding.backend.01',
        task_refs=('T-1',), plan_refs=('P-1',), requirement_refs=('REQ-1',),
        architecture_version_expected=runtime.architecture.graph.version,
        changed_component_refs=('A',), changed_interface_refs=(),
        compatibility_assessments=(assessment,), verification_evidence_refs=('EV-S-5',),
    )
    runtime.integration.add_candidate(actor_agent_id='integration.chief', candidate=candidate)

    snap = OrganizationSnapshot.capture(runtime)
    restored = OrganizationSnapshot.from_json(snap.to_json()).restore()
    assert restored.architecture.to_state() == runtime.architecture.to_state()
    assert restored.adr.to_state() == runtime.adr.to_state()
    assert restored.integration.to_state() == runtime.integration.to_state()
    assert restored.adr.get(adr.adr_id).status is ADRStatus.ACCEPTED


def test_context_exposes_current_architecture_and_integration_authority_versions():
    runtime = OrganizationRuntime.first_generation()
    checkpoint = runtime.checkpoint_agent('coding.backend.01')
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief', reason='new boundary', evidence_refs=('EV-C-1',),
        upsert_components=(ArchitectureComponent('A','A',ComponentKind.MODULE,'core-coding','internal'),),
    )
    capsule = runtime.wake_agent('coding.backend.01', reason='architecture changed')
    assert capsule.since_event_id == checkpoint
    assert ('architecture-graph', runtime.architecture.graph.version) in capsule.authoritative_artifacts
    assert ('integration-state', runtime.integration.graph.version) in capsule.authoritative_artifacts
