from cogcoder.organization.assurance_evidence import AssuranceEvidence
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot


def test_assurance_state_round_trips_exactly_through_organization_snapshot():
    runtime = OrganizationRuntime.first_generation()
    artifact = runtime.artifacts.put(kind='snapshot-subject', producer_agent_id='coding.backend.01', content='candidate-v1')
    subject = runtime.assurance.register_subject(
        subject_id='SUBJECT-SNAPSHOT', artifact_id=artifact.artifact_id, producer_agent_id='coding.backend.01',
        subject_version='v1', policy_class='code-change', evidence_refs=('EV-SNAPSHOT-SUBJECT',),
    )
    challenge = runtime.assurance.create_challenge(
        subject_id=subject.subject_id, creator_agent_id='verification.unit-property.01',
        domain=AssuranceDomain.UNIT_PROPERTY, objective='probe arithmetic invariant',
        input_artifact_refs=('artifact-heldout',), expected_invariant='result is deterministic',
        evidence_refs=('EV-SNAPSHOT-CHALLENGE',),
    )
    evidence = runtime.assurance.record_evidence(AssuranceEvidence(
        evidence_id='EV-SNAPSHOT', subject_id=subject.subject_id, subject_version=subject.subject_version,
        verifier_agent_id='verification.unit-property.01', domain=AssuranceDomain.UNIT_PROPERTY,
        passed=True, sandbox_digest='sandbox-snapshot', heldout_digest='heldout-snapshot',
        cross_version_refs=('v0',), observed_epoch=runtime.assurance.evidence.current_epoch,
        challenge_case_refs=(challenge.case_id,), evidence_refs=('EV-SNAPSHOT-RAW',),
    ))
    runtime.assurance.assess(subject.subject_id, evidence_ids=(evidence.evidence_id,))

    first = OrganizationSnapshot.capture(runtime)
    restored = OrganizationSnapshot.from_json(first.to_json()).restore()
    second = OrganizationSnapshot.capture(restored)
    assert second.to_json() == first.to_json()
    assert restored.assurance.to_state() == runtime.assurance.to_state()
