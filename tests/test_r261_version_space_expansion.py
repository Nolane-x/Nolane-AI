from __future__ import annotations

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
    macro = PatchMacro('pm:floor-div-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=1)

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


def test_solver_expands_after_oracle_outside_initial_version_space() -> None:
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

    macro = PatchMacro('pm:floor-div-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=3)
    result = solve_repository_patch_with_version_space_expansion(
        (floor, subtract),
        initial,
        probes,
        oracle,
        verification_inputs=verification,
        expansion_seeds=(floor,),
        expansion_macros=(macro,),
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
