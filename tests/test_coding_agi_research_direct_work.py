from cogcoder.organization.research_profiles import ResearchDomain
from cogcoder.organization.research_provenance import EvidenceMode, SourceKind, SourceQuality
from cogcoder.organization.runtime import OrganizationRuntime


def test_research_chief_directly_completes_multi_domain_evidence_synthesis_and_ordinary_chief_work():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-RESEARCH-CHIEF', title='Resolve repository vs documented API convention', plan_node_id='P-RESEARCH-CHIEF')
    runtime.tasks.lease('T-RESEARCH-CHIEF', 'research.chief')

    repo = runtime.research.provenance.register_source(
        source_id='SRC-CHIEF-REPO', kind=SourceKind.REPOSITORY_HISTORY,
        locator='repo://history/constructor', title='Repository constructor history',
        retrieved_at='2026-08-22T12:20:00Z', source_version='commit:abc123',
        retrieved_epoch=runtime.research.provenance.current_epoch, max_age_epochs=50,
        mode=EvidenceMode.CURRENT_EXTERNAL, quality=SourceQuality.PRIMARY,
        evidence_refs=('EV-CHIEF-REPO-SRC',),
    )
    docs = runtime.research.provenance.register_source(
        source_id='SRC-CHIEF-DOCS', kind=SourceKind.OFFICIAL_DOCUMENTATION,
        locator='https://docs.example/constructors', title='Official constructor docs',
        retrieved_at='2026-08-22T12:21:00Z', source_version='2026.08',
        retrieved_epoch=runtime.research.provenance.current_epoch, max_age_epochs=10,
        mode=EvidenceMode.CURRENT_EXTERNAL, quality=SourceQuality.AUTHORITATIVE,
        evidence_refs=('EV-CHIEF-DOCS-SRC',),
    )
    f_repo = runtime.research.provenance.record_finding(
        finding_id='F-CHIEF-REPO', producer_agent_id='research.repo-archaeology.01',
        domain=ResearchDomain.REPOSITORY_ARCHAEOLOGY, claim_key='constructor.compatibility',
        normalized_value='keyword-only', statement='repository convention is keyword-only',
        source_ids=(repo.source_id,), history_refs=('commit:abc123', 'tests:constructor-contract'),
        evidence_refs=('EV-CHIEF-REPO',),
    )
    f_docs = runtime.research.provenance.record_finding(
        finding_id='F-CHIEF-DOCS', producer_agent_id='research.docs-api.01',
        domain=ResearchDomain.DOCS_API, claim_key='docs.constructor.compatibility',
        normalized_value='keyword-only', statement='official docs specify keyword-only configuration',
        source_ids=(docs.source_id,), history_refs=(), evidence_refs=('EV-CHIEF-DOCS',),
    )
    synthesis = runtime.research.synthesize(
        synthesis_id='SYN-CHIEF', producer_agent_id='research.chief',
        title='Repository and official API constructor synthesis',
        finding_ids=(f_repo.finding_id, f_docs.finding_id),
        limitations=('does not establish behavior for undocumented third-party adapters',),
        evidence_refs=('EV-SYN-CHIEF',),
    )
    assert synthesis.shareable is True
    assert set(synthesis.domains) == {ResearchDomain.REPOSITORY_ARCHAEOLOGY, ResearchDomain.DOCS_API}
    assert synthesis.limitations
    artifact = runtime.artifacts.get(synthesis.artifact_id)
    completed = runtime.chief_direct_work(
        'research.chief', 'T-RESEARCH-CHIEF', output_artifact_ids=(artifact.artifact_id,),
    )
    assert completed['chief_agent_id'] == 'research.chief'
    assert artifact.artifact_id in completed['output_artifact_ids']
