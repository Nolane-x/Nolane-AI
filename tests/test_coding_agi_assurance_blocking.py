from cogcoder.organization.assurance import AssuranceDisposition
from cogcoder.organization.assurance_evidence import AssuranceEvidence
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.runtime import OrganizationRuntime


def _subject(runtime, subject_id, producer, policy):
    artifact = runtime.artifacts.put(kind='governed-artifact', producer_agent_id=producer, content=subject_id)
    return runtime.assurance.register_subject(
        subject_id=subject_id, artifact_id=artifact.artifact_id, producer_agent_id=producer,
        subject_version='r1', policy_class=policy, evidence_refs=('EV-' + subject_id,),
    )


def _record(runtime, subject, eid, verifier, domain, *, passed=True, regressions=0):
    return runtime.assurance.record_evidence(AssuranceEvidence(
        evidence_id=eid, subject_id=subject.subject_id, subject_version=subject.subject_version,
        verifier_agent_id=verifier, domain=domain, passed=passed, regressions=regressions,
        sandbox_digest='sandbox-' + eid, observed_epoch=runtime.assurance.evidence.current_epoch,
        evidence_refs=(eid + '-RAW',),
    ))


def test_verification_can_block_chief_originated_artifact_revision():
    runtime = OrganizationRuntime.first_generation()
    subject = _subject(runtime, 'SUBJECT-CHIEF', 'coding.chief', 'acceptance-critical')
    unit = _record(runtime, subject, 'EV-U', 'verification.unit-property.01', AssuranceDomain.UNIT_PROPERTY)
    e2e = _record(runtime, subject, 'EV-E', 'verification.integration-e2e.01', AssuranceDomain.INTEGRATION_E2E)
    spec = _record(runtime, subject, 'EV-S', 'verification.spec-acceptance.01', AssuranceDomain.SPEC_ACCEPTANCE, passed=False)
    fuzz = _record(runtime, subject, 'EV-F', 'verification.fuzz-regression.01', AssuranceDomain.FUZZ_REGRESSION)
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=(unit.evidence_id, e2e.evidence_id, spec.evidence_id, fuzz.evidence_id))
    assert decision.disposition is AssuranceDisposition.REJECTED
    block = runtime.assurance.blocking_receipt(decision.blocking_receipt_id)
    assert block.subject_id == subject.subject_id
    assert runtime.authority.blocks_for(subject.artifact_id)


def test_security_can_block_nolane_central_originated_security_sensitive_artifact():
    runtime = OrganizationRuntime.first_generation()
    subject = _subject(runtime, 'SUBJECT-CENTRAL', 'nolane.central', 'security-sensitive')
    evidence = (
        _record(runtime, subject, 'EV-U2', 'verification.unit-property.01', AssuranceDomain.UNIT_PROPERTY),
        _record(runtime, subject, 'EV-E2', 'verification.integration-e2e.01', AssuranceDomain.INTEGRATION_E2E),
        _record(runtime, subject, 'EV-S2', 'verification.spec-acceptance.01', AssuranceDomain.SPEC_ACCEPTANCE),
        _record(runtime, subject, 'EV-F2', 'verification.fuzz-regression.01', AssuranceDomain.FUZZ_REGRESSION),
        _record(runtime, subject, 'EV-T2', 'security.threat-model.01', AssuranceDomain.THREAT_MODEL),
        _record(runtime, subject, 'EV-A2', 'security.adversarial.01', AssuranceDomain.ADVERSARIAL, regressions=1),
    )
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=tuple(x.evidence_id for x in evidence))
    assert decision.disposition is AssuranceDisposition.REJECTED
    block = runtime.assurance.blocking_receipt(decision.blocking_receipt_id)
    assert block.blocker_agent_id in {'security.adversarial.01', 'security.chief'}
    assert runtime.authority.blocks_for(subject.artifact_id)
