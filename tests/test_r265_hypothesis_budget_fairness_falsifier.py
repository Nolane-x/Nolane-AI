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
    # With only Add observed in the seed, deterministic enumeration is:
    # Add->FloorDiv, Add->Mod, Add->Mult.  The source contains two Add sites.
    return PatchPrimitiveGrammar(
        allowed_slots=('binop',),
        allowed_operations=('replace',),
        allowed_target_values=('FloorDiv', 'Mod', 'Mult'),
        max_hypotheses=16,
    )


def _case(max_generated_candidates: int):
    source = _candidate('caller:source', 'Add')
    wrong = _candidate('caller:wrong', 'Sub')
    diagnostic = (RepositoryProbe((5, 2)),)
    challenges = tuple(RepositoryProbe(args) for args in ((4, 3), (7, 2), (9, 4), (-3, 5)))
    learning = {(5, 2), (4, 3), (7, 2), (9, 4), (-3, 5)}
    final = tuple(
        RepositoryProbe((x, y))
        for x in (-11, -7, -2, 1, 3, 6, 10)
        for y in (-5, -2, 1, 4, 8)
        if (x, y) not in learning
    )
    return solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, _oracle,
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


def test_roomy_budget_control_proves_correct_primitive_is_expressible() -> None:
    source = _candidate('caller:source', 'Add')
    hypotheses = enumerate_patch_macro_hypotheses((source,), _grammar())
    assert [(row.source_value, row.target_value) for row in hypotheses] == [
        ('Add', 'FloorDiv'),
        ('Add', 'Mod'),
        ('Add', 'Mult'),
    ]

    result = _case(5)
    assert result.status == 'accept'
    assert result.exact is True
    assert result.learned_macro is not None
    assert result.learned_macro.source_value == 'Add'
    assert result.learned_macro.target_value == 'Mult'
    assert result.generation_used_target_outputs is False
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0


def test_global_candidate_budget_does_not_starve_later_primitive_hypotheses() -> None:
    # There are three primitive hypotheses and a budget of three generated
    # candidates. A hypothesis-fair scheduler can allocate one first-site
    # candidate per hypothesis, which includes the exact Add->Mult repair.
    # The current sequential scheduler lets Add->FloorDiv consume two slots
    # and Add->Mod consume the third, so Add->Mult is never evaluated.
    result = _case(3)
    assert result.status == 'accept'
    assert result.exact is True
    assert result.learned_macro is not None
    assert result.learned_macro.source_value == 'Add'
    assert result.learned_macro.target_value == 'Mult'
    assert result.generated_candidates <= 3
    assert result.generation_used_target_outputs is False
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0
