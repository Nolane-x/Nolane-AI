from __future__ import annotations

def test_hook_can_retrieve_between_generation_steps():
    from cogcoder.generation_retrieval import GenerationRetrievalHook
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    from cogcoder.knowledge_types import KnowledgeDocument
    store=InMemoryKnowledgeStore([KnowledgeDocument('x','mem://x','Aster --discovered_by--> Mira')])
    hook=GenerationRetrievalHook.from_source(store,max_calls=2,top_k=1)
    before=hook.before_step(step_index=0,visible_text='Who discovered Aster?',uncertainty=.9)
    assert before.retrieved
    hook.after_step(step_index=0,emitted_text='Mira',uncertainty=.1)
    second=hook.before_step(step_index=1,visible_text='Who discovered Aster? Mira',uncertainty=.05)
    assert not second.retrieved
    assert hook.events[0].phase=='before_step' and hook.events[1].phase=='after_step'
