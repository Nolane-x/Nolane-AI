from cogcoder.organization.debug_evidence import DebugEvidenceKind, FailureClass
from cogcoder.organization.runtime import OrganizationRuntime


def test_debug_chief_personally_investigates_root_cause_and_completes_task():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-CHIEF-DEBUG', title='Investigate cross-system corruption', plan_node_id='P-DEBUG')
    runtime.tasks.lease('T-CHIEF-DEBUG', 'debug.chief')

    runtime.debugging.open_case(
        case_id='CASE-CHIEF', task_id='T-CHIEF-DEBUG', title='Cross-system corruption',
        symptom='adapter writes invalid state', failure_class=FailureClass.RUNTIME,
        affected_refs=('src/adapter.py',), reporter_agent_id='debug.chief',
        evidence_refs=('EV-CHIEF-CASE',),
    )
    runtime.debugging.record_reproduction(
        case_id='CASE-CHIEF', reproducer_agent_id='debug.chief',
        deterministic=True, minimized=True, environment_digest='env-chief',
        failure_fingerprint='fp-chief', artifact_refs=('artifact-chief-repro',),
        evidence_refs=('EV-CHIEF-REPRO',),
    )
    artifact = runtime.debugging.add_evidence(
        case_id='CASE-CHIEF', producer_agent_id='debug.chief',
        kind=DebugEvidenceKind.STATE_DIFF, summary='state diverges at adapter boundary',
        output_artifact_refs=('artifact-chief-state-diff',), evidence_refs=('EV-CHIEF-DIFF',),
    )
    hypothesis = runtime.debugging.propose_hypothesis(
        case_id='CASE-CHIEF', proposer_agent_id='debug.chief',
        statement='adapter writes pre-normalized state into canonical store',
        supporting_evidence_ids=(artifact.artifact_id,), confidence=0.97,
    )
    accepted = runtime.debugging.accept_hypothesis(hypothesis.hypothesis_id, actor_agent_id='debug.chief')
    assert accepted.hypothesis_id == hypothesis.hypothesis_id

    receipt = runtime.chief_direct_work(
        'debug.chief', 'T-CHIEF-DEBUG', output_artifact_ids=('artifact-chief-investigation',),
    )
    assert receipt['chief_agent_id'] == 'debug.chief'
    assert runtime.tasks.get('T-CHIEF-DEBUG').completed_by == 'debug.chief'
