from cogcoder.organization.assurance_evidence import AssuranceEvidence, ChallengeStatus
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.runtime import OrganizationRuntime


def _subject(runtime, *, sid, producer, policy):
    artifact = runtime.artifacts.put(kind='assurance-target', producer_agent_id=producer, content=sid)
    return runtime.assurance.register_subject(
        subject_id=sid, artifact_id=artifact.artifact_id, producer_agent_id=producer,
        subject_version='r1', policy_class=policy, evidence_refs=('EV-' + sid,),
    )


def test_verification_chief_personally_constructs_falsifying_case_and_blocks_subject():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-VERIFY-CHIEF', title='Falsify critical adapter claim', plan_node_id='P-VERIFY-CHIEF')
    runtime.tasks.lease('T-VERIFY-CHIEF', 'verification.chief')
    subject = _subject(runtime, sid='SUBJECT-VERIFY-CHIEF', producer='coding.chief', policy='acceptance-critical')
    challenge = runtime.assurance.create_challenge(
        subject_id=subject.subject_id, creator_agent_id='verification.chief',
        domain=AssuranceDomain.SPEC_ACCEPTANCE, objective='construct state sequence that violates acceptance rule',
        input_artifact_refs=('artifact-heldout-sequence',), expected_invariant='adapter preserves external contract',
        evidence_refs=('EV-VERIFY-CHALLENGE',),
    )
    runtime.assurance.evidence.set_challenge_status(challenge.case_id, ChallengeStatus.FALSIFIED)
    evidence = runtime.assurance.record_evidence(AssuranceEvidence(
        evidence_id='EV-VERIFY-CHIEF-FAIL', subject_id=subject.subject_id, subject_version=subject.subject_version,
        verifier_agent_id='verification.chief', domain=AssuranceDomain.SPEC_ACCEPTANCE, passed=False,
        sandbox_digest='sandbox-verify-chief', observed_epoch=runtime.assurance.evidence.current_epoch,
        challenge_case_refs=(challenge.case_id,), evidence_refs=('EV-COUNTEREXAMPLE',),
    ))
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=(evidence.evidence_id,))
    assert decision.blocking_receipt_id is not None
    challenge_artifact = runtime.artifacts.put(kind='falsification-case', producer_agent_id='verification.chief', content=challenge.digest)
    evidence_artifact = runtime.artifacts.put(kind='verification-evidence', producer_agent_id='verification.chief', content=evidence.digest)
    completed = runtime.chief_direct_work(
        'verification.chief', 'T-VERIFY-CHIEF', output_artifact_ids=(challenge_artifact.artifact_id, evidence_artifact.artifact_id),
    )
    assert completed['chief_agent_id'] == 'verification.chief'


def test_security_chief_personally_constructs_adversarial_case_and_blocks_security_regression():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-SECURITY-CHIEF', title='Attack trust boundary change', plan_node_id='P-SECURITY-CHIEF')
    runtime.tasks.lease('T-SECURITY-CHIEF', 'security.chief')
    subject = _subject(runtime, sid='SUBJECT-SECURITY-CHIEF', producer='nolane.central', policy='security-sensitive')
    challenge = runtime.assurance.create_challenge(
        subject_id=subject.subject_id, creator_agent_id='security.chief', domain=AssuranceDomain.ADVERSARIAL,
        objective='cross tenant boundary using malformed authorization state',
        input_artifact_refs=('artifact-attack-corpus',), expected_invariant='tenant boundary cannot be crossed',
        evidence_refs=('EV-SECURITY-CHALLENGE',),
    )
    runtime.assurance.evidence.set_challenge_status(challenge.case_id, ChallengeStatus.FALSIFIED)
    evidence = runtime.assurance.record_evidence(AssuranceEvidence(
        evidence_id='EV-SECURITY-CHIEF-FAIL', subject_id=subject.subject_id, subject_version=subject.subject_version,
        verifier_agent_id='security.chief', domain=AssuranceDomain.ADVERSARIAL, passed=False, regressions=1,
        sandbox_digest='sandbox-security-chief', observed_epoch=runtime.assurance.evidence.current_epoch,
        challenge_case_refs=(challenge.case_id,), evidence_refs=('EV-ATTACK-TRACE',),
    ))
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=(evidence.evidence_id,))
    assert decision.blocking_receipt_id is not None
    challenge_artifact = runtime.artifacts.put(kind='adversarial-case', producer_agent_id='security.chief', content=challenge.digest)
    evidence_artifact = runtime.artifacts.put(kind='security-evidence', producer_agent_id='security.chief', content=evidence.digest)
    completed = runtime.chief_direct_work(
        'security.chief', 'T-SECURITY-CHIEF', output_artifact_ids=(challenge_artifact.artifact_id, evidence_artifact.artifact_id),
    )
    assert completed['chief_agent_id'] == 'security.chief'
