import pytest

from cogcoder.organization.adr import ADRStatus
from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.runtime import OrganizationRuntime


def test_adr_acceptance_and_supersession_preserve_history():
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief', reason='seed', evidence_refs=('EV-ADR-0',),
        upsert_components=(ArchitectureComponent('A', 'Module A', ComponentKind.MODULE, 'core-coding', 'internal'),),
    )
    proposal = runtime.adr.propose(
        source_agent_id='coding.backend.01',
        title='Choose persistence boundary',
        context='Direct storage access couples modules',
        alternatives=('repository-interface', 'direct-storage'),
        decision='repository-interface',
        rationale='keeps storage behind a stable boundary',
        architecture_refs=('A',),
        evidence_refs=('EV-ADR-1',),
    )
    assert proposal.status is ADRStatus.PROPOSED

    with pytest.raises(PermissionError):
        runtime.adr.accept(proposal.adr_id, actor_agent_id='coding.backend.01', evidence_refs=('EV-ADR-2',))

    accepted = runtime.adr.accept(
        proposal.adr_id, actor_agent_id='architecture.chief', evidence_refs=('EV-ADR-2',),
    )
    assert accepted.status is ADRStatus.ACCEPTED

    replacement = runtime.adr.propose(
        source_agent_id='architecture.chief', title='Evolve persistence boundary',
        context='Need async durability', alternatives=('event-store', 'repository-interface'),
        decision='event-store', rationale='supports durable async flow',
        architecture_refs=('A',), evidence_refs=('EV-ADR-3',),
    )
    replacement = runtime.adr.accept(
        replacement.adr_id, actor_agent_id='architecture.chief',
        evidence_refs=('EV-ADR-4',), supersedes=accepted.adr_id,
    )
    assert runtime.adr.get(accepted.adr_id).status is ADRStatus.SUPERSEDED
    assert replacement.status is ADRStatus.ACCEPTED
    assert len(runtime.adr.records()) == 2


def test_adr_requires_real_alternatives_and_evidence():
    runtime = OrganizationRuntime.first_generation()
    with pytest.raises(ValueError):
        runtime.adr.propose(
            source_agent_id='architecture.chief', title='bad', context='x',
            alternatives=(), decision='x', rationale='x', architecture_refs=(), evidence_refs=(),
        )
