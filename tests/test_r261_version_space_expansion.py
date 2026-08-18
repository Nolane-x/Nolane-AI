from __future__ import annotations

import inspect

from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe, solve_repository_patch_with_active_probes
from cogcoder.r261_version_space_expansion import (
    expand_repository_candidates,
    solve_repository_patch_with_version_space_expansion,
)


def _candidate(candidate_id: str, expression: str) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(
        candidate_id,
        (),
        (('a.py', f'def f(x, y):\n    return {expression}\n'),),
        0,
        0,
    )


def _floor_to_mod(mid: str = 'pm:floor-div-to-mod') -> PatchMacro:
    return PatchMacro(mid, 'binop', 'replace', 'FloorDiv', 'Mod', support=3)


def _base_case():
    floor = _candidate('candidate:floor', 'x // y')
    subtract = _candidate('candidate:subtract', 'x - y')
    initial = (PatchTest('initial', (3, 2), 1),)
    probes = (RepositoryProbe((5, 2)),)
    verification = (
        RepositoryProbe((5, 2)),
        RepositoryProbe((7, 3)),
        RepositoryProbe((8, 3)),
        RepositoryProbe((11, 4)),
    )
    return floor, subtract, initial, probes, verification


def test_expander_generates_each_single_site_mutation_without_oracle() -> None:
    seed = RepositoryPatchCandidate(
        'seed:two-floor-divs',
        (),
        (
            (
                'a.py',
                'def f(x, y):\n'
                '    a = x // y\n'
                '    b = x // y\n'
                '    return a + b\n',
            ),
        ),
        0,
        0,
    )
    macro = _floor_to_mod()

    rows = expand_repository_candidates(
        (seed,),
        (macro,),
        max_generated_candidates=16,
        max_sites_per_macro=8,
    )

    assert len(rows) == 2
    assert {row.mutation.site_index for row in rows} == {0, 1}
    assert len({row.candidate.candidate_id for row in rows}) == 2
    assert all(row.candidate.edit_count == 1 for row in rows)
    assert all(row.mutation.seed_candidate_id == seed.candidate_id for row in rows)
    assert all(row.mutation.macro_id == macro.macro_id for row in rows)
    assert all(sum(source.count('%') for _path, source in row.candidate.files) == 1 for row in rows)
    assert 'oracle' not in inspect.signature(expand_repository_candidates).parameters


def test_expander_is_input_order_invariant_and_budgeted() -> None:
    first = RepositoryPatchCandidate(
        'seed:first', (),
        (('a.py', 'def f(x, y):\n    return (x // y) + (x // y) + (x // y)\n'),),
        0, 0,
    )
    second = RepositoryPatchCandidate(
        'seed:second', (),
        (('a.py', 'def f(x, y):\n    return (x // y) - (x // y)\n'),),
        0, 0,
    )
    mod = _floor_to_mod('pm:z-mod')
    add = PatchMacro('pm:a-add', 'binop', 'replace', 'FloorDiv', 'Add', support=1)

    forward = expand_repository_candidates(
        (first, second), (mod, add),
        max_generated_candidates=3, max_sites_per_macro=2,
    )
    reverse = expand_repository_candidates(
        (second, first), (add, mod),
        max_generated_candidates=3, max_sites_per_macro=2,
    )

    assert len(forward) == len(reverse) == 3
    assert tuple(row.candidate.files for row in forward) == tuple(row.candidate.files for row in reverse)
    assert tuple(row.candidate.candidate_id for row in forward) == tuple(row.candidate.candidate_id for row in reverse)
    assert all(row.mutation.site_index < 2 for row in forward)


def test_solver_expands_after_oracle_outside_initial_version_space() -> None:
    floor, subtract, initial, probes, verification = _base_case()
    oracle = lambda x, y: x % y

    baseline = solve_repository_patch_with_active_probes(
        (floor, subtract),
        initial,
        probes,
        oracle,
        verification_inputs=verification,
        max_selection_oracle_calls=1,
    )
    assert baseline.status == 'abstain'
    assert baseline.reason == 'oracle_outside_candidate_version_space'

    result = solve_repository_patch_with_version_space_expansion(
        (floor, subtract),
        initial,
        probes,
        oracle,
        verification_inputs=verification,
        expansion_seeds=(floor,),
        expansion_macros=(_floor_to_mod(),),
        max_selection_oracle_calls=1,
        max_expansion_rounds=1,
        max_generated_candidates_per_round=16,
        max_sites_per_macro=8,
    )

    assert result.status == 'accept'
    assert result.exact is True
    assert result.candidate is not None
    assert result.candidate.files == _candidate('target', 'x % y').files
    assert result.initial_survivors == 2
    assert result.final_survivors == 1
    assert result.selection_oracle_calls == 1
    assert result.expansion_round_count == 1
    assert result.generated_candidates == 1
    assert result.admitted_generated_candidates == 1
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0
    assert result.reason == 'expanded_candidate_verified'


def test_solver_fail_closes_without_expansion_authority_or_budget() -> None:
    floor, subtract, initial, probes, verification = _base_case()
    oracle = lambda x, y: x % y

    no_macros = solve_repository_patch_with_version_space_expansion(
        (floor, subtract), initial, probes, oracle,
        verification_inputs=verification,
        expansion_seeds=(floor,), expansion_macros=(),
        max_selection_oracle_calls=1, max_expansion_rounds=1,
    )
    assert no_macros.status == 'abstain'
    assert no_macros.reason == 'no_expansion_macros'
    assert no_macros.false_terminal_accepts == 0

    no_rounds = solve_repository_patch_with_version_space_expansion(
        (floor, subtract), initial, probes, oracle,
        verification_inputs=verification,
        expansion_seeds=(floor,), expansion_macros=(_floor_to_mod(),),
        max_selection_oracle_calls=1, max_expansion_rounds=0,
    )
    assert no_rounds.status == 'abstain'
    assert no_rounds.reason == 'expansion_round_budget_exhausted'
    assert no_rounds.false_terminal_accepts == 0

    no_generation = solve_repository_patch_with_version_space_expansion(
        (floor, subtract), initial, probes, oracle,
        verification_inputs=verification,
        expansion_seeds=(floor,), expansion_macros=(_floor_to_mod(),),
        max_selection_oracle_calls=1, max_expansion_rounds=1,
        max_generated_candidates_per_round=0,
    )
    assert no_generation.status == 'abstain'
    assert no_generation.reason == 'expansion_generation_budget_exhausted'
    assert no_generation.false_terminal_accepts == 0


def test_solver_abstains_when_target_is_not_expressible() -> None:
    floor, subtract, initial, probes, verification = _base_case()
    oracle = lambda x, y: x % y
    wrong_macro = PatchMacro('pm:floor-to-add', 'binop', 'replace', 'FloorDiv', 'Add', support=1)

    result = solve_repository_patch_with_version_space_expansion(
        (floor, subtract), initial, probes, oracle,
        verification_inputs=verification,
        expansion_seeds=(floor,), expansion_macros=(wrong_macro,),
        max_selection_oracle_calls=1, max_expansion_rounds=1,
    )

    assert result.status == 'abstain'
    assert result.reason == 'expansion_no_candidate_matches_counterexample'
    assert result.generated_candidates == 1
    assert result.admitted_generated_candidates == 0
    assert result.false_terminal_accepts == 0


def test_solver_abstains_on_oracle_error() -> None:
    floor, subtract, initial, probes, verification = _base_case()

    def broken_oracle(x, y):
        raise RuntimeError('oracle unavailable')

    result = solve_repository_patch_with_version_space_expansion(
        (floor, subtract), initial, probes, broken_oracle,
        verification_inputs=verification,
        expansion_seeds=(floor,), expansion_macros=(_floor_to_mod(),),
        max_selection_oracle_calls=1, max_expansion_rounds=1,
    )

    assert result.status == 'abstain'
    assert result.reason == 'selection_oracle_error'
    assert result.false_terminal_accepts == 0


def test_solver_requires_independent_verification_after_expansion() -> None:
    floor, subtract, initial, probes, verification = _base_case()

    def deceptive_oracle(x, y):
        if (x, y) == (7, 3):
            return 99
        return x % y

    result = solve_repository_patch_with_version_space_expansion(
        (floor, subtract), initial, probes, deceptive_oracle,
        verification_inputs=verification,
        expansion_seeds=(floor,), expansion_macros=(_floor_to_mod(),),
        max_selection_oracle_calls=1, max_expansion_rounds=1,
    )

    assert result.status == 'abstain'
    assert result.reason == 'independent_verification_failed'
    assert result.expansion_round_count == 1
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 1
