from __future__ import annotations

import inspect

from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r264_unified_adaptive_repository_search import solve_unified_adaptive_repository_patch
from cogcoder.r265_verified_patch_primitive_induction import (
    PatchPrimitiveGrammar,
    enumerate_patch_macro_hypotheses,
    solve_repository_patch_with_primitive_induction,
)


def _candidate(candidate_id: str, *, target_expr: str, aux_expr: str = 'x + y', edits: int = 0) -> RepositoryPatchCandidate:
    files = {
        'target.py': f'def target(x, y):\n    return {target_expr}\n',
        'aux.py': f'def aux(x, y):\n    return {aux_expr}\n',
        'entry.py': (
            'from aux import aux\n'
            'from target import target\n\n'
            'def solve(x, y):\n'
            '    aux(x, y)\n'
            '    return target(x, y)\n'
        ),
    }
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _oracle(x: int, y: int) -> int:
    return x * y


def _grammar() -> PatchPrimitiveGrammar:
    return PatchPrimitiveGrammar(
        allowed_slots=('binop',),
        allowed_operations=('replace',),
        allowed_target_values=('Mult', 'FloorDiv', 'Mod'),
        max_hypotheses=32,
    )


def _case():
    source = _candidate('caller:source', target_expr='x + y')
    wrong = _candidate('caller:wrong-sub', target_expr='x - y', edits=1)
    diagnostic = (RepositoryProbe((5, 2)),)
    challenges = tuple(RepositoryProbe(args) for args in ((4, 3), (7, 2), (9, 4), (-3, 5)))
    final = tuple(
        RepositoryProbe((x, y))
        for x in (-11, -7, -2, 1, 3, 6, 10)
        for y in (-5, -2, 1, 4, 8)
        if (x, y) not in {(5, 2), (4, 3), (7, 2), (9, 4), (-3, 5)}
    )
    return source, wrong, diagnostic, challenges, final


def test_r265_induces_missing_binop_patch_primitive_then_verifies_repository() -> None:
    source, wrong, diagnostic, challenges, final = _case()

    baseline = solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, _oracle,
        refinement_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        expansion_macros=(),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=len(challenges),
        max_expansion_rounds=1,
        max_composition_depth=1,
        max_generated_candidates_per_round=32,
        max_sites_per_macro=16,
    )
    assert baseline.status == 'abstain'
    assert baseline.reason == 'no_expansion_macros'

    result = solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, _oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        grammar=_grammar(),
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=len(challenges),
        max_generated_candidates=64,
        max_sites_per_hypothesis=16,
        min_independent_challenges=4,
    )

    assert result.status == 'accept'
    assert result.exact is True
    assert result.candidate is not None
    assert result.learned_macro is not None
    assert result.learned_macro.slot == 'binop'
    assert result.learned_macro.operation == 'replace'
    assert result.learned_macro.source_value == 'Add'
    assert result.learned_macro.target_value == 'Mult'
    assert result.primitive_promoted is True
    assert result.diagnostic_counterexamples == 1
    assert result.challenge_oracle_calls == len(challenges)
    assert result.independent_challenges_passed == len(challenges)
    assert result.final_verification_oracle_calls == len(final)
    assert result.accepted_content_digest is not None
    assert result.generation_used_target_outputs is False
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0
    assert result.reason == 'induced_patch_primitive_verified'


def test_r265_hypothesis_enumeration_has_no_oracle_or_target_output_channel() -> None:
    params = inspect.signature(enumerate_patch_macro_hypotheses).parameters
    assert 'oracle' not in params
    assert 'target' not in params
    assert 'expected' not in params


def test_r265_hypotheses_are_deterministic_and_caller_id_invariant() -> None:
    source, _wrong, _diagnostic, _challenges, _final = _case()
    renamed = RepositoryPatchCandidate('totally:different:id', source.macro_ids, source.files, source.support_score, source.edit_count)
    first = enumerate_patch_macro_hypotheses((source,), _grammar())
    second = enumerate_patch_macro_hypotheses((renamed,), _grammar())
    assert [(row.slot, row.operation, row.source_value, row.target_value, row.macro_id) for row in first] == [
        (row.slot, row.operation, row.source_value, row.target_value, row.macro_id) for row in second
    ]
    assert len({row.macro_id for row in first}) == len(first)
    assert all(row.macro_id.startswith('r265pm:') for row in first)


def test_r265_missing_target_from_closed_grammar_abstains_without_final_verification() -> None:
    source, wrong, diagnostic, challenges, final = _case()
    grammar = PatchPrimitiveGrammar(
        allowed_slots=('binop',),
        allowed_operations=('replace',),
        allowed_target_values=('FloorDiv', 'Mod'),
        max_hypotheses=16,
    )
    result = solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, _oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,), grammar=grammar,
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=len(challenges),
        max_generated_candidates=64,
        max_sites_per_hypothesis=16,
        min_independent_challenges=4,
    )
    assert result.status == 'abstain'
    assert result.primitive_promoted is False
    assert result.final_verification_oracle_calls == 0
    assert result.false_terminal_accepts == 0


def test_r265_final_verification_must_be_unique_and_disjoint_from_learning() -> None:
    source, wrong, diagnostic, challenges, final = _case()
    duplicate = (final[0], final[0], *final[1:])
    try:
        solve_repository_patch_with_primitive_induction(
            (source, wrong), (), diagnostic, _oracle,
            challenge_inputs=challenges,
            final_verification_inputs=duplicate,
            expansion_seeds=(source,), grammar=_grammar(),
        )
    except ValueError as exc:
        assert 'final verification inputs must be unique' in str(exc)
    else:
        raise AssertionError('duplicate final verification inputs must fail closed')

    overlapping = (challenges[0], *final)
    try:
        solve_repository_patch_with_primitive_induction(
            (source, wrong), (), diagnostic, _oracle,
            challenge_inputs=challenges,
            final_verification_inputs=overlapping,
            expansion_seeds=(source,), grammar=_grammar(),
        )
    except ValueError as exc:
        assert 'final verification inputs must be disjoint' in str(exc)
    else:
        raise AssertionError('learning/final overlap must fail closed')


def test_r265_insufficient_challenge_budget_cannot_promote_primitive() -> None:
    source, wrong, diagnostic, challenges, final = _case()
    result = solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, _oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,), grammar=_grammar(),
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=2,
        max_generated_candidates=64,
        max_sites_per_hypothesis=16,
        min_independent_challenges=4,
    )
    assert result.status == 'abstain'
    assert result.reason == 'insufficient_independent_challenges'
    assert result.primitive_promoted is False
    assert result.final_verification_oracle_calls == 0
    assert result.false_terminal_accepts == 0
