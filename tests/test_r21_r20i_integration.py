from __future__ import annotations
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WEIGHT=ROOT/'checkpoints/Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt'

def _models():
    from cogcoder.r20i_standalone import load_r20i_standalone
    return load_r20i_standalone(WEIGHT)[:3]

def test_no_source_runtime_is_exact_r20i_fallback():
    from cogcoder.r18_benchmark import make_r18_task
    from cogcoder.r20i_causal_discovery import run_r20i_episode
    from cogcoder.r21_runtime import R21Runtime
    p,r,e=_models(); runtime=R21Runtime(p,r,e)
    for family,index in [('conditional_regimes',2300),('causal_prerequisites',2301)]:
        direct=run_r20i_episode(p,r,e,make_r18_task(family,'train',index),mode='hybrid_active_causal')
        wrapped=runtime.run_episode(make_r18_task(family,'train',index),mode='hybrid_active_causal')
        assert wrapped['actions']==direct['actions']
        assert wrapped['solved']==direct['solved']
        assert wrapped['steps']==direct['steps']

def test_runtime_exposes_zero_parameter_cognition_time_retrieval():
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    from cogcoder.knowledge_types import KnowledgeDocument
    from cogcoder.r21_runtime import R21Runtime
    p,r,e=_models(); source=InMemoryKnowledgeStore([KnowledgeDocument('k','mem://k','Iris --located_on--> Europa')])
    runtime=R21Runtime(p,r,e,knowledge_source=source)
    decision=runtime.retrieve(query='Iris location',uncertainty=.9,query_drift=1.0)
    assert decision.retrieved
    assert runtime.new_neural_parameters==0
    hook=runtime.generation_hook(max_calls=2,top_k=1)
    assert hook.before_step(step_index=0,visible_text='Where is Iris?',uncertainty=.9).retrieved
