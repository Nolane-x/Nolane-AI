from __future__ import annotations

import ast
import hashlib
import itertools
from functools import lru_cache

from cogcoder.r247_executable_patch_cegis import PatchTest, apply_patch_macros
from cogcoder.r251_interprocedural_query import apply_interprocedural_query_macros
from cogcoder.r252_repository_query import (
    RepositoryPatchCandidate,
    RepositorySnapshot,
    apply_repository_query_macros,
    compile_repository_candidate,
    enumerate_repository_candidates,
    learn_repository_query_library,
    solve_repository_patch_with_sparse_tests,
)
from benchmarks.kfigg.r251_interprocedural_query_transfer import learn_r251_library


HELDOUT_EPISODES = (3301, 3313, 3323, 3331, 3343, 3359)
TRAINING_SEEDS = (701, 709)
EDIT_KINDS = (
    'binop_add', 'binop_mult', 'binop_floordiv', 'binop_mod',
    'operands_abs', 'operands_neg',
    'cmp_lte', 'cmp_gt', 'cmp_gte', 'cmp_eq',
)


def _canonical(source: str) -> str:
    return ast.unparse(ast.parse(source)) + '\n'


def _opaque(seed: int, role: str, index: int | None = None) -> str:
    suffix = '' if index is None else f'|{index}'
    return 'n_' + hashlib.sha256(f'r252|{seed}|{role}{suffix}'.encode()).hexdigest()[:11]


def _wrapped(value: str, wrapper: str | None) -> str:
    if wrapper is None:
        return value
    if wrapper == 'abs':
        return f'abs({value})'
    if wrapper == 'neg':
        return f'-{value}'
    raise ValueError(wrapper)


def _repository_source(
    *,
    seed: int,
    relay_count: int,
    target_op: str = '-',
    decoy_op: str = '-',
    target_wrap: str | None = None,
    target_cmp: str = '<',
    decoy_cmp: str = '<',
) -> RepositorySnapshot:
    if relay_count < 0:
        raise ValueError('relay_count must be nonnegative')

    core_mod = _opaque(seed, 'core_mod')
    mid_mod = _opaque(seed, 'mid_mod')
    entry_mod = _opaque(seed, 'entry_mod')
    relay_mods = [_opaque(seed, 'relay_mod', i) for i in range(relay_count)]

    target_fn = _opaque(seed, 'target_fn')
    decoy_fn = _opaque(seed, 'decoy_fn')
    adjust_fn = _opaque(seed, 'adjust_fn')
    noise_fn = _opaque(seed, 'noise_fn')
    entry_fn = _opaque(seed, 'entry_fn')
    relay_targets = [_opaque(seed, 'relay_target', i) for i in range(relay_count)]
    relay_decoys = [_opaque(seed, 'relay_decoy', i) for i in range(relay_count)]

    x = _opaque(seed, 'x')
    y = _opaque(seed, 'y')
    cap = _opaque(seed, 'cap')
    alt = _opaque(seed, 'alt')
    tval = _opaque(seed, 'tval')
    dval = _opaque(seed, 'dval')
    core = _opaque(seed, 'core')
    shadow = _opaque(seed, 'shadow')
    adjusted = _opaque(seed, 'adjusted')
    noisy = _opaque(seed, 'noisy')
    penalty = _opaque(seed, 'penalty')

    files: dict[str, str] = {}
    files[f'{core_mod}.py'] = _canonical(f'''
def {target_fn}({x}, {y}):
    {tval} = {x} {target_op} {y}
    return {tval}

def {decoy_fn}({x}, {y}):
    {dval} = {x} {decoy_op} {y}
    return {dval}
''')

    previous_mod = core_mod
    previous_target = target_fn
    previous_decoy = decoy_fn
    for i, relay_mod in enumerate(relay_mods):
        rx = _opaque(seed, 'rx', i)
        ry = _opaque(seed, 'ry', i)
        rt = _opaque(seed, 'rt', i)
        rd = _opaque(seed, 'rd', i)
        files[f'{relay_mod}.py'] = _canonical(f'''
from {previous_mod} import {previous_target}, {previous_decoy}

def {relay_targets[i]}({rx}, {ry}):
    {rt} = {previous_target}({rx}, {ry})
    return {rt}

def {relay_decoys[i]}({rx}, {ry}):
    {rd} = {previous_decoy}({rx}, {ry})
    return {rd}
''')
        previous_mod = relay_mod
        previous_target = relay_targets[i]
        previous_decoy = relay_decoys[i]

    files[f'{mid_mod}.py'] = _canonical(f'''
from {previous_mod} import {previous_target}, {previous_decoy}

def {adjust_fn}({x}, {y}, {alt}):
    {core} = {previous_target}({x}, {y})
    {adjusted} = {_wrapped(core, target_wrap)} + {_wrapped(alt, target_wrap)}
    return {adjusted}

def {noise_fn}({x}, {y}, {alt}):
    {shadow} = {previous_decoy}({x}, {y})
    {noisy} = {shadow} + {alt}
    return {noisy}
''')

    files[f'{entry_mod}.py'] = _canonical(f'''
from {mid_mod} import {adjust_fn}, {noise_fn}

def {entry_fn}({x}, {y}, {cap}, {alt}):
    {core} = {adjust_fn}({x}, {y}, {alt})
    {shadow} = {noise_fn}({x}, {y}, {alt})
    if {alt} {decoy_cmp} {cap}:
        {penalty} = 1
    else:
        {penalty} = 2
    if {core} {target_cmp} {cap}:
        return {core} + {penalty} + {shadow} + 11
    return {cap} + {penalty} + {shadow}
''')
    return RepositorySnapshot.from_mapping(files)


def training_demo(kind: str, rename_index: int):
    seed = TRAINING_SEEDS[rename_index]
    if kind.startswith('binop_'):
        before = _repository_source(seed=seed, relay_count=0, target_op='-', decoy_op='-')
        op = {
            'binop_add': '+', 'binop_mult': '*',
            'binop_floordiv': '//', 'binop_mod': '%',
        }[kind]
        after = _repository_source(seed=seed, relay_count=0, target_op=op, decoy_op='-')
    elif kind.startswith('operands_'):
        before = _repository_source(seed=seed, relay_count=0, target_op='+', decoy_op='+')
        wrapper = {'operands_abs': 'abs', 'operands_neg': 'neg'}[kind]
        after = _repository_source(
            seed=seed, relay_count=0, target_op='+', decoy_op='+', target_wrap=wrapper,
        )
    elif kind.startswith('cmp_'):
        before = _repository_source(seed=seed, relay_count=0, target_cmp='<', decoy_cmp='<')
        cmp_op = {'cmp_lte': '<=', 'cmp_gt': '>', 'cmp_gte': '>=', 'cmp_eq': '=='}[kind]
        after = _repository_source(
            seed=seed, relay_count=0, target_cmp=cmp_op, decoy_cmp='<',
        )
    else:
        raise ValueError(kind)
    return before, after


def grouped_training_demos():
    return {
        kind: (training_demo(kind, 0), training_demo(kind, 1))
        for kind in EDIT_KINDS
    }


@lru_cache(maxsize=1)
def learn_r252_library():
    library = learn_repository_query_library(grouped_training_demos(), max_depth=6)
    if len(library) != 10 or any(macro.support != 2 for macro in library):
        raise AssertionError((len(library), [macro.support for macro in library]))
    return library


def _essential_r252():
    essential = []
    for macro in learn_r252_library():
        base = macro.base
        if base.slot == 'binop' and base.src == 'Sub' and base.dst == 'Add':
            essential.append(macro)
        elif base.slot == 'operand_wrapper' and base.dst == 'abs':
            essential.append(macro)
        elif base.slot == 'compare' and base.src == 'Lt' and base.dst == 'LtE':
            essential.append(macro)
    if len(essential) != 3:
        raise AssertionError('essential R2.52 macro set')
    return tuple(essential)


def _episode(seed: int):
    if seed not in HELDOUT_EPISODES:
        raise ValueError(seed)
    relay_count = 2 + (HELDOUT_EPISODES.index(seed) % 2)  # alternate 5/6 files, unseen depth 4/5.
    source = _repository_source(
        seed=seed,
        relay_count=relay_count,
        target_op='-',
        decoy_op='-',
        target_cmp='<',
        decoy_cmp='<',
    )
    essential = _essential_r252()
    # Independent benchmark oracle: generate the intended repository directly,
    # rather than using R2.52 itself to manufacture the target.
    target = _repository_source(
        seed=seed,
        relay_count=relay_count,
        target_op='+',
        decoy_op='-',
        target_wrap='abs',
        target_cmp='<=',
        decoy_cmp='<',
    )
    return (
        source,
        target,
        tuple(sorted(macro.macro_id for macro in essential)),
        essential,
        relay_count + 2,
    )


def _root_callable(snapshot: RepositorySnapshot):
    candidate = RepositoryPatchCandidate('tmp', (), snapshot.files, 0, 0)
    return compile_repository_candidate(candidate)[1]


def _tests(seed: int, target: RepositorySnapshot):
    fn = _root_callable(target)
    rows = []
    for index, args in enumerate(itertools.product(range(-3, 4), range(-3, 4), range(0, 7), range(-3, 4))):
        rows.append(PatchTest(f't:{seed}:{index:04d}', tuple(args), fn(*args)))
    return tuple(rows)


def _order(seed: int, tests):
    return tuple(sorted(
        (test.test_id for test in tests),
        key=lambda test_id: hashlib.sha256(f'r252-order|{seed}|{test_id}'.encode()).hexdigest(),
    ))


def _passes_all(snapshot: RepositorySnapshot, tests) -> bool:
    try:
        fn = _root_callable(snapshot)
    except Exception:
        return False
    try:
        return all(fn(*test.args) == test.expected for test in tests)
    except Exception:
        return False


def _global_apply_baseline(source: RepositorySnapshot, essential) -> RepositorySnapshot:
    base_macros = tuple(macro.base for macro in essential)
    return RepositorySnapshot.from_mapping({
        path: apply_patch_macros(text, base_macros)
        for path, text in source.files
    })


def _r251_independent_baseline(source: RepositorySnapshot) -> RepositorySnapshot:
    essential = []
    for macro in learn_r251_library():
        base = macro.base
        if base.slot == 'binop' and base.src == 'Sub' and base.dst == 'Add':
            essential.append(macro)
        elif base.slot == 'operand_wrapper' and base.dst == 'abs':
            essential.append(macro)
        elif base.slot == 'compare' and base.src == 'Lt' and base.dst == 'LtE':
            essential.append(macro)
    files = {}
    for path, text in source.files:
        try:
            files[path] = apply_interprocedural_query_macros(text, essential, max_depth=7)
        except ValueError:
            files[path] = text
    return RepositorySnapshot.from_mapping(files)


def _changed_paths(before: RepositorySnapshot, after: RepositorySnapshot) -> tuple[str, ...]:
    left = before.as_dict(); right = after.as_dict()
    return tuple(sorted(path for path in left if left[path] != right[path]))


def run_heldout_episode(seed: int):
    source, target, essential_ids, essential, call_depth = _episode(seed)
    library = learn_r252_library()
    candidates = enumerate_repository_candidates(source, library, max_depth=6)
    tests = _tests(seed, target)
    order = _order(seed, tests)
    receipt = solve_repository_patch_with_sparse_tests(
        candidates,
        tests,
        initial_test_ids=order[:4],
        hidden_order=order,
        max_counterexamples=24,
    )
    selected_ids = () if receipt.candidate is None else receipt.candidate.macro_ids
    selected_snapshot = None if receipt.candidate is None else receipt.candidate.snapshot
    r251_baseline = _r251_independent_baseline(source)
    global_baseline = _global_apply_baseline(source, essential)
    file_count = len(source.files)
    return {
        'seed': seed,
        'file_count': file_count,
        'call_depth': call_depth,
        'exact': receipt.exact,
        'status': receipt.status,
        'learned_macros': len(library),
        'initial_candidates': receipt.initial_candidate_count,
        'selected_exact_macro_set': set(selected_ids) == set(essential_ids),
        'selected_three_file_transaction': selected_snapshot is not None and len(_changed_paths(source, selected_snapshot)) == 3,
        'r251_independent_baseline_exact': _passes_all(r251_baseline, tests),
        'global_apply_baseline_exact': _passes_all(global_baseline, tests),
        'direct_essential_patch_exact': _passes_all(target, tests),
        'direct_target_changed_files': len(_changed_paths(source, target)),
        'initial_tests': receipt.initial_tests,
        'counterexamples_revealed': receipt.counterexamples_revealed,
        'observed_tests': len(receipt.observed_test_ids),
        'feedback_fraction': receipt.feedback_fraction,
        'candidate_test_evaluations': receipt.candidate_test_evaluations,
        'exhaustive_tests_verified': receipt.exhaustive_tests_verified,
        'test_suite_size': len(tests),
        'opaque_identifiers': all('train_' not in text for _path, text in source.files),
        'query_patterns': sorted({pattern.signature for macro in library for pattern in macro.query.patterns}),
    }


def run_frozen_heldout():
    rows = [run_heldout_episode(seed) for seed in HELDOUT_EPISODES]
    summary = {
        'episodes': 6,
        'exact': sum(row['exact'] for row in rows),
        'false_accepts': sum(not row['exact'] for row in rows),
        'learned_macros': rows[0]['learned_macros'],
        'selected_exact_macro_set': sum(row['selected_exact_macro_set'] for row in rows),
        'selected_three_file_transaction': sum(row['selected_three_file_transaction'] for row in rows),
        'r251_independent_baseline_exact': sum(row['r251_independent_baseline_exact'] for row in rows),
        'global_apply_baseline_exact': sum(row['global_apply_baseline_exact'] for row in rows),
        'direct_essential_patch_exact': sum(row['direct_essential_patch_exact'] for row in rows),
        'direct_target_three_files': sum(row['direct_target_changed_files'] == 3 for row in rows),
        'initial_candidates': rows[0]['initial_candidates'],
        'initial_tests_per_episode': 4,
        'max_counterexamples_revealed': max(row['counterexamples_revealed'] for row in rows),
        'max_observed_tests': max(row['observed_tests'] for row in rows),
        'max_feedback_fraction': max(row['feedback_fraction'] for row in rows),
        'mean_feedback_fraction': sum(row['feedback_fraction'] for row in rows) / len(rows),
        'max_candidate_test_evaluations': max(row['candidate_test_evaluations'] for row in rows),
        'exhaustive_tests_per_episode': min(row['exhaustive_tests_verified'] for row in rows),
        'test_suite_size': rows[0]['test_suite_size'],
        'opaque_identifiers': all(row['opaque_identifiers'] for row in rows),
        'min_file_count': min(row['file_count'] for row in rows),
        'max_file_count': max(row['file_count'] for row in rows),
        'min_call_depth': min(row['call_depth'] for row in rows),
        'max_call_depth': max(row['call_depth'] for row in rows),
        'learned_query_patterns': len(rows[0]['query_patterns']),
        'execution_mode': 'repository import-aware FLOW* query induction + atomic multi-file transactional patches + sparse executable CEGIS',
    }
    gates = {
        'all_exact': summary['exact'] == 6,
        'zero_false_accepts': summary['false_accepts'] == 0,
        'learned_distractor_library': summary['learned_macros'] == 10,
        'selected_exact_all': summary['selected_exact_macro_set'] == 6,
        'three_file_transaction_all': summary['selected_three_file_transaction'] == 6,
        'direct_target_three_files': summary['direct_target_three_files'] == 6,
        'r251_independent_baseline_fails_all': summary['r251_independent_baseline_exact'] == 0,
        'global_baseline_fails_all': summary['global_apply_baseline_exact'] == 0,
        'direct_patch_exact': summary['direct_essential_patch_exact'] == 6,
        'unseen_repository_scale': summary['min_file_count'] >= 5 and summary['min_call_depth'] >= 4,
        'sparse_feedback_under_0_3_percent': summary['max_feedback_fraction'] <= 0.003,
        'final_exhaustive_execution': summary['exhaustive_tests_per_episode'] == 2401,
        'opaque_identifiers': summary['opaque_identifiers'],
        'query_induction_present': summary['learned_query_patterns'] >= 1,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.52 Repository Multi-File Query Induction',
        'heldout_episodes': list(HELDOUT_EPISODES),
        'rows': rows,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
    }
