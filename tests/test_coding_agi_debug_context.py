from cogcoder.organization.debug_evidence import FailureClass
from cogcoder.organization.debug_profiles import DebugDomain, DebugWorkRequest
from cogcoder.organization.runtime import OrganizationRuntime


def test_debugger_wakes_with_debugging_state_and_relevant_delta_only():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-CTX-DEBUG', title='Trace context bug', plan_node_id='P-CTX-DEBUG')
    runtime.checkpoint_agent('debug.runtime-trace.01')

    runtime.debugging.open_case(
        case_id='CASE-CTX', task_id='T-CTX-DEBUG', title='Context crash', symptom='trace needed',
        failure_class=FailureClass.RUNTIME, affected_refs=('src/context_bug.py',),
        reporter_agent_id='coding.backend.01', evidence_refs=('EV-CTX-CASE',),
    )
    assignment = runtime.debugging.request_investigation(DebugWorkRequest(
        work_id='DW-CTX', case_id='CASE-CTX', task_id='T-CTX-DEBUG',
        requested_domains=(DebugDomain.RUNTIME_TRACE,), scope_hints=('trace', 'stack'),
        priority=70, requester_agent_id='debug.chief', evidence_refs=('EV-CTX-WORK',),
    ))
    assert assignment.selected_agent_id == 'debug.runtime-trace.01'

    capsule = runtime.wake_agent('debug.runtime-trace.01', reason='debug case assigned')
    assert ('debugging-state', runtime.debugging.digest) in capsule.authoritative_artifacts
    assert any(event.target_agent_id == 'debug.runtime-trace.01' for event in capsule.event_delta)

    non_debug = runtime.context.compile('coding.backend.01')
    assert not any(name == 'debugging-state' for name, _ in non_debug.authoritative_artifacts)
