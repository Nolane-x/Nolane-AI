from __future__ import annotations

import hashlib
import itertools

from cogcoder.r247_executable_patch_cegis import (
    PatchMacro,
    PatchTest,
    apply_patch_macros,
    enumerate_patch_candidates,
    learn_patch_library,
    solve_patch_with_sparse_tests,
)

TRAIN_RENAMES = (('a', 'b', 'cap'), ('left', 'right', 'limit'))
HELDOUT_EPISODES = (1701, 1709, 1721, 1723, 1733, 1741)


def _fn(name, x, y, cap, body_expr, cmp='<', return_wrap=None):
    expr = body_expr.format(x=x, y=y)
    ret1 = 'total'
    ret2 = f'{cap} + 1'
    if return_wrap == 'abs':
        ret1, ret2 = f'abs({ret1})', f'abs({ret2})'
    elif return_wrap == 'neg':
        ret1, ret2 = f'-({ret1})', f'-({ret2})'
    elif return_wrap == 'max0':
        ret1, ret2 = f'max(0, {ret1})', f'max(0, {ret2})'
    return (
        f'def {name}({x}, {y}, {cap}):\n'
        f'    total = {expr}\n'
        f'    if total {cmp} {cap}:\n'
        f'        return {ret1}\n'
        f'    return {ret2}\n'
    )


def _demo_pair(kind: str, rename_index: int):
    x, y, cap = TRAIN_RENAMES[rename_index]
    name = f'train_{kind}_{rename_index}'
    before = _fn(name, x, y, cap, f'{{x}} - {{y}}')
    if kind.startswith('binop_'):
        op = {'binop_add': '+', 'binop_mult': '*', 'binop_floordiv': '//', 'binop_mod': '%'}[kind]
        after = _fn(name, x, y, cap, f'{{x}} {op} {{y}}')
    elif kind == 'operands_abs':
        before = _fn(name, x, y, cap, f'{{x}} + {{y}}')
        after = _fn(name, x, y, cap, f'abs({{x}}) + abs({{y}})')
    elif kind == 'operands_neg':
        before = _fn(name, x, y, cap, f'{{x}} + {{y}}')
        after = _fn(name, x, y, cap, f'-{{x}} + -{{y}}')
    elif kind.startswith('cmp_'):
        cmp = {'cmp_lte': '<=', 'cmp_gt': '>', 'cmp_gte': '>=', 'cmp_eq': '=='}[kind]
        after = _fn(name, x, y, cap, f'{{x}} - {{y}}', cmp=cmp)
    elif kind.startswith('return_'):
        wrapper = {'return_abs': 'abs', 'return_neg': 'neg', 'return_max0': 'max0'}[kind]
        after = _fn(name, x, y, cap, f'{{x}} - {{y}}', return_wrap=wrapper)
    else:
        raise ValueError(kind)
    return before, after


def training_demonstrations():
    kinds = (
        'binop_add', 'binop_mult', 'binop_floordiv', 'binop_mod',
        'operands_abs', 'operands_neg',
        'cmp_lte', 'cmp_gt', 'cmp_gte', 'cmp_eq',
        'return_abs', 'return_neg', 'return_max0',
    )
    return tuple(_demo_pair(kind, rename) for kind in kinds for rename in range(len(TRAIN_RENAMES)))


def learn_r247_library():
    library = learn_patch_library(training_demonstrations())
    if len(library) != 13:
        raise AssertionError(f'unexpected learned patch library size: {len(library)}')
    if any(m.support != 2 for m in library):
        raise AssertionError('each R2.47 macro must have two renamed demonstrations')
    return library


def _opaque_name(seed: int, role: str) -> str:
    return 'v_' + hashlib.sha256(f'r247|{seed}|{role}'.encode()).hexdigest()[:10]


def _episode_sources(seed: int):
    fn = 'f_' + hashlib.sha256(f'r247|{seed}|fn'.encode()).hexdigest()[:12]
    x = _opaque_name(seed, 'x')
    y = _opaque_name(seed, 'y')
    cap = _opaque_name(seed, 'cap')
    source = _fn(fn, x, y, cap, '{x} - {y}', cmp='<')
    library = learn_r247_library()
    essential = []
    for macro in library:
        if macro.slot == 'binop' and macro.src == 'Sub' and macro.dst == 'Add':
            essential.append(macro)
        elif macro.slot == 'operand_wrapper' and macro.dst == 'abs':
            essential.append(macro)
        elif macro.slot == 'compare' and macro.src == 'Lt' and macro.dst == 'LtE':
            essential.append(macro)
    if len(essential) != 3:
        raise AssertionError('essential macro lookup failed')
    target = apply_patch_macros(source, essential)
    return source, target, tuple(sorted(m.macro_id for m in essential))


def _compile_source(source: str):
    namespace = {'__builtins__': {'abs': abs, 'max': max}}
    exec(compile(source, '<r247-target>', 'exec'), namespace, namespace)
    functions = [value for key, value in namespace.items() if key.startswith('f_')]
    if len(functions) != 1:
        raise AssertionError('target compile failed')
    return functions[0]


def _tests(seed: int, target_source: str):
    target_fn = _compile_source(target_source)
    tests = []
    for i, args in enumerate(itertools.product(range(-4, 5), range(-4, 5), range(0, 9))):
        expected = target_fn(*args)
        tests.append(PatchTest(f't:{seed}:{i:03d}', tuple(map(int, args)), expected))
    return tuple(tests)


def _order(seed: int, tests):
    return tuple(sorted(
        (t.test_id for t in tests),
        key=lambda tid: hashlib.sha256(f'r247-order|{seed}|{tid}'.encode()).hexdigest(),
    ))


def run_heldout_episode(seed: int):
    if int(seed) not in HELDOUT_EPISODES:
        raise ValueError('seed outside frozen R2.47 heldout block')
    source, target_source, essential_ids = _episode_sources(seed)
    library = learn_r247_library()
    candidates = enumerate_patch_candidates(source, library)
    tests = _tests(seed, target_source)
    order = _order(seed, tests)
    initial = order[:4]
    receipt = solve_patch_with_sparse_tests(
        candidates, tests, initial_test_ids=initial, hidden_order=order, max_counterexamples=24
    )
    selected_ids = () if receipt.candidate is None else receipt.candidate.macro_ids
    return {
        'seed': int(seed),
        'exact': receipt.exact,
        'status': receipt.status,
        'learned_macros': len(library),
        'initial_candidates': receipt.initial_candidate_count,
        'final_survivors': receipt.final_survivor_count,
        'essential_macro_count': len(essential_ids),
        'selected_macro_ids': list(selected_ids),
        'essential_macro_ids': list(essential_ids),
        'selected_exact_macro_set': set(selected_ids) == set(essential_ids),
        'initial_tests': receipt.initial_tests,
        'counterexamples_revealed': receipt.counterexamples_revealed,
        'observed_tests': len(receipt.observed_test_ids),
        'feedback_fraction': receipt.feedback_fraction,
        'rounds': len(receipt.rounds),
        'candidate_test_evaluations': receipt.candidate_test_evaluations,
        'exhaustive_tests_verified': receipt.exhaustive_tests_verified,
        'test_suite_size': len(tests),
        'opaque_identifiers': all(token not in source for token in ('left', 'right', 'limit', 'train_')),
    }


def run_frozen_heldout():
    rows = [run_heldout_episode(seed) for seed in HELDOUT_EPISODES]
    summary = {
        'episodes': len(rows),
        'exact': sum(row['exact'] for row in rows),
        'false_accepts': sum(not row['exact'] for row in rows),
        'learned_macros': rows[0]['learned_macros'],
        'initial_candidates': rows[0]['initial_candidates'],
        'essential_macro_count': rows[0]['essential_macro_count'],
        'selected_exact_macro_set': sum(row['selected_exact_macro_set'] for row in rows),
        'initial_tests_per_episode': rows[0]['initial_tests'],
        'max_counterexamples_revealed': max(row['counterexamples_revealed'] for row in rows),
        'max_observed_tests': max(row['observed_tests'] for row in rows),
        'max_feedback_fraction': max(row['feedback_fraction'] for row in rows),
        'mean_feedback_fraction': sum(row['feedback_fraction'] for row in rows) / len(rows),
        'max_candidate_test_evaluations': max(row['candidate_test_evaluations'] for row in rows),
        'exhaustive_tests_per_episode': min(row['exhaustive_tests_verified'] for row in rows),
        'test_suite_size': rows[0]['test_suite_size'],
        'opaque_identifiers': all(row['opaque_identifiers'] for row in rows),
        'execution_mode': 'compiled Python AST patches + executable tests',
    }
    gates = {
        'all_exact': summary['exact'] == summary['episodes'],
        'zero_false_accepts': summary['false_accepts'] == 0,
        'learned_macro_library_has_distractors': summary['learned_macros'] >= 10,
        'multi_macro_composition_required': summary['essential_macro_count'] >= 3,
        'selected_exact_macro_set_all': summary['selected_exact_macro_set'] == summary['episodes'],
        'sparse_feedback_under_5_percent': summary['max_feedback_fraction'] <= 0.05,
        'final_exhaustive_execution': summary['exhaustive_tests_per_episode'] == summary['test_suite_size'] == 729,
        'opaque_renamed_identifiers': summary['opaque_identifiers'],
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.47 Executable Python Patch Composition CEGIS Transfer',
        'heldout_episodes': list(HELDOUT_EPISODES),
        'rows': rows,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
    }
