import pytest

from cogcoder.organization.assurance_evidence import AssuranceEvidence
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.verification import CandidateEvaluation


def _subject(runtime, version='backend-v2'):
    artifact = runtime.artifacts.put(kind='neural-candidate', producer_agent_id='coding.backend.01', content=version)
    return runtime.assurance.register_subject(
        subject_id='SUBJECT-PROMOTION', artifact_id=artifact.artifact_id,
        producer_agent_id='coding.backend.01', subject_version=version,
        policy_class='promotion', evidence_refs=('EV-PROMOTION-SUBJECT',),
    )


def _ev(runtime, subject, eid, verifier, domain, *, heldout='heldout-a', cross=('NUC-0.1+coding.backend.01-delta-0.1',), false_accepts=0, regressions=0):
    return runtime.assurance.record_evidence(AssuranceEvidence(
        evidence_id=eid, subject_id=subject.subject_id, subject_version=subject.subject_version,
        verifier_agent_id=verifier, domain=domain, passed=True,
        false_accepts=false_accepts, regressions=regressions, sandbox_digest='sandbox-' + eid,
        heldout_digest=heldout, cross_version_refs=cross,
        observed_epoch=runtime.assurance.evidence.current_epoch, evidence_refs=(eid + '-RAW',),
    ))


def test_promotion_authorization_requires_heldout_cross_version_and_multiple_independent_verifiers():
    runtime = OrganizationRuntime.first_generation()
    subject = _subject(runtime)
    no_heldout = _ev(runtime, subject, 'EV-NO-HELDOUT', 'verification.unit-property.01', AssuranceDomain.UNIT_PROPERTY, heldout='')
    fuzz = _ev(runtime, subject, 'EV-FUZZ', 'verification.fuzz-regression.01', AssuranceDomain.FUZZ_REGRESSION)
    denied = runtime.assurance.authorize_promotion(
        subject_id=subject.subject_id, evidence_ids=(no_heldout.evidence_id, fuzz.evidence_id),
        predecessor_version='NUC-0.1+coding.backend.01-delta-0.1',
    )
    assert denied.authorized is False
    assert 'missing_heldout_evidence' in denied.reasons

    runtime2 = OrganizationRuntime.first_generation()
    subject2 = _subject(runtime2)
    unit = _ev(runtime2, subject2, 'EV-UNIT-X', 'verification.unit-property.01', AssuranceDomain.UNIT_PROPERTY, cross=())
    fuzz2 = _ev(runtime2, subject2, 'EV-FUZZ-X', 'verification.fuzz-regression.01', AssuranceDomain.FUZZ_REGRESSION, cross=())
    denied2 = runtime2.assurance.authorize_promotion(
        subject_id=subject2.subject_id, evidence_ids=(unit.evidence_id, fuzz2.evidence_id),
        predecessor_version='NUC-0.1+coding.backend.01-delta-0.1',
    )
    assert denied2.authorized is False
    assert 'missing_cross_version_evidence' in denied2.reasons


def test_clean_assured_promotion_receipt_can_invoke_existing_low_level_neural_promotion():
    runtime = OrganizationRuntime.first_generation()
    subject = _subject(runtime)
    predecessor = runtime.registry.get('coding.backend.01').neural_version
    unit = _ev(runtime, subject, 'EV-UNIT-OK', 'verification.unit-property.01', AssuranceDomain.UNIT_PROPERTY, cross=(predecessor,))
    fuzz = _ev(runtime, subject, 'EV-FUZZ-OK', 'verification.fuzz-regression.01', AssuranceDomain.FUZZ_REGRESSION, cross=(predecessor,))
    authorization = runtime.assurance.authorize_promotion(
        subject_id=subject.subject_id, evidence_ids=(unit.evidence_id, fuzz.evidence_id),
        predecessor_version=predecessor,
    )
    assert authorization.authorized is True

    low_level = runtime.verification.evaluate_candidate(CandidateEvaluation(
        agent_id='coding.backend.01', candidate_version=subject.subject_version,
        physical_parameters=64_000_000, passed=True, false_accepts=0, regressions=0,
        evidence_ids=('EV-LOW-LEVEL',),
    ))
    promoted = runtime.assurance.promote_neural_candidate(
        authorization.receipt_id, low_level.receipt_id,
    )
    assert promoted.promoted is True
    assert runtime.registry.get('coding.backend.01').neural_version == subject.subject_version


def test_assured_promotion_refuses_receipt_with_false_accept_or_single_identity():
    runtime = OrganizationRuntime.first_generation()
    subject = _subject(runtime)
    predecessor = runtime.registry.get('coding.backend.01').neural_version
    unit = _ev(runtime, subject, 'EV-UNIT-BAD', 'verification.unit-property.01', AssuranceDomain.UNIT_PROPERTY, cross=(predecessor,), false_accepts=1)
    denied = runtime.assurance.authorize_promotion(
        subject_id=subject.subject_id, evidence_ids=(unit.evidence_id,), predecessor_version=predecessor,
    )
    assert denied.authorized is False
    assert 'insufficient_independent_verifiers' in denied.reasons
    assert 'evidence_false_accepts' in denied.reasons
