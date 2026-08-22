import pytest

from cogcoder.organization.coding import PatchVerificationEvidence
from cogcoder.organization.coding_profiles import CodingDomain, CodingWorkRequest
from cogcoder.organization.debug_evidence import DebugCaseStatus, DebugEvidenceKind, FailureClass
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import SkillScope


def _accepted_case(runtime):
    runtime.tasks.add_task('T-BUG', title='Investigate auth crash', plan_node_id='P-BUG')
    runtime.debugging.open_case(
        case_id='CASE-HANDOFF', task_id='T-BUG', title='Auth crash',
        symptom='refresh crashes on stale token', failure_class=FailureClass.RUNTIME,
        affected_refs=('src/api/auth.py', 'AuthService.refresh'),
        reporter_agent_id='coding.backend.01', evidence_refs=('EV-CASE',),
    )
    runtime.debugging.record_reproduction(
        case_id='CASE-HANDOFF', reproducer_agent_id='debug.reproducer.01',
        deterministic=True, minimized=True, environment_digest='env-auth',
        failure_fingerprint='fp-auth', artifact_refs=('artifact-repro',), evidence_refs=('EV-REPRO',),
    )
    evidence = runtime.debugging.add_evidence(
        case_id='CASE-HANDOFF', producer_agent_id='debug.static-root-cause.01',
        kind=DebugEvidenceKind.STATIC_FLOW, summary='stale token reaches unsafe dereference',
        output_artifact_refs=('artifact-flow',), evidence_refs=('EV-FLOW',),
    )
    hypothesis = runtime.debugging.propose_hypothesis(
        case_id='CASE-HANDOFF', proposer_agent_id='debug.static-root-cause.01',
        statement='stale token reaches unsafe dereference',
        supporting_evidence_ids=(evidence.artifact_id,), confidence=0.95,
    )
    runtime.debugging.accept_hypothesis(hypothesis.hypothesis_id, actor_agent_id='debug.chief')
    return hypothesis


def test_accepted_root_cause_links_to_part_v_patch_and_only_ready_patch_resolves_case():
    runtime = OrganizationRuntime.first_generation()
    hypothesis = _accepted_case(runtime)

    runtime.tasks.add_task('T-FIX', title='Fix auth crash', plan_node_id='P-FIX')
    runtime.tasks.lease('T-FIX', 'coding.backend.01')
    work = CodingWorkRequest(
        work_id='W-FIX', task_id='T-FIX', plan_node_id='P-FIX', requirement_refs=(),
        architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version,
        requested_domains=(CodingDomain.BACKEND,), scope_hints=('backend', 'service'),
        acceptance_refs=('AC-FIX',), priority=90, requester_agent_id='debug.chief',
        evidence_refs=('EV-HANDOFF',),
    )
    handoff = runtime.debugging.handoff_to_coding(
        case_id='CASE-HANDOFF', hypothesis_id=hypothesis.hypothesis_id,
        work_request=work, affected_source_refs=('src/api/auth.py', 'AuthService.refresh'),
        evidence_refs=('EV-HANDOFF',),
    )
    assert handoff.selected_coder_agent_id == 'coding.backend.01'
    assert runtime.debugging.evidence.get_case('CASE-HANDOFF').status is DebugCaseStatus.PATCH_IN_PROGRESS

    runtime.coding.claim_sources(
        agent_id='coding.backend.01', task_id='T-FIX',
        file_paths=('src/api/auth.py',), symbol_ids=('AuthService.refresh',),
    )
    patch = runtime.coding.submit_patch(
        producer_agent_id='coding.backend.01', task_id='T-FIX', work_id='W-FIX',
        touched_files=('src/api/auth.py',), touched_symbols=('AuthService.refresh',),
        patch_artifact_id='artifact-fix-patch',
        compile_evidence_refs=('EV-COMPILE',), test_evidence_refs=('EV-TEST',),
    )
    rejected = runtime.coding.assess_readiness(
        patch.patch_id,
        PatchVerificationEvidence('EV-SELF', 'coding.backend.01', True, 0, 0),
    )
    assert rejected.ready is False
    with pytest.raises(PermissionError):
        runtime.debugging.resolve(
            case_id='CASE-HANDOFF', handoff_id=handoff.handoff_id,
            patch_id=patch.patch_id, coding_readiness_receipt_id=rejected.receipt_id,
        )

    ready = runtime.coding.assess_readiness(
        patch.patch_id,
        PatchVerificationEvidence('EV-VERIFY', 'verification.unit-property.01', True, 0, 0),
    )
    resolution = runtime.debugging.resolve(
        case_id='CASE-HANDOFF', handoff_id=handoff.handoff_id,
        patch_id=patch.patch_id, coding_readiness_receipt_id=ready.receipt_id,
    )
    assert resolution.patch_id == patch.patch_id
    assert resolution.hypothesis_id == hypothesis.hypothesis_id
    assert runtime.debugging.evidence.get_case('CASE-HANDOFF').status is DebugCaseStatus.RESOLVED

    skill = runtime.debugging.propose_personal_skill_from_resolution(
        resolution.resolution_id,
        name='stale token root-cause pattern',
        body='trace stale token flow before patching refresh state',
    )
    assert skill.owner_agent_id == 'debug.static-root-cause.01'
    assert skill.scope is SkillScope.CANDIDATE
