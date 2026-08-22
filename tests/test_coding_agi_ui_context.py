from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.ui_profiles import UIDomain, UIWorkRequest


def test_frontend_and_ux_wake_with_ui_state_but_only_granted_frontend_gets_coding_state():
    runtime = OrganizationRuntime.first_generation()

    runtime.tasks.add_task('T-FRONTEND-CONTEXT', title='Frontend context', plan_node_id='P-FRONTEND-CONTEXT')
    runtime.tasks.lease('T-FRONTEND-CONTEXT', 'frontend.logic.01')
    runtime.checkpoint_agent('frontend.logic.01')
    runtime.ui.request_work(UIWorkRequest(
        work_id='W-FRONTEND-CONTEXT', task_id='T-FRONTEND-CONTEXT', requested_domains=(UIDomain.FRONTEND_LOGIC,),
        scope_hints=('state',), priority=60, requester_agent_id='frontend.chief', evidence_refs=('EV-UI-CONTEXT',),
    ))
    runtime.coding.grant_external_coder(
        agent_id='frontend.logic.01', task_id='T-FRONTEND-CONTEXT', actor_agent_id='coding.chief',
        reason='context source work', evidence_refs=('EV-GRANT-CONTEXT',),
    )
    frontend = runtime.wake_agent('frontend.logic.01', reason='UI work changed')
    assert ('ui-state', runtime.ui.digest) in frontend.authoritative_artifacts
    assert ('coding-state', runtime.coding.digest) in frontend.authoritative_artifacts

    runtime.tasks.add_task('T-UX-CONTEXT', title='UX context', plan_node_id='P-UX-CONTEXT')
    runtime.tasks.lease('T-UX-CONTEXT', 'ux.flow.01')
    runtime.checkpoint_agent('ux.flow.01')
    runtime.ui.request_work(UIWorkRequest(
        work_id='W-UX-CONTEXT', task_id='T-UX-CONTEXT', requested_domains=(UIDomain.UX_FLOW,),
        scope_hints=('journey',), priority=60, requester_agent_id='ux.chief', evidence_refs=('EV-UX-CONTEXT',),
    ))
    ux = runtime.wake_agent('ux.flow.01', reason='UX work changed')
    assert ('ui-state', runtime.ui.digest) in ux.authoritative_artifacts
    assert not any(name == 'coding-state' for name, _ in ux.authoritative_artifacts)


def test_non_ui_region_does_not_receive_full_ui_state_by_default():
    runtime = OrganizationRuntime.first_generation()
    capsule = runtime.context.compile('debug.runtime-trace.01')
    assert not any(name == 'ui-state' for name, _ in capsule.authoritative_artifacts)
