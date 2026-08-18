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
    return RepositoryPatchCandidate('diagnostic-order:source', (), files, 0, 0)


def _oracle(x: int, y: int) -> int:
    return x * y


def _run(diagnostics: tuple[RepositoryProbe, ...]):
    source = _source()
    challenges = tuple(RepositoryProbe(args) for args in ((5, 2), (-3, 5), (9, -2)))
    learning = {tuple(probe.args) for probe in diagnostics + challenges}
    final = tuple(
        RepositoryProbe(args)
        for args in ((7, 2), (6, 4), (-4, -3), (11, 3))
        if args not in learning
    )
    return solve_repository_patch_with_primitive_induction(
        (source,), (), diagnostics, _oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        grammar=PatchPrimitiveGrammar(allowed_target_values=('Mult',), max_hypotheses=4),
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=3,
        max_generated_candidates=4,
        max_sites_per_hypothesis=4,
        min_independent_challenges=3,
    )


def _semantic_receipt(result):
    macro = None if result.learned_macro is None else (
        result.learned_macro.source_value,
        result.learned_macro.target_value,
    )
    return (
        result.status,
        result.exact,
        macro,
        result.reason,
        result.diagnostic_oracle_calls,
        result.diagnostic_counterexamples,
        result.generation_used_target_outputs,
        result.false_terminal_accepts,
        result.verification_failures,
    )


def test_fallback_diagnostic_set_is_invariant_to_caller_order_under_tight_budget() -> None:
    matching = RepositoryProbe((2, 2))      # Add and Mult both return 4.
    mismatch = RepositoryProbe((4, 3))      # Add returns 7; Mult returns 12.
    assert matching.probe_id != mismatch.probe_id

    forward = _run((matching, mismatch))
    reverse = _run((mismatch, matching))

    assert _semantic_receipt(forward) == _semantic_receipt(reverse)
    assert forward.diagnostic_oracle_calls == reverse.diagnostic_oracle_calls == 1
    assert forward.generation_used_target_outputs is False
    assert reverse.generation_used_target_outputs is False
    assert forward.false_terminal_accepts == reverse.false_terminal_accepts == 0
    assert forward.verification_failures == reverse.verification_failures == 0
