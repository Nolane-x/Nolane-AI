from __future__ import annotations

import ast
import hashlib
import itertools
from functools import lru_cache

from cogcoder.r247_executable_patch_cegis import PatchTest, apply_patch_macros
from cogcoder.r250_relational_query import enumerate_query_patch_candidates
from cogcoder.r251_interprocedural_query import (
    apply_interprocedural_query_macros,
    compile_interprocedural_candidate,
    enumerate_interprocedural_candidates,
    learn_interprocedural_query_library,
    solve_interprocedural_patch_with_sparse_tests,
)
from cogcoder.r247_executable_patch_cegis import PatchCandidate

HELDOUT_EPISODES = (2203, 2213, 2221, 2237, 2243, 2251)
TRAINING_RENAMES = (
    ('left', 'right', 'cap', 'other'),
    ('alpha', 'beta', 'limit', 'alternate'),
)
EDIT_KINDS = (
    'binop_add', 'binop_mult', 'binop_floordiv', 'binop_mod',
    'operands_abs', 'operands_neg',
    'cmp_lte', 'cmp_gt', 'cmp_gte', 'cmp_eq',
)


def _canonical(source: str) -> str:
    return ast.unparse(ast.parse(source)) + '\n'


def _opaque(seed: int, role: str, index: int | None = None) -> str:
    suffix = '' if index is None else f'|{index}'
    return 'n_' + hashlib.sha256(f'r251|{seed}|{role}{suffix}'.encode()).hexdigest()[:11]


def _wrapped(value: str, wrapper: str | None) -> str:
    if wrapper is None: return value
    if wrapper == 'abs': return f'abs({value})'
    if wrapper == 'neg': return f'-{value}'
    raise ValueError(wrapper)


def _module_source(
    names: tuple[str, str, str, str], *, seed: int, call_depth: int,
    target_op: str = '-', decoy_op: str = '-', target_wrap: str | None = None,
    target_cmp: str = '<', decoy_cmp: str = '<', opaque_functions: bool = False,
) -> str:
    if call_depth < 1: raise ValueError('call_depth must be >=1')
    x, y, cap, alt = names
    if opaque_functions:
        target_fn = _opaque(seed, 'target_fn'); decoy_fn = _opaque(seed, 'decoy_fn'); entry_fn = _opaque(seed, 'entry_fn')
        bridge_names = [_opaque(seed, 'bridge', i) for i in range(call_depth)]
        tval = _opaque(seed, 'tval'); dval = _opaque(seed, 'dval'); core = _opaque(seed, 'core'); shadow = _opaque(seed, 'shadow'); penalty = _opaque(seed, 'penalty')
    else:
        target_fn = f'train_target_{seed}'; decoy_fn = f'train_decoy_{seed}'; entry_fn = f'train_entry_{seed}'
        bridge_names = [f'train_bridge_{seed}_{i}' for i in range(call_depth)]
        tval='target_value'; dval='decoy_value'; core='core_value'; shadow='shadow_value'; penalty='penalty_value'

    lines = [
        f'def {target_fn}({x}, {y}):',
        f'    {tval} = {_wrapped(x, target_wrap)} {target_op} {_wrapped(y, target_wrap)}',
        f'    return {tval}',
        '',
        f'def {decoy_fn}({x}, {y}):',
        f'    {dval} = {x} {decoy_op} {y}',
        f'    return {dval}',
        '',
    ]
    previous = target_fn
    for i, bridge in enumerate(bridge_names):
        bx = _opaque(seed, 'bx', i) if opaque_functions else f'bx_{i}'
        by = _opaque(seed, 'by', i) if opaque_functions else f'by_{i}'
        out = _opaque(seed, 'bout', i) if opaque_functions else f'bout_{i}'
        lines += [
            f'def {bridge}({bx}, {by}):',
            f'    {out} = {previous}({bx}, {by})',
            f'    return {out}',
            '',
        ]
        previous = bridge
    lines += [
        f'def {entry_fn}({x}, {y}, {cap}, {alt}):',
        f'    {core} = {previous}({x}, {y})',
        f'    {shadow} = {decoy_fn}({x}, {y})',
        f'    if {alt} {decoy_cmp} {cap}:',
        f'        {penalty} = 1',
        '    else:',
        f'        {penalty} = 2',
        f'    if {core} {target_cmp} {cap}:',
        f'        return {core} + {penalty} + {shadow} + 11',
        f'    return {cap} + {penalty} + {shadow}',
    ]
    return _canonical('\n'.join(lines) + '\n')


def training_demo(kind: str, rename_index: int, *, call_depth: int) -> tuple[str, str]:
    names = TRAINING_RENAMES[rename_index]
    seed = 500 + rename_index + call_depth * 10
    if kind.startswith('binop_'):
        before = _module_source(names, seed=seed, call_depth=call_depth, target_op='-', decoy_op='-')
        op = {'binop_add': '+', 'binop_mult': '*', 'binop_floordiv': '//', 'binop_mod': '%'}[kind]
        after = _module_source(names, seed=seed, call_depth=call_depth, target_op=op, decoy_op='-')
    elif kind.startswith('operands_'):
        before = _module_source(names, seed=seed, call_depth=call_depth, target_op='+', decoy_op='+')
        wrapper = {'operands_abs': 'abs', 'operands_neg': 'neg'}[kind]
        after = _module_source(names, seed=seed, call_depth=call_depth, target_op='+', decoy_op='+', target_wrap=wrapper)
    elif kind.startswith('cmp_'):
        before = _module_source(names, seed=seed, call_depth=call_depth, target_cmp='<', decoy_cmp='<')
        cmp_op = {'cmp_lte': '<=', 'cmp_gt': '>', 'cmp_gte': '>=', 'cmp_eq': '=='}[kind]
        after = _module_source(names, seed=seed, call_depth=call_depth, target_cmp=cmp_op, decoy_cmp='<')
    else:
        raise ValueError(kind)
    return before, after


def grouped_training_demos():
    return {kind: (training_demo(kind, 0, call_depth=1), training_demo(kind, 1, call_depth=2)) for kind in EDIT_KINDS}


@lru_cache(maxsize=1)
def learn_r251_library():
    library = learn_interprocedural_query_library(grouped_training_demos(), max_depth=7)
    if len(library) != 10 or any(m.support != 2 for m in library):
        raise AssertionError((len(library), [m.support for m in library]))
    return library


def _episode(seed: int):
    if seed not in HELDOUT_EPISODES: raise ValueError(seed)
    names = tuple(_opaque(seed, role) for role in ('x','y','cap','alt'))
    depth = 3 + (seed % 3)  # unseen 3..5 call depth; FLOW* makes depth irrelevant.
    source = _module_source(names, seed=seed, call_depth=depth, target_op='-', decoy_op='-', target_cmp='<', decoy_cmp='<', opaque_functions=True)
    library = learn_r251_library(); essential = []
    for macro in library:
        b = macro.base
        if b.slot == 'binop' and b.src == 'Sub' and b.dst == 'Add': essential.append(macro)
        elif b.slot == 'operand_wrapper' and b.dst == 'abs': essential.append(macro)
        elif b.slot == 'compare' and b.src == 'Lt' and b.dst == 'LtE': essential.append(macro)
    if len(essential) != 3: raise AssertionError('essential macro set')
    target = apply_interprocedural_query_macros(source, essential, max_depth=7)
    return source, target, tuple(sorted(m.macro_id for m in essential)), tuple(essential), depth


def _root_callable(source: str):
    candidate = PatchCandidate('tmp', (), source, 0, 0)
    return compile_interprocedural_candidate(candidate)[1]


def _tests(seed: int, target: str):
    fn = _root_callable(target); out=[]
    for i, args in enumerate(itertools.product(range(-3,4), range(-3,4), range(0,7), range(-3,4))):
        out.append(PatchTest(f't:{seed}:{i:04d}', tuple(args), fn(*args)))
    return tuple(out)


def _order(seed, tests):
    return tuple(sorted((t.test_id for t in tests), key=lambda tid: hashlib.sha256(f'r251-order|{seed}|{tid}'.encode()).hexdigest()))


def _passes_all(source, tests):
    try: fn = _root_callable(source)
    except Exception: return False
    try: return all(fn(*t.args) == t.expected for t in tests)
    except Exception: return False


def run_heldout_episode(seed: int):
    source, target, essential_ids, essential, depth = _episode(seed)
    library = learn_r251_library(); candidates = enumerate_interprocedural_candidates(source, library, max_depth=7)
    tests = _tests(seed, target); order = _order(seed, tests)
    receipt = solve_interprocedural_patch_with_sparse_tests(candidates, tests, initial_test_ids=order[:4], hidden_order=order, max_counterexamples=24)
    selected = () if receipt.candidate is None else receipt.candidate.macro_ids

    # R2.50 rejects the multi-function source by construction.
    r250_scope_rejected = False
    try:
        enumerate_query_patch_candidates(source, ())
    except ValueError:
        r250_scope_rejected = True

    base_macros = tuple(m.base for m in essential)
    global_source = apply_patch_macros(source, base_macros)
    return {
        'seed': seed, 'call_depth': depth, 'exact': receipt.exact, 'status': receipt.status,
        'learned_macros': len(library), 'initial_candidates': receipt.initial_candidate_count,
        'selected_exact_macro_set': set(selected) == set(essential_ids),
        'r250_scope_rejected': r250_scope_rejected,
        'global_apply_baseline_exact': _passes_all(global_source, tests),
        'direct_essential_patch_exact': _passes_all(target, tests),
        'initial_tests': receipt.initial_tests, 'counterexamples_revealed': receipt.counterexamples_revealed,
        'observed_tests': len(receipt.observed_test_ids), 'feedback_fraction': receipt.feedback_fraction,
        'candidate_test_evaluations': receipt.candidate_test_evaluations,
        'exhaustive_tests_verified': receipt.exhaustive_tests_verified, 'test_suite_size': len(tests),
        'opaque_identifiers': 'train_' not in source and all(name not in source for name in ('left','right','limit','target_value','core_value')),
        'query_patterns': sorted({p.signature for m in library for p in m.query.patterns}),
    }


def run_frozen_heldout():
    rows = [run_heldout_episode(seed) for seed in HELDOUT_EPISODES]
    summary = {
        'episodes': 6, 'exact': sum(r['exact'] for r in rows), 'false_accepts': sum(not r['exact'] for r in rows),
        'learned_macros': rows[0]['learned_macros'], 'selected_exact_macro_set': sum(r['selected_exact_macro_set'] for r in rows),
        'r250_scope_rejected_episodes': sum(r['r250_scope_rejected'] for r in rows),
        'global_apply_baseline_exact': sum(r['global_apply_baseline_exact'] for r in rows),
        'direct_essential_patch_exact': sum(r['direct_essential_patch_exact'] for r in rows),
        'initial_candidates': rows[0]['initial_candidates'], 'initial_tests_per_episode': 4,
        'max_counterexamples_revealed': max(r['counterexamples_revealed'] for r in rows),
        'max_observed_tests': max(r['observed_tests'] for r in rows),
        'max_feedback_fraction': max(r['feedback_fraction'] for r in rows),
        'mean_feedback_fraction': sum(r['feedback_fraction'] for r in rows)/6,
        'max_candidate_test_evaluations': max(r['candidate_test_evaluations'] for r in rows),
        'exhaustive_tests_per_episode': min(r['exhaustive_tests_verified'] for r in rows),
        'test_suite_size': rows[0]['test_suite_size'], 'opaque_identifiers': all(r['opaque_identifiers'] for r in rows),
        'min_call_depth': min(r['call_depth'] for r in rows), 'max_call_depth': max(r['call_depth'] for r in rows),
        'learned_query_patterns': len(rows[0]['query_patterns']),
        'execution_mode': 'interprocedural FLOW* query induction + multi-function transactional compiled Python patches + sparse executable CEGIS',
    }
    gates = {
        'all_exact': summary['exact'] == 6, 'zero_false_accepts': summary['false_accepts'] == 0,
        'learned_distractor_library': summary['learned_macros'] == 10, 'selected_exact_all': summary['selected_exact_macro_set'] == 6,
        'r250_single_function_baseline_rejected': summary['r250_scope_rejected_episodes'] == 6,
        'global_baseline_fails_all': summary['global_apply_baseline_exact'] == 0,
        'direct_patch_exact': summary['direct_essential_patch_exact'] == 6,
        'unseen_call_depths': summary['min_call_depth'] >= 3 and summary['max_call_depth'] >= 4,
        'sparse_feedback_under_1_percent': summary['max_feedback_fraction'] <= 0.01,
        'final_exhaustive_execution': summary['exhaustive_tests_per_episode'] == 2401,
        'opaque_identifiers': summary['opaque_identifiers'], 'query_induction_present': summary['learned_query_patterns'] >= 1,
    }
    return {'schema_version':1, 'milestone':'R2.51 Interprocedural Call-Flow Query Induction', 'heldout_episodes': list(HELDOUT_EPISODES), 'rows': rows, 'summary': summary, 'gates': gates, 'all_gates_pass': all(gates.values())}
