from __future__ import annotations

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r261_version_space_expansion import expand_repository_candidates


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
