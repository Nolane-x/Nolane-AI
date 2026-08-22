import pytest

from cogcoder.organization.assurance import AssuranceDisposition
from cogcoder.organization.assurance_evidence import AssuranceEvidence
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.foundry_memory import ScratchDisposition
from cogcoder.organization.foundry_resources import FoundryBudget
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord


def _worker_and_output():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-F14-EV', title='ephemeral evidence task', plan_node_id='P-F14-EV')
    runtime.coordination.grant_lease('T-F14-EV', 'coding.backend.01', token=1, stale_after_tokens=30)
    request = runtime.foundry.request_spawn(
        sponsor_agent_id='coding.chief', parent_task_id='T-F14-EV', template_id='bug-reproducer',
        mission='produce a minimal retry reproduction', team_id='team-ev',
        budget=FoundryBudget(compute_units=30, tool_calls=10, external_core_calls=4, max_workers=2, lifetime_tokens=30),
        requested_tools=('filesystem', 'terminal', 'test-runner'),
        requested_external_cores=('runtime-tracer',), allowed_artifact_kinds=('reproduction', 'evidence'),
        current_token=2,
    )
    runtime.foundry.approve_spawn(request.request_id, actor_agent_id='coding.chief')
    manifest = runtime.foundry.instantiate(request.request_id, current_token=2)
    runtime.foundry.activate(manifest.ephemeral_id, actor_agent_id='coding.chief')
    output = runtime.foundry.emit_output(
        manifest.ephemeral_id, kind='reproduction', content='retry fails after duplicate acknowledgement',
        evidence_refs=('EV-RAW',),
    )
    return runtime, manifest, output


def _verify_bridge(runtime, handoff, *, subject_id='F14-BRIDGE-SUBJECT'):
    subject = runtime.assurance.register_subject(
        subject_id=subject_id, artifact_id=handoff.bridge_artifact_id,
        producer_agent_id=handoff.sponsor_agent_id, subject_version='handoff-v1',
        policy_class='code-change', evidence_refs=('EV-BRIDGE-BASE',),
        required_domains=(AssuranceDomain.UNIT_PROPERTY,),
    )
    evidence = AssuranceEvidence(
        evidence_id=subject_id + '-EV', subject_id=subject.subject_id,
        subject_version=subject.subject_version, verifier_agent_id='verification.unit-property.01',
        domain=AssuranceDomain.UNIT_PROPERTY, passed=True, sandbox_digest='sandbox-f14',
        observed_epoch=subject.registered_epoch, evidence_refs=('EV-BRIDGE-CHECK',),
    )
    runtime.assurance.record_evidence(evidence)
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=(evidence.evidence_id,))
    assert decision.disposition is AssuranceDisposition.VERIFIED
    return subject, decision


def test_raw_output_keeps_ephemeral_producer_and_survives_retirement_but_cannot_own_authority():
    runtime, manifest, output = _worker_and_output()
    artifact = runtime.artifacts.get(output.artifact_id)
    assert artifact.producer_agent_id == manifest.ephemeral_id
    with pytest.raises(KeyError):
        runtime.authority.claim_owner('ephemeral-authority-test', manifest.ephemeral_id)
    with pytest.raises(KeyError):
        runtime.assurance.register_subject(
            subject_id='RAW-EPHEMERAL-SUBJECT', artifact_id=artifact.artifact_id,
            producer_agent_id=manifest.ephemeral_id, subject_version='raw-v1',
            policy_class='code-change', evidence_refs=('EV-RAW',),
            required_domains=(AssuranceDomain.UNIT_PROPERTY,),
        )
    runtime.foundry.retire(manifest.ephemeral_id, actor_agent_id='coding.chief', scratch_policy=ScratchDisposition.DESTROY)
    assert runtime.artifacts.get(output.artifact_id) == artifact


def test_sponsor_only_or_dirty_verification_cannot_prepare_authorizing_bridge():
    runtime, _, output = _worker_and_output()
    sponsor_evidence = EvidenceRecord('F14-SPONSOR', 'coding.chief', True)
    sponsor = runtime.foundry.record_verification(output.output_id, sponsor_evidence)
    assert not sponsor.independent
    with pytest.raises(PermissionError):
        runtime.foundry.prepare_handoff(output.output_id, target_agent_id='coding.backend.01')

    dirty = runtime.foundry.record_verification(
        output.output_id, EvidenceRecord('F14-DIRTY', 'verification.unit-property.01', True, regressions=1),
    )
    assert not dirty.clean
    with pytest.raises(PermissionError):
        runtime.foundry.prepare_handoff(output.output_id, target_agent_id='coding.backend.01')


def test_permanent_external_verification_creates_sponsor_bridge_and_verified_part8_authorizes():
    runtime, manifest, output = _worker_and_output()
    verified = runtime.foundry.record_verification(
        output.output_id, EvidenceRecord('F14-EXT', 'verification.unit-property.01', True),
    )
    assert verified.clean and verified.independent
    handoff = runtime.foundry.prepare_handoff(output.output_id, target_agent_id='coding.backend.01')
    bridge = runtime.artifacts.get(handoff.bridge_artifact_id)
    assert bridge.producer_agent_id == 'coding.chief'
    assert bridge.metadata['raw_artifact_id'] == output.artifact_id
    assert bridge.metadata['raw_artifact_digest'] == runtime.artifacts.get(output.artifact_id).digest
    assert bridge.metadata['ephemeral_id'] == manifest.ephemeral_id
    subject, decision = _verify_bridge(runtime, handoff)
    authorized = runtime.foundry.authorize_handoff(handoff.handoff_id, assurance_decision_id=decision.decision_id)
    assert authorized.authorized
    assert authorized.assurance_subject_id == subject.subject_id
    assert runtime.assurance.effective_disposition(subject.subject_id) is AssuranceDisposition.VERIFIED


def test_part8_override_of_bridge_is_not_relabelled_as_independent_verified_handoff():
    runtime, _, output = _worker_and_output()
    runtime.foundry.record_verification(
        output.output_id, EvidenceRecord('F14-EXT-OVR', 'verification.unit-property.01', True),
    )
    handoff = runtime.foundry.prepare_handoff(output.output_id, target_agent_id='coding.backend.01')
    subject = runtime.assurance.register_subject(
        subject_id='F14-BRIDGE-OVERRIDE', artifact_id=handoff.bridge_artifact_id,
        producer_agent_id=handoff.sponsor_agent_id, subject_version='handoff-v1',
        policy_class='acceptance-critical', evidence_refs=('EV-OVERRIDE-BASE',),
        required_domains=(AssuranceDomain.UNIT_PROPERTY, AssuranceDomain.SPEC_ACCEPTANCE),
    )
    evidence = AssuranceEvidence(
        evidence_id='F14-OVERRIDE-UNIT', subject_id=subject.subject_id,
        subject_version=subject.subject_version, verifier_agent_id='verification.unit-property.01',
        domain=AssuranceDomain.UNIT_PROPERTY, passed=True, sandbox_digest='sandbox-override',
        observed_epoch=subject.registered_epoch, evidence_refs=('EV-OVERRIDE-UNIT',),
    )
    runtime.assurance.record_evidence(evidence)
    rejected = runtime.assurance.assess(subject.subject_id, evidence_ids=(evidence.evidence_id,))
    assert rejected.disposition is AssuranceDisposition.REJECTED
    runtime.assurance.central_override(
        subject_id=subject.subject_id, decision_id=rejected.decision_id,
        reason='emergency delivery', evidence_ids=('EV-RISK',),
    )
    assert runtime.assurance.effective_disposition(subject.subject_id) is AssuranceDisposition.OVERRIDDEN
    with pytest.raises(PermissionError):
        runtime.foundry.authorize_handoff(handoff.handoff_id, assurance_decision_id=rejected.decision_id)
