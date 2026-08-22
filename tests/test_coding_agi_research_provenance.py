import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.research_profiles import ResearchDomain
from cogcoder.organization.research_provenance import (
    EvidenceMode, ResearchProvenanceLedger, SourceKind, SourceQuality,
)


def _ledger():
    return ResearchProvenanceLedger(registry=AgentRegistry(build_first_generation_blueprint()))


def _source(ledger, source_id, kind, *, mode=EvidenceMode.CURRENT_EXTERNAL, quality=SourceQuality.AUTHORITATIVE, version='v1', age=3):
    return ledger.register_source(
        source_id=source_id, kind=kind, locator=f'https://example.invalid/{source_id}', title=source_id,
        retrieved_at='2026-08-22T10:30:00Z', source_version=version,
        retrieved_epoch=ledger.current_epoch, max_age_epochs=age, mode=mode, quality=quality,
        evidence_refs=(f'EV-{source_id}',),
    )


def test_sources_preserve_locator_retrieval_version_mode_quality_and_cannot_rebind():
    ledger = _ledger()
    external = _source(ledger, 'SRC-DOC', SourceKind.OFFICIAL_DOCUMENTATION)
    internal = _source(
        ledger, 'SRC-INTERNAL', SourceKind.INTERNAL_OFFLINE,
        mode=EvidenceMode.INTERNAL_OFFLINE, quality=SourceQuality.PRIMARY,
    )
    assert external.mode is EvidenceMode.CURRENT_EXTERNAL
    assert internal.mode is EvidenceMode.INTERNAL_OFFLINE
    assert external.source_version == 'v1' and external.retrieved_at.endswith('Z')
    assert external.digest != internal.digest
    with pytest.raises(ValueError):
        ledger.register_source(
            source_id='SRC-DOC', kind=SourceKind.PAPER, locator='paper://changed', title='changed',
            retrieved_at='later', source_version='v2', retrieved_epoch=ledger.current_epoch,
            max_age_epochs=5, mode=EvidenceMode.CURRENT_EXTERNAL, quality=SourceQuality.PRIMARY,
            evidence_refs=('EV-CHANGED',),
        )
    state = ledger.to_state()
    restored = ResearchProvenanceLedger.from_state(registry=ledger.registry, state=state)
    assert restored.to_state() == state
    assert restored.get_source('SRC-INTERNAL').mode is EvidenceMode.INTERNAL_OFFLINE


def test_finding_authority_and_domain_source_grounding_are_fail_closed():
    ledger = _ledger()
    repo = _source(ledger, 'SRC-REPO', SourceKind.REPOSITORY_HISTORY, quality=SourceQuality.PRIMARY)
    docs = _source(ledger, 'SRC-DOCS', SourceKind.OFFICIAL_DOCUMENTATION)
    paper = _source(ledger, 'SRC-PAPER', SourceKind.PAPER, quality=SourceQuality.PRIMARY)

    archaeology = ledger.record_finding(
        finding_id='F-REPO', producer_agent_id='research.repo-archaeology.01',
        domain=ResearchDomain.REPOSITORY_ARCHAEOLOGY, claim_key='repo.api-convention', normalized_value='keyword-only',
        statement='public constructors use keyword-only configuration', source_ids=(repo.source_id,),
        history_refs=('commit:abc123', 'convention:tests'), evidence_refs=('EV-F-REPO',),
    )
    assert archaeology.source_ids == ('SRC-REPO',)

    with pytest.raises(PermissionError):
        ledger.record_finding(
            finding_id='F-NON-RESEARCH', producer_agent_id='coding.backend.01',
            domain=ResearchDomain.DOCS_API, claim_key='api.version', normalized_value='2', statement='version 2',
            source_ids=(docs.source_id,), history_refs=(), evidence_refs=('EV-X',),
        )
    with pytest.raises(ValueError):
        ledger.record_finding(
            finding_id='F-BAD-REPO', producer_agent_id='research.repo-archaeology.01',
            domain=ResearchDomain.REPOSITORY_ARCHAEOLOGY, claim_key='repo.guess', normalized_value='guess', statement='guess',
            source_ids=(docs.source_id,), history_refs=('generic-guess',), evidence_refs=('EV-BAD',),
        )
    with pytest.raises(ValueError):
        ledger.record_finding(
            finding_id='F-BAD-DOCS', producer_agent_id='research.docs-api.01',
            domain=ResearchDomain.DOCS_API, claim_key='docs.claim', normalized_value='x', statement='x',
            source_ids=(paper.source_id,), history_refs=(), evidence_refs=('EV-BAD-DOCS',),
        )
    with pytest.raises(ValueError):
        ledger.record_finding(
            finding_id='F-BAD-PAPER', producer_agent_id='research.prior-art.01',
            domain=ResearchDomain.PRIOR_ART, claim_key='paper.claim', normalized_value='x', statement='x',
            source_ids=(docs.source_id,), history_refs=(), evidence_refs=('EV-BAD-PAPER',),
        )
