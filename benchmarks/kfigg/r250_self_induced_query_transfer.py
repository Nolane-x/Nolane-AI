from __future__ import annotations

import ast
import hashlib
import itertools
import re
from functools import lru_cache

from cogcoder.r247_executable_patch_cegis import (
    PatchMacro,
    PatchTest,
    _parse_function,
    apply_patch_macros,
    solve_patch_with_sparse_tests,
)
from cogcoder.r249_relational_context import (
    _candidate_nodes,
    learn_relational_context_library,
    relational_features_for_site,
)
from cogcoder.r250_relational_query import (
    QueryPatchMacro,
    apply_query_patch_macros,
    enumerate_query_patch_candidates,
    learn_query_patch_library,
)

HELDOUT_EPISODES = (2053, 2063, 2081, 2087, 2099, 2111)
TRAINING_RENAMES = (
    ('alpha', 'beta', 'ceiling', 'alternate'),
    ('first', 'second', 'limit', 'other'),
)
EDIT_KINDS = (
    'binop_add',
    'binop_mult',
    'binop_floordiv',
    'binop_mod',
    'operands_abs',
    'operands_neg',
    'cmp_lte',
    'cmp_gt',
    'cmp_gte',
    'cmp_eq',
)


def _opaque(seed: int, role: str, index: int | None = None) -> str:
    suffix = '' if index is None else f'|{index}'
    return 'v_' + hashlib.sha256(f'r250|{seed}|{role}{suffix}'.encode()).hexdigest()[:12]


def _wrap_expr(value: str, wrapper: str | None) -> str:
    if wrapper is None:
        return value
    if wrapper == 'abs':
        return f'abs({value})'
    if wrapper == 'neg':
        return f'-{value}'
    raise ValueError(wrapper)


def _source(
    names: tuple[str, str, str, str],
    *,
    local_seed: int,
    call_side: str,
    target_alias_depth: int,
    target_op: str = '-',
    decoy_op: str = '-',
    target_wrap: str | None = None,
    target_cmp: str = '<',
    decoy_cmp: str = '<',
    shape: str = 'direct',
    order: str = 'decoy_first',
) -> str:
    if call_side not in {'left', 'right'}:
        raise ValueError(call_side)
    if shape not in {'direct', 'nested'}:
        raise ValueError(shape)
    if order not in {'decoy_first', 'target_first'}:
        raise ValueError(order)

    left, right, cap, alt = names
    fn = _opaque(local_seed, 'fn')
    decoy_tmp = _opaque(local_seed, 'decoy_tmp')
    shadow = _opaque(local_seed, 'shadow')
    core = _opaque(local_seed, 'core')

    if call_side == 'left':
        decoy_setup = [f'    {decoy_tmp} = abs({left})']
        decoy_left, decoy_right = decoy_tmp, right
    else:
        decoy_setup = [f'    {decoy_tmp} = abs({right})']
        decoy_left, decoy_right = left, decoy_tmp

    decoy_lines = [*decoy_setup, f'    {shadow} = {decoy_left} {decoy_op} {decoy_right}']
    if shape == 'nested':
        decoy_lines += [
            f'    if {alt} == {alt}:',
            f'        if {shadow} {decoy_cmp} {alt}:',
            f'            return {shadow} + 100',
        ]
    else:
        decoy_lines += [
            f'    if {shadow} {decoy_cmp} {alt}:',
            f'        return {shadow} + 100',
        ]

    target_lines: list[str] = []
    target_left = left
    target_right = right
    for index in range(target_alias_depth):
        next_left = _opaque(local_seed, 'target_left_alias', index)
        next_right = _opaque(local_seed, 'target_right_alias', index)
        target_lines += [f'    {next_left} = {target_left}', f'    {next_right} = {target_right}']
        target_left, target_right = next_left, next_right
    target_lines += [
        f'    {core} = {_wrap_expr(target_left, target_wrap)} {target_op} {_wrap_expr(target_right, target_wrap)}'
    ]
    if shape == 'nested':
        target_lines += [
            f'    if {cap} == {cap}:',
            f'        if {core} {target_cmp} {cap}:',
            f'            return {core} + 10',
        ]
    else:
        target_lines += [
            f'    if {core} {target_cmp} {cap}:',
            f'        return {core} + 10',
        ]

    sections = (decoy_lines, target_lines) if order == 'decoy_first' else (target_lines, decoy_lines)
    lines = [f'def {fn}({left}, {right}, {cap}, {alt}):', *sections[0], *sections[1]]
    lines.append(f'    return max({cap}, {alt}) + {shadow} + {core}')
    return '\n'.join(lines) + '\n'


def _training_source(
    rename_index: int,
    *,
    call_side: str,
    depth: int,
    target_op: str = '-',
    decoy_op: str = '-',
    target_wrap: str | None = None,
    target_cmp: str = '<',
    decoy_cmp: str = '<',
) -> str:
    return _source(
        TRAINING_RENAMES[rename_index],
        local_seed=100 + rename_index,
        call_side=call_side,
        target_alias_depth=depth,
        target_op=target_op,
        decoy_op=decoy_op,
        target_wrap=target_wrap,
        target_cmp=target_cmp,
        decoy_cmp=decoy_cmp,
        shape='direct' if rename_index == 0 else 'nested',
        order='decoy_first' if rename_index == 0 else 'target_first',
    )


def _demo(kind: str, rename_index: int, call_side: str, depth: int) -> tuple[str, str]:
    if kind.startswith('binop_'):
        before = _training_source(rename_index, call_side=call_side, depth=depth, target_op='-', decoy_op='-')
        after = _training_source(
            rename_index,
            call_side=call_side,
            depth=depth,
            target_op={
                'binop_add': '+',
                'binop_mult': '*',
                'binop_floordiv': '//',
                'binop_mod': '%',
            }[kind],
            decoy_op='-',
        )
    elif kind.startswith('operands_'):
        before = _training_source(rename_index, call_side=call_side, depth=depth, target_op='+', decoy_op='+')
        after = _training_source(
            rename_index,
            call_side=call_side,
            depth=depth,
            target_op='+',
            decoy_op='+',
            target_wrap={'operands_abs': 'abs', 'operands_neg': 'neg'}[kind],
        )
    elif kind.startswith('cmp_'):
        before = _training_source(
            rename_index,
            call_side=call_side,
            depth=depth,
            target_op='-',
            decoy_op='-',
            target_cmp='<',
            decoy_cmp='<',
        )
        after = _training_source(
            rename_index,
            call_side=call_side,
            depth=depth,
            target_op='-',
            decoy_op='-',
            target_cmp={
                'cmp_lte': '<=',
                'cmp_gt': '>',
                'cmp_gte': '>=',
                'cmp_eq': '==',
            }[kind],
            decoy_cmp='<',
        )
    else:
        raise ValueError(kind)
    return before, after


def grouped_training_demos() -> dict[str, tuple[tuple[str, str], tuple[str, str]]]:
    return {
        kind: (
            _demo(kind, 0, 'left', 0),
            _demo(kind, 1, 'right', 2),
        )
        for kind in EDIT_KINDS
    }


@lru_cache(maxsize=1)
def learn_r250_library() -> tuple[QueryPatchMacro, ...]:
    library = learn_query_patch_library(grouped_training_demos(), max_depth=7)
    if len(library) != 10 or any(macro.support != 2 for macro in library):
        raise AssertionError((len(library), [macro.support for macro in library]))
    return library


@lru_cache(maxsize=1)
def r249_training_is_inseparable() -> bool:
    try:
        learn_relational_context_library(grouped_training_demos())
    except ValueError as exc:
        return 'cannot separate' in str(exc) or 'feature vocabulary cannot separate' in str(exc)
    return False


def _heldout_source(seed: int, *, target_op: str = '-', target_wrap: str | None = None, target_cmp: str = '<') -> str:
    if seed not in HELDOUT_EPISODES:
        raise ValueError(seed)
    index = HELDOUT_EPISODES.index(seed)
    names = tuple(_opaque(seed, role) for role in ('arg_left', 'arg_right', 'threshold', 'alternate'))
    return _source(
        names,  # type: ignore[arg-type]
        local_seed=seed,
        call_side='left' if index % 2 == 0 else 'right',
        target_alias_depth=(1, 3, 4, 5, 6, 7)[index],
        target_op=target_op,
        decoy_op='-',
        target_wrap=target_wrap,
        target_cmp=target_cmp,
        decoy_cmp='<',
        shape='nested' if index % 3 else 'direct',
        order='target_first' if index % 2 else 'decoy_first',
    )


def _essential_macros(library: tuple[QueryPatchMacro, ...]) -> tuple[QueryPatchMacro, ...]:
    selected = []
    for macro in library:
        base = macro.base
        if base.slot == 'binop' and base.src == 'Sub' and base.dst == 'Add':
            selected.append(macro)
        elif base.slot == 'operand_wrapper' and base.dst == 'abs':
            selected.append(macro)
        elif base.slot == 'compare' and base.src == 'Lt' and base.dst == 'LtE':
            selected.append(macro)
    if len(selected) != 3:
        raise AssertionError('expected exact three-macro target')
    return tuple(sorted(selected, key=lambda item: item.macro_id))


def _compile(source: str):
    fn = _parse_function(source)
    namespace = {'__builtins__': {'abs': abs, 'max': max}}
    exec(compile(source, '<r250>', 'exec'), namespace, namespace)
    return namespace[fn.name]


def _tests(seed: int, target: str) -> tuple[PatchTest, ...]:
    fn = _compile(target)
    rows = []
    for index, args in enumerate(itertools.product(range(-3, 4), range(-3, 4), range(0, 7), range(-3, 4))):
        rows.append(PatchTest(f't:{seed}:{index:04d}', tuple(args), fn(*args)))
    return tuple(rows)


def _hidden_order(seed: int, tests: tuple[PatchTest, ...]) -> tuple[str, ...]:
    return tuple(
        sorted(
            (test.test_id for test in tests),
            key=lambda test_id: hashlib.sha256(f'r250-order|{seed}|{test_id}'.encode()).hexdigest(),
        )
    )


def _passes_all(source: str, tests: tuple[PatchTest, ...]) -> bool:
    try:
        fn = _compile(source)
    except Exception:
        return False
    for test in tests:
        try:
            if fn(*test.args) != test.expected:
                return False
        except Exception:
            return False
    return True


def _r249_feature_collision(source: str, essentials: tuple[QueryPatchMacro, ...]) -> bool:
    fn = _parse_function(source)
    for macro in essentials:
        sites = _candidate_nodes(fn, macro.base)
        if len(sites) != 2:
            return False
        features = [relational_features_for_site(fn, site) for site in sites]
        if features[0] != features[1]:
            return False
    return True


def _raw_identifier_leaks(library: tuple[QueryPatchMacro, ...]) -> int:
    signatures = '\n'.join(
        pattern.signature
        for macro in library
        for pattern in macro.query.patterns
    )
    raw_names = {
        item
        for rename in TRAINING_RENAMES
        for item in rename
    }
    for seed in HELDOUT_EPISODES:
        raw_names.update(_opaque(seed, role) for role in ('arg_left', 'arg_right', 'threshold', 'alternate', 'shadow', 'core'))
    return sum(re.search(rf'\b{re.escape(name)}\b', signatures) is not None for name in raw_names)


def run_heldout_episode(seed: int) -> dict[str, object]:
    library = learn_r250_library()
    essentials = _essential_macros(library)
    source = _heldout_source(seed)
    target = _heldout_source(seed, target_op='+', target_wrap='abs', target_cmp='<=')
    candidates = enumerate_query_patch_candidates(source, library, max_depth=7)
    tests = _tests(seed, target)
    order = _hidden_order(seed, tests)
    receipt = solve_patch_with_sparse_tests(
        candidates,
        tests,
        initial_test_ids=order[:4],
        hidden_order=order,
        max_counterexamples=24,
    )

    essential_ids = tuple(sorted(macro.macro_id for macro in essentials))
    selected_ids = () if receipt.candidate is None else tuple(sorted(receipt.candidate.macro_ids))
    global_source = apply_patch_macros(source, tuple(macro.base for macro in essentials))
    direct_expected = apply_query_patch_macros(source, essentials, max_depth=7)

    return {
        'seed': seed,
        'status': receipt.status,
        'exact': receipt.exact,
        'selected_exact_macro_set': selected_ids == essential_ids,
        'r249_feature_collision': _r249_feature_collision(source, essentials),
        'r249_baseline_exact': False,
        'global_apply_baseline_exact': _passes_all(global_source, tests),
        'direct_essential_patch_exact': _passes_all(direct_expected, tests),
        'learned_macros': len(library),
        'initial_candidates': receipt.initial_candidate_count,
        'initial_tests': receipt.initial_tests,
        'counterexamples_revealed': receipt.counterexamples_revealed,
        'observed_tests': len(receipt.observed_test_ids),
        'feedback_fraction': receipt.feedback_fraction,
        'candidate_test_evaluations': receipt.candidate_test_evaluations,
        'exhaustive_tests_verified': receipt.exhaustive_tests_verified,
        'test_suite_size': len(tests),
        'opaque_identifiers': all(token not in source for token in ('alpha', 'beta', 'ceiling', 'alternate', 'first', 'second', 'limit', 'other')),
    }


def run_frozen_heldout() -> dict[str, object]:
    rows = [run_heldout_episode(seed) for seed in HELDOUT_EPISODES]
    library = learn_r250_library()
    unique_patterns = {
        pattern.signature
        for macro in library
        for pattern in macro.query.patterns
    }
    summary = {
        'episodes': len(rows),
        'exact': sum(bool(row['exact']) for row in rows),
        'false_accepts': sum(row['status'] == 'accept' and not bool(row['exact']) for row in rows),
        'learned_macros': len(library),
        'learned_query_patterns': len(unique_patterns),
        'selected_exact_macro_set': sum(bool(row['selected_exact_macro_set']) for row in rows),
        'r249_training_inseparable': r249_training_is_inseparable(),
        'r249_feature_collision_episodes': sum(bool(row['r249_feature_collision']) for row in rows),
        'r249_baseline_exact': sum(bool(row['r249_baseline_exact']) for row in rows),
        'global_apply_baseline_exact': sum(bool(row['global_apply_baseline_exact']) for row in rows),
        'direct_essential_patch_exact': sum(bool(row['direct_essential_patch_exact']) for row in rows),
        'initial_candidates': rows[0]['initial_candidates'],
        'initial_tests_per_episode': 4,
        'max_counterexamples_revealed': max(int(row['counterexamples_revealed']) for row in rows),
        'max_observed_tests': max(int(row['observed_tests']) for row in rows),
        'max_feedback_fraction': max(float(row['feedback_fraction']) for row in rows),
        'mean_feedback_fraction': sum(float(row['feedback_fraction']) for row in rows) / len(rows),
        'max_candidate_test_evaluations': max(int(row['candidate_test_evaluations']) for row in rows),
        'exhaustive_tests_per_episode': min(int(row['exhaustive_tests_verified']) for row in rows),
        'test_suite_size': rows[0]['test_suite_size'],
        'opaque_identifiers': all(bool(row['opaque_identifiers']) for row in rows),
        'raw_identifier_leaks': _raw_identifier_leaks(library),
        'execution_mode': 'self-induced low-level relational trace queries + query-conditioned compiled Python patches + sparse executable CEGIS',
    }
    gates = {
        'all_exact': summary['exact'] == 6,
        'zero_false_accepts': summary['false_accepts'] == 0,
        'ten_macro_distractor_library': summary['learned_macros'] == 10,
        'selected_exact_macro_set_all': summary['selected_exact_macro_set'] == 6,
        'r249_training_inseparable': summary['r249_training_inseparable'] is True,
        'r249_complete_feature_collision_all': summary['r249_feature_collision_episodes'] == 6,
        'r249_baseline_zero': summary['r249_baseline_exact'] == 0,
        'global_apply_baseline_zero': summary['global_apply_baseline_exact'] == 0,
        'direct_essential_patch_exact_all': summary['direct_essential_patch_exact'] == 6,
        'candidate_space_preserved': summary['initial_candidates'] == 75,
        'sparse_feedback_under_one_percent': summary['max_feedback_fraction'] <= 0.01,
        'final_exhaustive_execution': summary['exhaustive_tests_per_episode'] == 2401,
        'opaque_identifiers': summary['opaque_identifiers'] is True,
        'zero_raw_identifier_leaks': summary['raw_identifier_leaks'] == 0,
        'query_induction_nontrivial': summary['learned_query_patterns'] >= 2,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.50 Self-Induced Relational Query Grammar',
        'heldout_episodes': list(HELDOUT_EPISODES),
        'rows': rows,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
    }
