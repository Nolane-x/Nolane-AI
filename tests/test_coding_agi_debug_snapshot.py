from cogcoder.organization.debug_evidence import DebugEvidenceKind, FailureClass
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot


def test_debugging_state_round_trips_exactly_through_snapshot():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-SNAP-DEBUG', title='Debug snapshot case', plan_node_id='P-SNAP-DEBUG')
    runtime.debugging.open_case(
        case_id='CASE-SNAP', task_id='T-SNAP-DEBUG', title='Snapshot bug', symptom='deterministic failure',
        failure_class=FailureClass.RUNTIME, affected_refs=('src/snapshot_bug.py',),
        reporter_agent_id='coding.backend.01', evidence_refs=('EV-SNAP-CASE',),
    )
    runtime.debugging.record_reproduction(
        case_id='CASE-SNAP', reproducer_agent_id='debug.reproducer.01', deterministic=True,
        minimized=True, environment_digest='env-snap', failure_fingerprint='fp-snap',
        artifact_refs=('artifact-snap-repro',), evidence_refs=('EV-SNAP-REPRO',),
    )
    evidence = runtime.debugging.add_evidence(
        case_id='CASE-SNAP', producer_agent_id='debug.runtime-trace.01',
        kind=DebugEvidenceKind.RUNTIME_TRACE, summary='trace points to bad branch',
        output_artifact_refs=('artifact-snap-trace',), evidence_refs=('EV-SNAP-TRACE',),
    )
    hypothesis = runtime.debugging.propose_hypothesis(
        case_id='CASE-SNAP', proposer_agent_id='debug.runtime-trace.01',
        statement='bad branch causes crash', supporting_evidence_ids=(evidence.artifact_id,), confidence=0.9,
    )
    runtime.debugging.accept_hypothesis(hypothesis.hypothesis_id, actor_agent_id='debug.chief')

    before = runtime.debugging.to_state()
    snapshot = OrganizationSnapshot.capture(runtime)
    restored = snapshot.restore()
    assert restored.debugging.to_state() == before
    assert OrganizationSnapshot.capture(restored).digest == snapshot.digest
