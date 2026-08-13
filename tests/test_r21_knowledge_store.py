from __future__ import annotations

import dataclasses

import pytest


def _docs():
    from cogcoder.knowledge_types import KnowledgeDocument
    return [
        KnowledgeDocument('d1','mem://d1','The Zephyr engine uses a cobalt lattice for phase stabilization.', version='7', trust_score=0.95),
        KnowledgeDocument('d2','mem://d2','A cobalt-lattice stabilizer prevents phase drift inside Zephyr engines.', version='2', trust_score=0.9),
        KnowledgeDocument('d3','mem://d3','Orchid farms use violet lamps and hydroponic trays.', version='1', trust_score=0.8),
    ]


def test_hybrid_store_is_deterministic_and_provenance_bound():
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    store=InMemoryKnowledgeStore(_docs(), chunk_chars=220)
    a=store.search('Zephyr phase stabilizer', k=3)
    b=store.search('Zephyr phase stabilizer', k=3)
    assert [x.chunk_id for x in a] == [x.chunk_id for x in b]
    assert a[0].source_uri.startswith('mem://')
    assert len(a[0].content_sha256) == 64
    assert a[0].version in {'7','2'}
    assert 0.0 <= a[0].score <= 1.0
    assert dataclasses.is_dataclass(a[0])


def test_hybrid_store_recovers_lexical_and_character_semantic_matches():
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    store=InMemoryKnowledgeStore(_docs(), chunk_chars=220)
    exact=store.search('cobalt lattice Zephyr', k=1)[0]
    fuzzy=store.search('cobalt-lattic stabilisation Zephyr', k=2)
    assert exact.document_id in {'d1','d2'}
    assert any(x.document_id in {'d1','d2'} for x in fuzzy)


def test_composite_store_deduplicates_identical_content():
    from cogcoder.knowledge_store import CompositeKnowledgeStore, InMemoryKnowledgeStore
    from cogcoder.knowledge_types import KnowledgeDocument
    doc=KnowledgeDocument('a','mem://a','Delta relay connects Port Kappa to Moon Iris.', version='1')
    s1=InMemoryKnowledgeStore([doc])
    s2=InMemoryKnowledgeStore([KnowledgeDocument('b','mem://b','Delta relay connects Port Kappa to Moon Iris.', version='9')])
    out=CompositeKnowledgeStore([s1,s2]).search('Delta relay Kappa',k=5)
    assert len({x.content_sha256 for x in out}) == len(out)
    assert len(out) == 1


def test_empty_query_fails_closed_and_store_has_no_trainable_state():
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    store=InMemoryKnowledgeStore(_docs())
    with pytest.raises(ValueError):
        store.search('   ', k=3)
    assert store.trainable_parameter_count == 0

def test_callback_source_can_bridge_live_host_search_with_provenance():
    from cogcoder.knowledge_adapters import CallbackKnowledgeSource
    from cogcoder.knowledge_types import KnowledgeDocument
    calls=[]
    def search_fn(query,k):
        calls.append((query,k))
        return [KnowledgeDocument('live1','https://example.test/live1','Nova relay frequency is 17.4 MHz.',version='2026-08-13',trust_score=.92)]
    source=CallbackKnowledgeSource(search_fn)
    out=source.search('Nova relay frequency',k=1)
    assert calls==[('Nova relay frequency',1)]
    assert out[0].source_uri=='https://example.test/live1'
    assert len(out[0].content_sha256)==64
    assert source.trainable_parameter_count==0
