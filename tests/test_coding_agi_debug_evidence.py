import pytest

from cogcoder.organization.debug_evidence import (
    DebugCaseStatus,
    DebugEvidenceKind,
    DebugEvidenceLedger,
    FailureClass,
)


def _ledger_with_case():
    ledger = DebugEvidenceLedger()
    case = ledger.open_case(
        case_id='CASE-1', task_id='T-1', title='Auth crash',
        symptom='refresh crashes under malformed state', failure_class=FailureClass.RUNTIME,
        affected_refs=('COMP-AUTH', 'src/api/auth.py'), reporter_agent_id='coding.backend.01',
        evidence_refs=('EV-CASE-1',),
    )
    return ledger, case


def test_case_identity_and_initial_provenance_are_immutable():
    ledger, case = _ledger_with_case()
    assert case.status is DebugCaseStatus.OPEN
    assert case.reporter_agent_id == 'coding.backend.01'
    assert case.initial_evidence_refs == ('EV-CASE-1',)
    before = ledger.to_state()
    with pytest.raises(ValueError):
        ledger.open_case(
            case_id='CASE-1', task_id='T-2', title='different', symptom='different',
            failure_class=FailureClass.RUNTIME, affected_refs=('x',),
            reporter_agent_id='debug.chief', evidence_refs=('EV-X',),
        )
    assert ledger.to_state() == before


def test_nondeterministic_reproduction_is_preserved_but_does_not_advance_case():
    ledger, _ = _ledger_with_case()
    attempt = ledger.record_reproduction(
        case_id='CASE-1', reproducer_agent_id='debug.reproducer.01',
        deterministic=False, minimized=False, environment_digest='env-1',
        failure_fingerprint='fp-flaky', artifact_refs=('artifact-repro-flaky',),
        evidence_refs=('EV-REPRO-FLAKY',),
    )
    assert attempt.deterministic is False
    assert ledger.get_case('CASE-1').status is DebugCaseStatus.OPEN
    assert len(ledger.reproductions_for('CASE-1')) == 1

    accepted = ledger.record_reproduction(
        case_id='CASE-1', reproducer_agent_id='debug.reproducer.01',
        deterministic=True, minimized=True, environment_digest='env-1',
        failure_fingerprint='fp-stable', artifact_refs=('artifact-repro-min',),
        evidence_refs=('EV-REPRO-STABLE',),
    )
    assert accepted.deterministic is True
    assert ledger.get_case('CASE-1').status is DebugCaseStatus.REPRODUCED
    assert len(ledger.reproductions_for('CASE-1')) == 2


def test_evidence_timeline_is_append_only_ordered_and_restart_safe():
    ledger, _ = _ledger_with_case()
    first = ledger.add_evidence(
        case_id='CASE-1', producer_agent_id='debug.runtime-trace.01',
        kind=DebugEvidenceKind.RUNTIME_TRACE, summary='exception path trace',
        input_artifact_refs=('artifact-repro',), output_artifact_refs=('artifact-trace',),
        evidence_refs=('EV-TRACE',),
    )
    second = ledger.add_evidence(
        case_id='CASE-1', producer_agent_id='debug.static-root-cause.01',
        kind=DebugEvidenceKind.STATIC_FLOW, summary='bad state reaches dereference',
        input_artifact_refs=('artifact-source',), output_artifact_refs=('artifact-flow',),
        evidence_refs=('EV-FLOW',),
    )
    assert first.sequence < second.sequence
    assert ledger.evidence_for('CASE-1') == (first, second)

    restored = DebugEvidenceLedger.from_state(ledger.to_state())
    assert restored.to_state() == ledger.to_state()
    assert restored.evidence_for('CASE-1') == (first, second)
