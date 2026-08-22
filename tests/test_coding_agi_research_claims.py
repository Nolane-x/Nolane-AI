import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.research_profiles import ResearchDomain
from cogcoder.organization.research_provenance import (
    ClaimDisposition, EvidenceMode, ResearchProvenanceLedger, SourceKind, SourceQuality,
)


def _ledger():
    return ResearchProvenanceLedger(registry=AgentRegistry(build_first_generation_blueprint()))


def _source(ledger, sid, *, value_quality, max_age=10):
    return ledger.register_source(
        source_id=sid, kind=SourceKind.OFFICIAL_DOCUMENTATION,
        locator=f'https://docs.example/{sid}', title=sid, retrieved_at='2026-08-22T10:35:00Z',
        source_version='2026.08', retrieved_epoch=ledger.current_epoch, max_age_epochs=max_age,
        mode=EvidenceMode.CURRENT_EXTERNAL, quality=value_quality, evidence_refs=(f'EV-{sid}',),
    )


def _finding(ledger, fid, sid, value):
    return ledger.record_finding(
        finding_id=fid, producer_agent_id='research.docs-api.01', domain=ResearchDomain.DOCS_API,
        claim_key='sdk.default-timeout', normalized_value=value,
        statement=f'default timeout is {value}', source_ids=(sid,), history_refs=(), evidence_refs=(f'EV-{fid}',),
    )


def test_live_incompatible_findings_are_contradicted_and_resolution_preserves_competitors():
    ledger = _ledger()
    high = _source(ledger, 'SRC-HIGH', value_quality=SourceQuality.AUTHORITATIVE)
    low = _source(ledger, 'SRC-LOW', value_quality=SourceQuality.SECONDARY)
    f_high = _finding(ledger, 'F-HIGH', high.source_id, '30s')
    f_low = _finding(ledger, 'F-LOW', low.source_id, '60s')

    assessment = ledger.assess_claim('sdk.default-timeout')
    assert assessment.disposition is ClaimDisposition.CONTRADICTED
    assert set(assessment.finding_ids) == {f_high.finding_id, f_low.finding_id}
    assert set(assessment.normalized_values) == {'30s', '60s'}

    with pytest.raises(ValueError):
        ledger.resolve_contradiction(
            claim_key='sdk.default-timeout', resolver_agent_id='research.chief', selected_finding_id=f_low.finding_id,
            reason='prefer low-quality result', evidence_refs=('EV-BAD-RESOLUTION',),
        )

    resolution = ledger.resolve_contradiction(
        claim_key='sdk.default-timeout', resolver_agent_id='research.chief', selected_finding_id=f_high.finding_id,
        reason='official authoritative documentation outranks secondary commentary', evidence_refs=('EV-RESOLVE',),
    )
    assert set(resolution.competing_finding_ids) == {f_high.finding_id, f_low.finding_id}
    resolved = ledger.assess_claim('sdk.default-timeout')
    assert resolved.disposition is ClaimDisposition.SUPPORTED
    assert resolved.selected_finding_id == f_high.finding_id
    assert len(ledger.findings_for_claim('sdk.default-timeout')) == 2


def test_explicit_logical_freshness_distinguishes_stale_supported_and_unknown():
    ledger = _ledger()
    src = _source(ledger, 'SRC-SHORT', value_quality=SourceQuality.AUTHORITATIVE, max_age=1)
    finding = _finding(ledger, 'F-SHORT', src.source_id, '30s')
    assert ledger.assess_claim('sdk.default-timeout').disposition is ClaimDisposition.SUPPORTED
    assert ledger.is_finding_fresh(finding.finding_id) is True

    ledger.advance_epoch(2)
    stale = ledger.assess_claim('sdk.default-timeout')
    assert stale.disposition is ClaimDisposition.STALE
    assert ledger.is_finding_fresh(finding.finding_id) is False
    assert ledger.assess_claim('does.not.exist').disposition is ClaimDisposition.UNKNOWN
