from __future__ import annotations

# Hosted trigger after validation workflow installation.
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r265_verified_patch_primitive_induction import (
    PatchPrimitiveGrammar,
    solve_repository_patch_with_primitive_induction,
)


def _candidate(candidate_id: str, marker: str) -> RepositoryPatchCandidate:
    files = (
        ('entry.py', 'from worker import work\n\ndef solve(x, y):\n    return work(x, y)\n'),
        ('marker.py', f'MARKER = {marker!r}\n'),
        ('worker.py', 'def work(x, y):\n    return x + y\n'),
    )
    return RepositoryPatchCandidate(candidate_id, (), files, 0, 0)


def _oracle(x: int, y: int) -> int:
    return x * y


def _case(oracle):
    first = _candidate('unanimous:first', 'first')
    second = _candidate('unanimous:second', 'second')
    diagnostics = tuple(RepositoryProbe(args) for args in ((5, 2), (0, 3), (-4, 3)))
    challenges = tuple(RepositoryProbe(args) for args in ((4, 3), (7, 2), (-3, 5), (9, -2)))
    learning = {tuple(p.args) for p in diagnostics + challenges}
    final = tuple(
        RepositoryProbe((x, y))
        for x in (-9, -4, -1, 2, 6, 11)
        for y in (-5, -2, 1, 4, 8)
        if (x, y) not in learning
    )
    result = solve_repository_patch_with_primitive_induction(
        (first, second),
        (),
        diagnostics,
        oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(first,),
        grammar=PatchPrimitiveGrammar(
            allowed_target_values=('Add', 'Sub', 'Mult'),
            max_hypotheses=8,
        ),
        max_selection_oracle_calls=3,
        max_challenge_oracle_calls=4,
        max_generated_candidates=8,
        max_sites_per_hypothesis=8,
        min_independent_challenges=4,
    )
    return result


def test_unanimous_matching_version_space_remains_fail_closed() -> None:
    result = _case(lambda x, y: x + y)
    assert result.initial_unique_candidates == 2
    assert result.initial_survivors == 2
    assert result.status == 'abstain'
    assert result.primitive_promoted is False
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0


def test_unanimous_wrong_version_space_can_detect_misspecification_and_induce() -> None:
    # Both surviving repositories are content-distinct but predict exactly the
    # same Add behavior on every diagnostic. Entropy is therefore zero, yet the
    # oracle outcome lies outside the whole version space. A diagnostic layer
    # must not equate "cannot split survivors" with "survivors contain truth".
    result = _case(_oracle)
    assert result.initial_unique_candidates == 2
    assert result.initial_survivors == 2
    assert result.status == 'accept'
    assert result.exact is True
    assert result.learned_macro is not None
    assert (result.learned_macro.source_value, result.learned_macro.target_value) == ('Add', 'Mult')
    assert result.diagnostic_counterexamples == 1
    assert 1 <= result.diagnostic_oracle_calls <= 3
    assert result.generation_used_target_outputs is False
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0
