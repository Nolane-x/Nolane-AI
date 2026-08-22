import pytest

from cogcoder.organization.assurance_evidence import (
    AssuranceEvidence,
    AssuranceEvidenceLedger,
    ChallengeStatus,
)
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.events import EventLedger
from cogcoder.organization.registry import AgentRegistry


def _ledger():
    return AssuranceEvidenceLedger(
        registry=AgentRegistry(build_first_generation_blueprint()), ledger=EventLedger(),
    )


def _subject(ledger, *, producer='coding.backend.01', version='v2', policy='code-change'):
    return ledger.register_subject(
        subject_id='SUBJECT-1', artifact_id='artifact-subject-v2', producer_agent_id=producer,
        subject_version=version, policy_class=policy,
        required_domains=(AssuranceDomain.UNIT_PROPERTY, AssuranceDomain.INTEGRATION_E2E),
        evidence_refs=('EV-SUBJECT',),
    )


def test_subject_and_challenge_are_immutable_content_addressed_provenance():
    ledger = _ledger()
    subject = _subject(ledger)
    challenge = ledger.create_challenge(
        subject_id=subject.subject_id, creator_agent_id='verification.unit-property.01',
        domain=AssuranceDomain.UNIT_PROPERTY, objective='find invariant counterexample',
        input_artifact_refs=('artifact-heldout-input',), expected_invariant='balance never becomes negative',
        evidence_refs=('EV-CHALLENGE',),
    )
    assert challenge.status is ChallengeStatus.OPEN
    assert challenge.digest
    with pytest.raises(ValueError):
        ledger.register_subject(
            subject_id='SUBJECT-1', artifact_id='artifact-other', producer_agent_id='coding.backend.01',
            subject_version='v3', policy_class='code-change',
            required_domains=(AssuranceDomain.UNIT_PROPERTY,), evidence_refs=('EV-OTHER',),
        )
    survived = ledger.set_challenge_status(challenge.case_id, ChallengeStatus.SURVIVED)
    assert survived.status is ChallengeStatus.SURVIVED


def test_evidence_rejects_self_verification_wrong_domain_stale_version_epoch_and_missing_sandbox():
    ledger = _ledger()
    subject = _subject(ledger, producer='verification.unit-property.01')
    case = ledger.create_challenge(
        subject_id=subject.subject_id, creator_agent_id='verification.unit-property.01',
        domain=AssuranceDomain.UNIT_PROPERTY, objective='counterexample search', input_artifact_refs=('artifact-in',),
        expected_invariant='stable output', evidence_refs=('EV-C',),
    )
    with pytest.raises(PermissionError):
        ledger.record_evidence(AssuranceEvidence(
            evidence_id='EV-SELF', subject_id=subject.subject_id, subject_version=subject.subject_version,
            verifier_agent_id='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY,
            passed=True, sandbox_digest='sandbox-1', observed_epoch=ledger.current_epoch,
            challenge_case_refs=(case.case_id,), evidence_refs=('EV-RAW',),
        ))

    subject2 = ledger.register_subject(
        subject_id='SUBJECT-2', artifact_id='artifact-2', producer_agent_id='coding.backend.01',
        subject_version='v1', policy_class='code-change',
        required_domains=(AssuranceDomain.UNIT_PROPERTY,), evidence_refs=('EV-S2',),
    )
    with pytest.raises(PermissionError):
        ledger.record_evidence(AssuranceEvidence(
            evidence_id='EV-WRONG-DOMAIN', subject_id=subject2.subject_id, subject_version='v1',
            verifier_agent_id='verification.integration-e2e.01', domain=AssuranceDomain.UNIT_PROPERTY,
            passed=True, sandbox_digest='sandbox-2', observed_epoch=ledger.current_epoch,
            evidence_refs=('EV-RAW',),
        ))
    with pytest.raises(ValueError):
        ledger.record_evidence(AssuranceEvidence(
            evidence_id='EV-STALE-VERSION', subject_id=subject2.subject_id, subject_version='v0',
            verifier_agent_id='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY,
            passed=True, sandbox_digest='sandbox-2', observed_epoch=ledger.current_epoch,
            evidence_refs=('EV-RAW',),
        ))
    with pytest.raises(ValueError):
        ledger.record_evidence(AssuranceEvidence(
            evidence_id='EV-STALE-EPOCH', subject_id=subject2.subject_id, subject_version='v1',
            verifier_agent_id='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY,
            passed=True, sandbox_digest='sandbox-2', observed_epoch=0,
            evidence_refs=('EV-RAW',),
        ))
    with pytest.raises(ValueError):
        AssuranceEvidence(
            evidence_id='EV-NO-SANDBOX', subject_id=subject2.subject_id, subject_version='v1',
            verifier_agent_id='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY,
            passed=True, sandbox_digest='', observed_epoch=ledger.current_epoch, evidence_refs=('EV-RAW',),
        )


def test_clean_evidence_round_trips_and_id_cannot_be_rebound():
    ledger = _ledger()
    subject = _subject(ledger)
    evidence = AssuranceEvidence(
        evidence_id='EV-CLEAN', subject_id=subject.subject_id, subject_version=subject.subject_version,
        verifier_agent_id='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY,
        passed=True, sandbox_digest='sandbox-fresh', heldout_digest='heldout-a',
        cross_version_refs=('v1',), observed_epoch=ledger.current_epoch,
        evidence_refs=('EV-RAW-CLEAN',),
    )
    row = ledger.record_evidence(evidence)
    assert row.false_accepts == 0 and row.regressions == 0
    assert ledger.record_evidence(evidence) == row
    with pytest.raises(ValueError):
        ledger.record_evidence(AssuranceEvidence(
            evidence_id='EV-CLEAN', subject_id=subject.subject_id, subject_version=subject.subject_version,
            verifier_agent_id='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY,
            passed=False, sandbox_digest='sandbox-fresh', observed_epoch=ledger.current_epoch,
            evidence_refs=('EV-DIFFERENT',),
        ))

    state = ledger.to_state()
    restored = AssuranceEvidenceLedger.from_state(registry=ledger.registry, ledger=EventLedger(), state=state)
    assert restored.to_state() == state
