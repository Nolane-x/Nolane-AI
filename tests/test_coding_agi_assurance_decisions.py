from cogcoder.organization.assurance import AssuranceDisposition
from cogcoder.organization.assurance_evidence import AssuranceEvidence
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.runtime import OrganizationRuntime


def _register(runtime, *, subject_id='SUBJECT-CODE', producer='coding.backend.01', policy='code-change'):
    artifact = runtime.artifacts.put(kind='candidate-artifact', producer_agent_id=producer, content=subject_id)
    return runtime.assurance.register_subject(
        subject_id=subject_id, artifact_id=artifact.artifact_id, producer_agent_id=producer,
        subject_version='v2', policy_class=policy, evidence_refs=('EV-SUBJECT',),
    )


def _evidence(runtime, subject, *, eid, verifier, domain, passed=True, false_accepts=0, regressions=0):
    return runtime.assurance.record_evidence(AssuranceEvidence(
        evidence_id=eid, subject_id=subject.subject_id, subject_version=subject.subject_version,
        verifier_agent_id=verifier, domain=domain, passed=passed,
        false_accepts=false_accepts, regressions=regressions,
        sandbox_digest='sandbox-' + eid, observed_epoch=runtime.assurance.evidence.current_epoch,
        evidence_refs=(eid + '-RAW',),
    ))


def test_missing_required_policy_domains_reject_and_complete_clean_evidence_verifies():
    runtime = OrganizationRuntime.first_generation()
    subject = _register(runtime)
    unit = _evidence(runtime, subject, eid='EV-UNIT', verifier='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY)
    missing = runtime.assurance.assess(subject.subject_id, evidence_ids=(unit.evidence_id,))
    assert missing.disposition is AssuranceDisposition.REJECTED
    assert 'missing_integration_e2e' in missing.reasons
    assert 'missing_fuzz_regression' in missing.reasons

    integration = _evidence(runtime, subject, eid='EV-E2E', verifier='verification.integration-e2e.01', domain=AssuranceDomain.INTEGRATION_E2E)
    fuzz = _evidence(runtime, subject, eid='EV-FUZZ', verifier='verification.fuzz-regression.01', domain=AssuranceDomain.FUZZ_REGRESSION)
    verified = runtime.assurance.assess(
        subject.subject_id, evidence_ids=(unit.evidence_id, integration.evidence_id, fuzz.evidence_id),
    )
    assert verified.disposition is AssuranceDisposition.VERIFIED
    assert verified.reasons == ()


def test_false_accept_regression_or_failed_evidence_rejects_even_when_domains_complete():
    runtime = OrganizationRuntime.first_generation()
    subject = _register(runtime, subject_id='SUBJECT-NEG')
    unit = _evidence(runtime, subject, eid='EV-UNIT-N', verifier='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY)
    e2e = _evidence(runtime, subject, eid='EV-E2E-N', verifier='verification.integration-e2e.01', domain=AssuranceDomain.INTEGRATION_E2E, regressions=1)
    fuzz = _evidence(runtime, subject, eid='EV-FUZZ-N', verifier='verification.fuzz-regression.01', domain=AssuranceDomain.FUZZ_REGRESSION, passed=False)
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=(unit.evidence_id, e2e.evidence_id, fuzz.evidence_id))
    assert decision.disposition is AssuranceDisposition.REJECTED
    assert 'evidence_regressions' in decision.reasons
    assert 'evidence_failed' in decision.reasons
