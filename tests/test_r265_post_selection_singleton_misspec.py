from __future__ import annotations

from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r265_verified_patch_primitive_induction import (
    PatchPrimitiveGrammar,
    solve_repository_patch_with_primitive_induction,
)


def _candidate(candidate_id: str, operator: str) -> RepositoryPatchCandidate:
    files = (
        ('entry.py', 'from worker import work\n\ndef solve(x, y):\n    return work(x, y)\n'),
        ('worker.py', f'def work(x, y):\n    return x {operator} y\n'),
    )
    return RepositoryPatchCandidate(candidate_id, (), files, 0, 0)


def _oracle(x: int, y: int) -> int:
    return x * y


def test_post_selection_singleton_can_still_expose_out_of_space_counterexample() -> None:
    add = _candidate('post-singleton:add', '+')
    sub = _candidate('post-singleton:sub', '-')

    agreement = RepositoryProbe((2, 2))
    misspecification = RepositoryProbe((4, 3))
    assert agreement.probe_id < misspecification.probe_id
    diagnostics = (agreement, misspecification)

    challenges = tuple(RepositoryProbe(args) for args in ((5, 2), (-3, 5), (9, -2)))
    learning = {tuple(probe.args) for probe in diagnostics + challenges}
    final = tuple(
        RepositoryProbe(args)
        for args in ((7, 2), (6, 4), (-4, -3), (11, 3))
        if args not in learning
    )

    result = solve_repository_patch_with_primitive_induction(
        (add, sub),
        (),
        diagnostics,
        _oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(add,),
        grammar=PatchPrimitiveGrammar(allowed_target_values=('Mult',), max_hypotheses=4),
        max_selection_oracle_calls=2,
        max_challenge_oracle_calls=3,
        max_generated_candidates=4,
        max_sites_per_hypothesis=4,
        min_independent_challenges=3,
    )

    assert result.initial_survivors == 2
    assert result.diagnostic_oracle_calls == 2
    assert result.diagnostic_counterexamples == 1
    assert result.status == 'accept'
    assert result.exact is True
    assert result.primitive_promoted is True
    assert result.learned_macro is not None
    assert (result.learned_macro.source_value, result.learned_macro.target_value) == ('Add', 'Mult')
    assert result.generation_used_target_outputs is False
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0
