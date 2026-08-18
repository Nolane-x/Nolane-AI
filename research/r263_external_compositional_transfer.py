from __future__ import annotations

import itertools
from typing import Callable

from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_version_space_expansion import solve_repository_patch_with_version_space_expansion
from cogcoder.r263_compositional_repository_repair import solve_compositional_repository_patch


def _source_candidate() -> RepositoryPatchCandidate:
    files = (
        ('left.py', 'def left(x, y):\n    return x + y\n'),
        ('main.py', 'from left import left\nfrom right import right\n\ndef compute(x, y, a, b):\n    return left(x, y) + right(a, b)\n'),
        ('right.py', 'def right(a, b):\n    return a + b\n'),
    )
    return RepositoryPatchCandidate('r263:external:source', (), files, 0, 0)


def _macro() -> PatchMacro:
    return PatchMacro('r263:add-to-sub', 'binop', 'replace', 'Add', 'Sub', support=4)


def _refinement_inputs() -> tuple[RepositoryProbe, ...]:
    return (RepositoryProbe((5, 2, 3, 0)), RepositoryProbe((3, 0, 5, 2)))


def _final_inputs() -> tuple[RepositoryProbe, ...]:
    rows = itertools.product((-11, -4, 7, 13), (-6, -3, 2, 5), (-17, -2, 8, 19), (-7, -1, 3, 6))
    return tuple(RepositoryProbe(tuple(row)) for row in rows)


def run_external_transfer(
    subtract_callable: Callable[[object, object], object],
    *,
    source_id: str,
    source_version: str,
) -> dict[str, object]:
    if not callable(subtract_callable):
        raise TypeError('subtract_callable must be callable')

    def oracle(x: object, y: object, a: object, b: object) -> int:
        left = int(subtract_callable(x, y))
        right = int(subtract_callable(a, b))
        return left + right

    source = _source_candidate()
    initial_args = (3, 0, 3, 0)
    initial_tests = (PatchTest('r263:external:initial', initial_args, oracle(*initial_args)),)
    refinement = _refinement_inputs()
    final = _final_inputs()

    r261 = solve_repository_patch_with_version_space_expansion(
        (source,), initial_tests, refinement, oracle,
        verification_inputs=(*refinement, *final),
        expansion_seeds=(source,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=12,
        max_sites_per_macro=12,
    )
    r263 = solve_compositional_repository_patch(
        (source,), initial_tests,
        diagnostic_inputs=refinement,
        refinement_inputs=refinement,
        oracle=oracle,
        final_verification_inputs=final,
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=2,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=12,
        max_sites_per_macro=12,
    )

    passed = bool(
        r261.status == 'abstain'
        and r261.reason == 'independent_verification_failed'
        and r263.status == 'accept'
        and r263.exact is True
        and r263.expansion_round_count == 2
        and r263.refinement_counterexamples == 2
        and r263.accepted_edit_count == 2
        and len(r263.accepted_mutation_chain) == 2
        and not r263.generation_used_target_outputs
        and r263.false_terminal_accepts == 0
        and r263.verification_failures == 0
        and r263.final_verification_oracle_calls == len(final)
    )
    return {
        'milestone': 'R2.63',
        'passed': passed,
        'source_id': str(source_id),
        'source_version': str(source_version),
        'source_exposure': 'io_only',
        'external_function_family': 'binary_subtract_composed_twice',
        'initial_candidate_count': 1,
        'initial_repository_files': len(source.files),
        'trusted_patch_macro': ['binop', 'replace', 'Add', 'Sub'],
        'r261_status': r261.status,
        'r261_reason': r261.reason,
        'r261_expansion_rounds': r261.expansion_round_count,
        'r263_status': r263.status,
        'r263_reason': r263.reason,
        'r263_expansion_rounds': r263.expansion_round_count,
        'r263_refinement_counterexamples': r263.refinement_counterexamples,
        'r263_refinement_oracle_calls': r263.refinement_oracle_calls,
        'r263_accepted_edit_count': r263.accepted_edit_count,
        'r263_mutation_chain_length': len(r263.accepted_mutation_chain),
        'r263_mutation_chain_unique': len(set(r263.accepted_mutation_chain)) == len(r263.accepted_mutation_chain),
        'r263_generation_used_target_outputs': r263.generation_used_target_outputs,
        'r263_false_terminal_accepts': r263.false_terminal_accepts,
        'r263_verification_failures': r263.verification_failures,
        'r263_generated_candidates': r263.generated_candidates,
        'r263_admitted_generated_candidates': r263.admitted_generated_candidates,
        'verification_cases': len(final),
        'verification_exact': len(final) if r263.status == 'accept' and r263.exact else 0,
        'oracle_calls_total': r263.oracle_calls_total,
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'I/O-only transfer showing bounded composition of two trusted Add-to-Sub repository mutations '
            'against one external binary subtraction callable. The repository wrapper and mutation grammar are '
            'host-authored; this is not arbitrary patch invention, broad repository repair, or AGI.'
        ),
    }


__all__ = ['run_external_transfer']
