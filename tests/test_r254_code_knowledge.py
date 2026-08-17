from __future__ import annotations

from cogcoder.r254_cognitive_retrieval import (
    CallbackArtifactSource,
    CognitiveQueryCompiler,
    CognitiveRetrievalFabric,
    CognitiveRetrievalNeed,
    FederatedRetriever,
    InMemoryArtifactSource,
    make_artifact,
)
from cogcoder.r254_code_knowledge import PythonRepositoryIndexer


def test_python_repository_indexer_builds_call_graph_and_symbol_artifacts():
    files = {
        'app/router.py': '''
class Router:
    def handle(self, payload):
        cleaned = self._normalize(payload)
        return validate(cleaned)

    def _normalize(self, payload):
        return {k: v for k, v in payload.items() if v is not None}
''',
        'app/schema.py': '''
def validate(payload):
    if "retry_after_ms" not in payload:
        raise ValueError("missing retry_after_ms")
    return payload
''',
    }
    source = PythonRepositoryIndexer().build_source('repo', files)
    compiler = CognitiveQueryCompiler()
    hits = FederatedRetriever([source]).retrieve(compiler.compile(CognitiveRetrievalNeed(
        objective='debug Router.handle',
        deficit_kind='code_analysis_gap',
        query='Router.handle payload failure',
        symbols=frozenset({'Router.handle'}),
        context_tags=frozenset({'python'}),
        required_kinds=frozenset({'code'}),
    )), k=4)
    assert hits[0].artifact.kind == 'code'
    assert 'Router.handle' in hits[0].artifact.symbols
    handle = hits[0].artifact
    targets = {(row.relation, row.target_id) for row in handle.relations}
    assert any(relation == 'calls' and '_normalize' in target for relation, target in targets)
    assert any(relation == 'calls' and 'validate' in target for relation, target in targets)


def test_python_repository_indexer_enables_graph_recall_of_unmentioned_callee():
    files = {
        'pkg/service.py': '''
def entry(data):
    return hidden_normalize(data)

def hidden_normalize(data):
    return schema_check(data)
''',
        'pkg/schema.py': '''
def schema_check(data):
    return data["required_key"]
''',
    }
    source = PythonRepositoryIndexer().build_source('repo', files)
    fabric = CognitiveRetrievalFabric([source], max_results=1, max_graph_depth=2)
    receipt = fabric.retrieve(CognitiveRetrievalNeed(
        objective='debug entry KeyError',
        deficit_kind='code_analysis_gap',
        query='entry KeyError',
        symbols=frozenset({'entry'}),
        required_kinds=frozenset({'code'}),
        min_sufficiency=0.45,
    ))
    texts = '\n'.join(row.text for row in receipt.attachments)
    assert 'schema_check' in texts
    assert 'required_key' in texts
    assert receipt.graph_hops_used >= 2


def test_callback_source_admits_fresh_external_artifacts_and_caches_them_for_graph_use():
    calls = []

    def fetch(branch, k):
        calls.append((branch.branch_type, branch.query, k))
        if 'SDK' not in branch.query:
            return []
        return [
            make_artifact(
                artifact_id='remote-sdk-v7',
                kind='documentation',
                text='SDK --current_retry_field--> retry_after_ms',
                source_uri='https://docs.example/sdk/v7',
                version='7',
                trust_score=0.98,
                tags=frozenset({'sdk', 'retry'}),
                symbols=frozenset({'SDK'}),
            )
        ]

    source = CallbackArtifactSource('web-docs', fetch)
    fabric = CognitiveRetrievalFabric([source], max_rounds=2)
    receipt = fabric.retrieve(CognitiveRetrievalNeed(
        objective='adapt to SDK',
        deficit_kind='knowledge_gap',
        query='SDK retry field',
        symbols=frozenset({'SDK'}),
        required_kinds=frozenset({'documentation'}),
        min_sufficiency=0.4,
    ))
    assert calls
    assert 'remote-sdk-v7' in receipt.accepted_artifact_ids
    assert source.get('remote-sdk-v7') is not None


def test_external_provider_timeout_is_isolated_and_recorded_while_other_sources_continue():
    from cogcoder.r254_cognitive_retrieval import CognitiveRetrievalFabric, CognitiveRetrievalNeed

    def offline(_branch, _k):
        raise TimeoutError('provider unavailable')

    good = make_artifact(
        artifact_id='local.answer', kind='documentation', text='WidgetAPI --method--> safe_call',
        source_uri='docs://local', version='1', trust_score=0.9, tags=frozenset({'widget'}),
        symbols=frozenset({'WidgetAPI'}),
    )
    external = CallbackArtifactSource('external-offline', offline)
    local = InMemoryArtifactSource('local', [good])
    receipt = CognitiveRetrievalFabric((external, local), max_rounds=1).retrieve(CognitiveRetrievalNeed(
        objective='resolve WidgetAPI method', deficit_kind='knowledge_gap', query='WidgetAPI method',
        symbols=frozenset({'WidgetAPI'}), required_kinds=frozenset({'documentation'}), min_sufficiency=0.2,
    ))
    assert 'local.answer' in receipt.accepted_artifact_ids
    assert receipt.sufficient is True
    assert receipt.source_failures == ('external-offline:TimeoutError:provider unavailable',)


def test_repository_indexer_tracks_function_references_passed_as_values_across_files():
    files = {
        'pkg/main.py': '''
def wrapper(items):
    return partial(helper, items)
''',
        'pkg/helpers.py': '''
def helper(items):
    return list(items)
''',
    }
    artifacts = PythonRepositoryIndexer().build_artifacts(files)
    wrapper = next(row for row in artifacts if row.artifact_id == 'code:pkg/main.py:wrapper')
    edges = {(row.target_id, row.relation) for row in wrapper.relations}
    assert ('code:pkg/helpers.py:helper', 'references') in edges
