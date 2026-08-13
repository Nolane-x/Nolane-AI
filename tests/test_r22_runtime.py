from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHT = ROOT / 'checkpoints/Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt'


def _models():
    from cogcoder.r20i_standalone import load_r20i_standalone
    return load_r20i_standalone(WEIGHT)[:3]


def test_r22_without_knowledge_is_exact_r20i_fallback():
    from cogcoder.r18_benchmark import make_r18_task
    from cogcoder.r20i_causal_discovery import run_r20i_episode
    from cogcoder.r22_runtime import R22Runtime
    p, r, e = _models()
    runtime = R22Runtime(p, r, e)
    for family, index in [('conditional_regimes', 2310), ('causal_prerequisites', 2311)]:
        direct = run_r20i_episode(p, r, e, make_r18_task(family, 'train', index), mode='hybrid_active_causal')
        wrapped = runtime.run_episode(make_r18_task(family, 'train', index), mode='hybrid_active_causal')
        assert wrapped['actions'] == direct['actions']
        assert wrapped['solved'] == direct['solved']


def test_retrieval_updates_epistemic_workspace_and_resolves_newer_version():
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    from cogcoder.knowledge_types import KnowledgeDocument
    from cogcoder.r22_runtime import R22Runtime
    p, r, e = _models()
    source = InMemoryKnowledgeStore([
        KnowledgeDocument('old', 'mem://route', 'alpha --next--> old', version='1', trust_score=.99),
        KnowledgeDocument('new', 'mem://route', 'alpha --next--> new', version='2', trust_score=.80),
    ], chunk_chars=128)
    runtime = R22Runtime(p, r, e, knowledge_source=source, top_k=2)
    decision = runtime.retrieve(query='alpha next', uncertainty=1.0, query_drift=1.0, force=True)
    assert decision.retrieved
    assert runtime.belief('alpha', 'next').object == 'new'
    assert runtime.new_neural_parameters == 0


def test_runtime_compiles_and_executes_retrieved_program():
    from cogcoder.knowledge_store import InMemoryKnowledgeStore
    from cogcoder.knowledge_types import KnowledgeDocument
    from cogcoder.r22_runtime import R22Runtime
    p, r, e = _models()
    source = InMemoryKnowledgeStore([
        KnowledgeDocument('p', 'mem://program', 'PROGRAM transform :: ADD 4 | MUL 3 | MOD 17', version='5', trust_score=.95)
    ], chunk_chars=160)
    runtime = R22Runtime(p, r, e, knowledge_source=source, top_k=1)
    runtime.retrieve(query='PROGRAM transform', uncertainty=1.0, query_drift=1.0, force=True)
    names = runtime.compile_retrieved_programs()
    assert names == ('transform',)
    assert runtime.execute_program('transform', 2) == 1
