import pytest

from cogcoder.organization.debug_evidence import DebugEvidenceKind, DebugEvidenceLedger, FailureClass
from cogcoder.organization.debug_hypotheses import DebugHypothesisLedger


def _case(failure_class):
    evidence = DebugEvidenceLedger()
    evidence.open_case(
        case_id='CASE-X', task_id='T-X', title='Specialist failure', symptom='heldout failure',
        failure_class=failure_class, affected_refs=('src/x.py',),
        reporter_agent_id='coding.systems.01', evidence_refs=('EV-X',),
    )
    evidence.record_reproduction(
        case_id='CASE-X', reproducer_agent_id='debug.reproducer.01', deterministic=True,
        minimized=True, environment_digest='env-x', failure_fingerprint='fp-x',
        artifact_refs=('artifact-repro',), evidence_refs=('EV-REPRO',),
    )
    generic = evidence.add_evidence(
        case_id='CASE-X', producer_agent_id='debug.runtime-trace.01',
        kind=DebugEvidenceKind.RUNTIME_TRACE, summary='generic runtime trace',
        output_artifact_refs=('artifact-trace',), evidence_refs=('EV-TRACE',),
    )
    return evidence, generic


def test_concurrency_root_cause_requires_concurrency_specific_evidence():
    evidence, generic = _case(FailureClass.CONCURRENCY)
    hypotheses = DebugHypothesisLedger(evidence)
    row = hypotheses.propose(
        case_id='CASE-X', proposer_agent_id='debug.concurrency-state.01',
        statement='lost wakeup causes stale state', supporting_evidence_ids=(generic.artifact_id,), confidence=0.8,
    )
    with pytest.raises(ValueError):
        hypotheses.accept(row.hypothesis_id, actor_agent_id='debug.chief')

    race = evidence.add_evidence(
        case_id='CASE-X', producer_agent_id='debug.concurrency-state.01',
        kind=DebugEvidenceKind.CONCURRENCY_TRACE, summary='happens-before violation captured',
        input_artifact_refs=('artifact-repro',), output_artifact_refs=('artifact-race',),
        evidence_refs=('EV-RACE',),
    )
    row2 = hypotheses.propose(
        case_id='CASE-X', proposer_agent_id='debug.concurrency-state.01',
        statement='lost wakeup proven by happens-before trace',
        supporting_evidence_ids=(generic.artifact_id, race.artifact_id), confidence=0.95,
    )
    assert hypotheses.accept(row2.hypothesis_id, actor_agent_id='debug.chief').hypothesis_id == row2.hypothesis_id


def test_regression_root_cause_requires_bisect_evidence():
    evidence, generic = _case(FailureClass.REGRESSION)
    hypotheses = DebugHypothesisLedger(evidence)
    row = hypotheses.propose(
        case_id='CASE-X', proposer_agent_id='debug.regression-bisect.01',
        statement='recent parser change caused regression', supporting_evidence_ids=(generic.artifact_id,), confidence=0.7,
    )
    with pytest.raises(ValueError):
        hypotheses.accept(row.hypothesis_id, actor_agent_id='debug.chief')

    bisect = evidence.add_evidence(
        case_id='CASE-X', producer_agent_id='debug.regression-bisect.01',
        kind=DebugEvidenceKind.BISECT, summary='first bad commit isolated',
        output_artifact_refs=('artifact-bisect',), evidence_refs=('EV-BISECT',),
    )
    row2 = hypotheses.propose(
        case_id='CASE-X', proposer_agent_id='debug.regression-bisect.01',
        statement='bisect isolates parser change',
        supporting_evidence_ids=(generic.artifact_id, bisect.artifact_id), confidence=0.98,
    )
    assert hypotheses.accept(row2.hypothesis_id, actor_agent_id='debug.chief').hypothesis_id == row2.hypothesis_id
