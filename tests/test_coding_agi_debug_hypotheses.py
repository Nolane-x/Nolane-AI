import pytest

from cogcoder.organization.debug_evidence import DebugEvidenceKind, DebugEvidenceLedger, FailureClass
from cogcoder.organization.debug_hypotheses import DebugHypothesisLedger, HypothesisStatus


def _prepared_case(failure_class=FailureClass.RUNTIME):
    evidence = DebugEvidenceLedger()
    evidence.open_case(
        case_id='CASE-H', task_id='T-H', title='Failure', symptom='bad behavior',
        failure_class=failure_class, affected_refs=('src/core.py',),
        reporter_agent_id='coding.backend.01', evidence_refs=('EV-CASE',),
    )
    evidence.record_reproduction(
        case_id='CASE-H', reproducer_agent_id='debug.reproducer.01',
        deterministic=True, minimized=True, environment_digest='env-h',
        failure_fingerprint='fp-h', artifact_refs=('artifact-repro',), evidence_refs=('EV-REPRO',),
    )
    artifact = evidence.add_evidence(
        case_id='CASE-H', producer_agent_id='debug.static-root-cause.01',
        kind=DebugEvidenceKind.STATIC_FLOW, summary='flow reaches invalid branch',
        input_artifact_refs=('artifact-src',), output_artifact_refs=('artifact-flow',),
        evidence_refs=('EV-FLOW',),
    )
    return evidence, artifact


def test_competing_hypotheses_preserve_rejected_history_and_one_current_truth():
    evidence, artifact = _prepared_case()
    ledger = DebugHypothesisLedger(evidence)
    first = ledger.propose(
        case_id='CASE-H', proposer_agent_id='debug.static-root-cause.01',
        statement='cache state is stale', supporting_evidence_ids=(artifact.artifact_id,), confidence=0.55,
    )
    second = ledger.propose(
        case_id='CASE-H', proposer_agent_id='debug.runtime-trace.01',
        statement='null token reaches refresh path', supporting_evidence_ids=(artifact.artifact_id,), confidence=0.8,
    )
    rejected = ledger.reject(
        first.hypothesis_id, actor_agent_id='debug.chief', reason='trace contradicts cache theory',
        refuting_evidence_ids=(artifact.artifact_id,),
    )
    assert rejected.status is HypothesisStatus.REJECTED
    assert ledger.get(first.hypothesis_id).status is HypothesisStatus.REJECTED

    with pytest.raises(ValueError):
        ledger.accept(first.hypothesis_id, actor_agent_id='debug.chief')

    accepted = ledger.accept(second.hypothesis_id, actor_agent_id='debug.chief')
    assert accepted.status is HypothesisStatus.ACCEPTED
    assert ledger.current_root_cause('CASE-H').hypothesis_id == second.hypothesis_id
    assert ledger.get(first.hypothesis_id).status is HypothesisStatus.REJECTED

    third = ledger.propose(
        case_id='CASE-H', proposer_agent_id='debug.static-root-cause.01',
        statement='another theory', supporting_evidence_ids=(artifact.artifact_id,), confidence=0.6,
    )
    with pytest.raises(ValueError):
        ledger.accept(third.hypothesis_id, actor_agent_id='debug.chief')


def test_root_cause_acceptance_requires_debug_chief_and_deterministic_reproduction():
    evidence = DebugEvidenceLedger()
    evidence.open_case(
        case_id='CASE-ND', task_id='T-ND', title='Flaky', symptom='sometimes fails',
        failure_class=FailureClass.RUNTIME, affected_refs=('src/flaky.py',),
        reporter_agent_id='coding.backend.01', evidence_refs=('EV-ND',),
    )
    evidence.record_reproduction(
        case_id='CASE-ND', reproducer_agent_id='debug.reproducer.01', deterministic=False,
        minimized=False, environment_digest='env', failure_fingerprint='fp',
        artifact_refs=('artifact-flaky',), evidence_refs=('EV-FLAKY',),
    )
    artifact = evidence.add_evidence(
        case_id='CASE-ND', producer_agent_id='debug.runtime-trace.01',
        kind=DebugEvidenceKind.RUNTIME_TRACE, summary='one flaky trace',
        output_artifact_refs=('artifact-trace',), evidence_refs=('EV-TRACE',),
    )
    ledger = DebugHypothesisLedger(evidence)
    hypothesis = ledger.propose(
        case_id='CASE-ND', proposer_agent_id='debug.runtime-trace.01',
        statement='timing-sensitive branch', supporting_evidence_ids=(artifact.artifact_id,), confidence=0.5,
    )
    with pytest.raises(PermissionError):
        ledger.accept(hypothesis.hypothesis_id, actor_agent_id='debug.runtime-trace.01')
    with pytest.raises(ValueError):
        ledger.accept(hypothesis.hypothesis_id, actor_agent_id='debug.chief')
