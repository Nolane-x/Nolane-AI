from cogcoder.organization.assurance import AssuranceDisposition
from cogcoder.organization.assurance_evidence import AssuranceEvidence
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.research import ResearchHandoffDisposition
from cogcoder.organization.research_profiles import ResearchDomain
from cogcoder.organization.research_provenance import EvidenceMode, SourceKind, SourceQuality
from cogcoder.organization.runtime import OrganizationRuntime


def _shareable_synthesis(runtime, sid='SYN-HANDOFF'):
    source = runtime.research.provenance.register_source(
        source_id='SRC-HANDOFF-' + sid, kind=SourceKind.OFFICIAL_DOCUMENTATION,
        locator='https://docs.example/sdk', title='Official SDK docs',
        retrieved_at='2026-08-22T12:10:00Z', source_version='2026.08',
        retrieved_epoch=runtime.research.provenance.current_epoch, max_age_epochs=10,
        mode=EvidenceMode.CURRENT_EXTERNAL, quality=SourceQuality.AUTHORITATIVE,
        evidence_refs=('EV-SRC-' + sid,),
    )
    finding = runtime.research.provenance.record_finding(
        finding_id='F-HANDOFF-' + sid, producer_agent_id='research.docs-api.01',
        domain=ResearchDomain.DOCS_API, claim_key='sdk.transaction-api', normalized_value='context-manager',
        statement='transaction API is a context manager', source_ids=(source.source_id,),
        history_refs=(), evidence_refs=('EV-F-' + sid,),
    )
    return runtime.research.synthesize(
        synthesis_id=sid, producer_agent_id='research.chief', title='SDK transaction API evidence',
        finding_ids=(finding.finding_id,), limitations=('applies to current documented SDK version',),
        evidence_refs=('EV-SYN-' + sid,),
    )


def _assurance_subject(runtime, synthesis, subject_id):
    return runtime.assurance.register_subject(
        subject_id=subject_id, artifact_id=synthesis.artifact_id, producer_agent_id='research.chief',
        subject_version=synthesis.digest, policy_class='acceptance-critical',
        evidence_refs=('EV-SUBJECT-' + subject_id,),
    )


def _evidence(runtime, subject, eid, verifier, domain):
    return runtime.assurance.record_evidence(AssuranceEvidence(
        evidence_id=eid, subject_id=subject.subject_id, subject_version=subject.subject_version,
        verifier_agent_id=verifier, domain=domain, passed=True,
        sandbox_digest='sandbox-' + eid, observed_epoch=runtime.assurance.evidence.current_epoch,
        evidence_refs=(eid + '-RAW',),
    ))


def test_informative_handoff_needs_shareable_synthesis_but_not_assurance():
    runtime = OrganizationRuntime.first_generation()
    synthesis = _shareable_synthesis(runtime)
    owner_before = runtime.authority.owner_of('master-plan')
    handoff = runtime.research.create_handoff(
        synthesis_id=synthesis.synthesis_id, target_agent_id='planning.chief',
        purpose='inform planning with current SDK behavior', authorizing=False,
        assurance_subject_id=None, evidence_refs=('EV-INFORMATIVE',),
    )
    assert handoff.disposition is ResearchHandoffDisposition.INFORMATIVE
    assert handoff.authorizing is False
    assert runtime.authority.owner_of('master-plan') == owner_before


def test_authorizing_handoff_rejects_pending_rejected_and_overridden_assurance():
    runtime = OrganizationRuntime.first_generation()
    synthesis = _shareable_synthesis(runtime, 'SYN-PENDING')
    subject = _assurance_subject(runtime, synthesis, 'SUBJECT-PENDING')
    pending = runtime.research.create_handoff(
        synthesis_id=synthesis.synthesis_id, target_agent_id='architecture.chief',
        purpose='authorize architecture decision', authorizing=True,
        assurance_subject_id=subject.subject_id, evidence_refs=('EV-H-PENDING',),
    )
    assert pending.disposition is ResearchHandoffDisposition.BLOCKED
    assert pending.assurance_disposition is AssuranceDisposition.PENDING

    runtime2 = OrganizationRuntime.first_generation()
    synthesis2 = _shareable_synthesis(runtime2, 'SYN-REJECTED')
    subject2 = _assurance_subject(runtime2, synthesis2, 'SUBJECT-REJECTED')
    rejected_decision = runtime2.assurance.assess(subject2.subject_id, evidence_ids=())
    assert rejected_decision.disposition is AssuranceDisposition.REJECTED
    rejected = runtime2.research.create_handoff(
        synthesis_id=synthesis2.synthesis_id, target_agent_id='coding.chief',
        purpose='authorize code change', authorizing=True,
        assurance_subject_id=subject2.subject_id, evidence_refs=('EV-H-REJECTED',),
    )
    assert rejected.disposition is ResearchHandoffDisposition.BLOCKED
    assert rejected.assurance_disposition is AssuranceDisposition.REJECTED

    runtime2.assurance.central_override(
        subject_id=subject2.subject_id, decision_id=rejected_decision.decision_id,
        reason='temporary risk acceptance does not equal independent verification',
        evidence_ids=('EV-RISK-ACCEPTANCE',),
    )
    overridden = runtime2.research.create_handoff(
        synthesis_id=synthesis2.synthesis_id, target_agent_id='coding.chief',
        purpose='try authorizing after override', authorizing=True,
        assurance_subject_id=subject2.subject_id, evidence_refs=('EV-H-OVERRIDE',),
    )
    assert overridden.disposition is ResearchHandoffDisposition.BLOCKED
    assert overridden.assurance_disposition is AssuranceDisposition.OVERRIDDEN


def test_exact_part8_verified_synthesis_artifact_authorizes_engineering_handoff_without_mutating_target_authority():
    runtime = OrganizationRuntime.first_generation()
    synthesis = _shareable_synthesis(runtime, 'SYN-VERIFIED')
    subject = _assurance_subject(runtime, synthesis, 'SUBJECT-VERIFIED')
    rows = (
        _evidence(runtime, subject, 'EV-R-U', 'verification.unit-property.01', AssuranceDomain.UNIT_PROPERTY),
        _evidence(runtime, subject, 'EV-R-E', 'verification.integration-e2e.01', AssuranceDomain.INTEGRATION_E2E),
        _evidence(runtime, subject, 'EV-R-S', 'verification.spec-acceptance.01', AssuranceDomain.SPEC_ACCEPTANCE),
        _evidence(runtime, subject, 'EV-R-F', 'verification.fuzz-regression.01', AssuranceDomain.FUZZ_REGRESSION),
    )
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=tuple(x.evidence_id for x in rows))
    assert decision.disposition is AssuranceDisposition.VERIFIED
    owner_before = runtime.authority.owner_of('architecture-graph')
    handoff = runtime.research.create_handoff(
        synthesis_id=synthesis.synthesis_id, target_agent_id='architecture.chief',
        purpose='authorize documented transaction contract in architecture', authorizing=True,
        assurance_subject_id=subject.subject_id, evidence_refs=('EV-H-VERIFIED',),
    )
    assert handoff.disposition is ResearchHandoffDisposition.AUTHORIZED
    assert handoff.assurance_disposition is AssuranceDisposition.VERIFIED
    assert handoff.synthesis_artifact_id == synthesis.artifact_id
    assert runtime.authority.owner_of('architecture-graph') == owner_before
