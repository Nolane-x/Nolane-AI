from __future__ import annotations

import hashlib

import pytest

from cogcoder.r253_external_cognition import (
    CognitiveDeficitDetector,
    CognitiveOperatorRegistry,
    CognitiveOperatorSpec,
    CognitiveReflexRouter,
    CognitiveReflexRuntime,
    CognitiveSnapshot,
    CounterexampleMemory,
    ExternalWorkingState,
    ProcedureCard,
    ProcedureCompiler,
    ProcedureCreditLedger,
    ProcedureLibrary,
    make_procedure_digest,
)


def _snapshot(**overrides):
    values = dict(
        objective='repair opaque task',
        step_index=3,
        self_confidence=0.9,
        progress_score=0.5,
        previous_progress_score=0.4,
        unresolved_requirements=(),
        evidence_coverage=1.0,
        verifier_failures=0,
        recent_action_fingerprints=('a', 'b'),
        representation_id='text',
        representation_failures=0,
        available_capabilities=frozenset({'reason'}),
        missing_capabilities=frozenset(),
        evidence_conflicts=0,
        stale_evidence=0,
        blocked_subgoals=0,
        working_memory_pressure=0.1,
        counterexample_repeat_count=0,
        resource_pressure=0.1,
        candidate_verified=True,
        terminal_candidate=True,
        host_observations=(),
    )
    values.update(overrides)
    return CognitiveSnapshot(**values)


def test_objective_failures_override_adversarially_high_self_confidence():
    detector = CognitiveDeficitDetector()
    snapshot = _snapshot(
        self_confidence=0.999,
        progress_score=0.40,
        previous_progress_score=0.40,
        verifier_failures=3,
        recent_action_fingerprints=('same', 'same', 'same', 'same'),
        candidate_verified=False,
    )
    deficits = {signal.kind: signal for signal in detector.detect(snapshot)}
    assert deficits['search_stagnation'].severity >= 0.8
    assert deficits['verification_gap'].severity >= 0.8
    assert deficits['search_stagnation'].source == 'objective'
    assert deficits['verification_gap'].source == 'objective'


def test_detector_surfaces_multiple_missing_external_capabilities():
    detector = CognitiveDeficitDetector()
    snapshot = _snapshot(
        unresolved_requirements=('latest API behavior', 'symbolic proof'),
        evidence_coverage=0.1,
        missing_capabilities=frozenset({'tool:smt', 'tool:docs'}),
        evidence_conflicts=2,
        stale_evidence=3,
        representation_failures=2,
        blocked_subgoals=2,
        working_memory_pressure=0.93,
        counterexample_repeat_count=2,
        resource_pressure=0.91,
        candidate_verified=False,
        terminal_candidate=False,
    )
    kinds = {signal.kind for signal in detector.detect(snapshot)}
    assert {
        'knowledge_gap', 'tool_gap', 'contradiction', 'temporal_conflict',
        'representation_mismatch', 'planning_gap', 'working_memory_pressure',
        'counterexample_gap', 'resource_pressure', 'stopping_uncertainty',
    } <= kinds


def _operator(op_id, *, provides=(), requires=(), cost=1.0, risk=0.1, result_key=None):
    def execute(state, _snapshot, _signal):
        updates = {} if result_key is None else {result_key: True}
        return {'success': True, 'updates': updates, 'evidence': (op_id,)}
    return CognitiveOperatorSpec(
        operator_id=op_id,
        family='test',
        tags=frozenset(op_id.split('.')),
        requires=frozenset(requires),
        provides=frozenset(provides),
        cost=cost,
        risk=risk,
        side_effect_class='state_only',
        version='1',
        source_uri='unit://operator',
        executor=execute,
    )


def _card(card_id, deficit_tags, steps, *, context_tags=(), trust=0.95, max_cost=10.0, verifier=None):
    fields = dict(
        procedure_id=card_id,
        version='1',
        deficit_tags=frozenset(deficit_tags),
        context_tags=frozenset(context_tags),
        steps=tuple(steps),
        preconditions=frozenset(),
        expected_outputs=frozenset(),
        verifier_operator_id=verifier,
        max_cost=max_cost,
        max_risk=1.0,
        trust_score=trust,
        source_uri='unit://procedure',
    )
    digest = make_procedure_digest(**fields)
    return ProcedureCard(content_sha256=digest, **fields)


def test_procedure_compiler_rejects_unregistered_steps_and_tampered_provenance():
    registry = CognitiveOperatorRegistry([_operator('retrieve.knowledge')])
    compiler = ProcedureCompiler(registry, min_trust=0.8)
    with pytest.raises(ValueError, match='unregistered'):
        compiler.compile(_card('bad-step', {'knowledge_gap'}, ('retrieve.knowledge', 'arbitrary.exec')))

    good = _card('good', {'knowledge_gap'}, ('retrieve.knowledge',))
    tampered = ProcedureCard(**{**good.__dict__, 'content_sha256': hashlib.sha256(b'wrong').hexdigest()})
    with pytest.raises(ValueError, match='provenance'):
        compiler.compile(tampered)


def test_procedure_compiler_enforces_capability_order_and_cost_budget():
    registry = CognitiveOperatorRegistry([
        _operator('retrieve.knowledge', provides={'evidence'}, cost=1.0),
        _operator('verify.claim', requires={'evidence'}, provides={'verified'}, cost=2.0),
    ])
    compiler = ProcedureCompiler(registry)
    compiled = compiler.compile(_card('ok', {'knowledge_gap'}, ('retrieve.knowledge', 'verify.claim'), max_cost=4.0))
    assert compiled.total_cost == 3.0
    assert compiled.provided_capabilities == frozenset({'evidence', 'verified'})

    with pytest.raises(ValueError, match='capability'):
        compiler.compile(_card('wrong-order', {'knowledge_gap'}, ('verify.claim', 'retrieve.knowledge')))
    with pytest.raises(ValueError, match='cost'):
        compiler.compile(_card('too-costly', {'knowledge_gap'}, ('retrieve.knowledge', 'verify.claim'), max_cost=2.5))


def test_procedure_library_retrieves_by_deficit_context_not_only_name():
    cards = [
        _card('docs-for-code', {'knowledge_gap'}, ('retrieve.knowledge',), context_tags={'code', 'api'}),
        _card('docs-for-history', {'knowledge_gap'}, ('retrieve.knowledge',), context_tags={'history'}),
        _card('stagnation', {'search_stagnation'}, ('retrieve.knowledge',), context_tags={'code'}),
    ]
    library = ProcedureLibrary(cards)
    ranked = library.search('knowledge_gap', {'code', 'api', 'python'}, k=2)
    assert ranked[0].procedure_id == 'docs-for-code'
    assert {card.procedure_id for card in ranked} <= {'docs-for-code', 'docs-for-history'}


def test_credit_ledger_and_counterexample_memory_change_future_routing_without_weight_updates():
    ledger = ProcedureCreditLedger()
    memory = CounterexampleMemory()
    for _ in range(4):
        ledger.record('good', 'knowledge_gap', success=True)
    for _ in range(3):
        ledger.record('bad', 'knowledge_gap', success=False)
    memory.add('bad', 'knowledge_gap', 'ctx:abc', 'verifier_rejected')
    assert ledger.competence('good', 'knowledge_gap') > ledger.competence('bad', 'knowledge_gap')
    assert memory.has('bad', 'knowledge_gap', 'ctx:abc')


def test_router_prefers_competent_low_risk_non_counterexample_procedure():
    registry = CognitiveOperatorRegistry([
        _operator('retrieve.knowledge', cost=1.0, risk=0.05),
        _operator('search.diversify', cost=2.0, risk=0.1),
    ])
    compiler = ProcedureCompiler(registry)
    cards = [
        compiler.compile(_card('good', {'knowledge_gap'}, ('retrieve.knowledge',), context_tags={'code'})),
        compiler.compile(_card('bad', {'knowledge_gap'}, ('search.diversify',), context_tags={'code'})),
    ]
    credit = ProcedureCreditLedger(); counter = CounterexampleMemory()
    for _ in range(5): credit.record('good', 'knowledge_gap', success=True)
    for _ in range(4): credit.record('bad', 'knowledge_gap', success=False)
    counter.add('bad', 'knowledge_gap', 'ctx:1', 'known_failure')
    router = CognitiveReflexRouter(credit, counter)
    chosen = router.choose(cards, deficit_kind='knowledge_gap', deficit_severity=0.9, context_tags={'code'}, context_fingerprint='ctx:1')
    assert chosen.procedure_id == 'good'


def test_reflex_runtime_detects_gap_retrieves_procedure_executes_and_verifies():
    state = ExternalWorkingState(context={'answer_ready': False}, capabilities={'reason'})

    def retrieve(state, _snapshot, _signal):
        return {'success': True, 'updates': {'fact': 7}, 'provides': {'evidence'}, 'evidence': ('fact:7',)}

    def verify(state, _snapshot, _signal):
        ok = state.context.get('fact') == 7
        return {'success': ok, 'updates': {'answer_ready': ok}, 'provides': {'verified'}, 'evidence': ('verify:fact',)}

    registry = CognitiveOperatorRegistry([
        CognitiveOperatorSpec('retrieve.knowledge','knowledge',frozenset({'knowledge','retrieve'}),frozenset(),frozenset({'evidence'}),1.0,0.05,'state_only','1','unit://op',retrieve),
        CognitiveOperatorSpec('verify.claim','verification',frozenset({'verify'}),frozenset({'evidence'}),frozenset({'verified'}),1.0,0.02,'state_only','1','unit://op',verify),
    ])
    card = _card('knowledge-reflex', {'knowledge_gap'}, ('retrieve.knowledge','verify.claim'), context_tags={'code'}, verifier='verify.claim')
    runtime = CognitiveReflexRuntime(
        detector=CognitiveDeficitDetector(),
        registry=registry,
        library=ProcedureLibrary([card]),
        compiler=ProcedureCompiler(registry),
        router=CognitiveReflexRouter(ProcedureCreditLedger(), CounterexampleMemory()),
    )
    snapshot = _snapshot(unresolved_requirements=('fact',), evidence_coverage=0.0, candidate_verified=False, terminal_candidate=False)
    receipt = runtime.run_cycle(state, snapshot, context_tags={'code'}, context_fingerprint='ctx:test')
    assert receipt.status == 'executed'
    assert receipt.deficit_kind == 'knowledge_gap'
    assert receipt.procedure_id == 'knowledge-reflex'
    assert state.context['answer_ready'] is True
    assert 'verified' in state.capabilities
    assert receipt.verified is True


def test_reflex_runtime_fails_closed_when_no_trusted_behavioral_knowledge_exists():
    registry = CognitiveOperatorRegistry([_operator('retrieve.knowledge')])
    runtime = CognitiveReflexRuntime(
        detector=CognitiveDeficitDetector(),
        registry=registry,
        library=ProcedureLibrary([]),
        compiler=ProcedureCompiler(registry),
        router=CognitiveReflexRouter(ProcedureCreditLedger(), CounterexampleMemory()),
    )
    state = ExternalWorkingState(context={}, capabilities={'reason'})
    snapshot = _snapshot(unresolved_requirements=('missing',), evidence_coverage=0.0, terminal_candidate=False)
    receipt = runtime.run_cycle(state, snapshot, context_tags={'code'}, context_fingerprint='ctx:none')
    assert receipt.status == 'acquire_behavioral_knowledge'
    assert receipt.procedure_id is None


def test_detector_classifies_missing_capabilities_and_structured_host_observations():
    detector = CognitiveDeficitDetector()
    snapshot = _snapshot(
        missing_capabilities=frozenset({'skill:deadlock_debug', 'math:smt', 'code:taint'}),
        host_observations=(
            'causal_gap:root cause unresolved',
            'goal_ambiguous:two incompatible success criteria',
            'constraint_violation:must preserve public API',
            'routing_uncertain:no validated specialist',
            'episode_missing:similar prior failure unavailable',
        ),
        terminal_candidate=False,
        candidate_verified=False,
    )
    kinds = {signal.kind for signal in detector.detect(snapshot)}
    assert {
        'skill_gap', 'mathematical_support_gap', 'code_analysis_gap', 'causal_gap',
        'goal_ambiguity', 'constraint_violation', 'routing_uncertainty', 'episodic_gap',
    } <= kinds


def test_r253_can_wrap_the_existing_r21_cognition_time_retriever_as_an_external_operator():
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    from cogcoder.knowledge_types import KnowledgeDocument
    from cogcoder.retrieval_microcycle import CognitionTimeRetriever
    from cogcoder.r253_external_cognition import make_cognition_time_retrieval_operator, DeficitSignal

    store = InMemoryKnowledgeStore([
        KnowledgeDocument('doc-a', 'mem://a', 'Vega --stored_in--> Vault7'),
        KnowledgeDocument('doc-b', 'mem://b', 'Vault7 --located_on--> Luna'),
    ])
    retriever = CognitionTimeRetriever(store, max_calls=2, top_k=1)
    operator = make_cognition_time_retrieval_operator(retriever)
    state = ExternalWorkingState(context={'knowledge_query': 'Vega'}, capabilities={'reason'})
    snapshot = _snapshot(unresolved_requirements=('where Vega is stored',), evidence_coverage=0.0, terminal_candidate=False)
    signal = DeficitSignal('knowledge_gap', 0.9, 0.95, 'objective', ('missing fact',))
    result = dict(operator.executor(state, snapshot, signal))
    assert result['success'] is True
    assert 'evidence' in operator.provides
    assert result['provides'] == {'evidence'}
    assert any('Vega' in text for text in result['retrieved_text'])
