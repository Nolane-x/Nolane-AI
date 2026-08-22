from cogcoder.organization.assurance import AssuranceDisposition
from cogcoder.organization.runtime import OrganizationRuntime


def test_central_override_preserves_original_rejection_and_never_becomes_verified():
    runtime = OrganizationRuntime.first_generation()
    artifact = runtime.artifacts.put(kind='central-candidate', producer_agent_id='nolane.central', content='unsafe-change')
    subject = runtime.assurance.register_subject(
        subject_id='SUBJECT-OVERRIDE', artifact_id=artifact.artifact_id, producer_agent_id='nolane.central',
        subject_version='v1', policy_class='security-sensitive', evidence_refs=('EV-SUBJECT',),
    )
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=())
    assert decision.disposition is AssuranceDisposition.REJECTED
    assert decision.blocking_receipt_id is not None

    override = runtime.assurance.central_override(
        subject_id=subject.subject_id, decision_id=decision.decision_id,
        reason='emergency controlled deployment with compensating controls',
        evidence_ids=('EV-OVERRIDE-RISK-ACCEPTANCE',),
    )
    assert runtime.assurance.effective_disposition(subject.subject_id) is AssuranceDisposition.OVERRIDDEN
    assert runtime.assurance.get_decision(decision.decision_id).disposition is AssuranceDisposition.REJECTED
    assert override.original_decision_id == decision.decision_id
    assert override.authority_override_id
    assert runtime.authority.blocks_for(subject.artifact_id)
