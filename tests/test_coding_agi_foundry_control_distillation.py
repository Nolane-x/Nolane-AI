import pytest

from cogcoder.organization.assurance_evidence import AssuranceEvidence
from cogcoder.organization.assurance_profiles import AssuranceDomain
from cogcoder.organization.foundry_memory import ScratchDisposition
from cogcoder.organization.foundry_resources import FoundryBudget
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord, SkillScope


def _spawn_output():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-F14-DISTILL', title='foundry distillation task', plan_node_id='P-F14-DISTILL')
    lease = runtime.coordination.grant_lease('T-F14-DISTILL', 'coding.backend.01', token=1, stale_after_tokens=50)
    request = runtime.foundry.request_spawn(
        sponsor_agent_id='coding.chief', parent_task_id='T-F14-DISTILL', template_id='bug-reproducer',
        mission='derive a reusable retry invariant', team_id='team-distill',
        budget=FoundryBudget(compute_units=30, tool_calls=10, external_core_calls=4, max_workers=2, lifetime_tokens=40),
        requested_tools=('filesystem', 'terminal', 'test-runner'),
        requested_external_cores=('runtime-tracer',), allowed_artifact_kinds=('reproduction', 'evidence'),
        current_token=2,
    )
    runtime.foundry.approve_spawn(request.request_id, actor_agent_id='coding.chief')
    manifest = runtime.foundry.instantiate(request.request_id, current_token=2)
    runtime.foundry.activate(manifest.ephemeral_id, actor_agent_id='coding.chief')
    output = runtime.foundry.emit_output(
        manifest.ephemeral_id, kind='reproduction',
        content='idempotent acknowledgement must precede retry state advance', evidence_refs=('EV-DISTILL-RAW',),
    )
    runtime.foundry.record_verification(
        output.output_id, EvidenceRecord('F14-DISTILL-VERIFY', 'verification.unit-property.01', True),
    )
    handoff = runtime.foundry.prepare_handoff(output.output_id, target_agent_id='coding.backend.01')
    subject = runtime.assurance.register_subject(
        subject_id='F14-DISTILL-BRIDGE', artifact_id=handoff.bridge_artifact_id,
        producer_agent_id=handoff.sponsor_agent_id, subject_version='bridge-v1', policy_class='code-change',
        evidence_refs=('EV-DISTILL-BRIDGE',), required_domains=(AssuranceDomain.UNIT_PROPERTY,),
    )
    assurance_evidence = AssuranceEvidence(
        evidence_id='F14-DISTILL-ASSURANCE', subject_id=subject.subject_id,
        subject_version=subject.subject_version, verifier_agent_id='verification.unit-property.01',
        domain=AssuranceDomain.UNIT_PROPERTY, passed=True, sandbox_digest='sandbox-distill',
        observed_epoch=subject.registered_epoch, evidence_refs=('EV-DISTILL-ASSURANCE',),
    )
    runtime.assurance.record_evidence(assurance_evidence)
    decision = runtime.assurance.assess(subject.subject_id, evidence_ids=(assurance_evidence.evidence_id,))
    return runtime, manifest, output, handoff, decision, lease


def test_stale_parent_lease_blocks_handoff_authorization_after_reassignment():
    runtime, _, _, handoff, decision, lease = _spawn_output()
    runtime.coordination.revoke_lease(
        'T-F14-DISTILL', 'coding.chief', reason='reassign parent task', evidence_refs=('EV-REASSIGN',),
    )
    next_lease = runtime.coordination.grant_lease('T-F14-DISTILL', 'coding.systems.01', token=3, stale_after_tokens=50)
    assert next_lease.epoch == lease.epoch + 1
    with pytest.raises(PermissionError):
        runtime.foundry.authorize_handoff(handoff.handoff_id, assurance_decision_id=decision.decision_id)


def test_authorized_handoff_distills_only_candidate_owned_by_permanent_target():
    runtime, manifest, _, handoff, decision, _ = _spawn_output()
    authorized = runtime.foundry.authorize_handoff(handoff.handoff_id, assurance_decision_id=decision.decision_id)
    assert authorized.authorized
    skill = runtime.foundry.distill_skill(
        authorized.handoff_id, target_agent_id='coding.backend.01',
        name='retry acknowledgement invariant', body='acknowledge durable state before advancing retry cursor',
    )
    assert skill.owner_agent_id == 'coding.backend.01'
    assert skill.scope is SkillScope.CANDIDATE
    assert manifest.ephemeral_id not in skill.owner_agent_id
    with pytest.raises(PermissionError):
        runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    runtime.individual_evolution.verify_skill(
        skill.skill_id, EvidenceRecord('F14-SKILL-EXT', 'verification.unit-property.01', True),
    )
    promoted = runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    assert promoted.scope is SkillScope.PERSONAL


def test_even_previously_authorized_handoff_cannot_distill_after_parent_lease_becomes_stale():
    runtime, _, _, handoff, decision, _ = _spawn_output()
    authorized = runtime.foundry.authorize_handoff(handoff.handoff_id, assurance_decision_id=decision.decision_id)
    runtime.coordination.revoke_lease(
        'T-F14-DISTILL', 'coding.chief', reason='lease expired after handoff', evidence_refs=('EV-STALE',),
    )
    runtime.coordination.grant_lease('T-F14-DISTILL', 'coding.systems.01', token=4, stale_after_tokens=50)
    with pytest.raises(PermissionError):
        runtime.foundry.distill_skill(
            authorized.handoff_id, target_agent_id='coding.backend.01', name='stale skill', body='must not promote',
        )


def test_quarantined_or_retired_worker_cannot_emit_or_distill_new_output():
    runtime, manifest, output, handoff, decision, _ = _spawn_output()
    runtime.foundry.quarantine(
        manifest.ephemeral_id, actor_agent_id='coding.chief', reason='counterexample invalidated',
    )
    with pytest.raises(PermissionError):
        runtime.foundry.authorize_handoff(handoff.handoff_id, assurance_decision_id=decision.decision_id)
    with pytest.raises(PermissionError):
        runtime.foundry.emit_output(
            manifest.ephemeral_id, kind='evidence', content='late poisoned output', evidence_refs=('EV-LATE',),
        )

    runtime2, manifest2, *_ = _spawn_output()
    runtime2.foundry.retire(
        manifest2.ephemeral_id, actor_agent_id='coding.chief', scratch_policy=ScratchDisposition.DESTROY,
    )
    with pytest.raises(PermissionError):
        runtime2.foundry.emit_output(
            manifest2.ephemeral_id, kind='evidence', content='post retirement', evidence_refs=('EV-POST',),
        )
