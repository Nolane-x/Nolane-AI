from __future__ import annotations

import json

from cogcoder.r253_external_cognition import (
    CognitiveOperatorRegistry,
    CognitiveOperatorSpec,
    CognitiveSnapshot,
    DeficitSignal,
    ExternalWorkingState,
    make_procedure_digest,
)
from cogcoder.r254_behavioral_retrieval import RetrievedProcedureAcquirer, RetrievedProcedureExecutor
from cogcoder.r254_cognitive_retrieval import CognitiveAttachment, content_digest


def operator(operator_id, executor, *, requires=(), provides=(), risk=0.0):
    return CognitiveOperatorSpec(
        operator_id=operator_id,
        family='test',
        tags=frozenset({'test'}),
        requires=frozenset(requires),
        provides=frozenset(provides),
        cost=1.0,
        risk=risk,
        side_effect_class='state_only',
        version='1',
        source_uri=f'test://{operator_id}',
        executor=executor,
    )


def procedure_attachment(*, steps=('reason.derive', 'verify.final'), trust=1.0, artifact_id='proc.safe'):
    fields = dict(
        procedure_id='external.safe_reasoning',
        version='1',
        deficit_tags=frozenset({'knowledge_gap'}),
        context_tags=frozenset({'answer'}),
        steps=tuple(steps),
        preconditions=frozenset(),
        expected_outputs=frozenset({'candidate', 'verified'}),
        verifier_operator_id='verify.final',
        max_cost=4.0,
        max_risk=0.1,
        trust_score=float(trust),
        source_uri='skill://external/safe-reasoning',
    )
    digest = make_procedure_digest(**fields)
    payload = {
        **fields,
        'deficit_tags': sorted(fields['deficit_tags']),
        'context_tags': sorted(fields['context_tags']),
        'steps': list(fields['steps']),
        'preconditions': sorted(fields['preconditions']),
        'expected_outputs': sorted(fields['expected_outputs']),
        'content_sha256': digest,
    }
    text = json.dumps(payload, sort_keys=True)
    return CognitiveAttachment(
        artifact_id=artifact_id,
        kind='procedure',
        text=text,
        source_uri='external://procedure-store',
        version='1',
        activation=0.95,
        trust_score=1.0,
        rationale=('retrieved',),
        content_sha256=content_digest(text),
    )


def test_retrieved_safe_manifest_compiles_and_executes_only_registered_primitives():
    def derive(state, _snapshot, _signal):
        return {'success': True, 'updates': {'candidate': 42}, 'provides': {'candidate'}, 'evidence': ('derived:42',)}

    def verify(state, _snapshot, _signal):
        ok = state.context.get('candidate') == 42
        return {'success': ok, 'updates': {'verified': ok}, 'provides': {'verified'}, 'evidence': (f'verified:{ok}',)}

    registry = CognitiveOperatorRegistry([
        operator('reason.derive', derive, provides={'candidate'}),
        operator('verify.final', verify, requires={'candidate'}, provides={'verified'}),
    ])
    acquired = RetrievedProcedureAcquirer(registry).acquire((procedure_attachment(),))
    assert len(acquired.accepted) == 1
    assert not acquired.rejected

    state = ExternalWorkingState()
    snapshot = CognitiveSnapshot(
        objective='answer bounded task', step_index=1, self_confidence=0.99,
        progress_score=0.2, previous_progress_score=0.2, evidence_coverage=0.1,
    )
    signal = DeficitSignal('knowledge_gap', 0.9, 0.99, 'objective')
    receipt = RetrievedProcedureExecutor().execute(acquired.accepted[0], state, snapshot, signal)
    assert receipt.success is True
    assert receipt.verified is True
    assert receipt.executed_operator_ids == ('reason.derive', 'verify.final')
    assert state.context['candidate'] == 42


def test_retrieved_manifest_with_unknown_arbitrary_step_is_rejected_before_execution():
    registry = CognitiveOperatorRegistry([])
    acquired = RetrievedProcedureAcquirer(registry).acquire((
        procedure_attachment(steps=('arbitrary.exec', 'verify.final'), artifact_id='proc.malicious'),
    ))
    assert not acquired.accepted
    assert acquired.rejected[0].artifact_id == 'proc.malicious'
    assert 'unregistered operator step' in acquired.rejected[0].reason


def test_low_trust_or_tampered_procedure_manifest_is_rejected():
    registry = CognitiveOperatorRegistry([])
    low = procedure_attachment(trust=0.2, artifact_id='proc.low')
    tampered = CognitiveAttachment(
        artifact_id='proc.tampered', kind='procedure', text=low.text + ' ', source_uri=low.source_uri,
        version=low.version, activation=low.activation, trust_score=low.trust_score, rationale=low.rationale,
        content_sha256=low.content_sha256,
    )
    acquired = RetrievedProcedureAcquirer(registry, min_artifact_trust=0.8, min_card_trust=0.75).acquire((low, tampered))
    reasons = {row.artifact_id: row.reason for row in acquired.rejected}
    assert 'artifact trust below acquisition threshold' in reasons['proc.low']
    assert 'artifact provenance digest mismatch' in reasons['proc.tampered']
