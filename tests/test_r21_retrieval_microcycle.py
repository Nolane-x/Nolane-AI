from __future__ import annotations

def store():
    from cogcoder.knowledge_types import KnowledgeDocument
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    return InMemoryKnowledgeStore([
      KnowledgeDocument('a','mem://a','Vega --stored_in--> Vault7'),
      KnowledgeDocument('b','mem://b','Vault7 --located_on--> Luna'),
      KnowledgeDocument('c','mem://c','Luna --orbits--> Orpheus'),
      KnowledgeDocument('d','mem://d','Orchid --color--> Violet'),
    ])

def test_uncertainty_and_query_drift_trigger_retrieval_but_high_confidence_stable_state_does_not():
    from cogcoder.retrieval_microcycle import CognitionTimeRetriever, KnowledgeNeed
    r=CognitionTimeRetriever(store(),max_calls=4,top_k=1)
    a=r.step(KnowledgeNeed('Vega storage',uncertainty=.9,query_drift=1.0))
    assert a.retrieved and a.call_index==1
    b=r.step(KnowledgeNeed('Vega storage',uncertainty=.05,query_drift=0.0))
    assert not b.retrieved and b.reason=='stable_confident'

def test_anchor_based_requery_discovers_next_hop():
    from cogcoder.retrieval_microcycle import CognitionTimeRetriever, KnowledgeNeed
    r=CognitionTimeRetriever(store(),max_calls=4,top_k=1)
    first=r.step(KnowledgeNeed('Vega',uncertainty=.9,query_drift=1.0))
    assert 'Vault7' in r.state.anchors
    second=r.step(KnowledgeNeed('Where is the container?',uncertainty=.9,query_drift=1.0,use_anchors=True))
    assert any('Vault7' in c.text and 'Luna' in c.text for c in second.chunks)

def test_budget_and_novelty_stop_retrieval_deterministically():
    from cogcoder.retrieval_microcycle import CognitionTimeRetriever, KnowledgeNeed
    r=CognitionTimeRetriever(store(),max_calls=2,top_k=1)
    r.step(KnowledgeNeed('Vega',uncertainty=1,query_drift=1))
    r.step(KnowledgeNeed('Vault7',uncertainty=1,query_drift=1))
    out=r.step(KnowledgeNeed('Luna',uncertainty=1,query_drift=1))
    assert not out.retrieved and out.reason=='call_budget_exhausted'
    assert r.state.calls==2

def test_generic_prose_anchor_adapter_is_separate_from_locked_core():
    from cogcoder.knowledge_adapters import extract_generic_query_anchors
    anchors=extract_generic_query_anchors('The Aster Observatory is operated by Mira Venn.')
    assert 'Aster' in anchors and 'Mira' in anchors and 'Venn' in anchors
