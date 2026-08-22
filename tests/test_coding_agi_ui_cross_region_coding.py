import pytest

from cogcoder.organization.coding import PatchVerificationEvidence
from cogcoder.organization.coding_profiles import CodingDomain, CodingWorkRequest
from cogcoder.organization.runtime import OrganizationRuntime


def _coding_request(runtime, *, work_id: str, task_id: str, requester: str = 'frontend.chief'):
    task = runtime.tasks.get(task_id)
    return CodingWorkRequest(
        work_id=work_id, task_id=task_id, plan_node_id=task.plan_node_id,
        requirement_refs=(), architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version,
        requested_domains=(CodingDomain.CROSS_SYSTEM,), scope_hints=('frontend', 'ui'),
        acceptance_refs=('UI-AC',), priority=70, requester_agent_id=requester,
        evidence_refs=(f'EV-{work_id}',),
    )


def test_frontend_cross_region_grant_does_not_change_exact_seven_core_coding_profiles():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-UI-GRANT', title='Implement frontend flow', plan_node_id='P-UI-GRANT')
    runtime.tasks.lease('T-UI-GRANT', 'frontend.logic.01')
    before = runtime.coding.profiles.profiles()
    grant = runtime.coding.grant_external_coder(
        agent_id='frontend.logic.01', task_id='T-UI-GRANT', actor_agent_id='coding.chief',
        reason='frontend region requires audited source mutation', evidence_refs=('EV-GRANT',),
    )
    assert grant.agent_id == 'frontend.logic.01'
    assert grant.task_id == 'T-UI-GRANT'
    assert runtime.coding.profiles.profiles() == before
    assert len(before) == 7


def test_cross_region_grant_requires_coding_or_central_authority_and_rejects_ux_identity():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-UI-AUTH', title='Frontend work', plan_node_id='P-UI-AUTH')
    runtime.tasks.lease('T-UI-AUTH', 'frontend.component.01')
    with pytest.raises(PermissionError):
        runtime.coding.grant_external_coder(
            agent_id='frontend.component.01', task_id='T-UI-AUTH', actor_agent_id='frontend.chief',
            reason='self authorize', evidence_refs=('EV-BAD-ACTOR',),
        )
    runtime.tasks.add_task('T-UX-BAD', title='UX design', plan_node_id='P-UX-BAD')
    runtime.tasks.lease('T-UX-BAD', 'ux.flow.01')
    with pytest.raises(PermissionError):
        runtime.coding.grant_external_coder(
            agent_id='ux.flow.01', task_id='T-UX-BAD', actor_agent_id='coding.chief',
            reason='ux must not mutate source through Part VII', evidence_refs=('EV-BAD-REGION',),
        )


def test_external_frontend_assignment_uses_normal_claim_patch_and_readiness_path():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-UI-CODE', title='Implement responsive panel', plan_node_id='P-UI-CODE')
    runtime.tasks.lease('T-UI-CODE', 'frontend.logic.01')
    grant = runtime.coding.grant_external_coder(
        agent_id='frontend.logic.01', task_id='T-UI-CODE', actor_agent_id='coding.chief',
        reason='authorized frontend implementation', evidence_refs=('EV-GRANT-CODE',),
    )
    assignment = runtime.coding.request_external_work(
        _coding_request(runtime, work_id='W-UI-CODE', task_id='T-UI-CODE'),
        assignee_agent_id='frontend.logic.01', grant_id=grant.grant_id,
    )
    assert assignment.selected_agent_id == 'frontend.logic.01'
    claim = runtime.coding.claim_sources(
        agent_id='frontend.logic.01', task_id='T-UI-CODE', file_paths=('src/ui/panel.py',),
    )
    assert claim.agent_id == 'frontend.logic.01'
    patch = runtime.coding.submit_patch(
        producer_agent_id='frontend.logic.01', task_id='T-UI-CODE', work_id='W-UI-CODE',
        touched_files=('src/ui/panel.py',), patch_artifact_id='artifact-ui-patch',
        compile_evidence_refs=('EV-COMPILE',), test_evidence_refs=('EV-TEST',),
    )
    ready = runtime.coding.assess_readiness(
        patch.patch_id,
        PatchVerificationEvidence('EV-VERIFY', 'verification.unit-property.01', True),
    )
    assert ready.ready is True

    runtime.coding.revoke_external_grant(grant.grant_id, actor_agent_id='coding.chief', reason='task boundary closed')
    runtime.tasks.add_task('T-UI-OTHER', title='Other task', plan_node_id='P-UI-OTHER')
    runtime.tasks.lease('T-UI-OTHER', 'frontend.logic.01')
    with pytest.raises(PermissionError):
        runtime.coding.request_external_work(
            _coding_request(runtime, work_id='W-UI-OTHER', task_id='T-UI-OTHER'),
            assignee_agent_id='frontend.logic.01', grant_id=grant.grant_id,
        )
