import pytest

from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.compatibility import CompatibilityAssessment, CompatibilityClass
from cogcoder.organization.integration import ChangeCandidate, ChangeCandidateStatus
from cogcoder.organization.runtime import OrganizationRuntime


def _candidate(candidate_id: str, *, deps=(), conflicts=(), expected_version=1, compatibility=CompatibilityClass.COMPATIBLE):
    assessment = CompatibilityAssessment(
        assessment_id=f'CA-{candidate_id}',
        compatibility=compatibility,
        integration_safe=compatibility is CompatibilityClass.COMPATIBLE,
        reason='test assessment',
        evidence_refs=('EV-COMP',),
        digest=f'digest-{candidate_id}',
    )
    return ChangeCandidate(
        candidate_id=candidate_id,
        producer_agent_id='coding.backend.01',
        task_refs=(f'T-{candidate_id}',),
        plan_refs=('P-1',),
        requirement_refs=('REQ-1',),
        architecture_version_expected=expected_version,
        changed_component_refs=('A',),
        changed_interface_refs=(),
        dependency_candidate_ids=tuple(deps),
        conflicts_with=tuple(conflicts),
        compatibility_assessments=(assessment,),
        verification_evidence_refs=('EV-VERIFY',),
    )


def _seed(runtime):
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief', reason='seed', evidence_refs=('EV-ARCH',),
        upsert_components=(ArchitectureComponent('A','A',ComponentKind.MODULE,'core-coding','internal'),),
    )


def test_integration_dag_order_and_cycle_rejection_are_atomic():
    runtime = OrganizationRuntime.first_generation()
    _seed(runtime)
    runtime.integration.add_candidate(actor_agent_id='integration.chief', candidate=_candidate('A'))
    runtime.integration.add_candidate(actor_agent_id='integration.chief', candidate=_candidate('B', deps=('A',)))
    assert runtime.integration.graph.integration_order() == ('A', 'B')
    before = runtime.integration.to_state()
    with pytest.raises(ValueError, match='cycle'):
        runtime.integration.add_candidate(
            actor_agent_id='integration.chief',
            candidate=_candidate('A', deps=('B',)),
            replace=True,
        )
    assert runtime.integration.to_state() == before


def test_stale_or_unknown_compatibility_blocks_integration():
    runtime = OrganizationRuntime.first_generation()
    _seed(runtime)
    stale = _candidate('STALE', expected_version=0)
    runtime.integration.add_candidate(actor_agent_id='integration.chief', candidate=stale)
    with pytest.raises(PermissionError, match='architecture'):
        runtime.integration.integrate('STALE', actor_agent_id='integration.chief', evidence_refs=('EV-I-1',))

    unknown = _candidate('UNKNOWN', compatibility=CompatibilityClass.UNKNOWN)
    runtime.integration.add_candidate(actor_agent_id='integration.chief', candidate=unknown)
    with pytest.raises(PermissionError, match='compatibility'):
        runtime.integration.integrate('UNKNOWN', actor_agent_id='integration.chief', evidence_refs=('EV-I-2',))


def test_mutually_conflicting_individually_valid_candidates_cannot_both_integrate():
    runtime = OrganizationRuntime.first_generation()
    _seed(runtime)
    runtime.integration.add_candidate(actor_agent_id='integration.chief', candidate=_candidate('X', conflicts=('Y',)))
    runtime.integration.add_candidate(actor_agent_id='integration.chief', candidate=_candidate('Y', conflicts=('X',)))
    receipt = runtime.integration.integrate('X', actor_agent_id='integration.chief', evidence_refs=('EV-I-3',))
    assert receipt.status is ChangeCandidateStatus.INTEGRATED
    with pytest.raises(PermissionError, match='conflict'):
        runtime.integration.integrate('Y', actor_agent_id='integration.chief', evidence_refs=('EV-I-4',))
