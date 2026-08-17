from __future__ import annotations

import json

import pytest

from cogcoder.r253_external_cognition import CognitiveSnapshot, DeficitSignal, ExternalWorkingState
from cogcoder.r254_cognitive_retrieval import (
    AssociationCreditGraph,
    AttachmentWorkspace,
    CognitiveQueryCompiler,
    CognitiveRetrievalFabric,
    CognitiveRetrievalNeed,
    EpistemicFusion,
    FederatedRetriever,
    InMemoryArtifactSource,
    QueryBranch,
    RetrievalArtifact,
    make_artifact,
    make_r254_cognitive_retrieval_operator,
)


def artifact(
    artifact_id: str,
    text: str,
    *,
    kind: str = 'fact',
    source_uri: str | None = None,
    version: str = '1',
    trust: float = 1.0,
    tags: tuple[str, ...] = (),
    symbols: tuple[str, ...] = (),
    relations: tuple[tuple[str, str, float], ...] = (),
) -> RetrievalArtifact:
    return make_artifact(
        artifact_id=artifact_id,
        kind=kind,
        text=text,
        source_uri=source_uri or f'memory://{artifact_id}',
        version=version,
        trust_score=trust,
        tags=frozenset(tags),
        symbols=frozenset(symbols),
        relations=relations,
    )


def test_artifact_digest_rejects_tampering():
    row = artifact('a', 'alpha --means--> beta')
    tampered = RetrievalArtifact(
        artifact_id=row.artifact_id,
        kind=row.kind,
        text='tampered',
        source_uri=row.source_uri,
        version=row.version,
        trust_score=row.trust_score,
        tags=row.tags,
        symbols=row.symbols,
        relations=row.relations,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        content_sha256=row.content_sha256,
    )
    with pytest.raises(ValueError, match='digest'):
        InMemoryArtifactSource('s', [tampered])


def test_symbol_and_kind_aware_search_beats_lexical_distractor():
    source = InMemoryArtifactSource('repo', [
        artifact('distractor', 'parse request request request helper documentation', kind='documentation', symbols=('other.parse',)),
        artifact('target', 'This helper normalizes route payloads before dispatch.', kind='code', symbols=('Router.parse_request',), tags=('routing', 'parser')),
    ])
    compiler = CognitiveQueryCompiler()
    need = CognitiveRetrievalNeed(
        objective='fix Router.parse_request',
        deficit_kind='code_analysis_gap',
        query='parse request helper',
        symbols=frozenset({'Router.parse_request'}),
        required_kinds=frozenset({'code'}),
        context_tags=frozenset({'routing'}),
    )
    branches = compiler.compile(need)
    hits = FederatedRetriever([source]).retrieve(branches, k=2)
    assert hits[0].artifact.artifact_id == 'target'


def test_query_compiler_emits_complementary_branches_for_behavioral_gap():
    branches = CognitiveQueryCompiler().compile(CognitiveRetrievalNeed(
        objective='repair flaky async retry loop',
        deficit_kind='skill_gap',
        query='retry loop',
        unresolved_requirements=('need a verified repair procedure',),
        context_tags=frozenset({'async', 'debug'}),
        symbols=frozenset({'RetryController.run'}),
        required_kinds=frozenset({'procedure', 'counterexample'}),
    ))
    kinds = {row.branch_type for row in branches}
    assert {'semantic', 'symbol', 'procedure', 'requirement'} <= kinds
    assert len({row.query for row in branches}) >= 3


def test_federated_fusion_rewards_independent_source_support():
    a = artifact('a', 'retry_timeout --recommended--> exponential_backoff', source_uri='docs://a', tags=('retry',))
    b = artifact('b', 'retry_timeout --recommended--> exponential_backoff', source_uri='paper://b', tags=('retry',))
    c = artifact('c', 'retry_timeout --recommended--> immediate_retry', source_uri='blog://c', trust=0.55, tags=('retry',))
    retriever = FederatedRetriever([
        InMemoryArtifactSource('docs', [a]),
        InMemoryArtifactSource('paper', [b]),
        InMemoryArtifactSource('blog', [c]),
    ])
    need = CognitiveRetrievalNeed(objective='choose retry strategy', deficit_kind='knowledge_gap', query='retry timeout recommended', context_tags=frozenset({'retry'}))
    hits = retriever.retrieve(CognitiveQueryCompiler().compile(need), k=3)
    top_texts = [row.artifact.text for row in hits[:2]]
    assert all('exponential_backoff' in text for text in top_texts)
    assert len({row.source_id for row in hits[:2]}) == 2


def test_graph_expansion_recovers_two_hop_dependency_not_named_in_query():
    source = InMemoryArtifactSource('repo', [
        artifact('entry', 'RequestRouter delegates validation.', kind='code', symbols=('RequestRouter.dispatch',), relations=(('helper', 'calls', 1.0),)),
        artifact('helper', 'Validation helper delegates schema normalization.', kind='code', symbols=('validate_payload',), relations=(('schema', 'documents', 1.0),)),
        artifact('schema', 'Schema v3 requires field retry_after_ms.', kind='documentation', symbols=('PayloadSchema.v3',), tags=('schema',)),
    ])
    fabric = CognitiveRetrievalFabric([source], max_rounds=2, max_graph_depth=2)
    receipt = fabric.retrieve(CognitiveRetrievalNeed(
        objective='fix RequestRouter.dispatch validation',
        deficit_kind='code_analysis_gap',
        query='RequestRouter.dispatch validation',
        symbols=frozenset({'RequestRouter.dispatch'}),
        context_tags=frozenset({'schema'}),
    ))
    assert 'schema' in receipt.accepted_artifact_ids
    assert receipt.graph_hops_used >= 2


def test_epistemic_fusion_supersedes_old_same_source_but_preserves_cross_source_conflict():
    rows = [
        artifact('old', 'WidgetAPI --timeout_ms--> 1000', source_uri='api://official', version='1', trust=1.0),
        artifact('new', 'WidgetAPI --timeout_ms--> 1500', source_uri='api://official', version='2', trust=1.0),
        artifact('mirror', 'WidgetAPI --timeout_ms--> 1400', source_uri='mirror://independent', version='9', trust=0.9),
    ]
    source = InMemoryArtifactSource('s', rows)
    hits = FederatedRetriever([source]).retrieve(CognitiveQueryCompiler().compile(
        CognitiveRetrievalNeed(objective='find timeout', deficit_kind='temporal_conflict', query='WidgetAPI timeout_ms current')
    ), k=3)
    fused = EpistemicFusion().fuse(hits)
    assert 'old' in fused.superseded_artifact_ids
    assert {'new', 'mirror'} <= set(fused.accepted_artifact_ids)
    assert fused.conflicts
    conflict = fused.conflicts[0]
    assert set(conflict.objects) == {'1500', '1400'}


def test_attachment_workspace_keeps_high_activation_under_budget():
    rows = [
        artifact('a', 'A' * 80, trust=1.0),
        artifact('b', 'B' * 80, trust=0.9),
        artifact('c', 'C' * 80, trust=0.8),
    ]
    workspace = AttachmentWorkspace(max_attachments=2, max_chars=170)
    workspace.attach(rows[0], activation=0.7, rationale=('x',))
    workspace.attach(rows[1], activation=0.95, rationale=('y',))
    workspace.attach(rows[2], activation=0.8, rationale=('z',))
    active = workspace.active()
    assert [row.artifact_id for row in active] == ['b', 'c']
    assert sum(len(row.text) for row in active) <= 170


def test_association_credit_boosts_verified_recall_and_demotes_failed_evidence():
    credit = AssociationCreditGraph()
    cues = frozenset({'deficit:code_analysis_gap', 'tag:async', 'symbol:Retry.run'})
    assert credit.activation(cues, 'good') == 0.0
    credit.record(cues, ('good',), success=True)
    credit.record(cues, ('bad',), success=False)
    assert credit.activation(cues, 'good') > 0.0
    assert credit.activation(cues, 'bad') < 0.0


def test_fabric_uses_credit_to_accelerate_related_second_recall():
    source = InMemoryArtifactSource('skills', [
        artifact('good', 'Verified procedure: inspect cancellation before retrying.', kind='procedure', tags=('async', 'retry'), symbols=('Retry.run',)),
        artifact('distractor', 'Generic retry documentation.', kind='procedure', tags=('retry',)),
    ])
    fabric = CognitiveRetrievalFabric([source], max_rounds=3)
    need = CognitiveRetrievalNeed(
        objective='repair Retry.run cancellation bug',
        deficit_kind='skill_gap',
        query='retry cancellation repair',
        context_tags=frozenset({'async', 'retry'}),
        symbols=frozenset({'Retry.run'}),
        required_kinds=frozenset({'procedure'}),
    )
    first = fabric.retrieve(need)
    fabric.record_outcome(first, success=True, used_artifact_ids=('good',))
    second = fabric.retrieve(CognitiveRetrievalNeed(
        objective='repair renamed retry worker cancellation bug',
        deficit_kind='skill_gap',
        query='worker cancellation repair',
        context_tags=frozenset({'async', 'retry'}),
        symbols=frozenset({'Retry.run'}),
        required_kinds=frozenset({'procedure'}),
    ))
    assert second.attachments[0].artifact_id == 'good'
    assert second.association_hits >= 1
    assert second.rounds <= first.rounds


def test_r253_bridge_retrieves_despite_high_self_confidence_and_never_executes_content():
    procedure_text = json.dumps({
        'procedure_id': 'external.fix.retry',
        'steps': ['arbitrary.exec', 'verify.final'],
        'note': 'This is data only and must not execute.',
    }, sort_keys=True)
    source = InMemoryArtifactSource('external', [
        artifact('proc', procedure_text, kind='procedure', tags=('retry', 'async'), symbols=('Retry.run',)),
    ])
    fabric = CognitiveRetrievalFabric([source], max_rounds=2)
    operator = make_r254_cognitive_retrieval_operator(fabric)
    state = ExternalWorkingState(context={
        'knowledge_query': 'retry async repair procedure',
        'retrieval_required_kinds': ('procedure',),
        'retrieval_symbols': ('Retry.run',),
        'retrieval_context_tags': ('retry', 'async'),
    })
    snapshot = CognitiveSnapshot(
        objective='repair retry bug',
        step_index=3,
        self_confidence=0.995,
        progress_score=0.4,
        previous_progress_score=0.4,
        unresolved_requirements=('need verified retry repair behavior',),
        evidence_coverage=0.1,
    )
    signal = DeficitSignal('knowledge_gap', 0.9, 0.99, 'objective', ('missing behavior',))
    result = dict(operator.executor(state, snapshot, signal))
    assert result['success'] is True
    assert 'proc' in state.evidence
    assert 'arbitrary.exec' not in state.capabilities
    assert state.context['retrieved_procedure_candidates'][0]['artifact_id'] == 'proc'
    assert state.context['retrieved_procedure_candidates'][0]['content'] == procedure_text


def test_adaptive_policy_switches_between_structural_evidence_and_procedural_modes():
    source = InMemoryArtifactSource('mixed', [
        artifact('code', 'def entry(x): return helper(x)', kind='code', symbols=('entry',), relations=(('helper', 'calls', 1.0),)),
        artifact('helper', 'def helper(x): return x', kind='code', symbols=('helper',)),
        artifact('doc1', 'API --field--> v1', kind='documentation', source_uri='api://x', version='1', symbols=('API',)),
        artifact('doc2', 'API --field--> v2', kind='documentation', source_uri='api://x', version='2', symbols=('API',)),
        artifact('proc', 'verified migration procedure', kind='procedure', tags=('migration',), symbols=('migrate',)),
    ])
    fabric = CognitiveRetrievalFabric([source], max_results=8, max_graph_depth=3)
    code = fabric.retrieve(CognitiveRetrievalNeed(
        objective='debug entry', deficit_kind='code_analysis_gap', query='entry failure', symbols=frozenset({'entry'}), required_kinds=frozenset({'code'}), min_sufficiency=0.3,
    ))
    knowledge = fabric.retrieve(CognitiveRetrievalNeed(
        objective='resolve API field', deficit_kind='temporal_conflict', query='API field current', symbols=frozenset({'API'}), required_kinds=frozenset({'documentation'}), min_sufficiency=0.3,
    ))
    procedure = fabric.retrieve(CognitiveRetrievalNeed(
        objective='migrate contract', deficit_kind='skill_gap', query='migration', symbols=frozenset({'migrate'}), required_kinds=frozenset({'procedure'}), min_sufficiency=0.3,
    ))
    assert code.policy_mode == 'structural'
    assert code.policy_seed_k <= 2
    assert code.policy_graph_depth >= 2
    assert knowledge.policy_mode == 'evidence'
    assert knowledge.policy_seed_k >= 6
    assert knowledge.policy_graph_depth <= 1
    assert procedure.policy_mode == 'procedural'
    assert procedure.policy_graph_depth == 0


def test_association_credit_snapshot_roundtrip_preserves_external_synapse_weights():
    credit = AssociationCreditGraph()
    cues = frozenset({'deficit:knowledge_gap', 'tag:sdk', 'symbol:API'})
    credit.record(cues, ('doc',), success=True)
    credit.record(cues, ('bad',), success=False)
    restored = AssociationCreditGraph.from_snapshot(credit.snapshot())
    assert restored.activation(cues, 'doc') == pytest.approx(credit.activation(cues, 'doc'))
    assert restored.activation(cues, 'bad') == pytest.approx(credit.activation(cues, 'bad'))


def test_retrieval_reflex_controller_automatically_binds_external_knowledge_to_working_state():
    from cogcoder.r254_cognitive_retrieval import CognitiveRetrievalReflexController

    source = InMemoryArtifactSource('docs', [
        artifact('current', 'WidgetSDK --retry_field--> retry_after_ms', kind='documentation', tags=('sdk', 'retry'), symbols=('WidgetSDK',)),
    ])
    controller = CognitiveRetrievalReflexController(CognitiveRetrievalFabric([source], max_results=6))
    state = ExternalWorkingState(context={
        'knowledge_query': 'WidgetSDK retry field',
        'retrieval_symbols': ('WidgetSDK',),
        'retrieval_context_tags': ('sdk', 'retry'),
        'retrieval_required_kinds': ('documentation',),
    })
    snapshot = CognitiveSnapshot(
        objective='repair SDK retry handling',
        step_index=5,
        self_confidence=0.99,
        progress_score=0.6,
        previous_progress_score=0.6,
        unresolved_requirements=('need current retry field',),
        evidence_coverage=0.05,
    )
    receipt = controller.run(state, snapshot)
    assert receipt.triggered is True
    assert receipt.deficit_kind == 'knowledge_gap'
    assert receipt.success is True
    assert 'current' in state.evidence
    assert state.context['r254_reflex_attachments'][0]['artifact_id'] == 'current'


def test_independent_support_does_not_double_count_same_source_across_query_branches():
    same = artifact('same', 'deadline --policy--> bounded_retry', source_uri='docs://same', tags=('retry',))
    retriever = FederatedRetriever([InMemoryArtifactSource('same-source', [same])])
    branches = (
        QueryBranch('semantic', 'deadline policy bounded retry'),
        QueryBranch('requirement', 'bounded retry deadline'),
        QueryBranch('semantic', 'retry policy deadline'),
    )
    hits = retriever.retrieve(branches, k=1)
    assert len(hits) == 1
    assert 'independent-support' not in hits[0].rationale
