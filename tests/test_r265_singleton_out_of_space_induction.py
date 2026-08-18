from __future__ import annotations

from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r265_verified_patch_primitive_induction import (
    PatchPrimitiveGrammar,
    solve_repository_patch_with_primitive_induction,
)


def _source() -> RepositoryPatchCandidate:
    files = (
        ('entry.py', 'from worker import work\n\ndef solve(x, y):\n    return work(x, y)\n'),
        ('worker.py', 'def work(x, y):\n    return x + y\n'),
    )
    return RepositoryPatchCandidate('singleton:source', (), files, 0, 0)


def _oracle(x: int, y: int) -> int:
    return x * y


def test_single_wrong_survivor_can_discover_out_of_space_counterexample() -> None:
    source = _source()
    diagnostics = (
        RepositoryProbe((0, 3)),  # accidental agreement: add == multiply == 3 is false actually; keep distinct evidence ordering target-independent
        RepositoryProbe((5, 2)),
        RepositoryProbe((-4, 3)),
    )
    challenges = tuple(RepositoryProbe(args) for args in ((4, 3), (7, 2), (-3, 5), (9, -2)))
    learning = {tuple(p.args) for p in diagnostics + challenges}
    final = tuple(
        RepositoryProbe((x, y))
        for x in (-9, -4, -1, 2, 6, 11)
        for y in (-5, -2, 1, 4, 8)
        if (x, y) not in learning
    )

    result = solve_repository_patch_with_primitive_induction(
        (source,),
        (),
        diagnostics,
        _oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
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

    assert result.initial_survivors == 1
    assert result.status == 'accept'
    assert result.exact is True
    assert result.learned_macro is not None
    assert (result.learned_macro.source_value, result.learned_macro.target_value) == ('Add', 'Mult')
    assert result.diagnostic_counterexamples == 1
    assert 1 <= result.diagnostic_oracle_calls <= 3
    assert result.generation_used_target_outputs is False
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0


def test_matching_singleton_does_not_force_primitive_induction() -> None:
    source = _source()
    diagnostics = (RepositoryProbe((2, 3)), RepositoryProbe((-4, 5)))
    challenges = tuple(RepositoryProbe(args) for args in ((7, 2), (9, 4), (-3, 5)))
    final = tuple(RepositoryProbe(args) for args in ((11, 3), (-8, 2), (6, -4)))

    result = solve_repository_patch_with_primitive_induction(
        (source,),
        (),
        diagnostics,
        lambda x, y: x + y,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        grammar=PatchPrimitiveGrammar(allowed_target_values=('Sub', 'Mult'), max_hypotheses=8),
        max_selection_oracle_calls=2,
        max_challenge_oracle_calls=3,
        max_generated_candidates=8,
        min_independent_challenges=3,
    )

    assert result.status == 'abstain'
    assert result.primitive_promoted is False
    assert result.reason == 'no_out_of_space_counterexample_for_induction'
    assert result.diagnostic_oracle_calls == 2
    assert result.diagnostic_counterexamples == 0
    assert result.false_terminal_accepts == 0
