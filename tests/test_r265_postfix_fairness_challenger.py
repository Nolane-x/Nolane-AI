from __future__ import annotations

from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r265_verified_patch_primitive_induction import (
    PatchPrimitiveGrammar,
    enumerate_patch_macro_hypotheses,
    solve_repository_patch_with_primitive_induction,
)


def _candidate(candidate_id: str, target_op: str) -> RepositoryPatchCandidate:
    symbol = {'Add': '+', 'Sub': '-', 'Mult': '*'}[target_op]
    files = {
        'a_target.py': f'def target(x, y):\n    return x {symbol} y\n',
        'entry.py': (
            'from a_target import target\n'
            'from z_aux import aux\n\n'
            'def solve(x, y):\n'
            '    aux(x, y)\n'
            '    return target(x, y)\n'
        ),
        'z_aux.py': 'def aux(x, y):\n    return x + y\n',
    }
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, 0)


def _oracle(x: int, y: int) -> int:
    return x * y


def _grammar() -> PatchPrimitiveGrammar:
    return PatchPrimitiveGrammar(
        allowed_slots=('binop',),
        allowed_operations=('replace',),
        allowed_target_values=('FloorDiv', 'Mod', 'Mult'),
        max_hypotheses=16,
    )


def _case(max_generated_candidates: int):
    source = _candidate('challenger:source', 'Add')
    wrong = _candidate('challenger:wrong', 'Sub')
    diagnostic = (RepositoryProbe((5, 2)),)
    challenges = tuple(RepositoryProbe(args) for args in ((4, 3), (7, 2), (9, 4), (-3, 5)))
    learning = {(5, 2), (4, 3), (7, 2), (9, 4), (-3, 5)}
    final = tuple(
        RepositoryProbe((x, y))
        for x in (-13, -8, -1, 2, 5, 9, 12)
        for y in (-6, -3, 1, 5, 9)
        if (x, y) not in learning
    )
    return solve_repository_patch_with_primitive_induction(
        (wrong, source), (), diagnostic, _oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        grammar=_grammar(),
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=len(challenges),
        max_generated_candidates=max_generated_candidates,
        max_sites_per_hypothesis=16,
        min_independent_challenges=4,
    )


def test_challenger_confirms_hypothesis_order_and_roomy_control() -> None:
    source = _candidate('challenger:source', 'Add')
    hypotheses = enumerate_patch_macro_hypotheses((source,), _grammar())
    assert [(row.source_value, row.target_value) for row in hypotheses] == [
        ('Add', 'FloorDiv'),
        ('Add', 'Mod'),
        ('Add', 'Mult'),
    ]
    roomy = _case(5)
    assert roomy.status == 'accept'
    assert roomy.exact is True
    assert roomy.learned_macro is not None
    assert (roomy.learned_macro.source_value, roomy.learned_macro.target_value) == ('Add', 'Mult')


def test_challenger_confirms_tight_global_budget_cannot_starve_correct_primitive() -> None:
    result = _case(3)
    assert result.status == 'accept'
    assert result.exact is True
    assert result.learned_macro is not None
    assert (result.learned_macro.source_value, result.learned_macro.target_value) == ('Add', 'Mult')
    assert result.generated_candidates <= 3
    assert result.generation_used_target_outputs is False
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0
