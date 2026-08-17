import pytest

from cogcoder.r252_repository_query import RepositorySnapshot, build_repository_fact_graph


def _three_file_repo():
    return RepositorySnapshot.from_mapping({
        'entry.py': '''from bridge import bridge\n\ndef entry(a, b, cap):\n    value = bridge(a, b)\n    if value < cap:\n        return value + 1\n    return cap\n''',
        'bridge.py': '''from core import target\n\ndef bridge(a, b):\n    value = target(a, b)\n    return value\n''',
        'core.py': '''def target(a, b):\n    value = a - b\n    return value\n''',
    })


def test_repository_graph_resolves_cross_file_import_call_flow():
    graph = build_repository_fact_graph(_three_file_repo())
    relations = {edge.relation for edge in graph.edges}
    assert {'MODULE_CONTAINS', 'IMPORTS_SYMBOL', 'CALL_TARGET', 'ARG_BIND', 'FLOW', 'FLOW*'} <= relations
    assert len(graph.modules) == 3
    assert len(graph.functions) == 3
    cross_file_calls = [
        edge for edge in graph.edges
        if edge.relation == 'CALL_TARGET'
        and graph.node_modules.get(edge.src) != graph.node_modules.get(edge.dst)
    ]
    assert len(cross_file_calls) >= 2


def test_repository_snapshot_rejects_ambiguous_module_names():
    with pytest.raises(ValueError):
        RepositorySnapshot.from_mapping({'a.py': 'def f():\n    return 1\n', 'a/__init__.py': 'def g():\n    return 2\n'})


def _query_demo(prefix: str, *, target_op: str = '-', decoy_op: str = '-'):
    return RepositorySnapshot.from_mapping({
        f'{prefix}_entry.py': f'''from {prefix}_bridge import {prefix}_bridge\nfrom {prefix}_noise import {prefix}_noise\n\ndef {prefix}_entry(a, b, cap):\n    core = {prefix}_bridge(a, b)\n    shadow = {prefix}_noise(a, b)\n    if core < cap:\n        return core + shadow + 11\n    return cap + shadow\n''',
        f'{prefix}_bridge.py': f'''from {prefix}_core import {prefix}_target\n\ndef {prefix}_bridge(a, b):\n    value = {prefix}_target(a, b)\n    return value\n''',
        f'{prefix}_core.py': f'''def {prefix}_target(a, b):\n    value = a {target_op} b\n    return value\n''',
        f'{prefix}_noise.py': f'''def {prefix}_noise(a, b):\n    value = a {decoy_op} b\n    return value\n''',
    })


def test_learns_identifier_invariant_query_across_repository_imports_and_patches_only_target():
    from cogcoder.r252_repository_query import learn_repository_query_macro, apply_repository_query_macros

    demos = (
        (_query_demo('alpha', target_op='-'), _query_demo('alpha', target_op='+')),
        (_query_demo('beta', target_op='-'), _query_demo('beta', target_op='+')),
    )
    macro = learn_repository_query_macro(demos, max_depth=8)
    assert macro.support == 2
    assert macro.query.patterns
    assert all('alpha' not in p.signature and 'beta' not in p.signature for p in macro.query.patterns)

    before = _query_demo('gamma', target_op='-', decoy_op='-')
    patched = apply_repository_query_macros(before, (macro,), max_depth=8)
    files = patched.as_dict()
    assert 'a + b' in files['gamma_core.py']
    assert 'a - b' in files['gamma_noise.py']


def test_compiles_repository_in_import_dag_order_and_finds_unique_root():
    from cogcoder.r252_repository_query import RepositoryPatchCandidate, compile_repository_candidate

    repo = _three_file_repo()
    candidate = RepositoryPatchCandidate('tmp', (), repo.files, 0, 0)
    root, fn = compile_repository_candidate(candidate)
    assert root == 'entry::entry'
    assert fn(5, 2, 4) == 4
    assert fn(8, 2, 4) == 4


def test_repository_compiler_rejects_import_cycles():
    from cogcoder.r252_repository_query import RepositoryPatchCandidate, compile_repository_candidate

    repo = RepositorySnapshot.from_mapping({
        'a.py': 'from b import fb\n\ndef fa(x):\n    return fb(x)\n',
        'b.py': 'from a import fa\n\ndef fb(x):\n    return fa(x)\n',
    })
    with pytest.raises(ValueError, match='cycle'):
        compile_repository_candidate(RepositoryPatchCandidate('cycle', (), repo.files, 0, 0))
