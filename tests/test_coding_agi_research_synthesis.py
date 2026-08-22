from cogcoder.organization.research_profiles import ResearchDomain
from cogcoder.organization.research_provenance import EvidenceMode, SourceKind, SourceQuality
from cogcoder.organization.runtime import OrganizationRuntime


def _source(runtime, sid, kind, *, max_age=10, mode=EvidenceMode.CURRENT_EXTERNAL, quality=SourceQuality.AUTHORITATIVE):
    return runtime.research.provenance.register_source(
        source_id=sid, kind=kind, locator=f'https://example.invalid/{sid}', title=sid,
        retrieved_at='2026-08-22T12:00:00Z', source_version='v1',
        retrieved_epoch=runtime.research.provenance.current_epoch, max_age_epochs=max_age,
        mode=mode, quality=quality, evidence_refs=(f'EV-{sid}',),
    )


def _finding(runtime, fid, producer, domain, key, value, source_ids, *, history_refs=()):
    return runtime.research.provenance.record_finding(
        finding_id=fid, producer_agent_id=producer, domain=domain,
        claim_key=key, normalized_value=value, statement=f'{key}={value}',
        source_ids=tuple(source_ids), history_refs=tuple(history_refs), evidence_refs=(f'EV-{fid}',),
    )


def test_stale_or_unresolved_contradicted_findings_make_synthesis_non_shareable():
    runtime = OrganizationRuntime.first_generation()
    stale_source = _source(runtime, 'SRC-STALE', SourceKind.OFFICIAL_DOCUMENTATION, max_age=0)
    stale_finding = _finding(
        runtime, 'F-STALE', 'research.docs-api.01', ResearchDomain.DOCS_API,
        'sdk.retry', '3', (stale_source.source_id,),
    )
    runtime.research.provenance.advance_epoch(1)
    stale = runtime.research.synthesize(
        synthesis_id='SYN-STALE', producer_agent_id='research.chief', title='Stale synthesis',
        finding_ids=(stale_finding.finding_id,), limitations=('source expired',),
        evidence_refs=('EV-SYN-STALE',),
    )
    assert stale.shareable is False
    assert 'stale_finding' in stale.reasons

    runtime2 = OrganizationRuntime.first_generation()
    a = _source(runtime2, 'SRC-A', SourceKind.OFFICIAL_DOCUMENTATION, quality=SourceQuality.AUTHORITATIVE)
    b = _source(runtime2, 'SRC-B', SourceKind.OFFICIAL_DOCUMENTATION, quality=SourceQuality.PRIMARY)
    f1 = _finding(runtime2, 'F-A', 'research.docs-api.01', ResearchDomain.DOCS_API, 'sdk.timeout', '30s', (a.source_id,))
    f2 = _finding(runtime2, 'F-B', 'research.docs-api.01', ResearchDomain.DOCS_API, 'sdk.timeout', '60s', (b.source_id,))
    contradicted = runtime2.research.synthesize(
        synthesis_id='SYN-CONFLICT', producer_agent_id='research.chief', title='Conflict synthesis',
        finding_ids=(f1.finding_id, f2.finding_id), limitations=('live sources disagree',),
        evidence_refs=('EV-SYN-CONFLICT',),
    )
    assert contradicted.shareable is False
    assert 'unresolved_contradiction' in contradicted.reasons


def test_resolved_fresh_multi_source_synthesis_is_content_addressed_and_preserves_modes_domains_limitations():
    runtime = OrganizationRuntime.first_generation()
    repo = _source(runtime, 'SRC-REPO-HISTORY', SourceKind.REPOSITORY_HISTORY, quality=SourceQuality.PRIMARY)
    docs = _source(runtime, 'SRC-OFFICIAL', SourceKind.OFFICIAL_DOCUMENTATION)
    offline = _source(
        runtime, 'SRC-OFFLINE', SourceKind.INTERNAL_OFFLINE,
        mode=EvidenceMode.INTERNAL_OFFLINE, quality=SourceQuality.PRIMARY,
    )
    f_repo = _finding(
        runtime, 'F-REPO', 'research.repo-archaeology.01', ResearchDomain.REPOSITORY_ARCHAEOLOGY,
        'repo.constructor-style', 'keyword-only', (repo.source_id,), history_refs=('commit:abc123',),
    )
    f_docs = _finding(
        runtime, 'F-DOCS', 'research.docs-api.01', ResearchDomain.DOCS_API,
        'sdk.constructor-style', 'keyword-only', (docs.source_id,),
    )
    f_offline = _finding(
        runtime, 'F-OFFLINE', 'research.chief', ResearchDomain.CROSS_RESEARCH,
        'internal.prior-observation', 'consistent', (offline.source_id,),
    )
    synthesis = runtime.research.synthesize(
        synthesis_id='SYN-GOOD', producer_agent_id='research.chief', title='Constructor compatibility evidence',
        finding_ids=(f_repo.finding_id, f_docs.finding_id, f_offline.finding_id),
        limitations=('official docs do not cover historical private adapters',),
        evidence_refs=('EV-SYN-GOOD',),
    )
    assert synthesis.shareable is True
    assert set(synthesis.domains) == {ResearchDomain.REPOSITORY_ARCHAEOLOGY, ResearchDomain.DOCS_API, ResearchDomain.CROSS_RESEARCH}
    assert set(synthesis.evidence_modes) == {EvidenceMode.CURRENT_EXTERNAL, EvidenceMode.INTERNAL_OFFLINE}
    assert synthesis.limitations == ('official docs do not cover historical private adapters',)
    artifact = runtime.artifacts.get(synthesis.artifact_id)
    assert artifact.kind == 'research-synthesis'
    assert artifact.digest
    duplicate = runtime.research.synthesize(
        synthesis_id='SYN-GOOD', producer_agent_id='research.chief', title='Constructor compatibility evidence',
        finding_ids=(f_repo.finding_id, f_docs.finding_id, f_offline.finding_id),
        limitations=('official docs do not cover historical private adapters',),
        evidence_refs=('EV-SYN-GOOD',),
    )
    assert duplicate == synthesis
