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


def test_zero_required_and_zero_budget_challenges_cannot_promote_primitive() -> None:
    source = _candidate('zero-challenge:add', '+')
    wrong = _candidate('zero-challenge:sub', '-')
    diagnostics = (RepositoryProbe((5, 2)),)
    challenges = (RepositoryProbe((4, 3)),)
    final = tuple(RepositoryProbe(args) for args in ((7, 2), (6, 4), (-4, -3)))

    result = solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostics, lambda x, y: x * y,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        grammar=PatchPrimitiveGrammar(allowed_target_values=('Mult',), max_hypotheses=4),
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=0,
        max_generated_candidates=4,
        max_sites_per_hypothesis=4,
        min_independent_challenges=0,
    )

    assert result.status == 'abstain'
    assert result.primitive_promoted is False
    assert result.independent_challenges_passed == 0
    assert result.final_verification_oracle_calls == 0
    assert result.false_terminal_accepts == 0
