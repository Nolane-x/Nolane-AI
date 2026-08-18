from __future__ import annotations

import itertools
from collections.abc import Callable

from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import repository_content_digest
from cogcoder.r261_version_space_expansion import (
    expand_repository_candidates,
    solve_repository_patch_with_version_space_expansion,
)
from cogcoder.r263_compositional_version_space_expansion import solve_repository_patch_with_compositional_expansion


def _candidate(candidate_id: str, files: dict[str, str], *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _files(*, left_op: str, right_op: str) -> dict[str, str]:
    if left_op not in {'+', '-'} or right_op not in {'+', '-'}:
        raise ValueError('unsupported operator')
    return {
        'left.py': f'def left(x, y):\n    return x {left_op} y\n',
        'right.py': f'def right(a, b):\n    return a {right_op} b\n',
        'main.py': (
            'from left import left\n'
            'from right import right\n\n'
            'def compute(x, y, a, b):\n'
            '    return left(x, y) + right(a, b)\n'
        ),
    }


def _macro() -> PatchMacro:
    return PatchMacro('pm:r263:add-to-sub', 'binop', 'replace', 'Add', 'Sub', support=4)


def _refinement_inputs() -> tuple[RepositoryProbe, ...]:
    return (
        RepositoryProbe((5, 2, 3, 0)),
        RepositoryProbe((3, 0, 5, 2)),
    )


def _final_inputs() -> tuple[RepositoryProbe, ...]:
    rows = itertools.product(
        (-11, -4, 7, 13),
        (-6, -3, 2, 5),
        (-17, -2, 8, 19),
        (-7, -1, 3, 6),
    )
    return tuple(RepositoryProbe(tuple(row)) for row in rows)


def _normalize_scalar(value: object) -> object:
    item = getattr(value, 'item', None)
    if callable(item):
        try:
            value = item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return value


def _counted_binary(target: Callable[[object, object], object]):
    calls = {'count': 0}

    def wrapped(x: object, y: object) -> object:
        calls['count'] += 1
        return _normalize_scalar(target(x, y))

    return wrapped, calls


def _composed_oracle(subtract: Callable[[object, object], object]):
    def oracle(x: object, y: object, a: object, b: object) -> object:
        return _normalize_scalar(subtract(x, y)) + _normalize_scalar(subtract(a, b))
    return oracle


def run_external_subtract_transfer(
    subtract_callable: Callable[[object, object], object],
    *,
    source_id: str,
    source_version: str,
) -> dict[str, object]:
    if not callable(subtract_callable):
        raise TypeError('subtract_callable must be callable')
    if not source_id or not source_version:
        raise ValueError('source_id and source_version must be non-empty')

    source = _candidate('r263:subtract:source', _files(left_op='+', right_op='+'))
    target = _candidate('r263:subtract:target-evaluation-only', _files(left_op='-', right_op='-'), edits=2)
    target_digest = repository_content_digest(target)
    initial_digests = {repository_content_digest(source)}
    one_step = expand_repository_candidates(
        (source,), (_macro(),), max_generated_candidates=16, max_sites_per_macro=16,
    )
    one_step_digests = {repository_content_digest(row.candidate) for row in one_step}

    refinement = _refinement_inputs()
    final = _final_inputs()

    label_subtract, initial_counter = _counted_binary(subtract_callable)
    label_oracle = _composed_oracle(label_subtract)
    initial_args = (3, 0, 3, 0)
    initial_tests = (
        PatchTest('r263:subtract:initial', initial_args, label_oracle(*initial_args)),
    )
    # The composed oracle performs two binary external calls per repository query.
    # Report both repository-query counts and raw external callable invocations.
    initial_repository_queries = 1
    initial_raw_external_calls = int(initial_counter['count'])

    r261_subtract, r261_raw_counter = _counted_binary(subtract_callable)
    r261_oracle = _composed_oracle(r261_subtract)
    r261 = solve_repository_patch_with_version_space_expansion(
        (source,),
        initial_tests,
        refinement,
        r261_oracle,
        verification_inputs=(*refinement, *final),
        expansion_seeds=(source,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=16,
        max_sites_per_macro=16,
    )

    r263_subtract, r263_raw_counter = _counted_binary(subtract_callable)
    r263_oracle = _composed_oracle(r263_subtract)
    r263 = solve_repository_patch_with_compositional_expansion(
        (source,),
        initial_tests,
        refinement,
        r263_oracle,
        refinement_inputs=refinement,
        verification_inputs=final,
        expansion_seeds=(source,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=2,
        max_expansion_rounds=2,
        max_composition_depth=2,
        max_generated_candidates_per_round=16,
        max_sites_per_macro=16,
    )

    accepted_digest = r263.accepted_content_digest
    exact = bool(r263.status == 'accept' and r263.exact and accepted_digest == target_digest)
    verification_exact = len(final) if exact and r263.verification_failures == 0 else 0
    total_repository_queries = initial_repository_queries + int(r261.oracle_calls_total) + int(r263.oracle_calls_total)
    total_raw_external_calls = initial_raw_external_calls + int(r261_raw_counter['count']) + int(r263_raw_counter['count'])

    result = {
        'schema_version': 1,
        'milestone': 'R2.63',
        'capability': 'bounded-compositional-repository-version-space-expansion',
        'claim_boundary': (
            'Second pinned callable-I/O transfer showing two independently necessary trusted Add->Sub repository '
            'mutations composed from two public refinement counterexamples. The exact target repository is used only '
            'for content-addressed evaluation and is never supplied to either solver. The repository wrapper and '
            'mutation grammar remain host-authored; this is not source inspection, arbitrary patch invention, '
            'effectful experimentation, broad repository autonomy, or AGI.'
        ),
        'source_id': str(source_id),
        'source_version': str(source_version),
        'source_exposure': 'io_only',
        'source_implementation_inspected': False,
        'external_function_family': 'binary_subtract_composed_twice',
        'repository_file_count': len(source.files),
        'correct_target_absent_initial': target_digest not in initial_digests,
        'correct_target_absent_complete_one_step_space': target_digest not in one_step_digests,
        'complete_one_step_candidates': len(one_step),
        'host_authored_exact_candidate': False,
        'exact_target_supplied_to_solver': False,
        'trusted_patch_macro': ['binop', 'replace', 'Add', 'Sub'],
        'initial_label_oracle_calls': initial_repository_queries,
        'initial_label_raw_external_calls': initial_raw_external_calls,
        'r261_baseline': {
            'status': r261.status,
            'reason': r261.reason,
            'expansion_rounds': r261.expansion_round_count,
            'oracle_calls': r261.oracle_calls_total,
            'raw_external_calls': int(r261_raw_counter['count']),
            'selection_oracle_calls': r261.selection_oracle_calls,
            'verification_oracle_calls': r261.verification_oracle_calls,
        },
        'r263': {
            'status': r263.status,
            'reason': r263.reason,
            'exact': exact,
            'composition_depth': r263.max_composition_depth_reached,
            'expansion_rounds': r263.expansion_round_count,
            'refinement_counterexamples': r263.refinement_counterexamples,
            'accepted_edit_count': r263.accepted_edit_count,
            'accepted_mutation_chain': list(r263.accepted_mutation_chain),
            'accepted_content_digest': accepted_digest,
            'generation_used_target_outputs': r263.generation_used_target_outputs,
            'generated_candidates': r263.generated_candidates,
            'admitted_generated_candidates': r263.admitted_generated_candidates,
            'selection_oracle_calls': r263.selection_oracle_calls,
            'refinement_oracle_calls': r263.refinement_oracle_calls,
            'verification_oracle_calls': r263.verification_oracle_calls,
            'oracle_calls': r263.oracle_calls_total,
            'raw_external_calls': int(r263_raw_counter['count']),
            'false_terminal_accepts': r263.false_terminal_accepts,
            'verification_failures': r263.verification_failures,
        },
        'verification_cases': len(final),
        'verification_exact': verification_exact,
        'total_external_oracle_calls': total_repository_queries,
        'total_raw_external_callable_calls': total_raw_external_calls,
        'target_digest': target_digest,
        'accepted_digest': accepted_digest,
        'passed': bool(
            target_digest not in initial_digests
            and target_digest not in one_step_digests
            and r261.status == 'abstain'
            and r261.reason == 'independent_verification_failed'
            and r261.expansion_round_count == 0
            and exact
            and r263.expansion_round_count == 2
            and r263.max_composition_depth_reached == 2
            and r263.refinement_counterexamples == 2
            and r263.accepted_edit_count == 2
            and len(r263.accepted_mutation_chain) == 2
            and len(set(r263.accepted_mutation_chain)) == 2
            and r263.generation_used_target_outputs is False
            and r263.false_terminal_accepts == 0
            and r263.verification_failures == 0
            and verification_exact == len(final)
        ),
        'trainable_parameter_count': 0,
    }
    return result


__all__ = ['run_external_subtract_transfer']
