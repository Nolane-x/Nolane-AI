from cogcoder.organization.research_profiles import ResearchDomain
from cogcoder.organization.research_provenance import EvidenceMode, SourceKind, SourceQuality
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot


def test_research_state_round_trips_exactly_through_organization_snapshot():
    runtime = OrganizationRuntime.first_generation()
    source = runtime.research.provenance.register_source(
        source_id='SRC-SNAPSHOT-RESEARCH', kind=SourceKind.PAPER,
        locator='paper://algorithm-v3', title='Algorithm V3 paper',
        retrieved_at='2026-08-22T12:30:00Z', source_version='v3',
        retrieved_epoch=runtime.research.provenance.current_epoch, max_age_epochs=20,
        mode=EvidenceMode.CURRENT_EXTERNAL, quality=SourceQuality.PRIMARY,
        evidence_refs=('EV-SNAPSHOT-SOURCE',),
    )
    finding = runtime.research.provenance.record_finding(
        finding_id='F-SNAPSHOT-RESEARCH', producer_agent_id='research.prior-art.01',
        domain=ResearchDomain.PRIOR_ART, claim_key='algorithm.bound', normalized_value='O(n log n)',
        statement='reported bound is O(n log n)', source_ids=(source.source_id,),
        history_refs=(), evidence_refs=('EV-SNAPSHOT-FINDING',),
    )
    synthesis = runtime.research.synthesize(
        synthesis_id='SYN-SNAPSHOT-RESEARCH', producer_agent_id='research.chief',
        title='Algorithm complexity synthesis', finding_ids=(finding.finding_id,),
        limitations=('paper result assumes stated preconditions',),
        evidence_refs=('EV-SNAPSHOT-SYNTHESIS',),
    )
    runtime.research.create_handoff(
        synthesis_id=synthesis.synthesis_id, target_agent_id='architecture.chief',
        purpose='inform architecture exploration', authorizing=False,
        assurance_subject_id=None, evidence_refs=('EV-SNAPSHOT-HANDOFF',),
    )

    first = OrganizationSnapshot.capture(runtime)
    restored = OrganizationSnapshot.from_json(first.to_json()).restore()
    second = OrganizationSnapshot.capture(restored)
    assert second.to_json() == first.to_json()
    assert restored.research.to_state() == runtime.research.to_state()


def test_research_context_is_private_to_research_region_by_default():
    runtime = OrganizationRuntime.first_generation()
    researcher = runtime.context.compile('research.prior-art.01')
    coding = runtime.context.compile('coding.backend.01')
    assert ('research-state', runtime.research.digest) in researcher.authoritative_artifacts
    assert not any(name == 'research-state' for name, _ in coding.authoritative_artifacts)
