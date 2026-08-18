from __future__ import annotations

from dataclasses import replace

import pytest

from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_version_space_expansion import solve_repository_patch_with_version_space_expansion
from cogcoder.r263_compositional_repository_repair import solve_compositional_repository_patch


def _base_candidate(candidate_id: str = 'base') -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(
        candidate_id,
        (),
        (
            ('left.py', 'def left(x, y):\n    return x // y\n'),
            ('right.py', 'def right(a, b):\n    return a // b\n'),
            (
                'main.py',
                'from left import left\n'
                'from right import right\n\n'
                'def compute(x, y, a, b):\n'
                '    return left(x, y) + right(a, b)\n',
            ),
        ),
        0,
        0,
    )


def _macro() -> PatchMacro:
    return PatchMacro('pm:floor-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=4)


def _oracle(x, y, a, b):
    return x % y + a % b


def _initial_tests():
    # Both // and % equal 1 on each term, so the unmodified candidate survives.
    return (PatchTest('initial:same', (3, 2, 3, 2), 2),)


def _refinement_inputs():
    # First exposes left.py only; second exposes right.py after the first edit.
    return (RepositoryProbe((5, 2, 3, 2)), RepositoryProbe((3, 2, 5, 2)))


def _final_inputs():
    return (
        RepositoryProbe((8, 3, 7, 3)),
        RepositoryProbe((11, 4, 10, 4)),
        RepositoryProbe((14, 5, 13, 5)),
        RepositoryProbe((17, 6, 19, 6)),
    )


def test_r263_composes_two_expansion_rounds_after_r261_terminal_verification_failure() -> None:
    base = _base_candidate()
    refinement = _refinement_inputs()

    r261 = solve_repository_patch_with_version_space_expansion(
        (base,),
        _initial_tests(),
        refinement,
        _oracle,
        verification_inputs=(*refinement, *_final_inputs()),
        expansion_seeds=(base,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    assert r261.status == 'abstain'
    assert r261.reason == 'independent_verification_failed'
    assert r261.expansion_round_count == 0

    result = solve_compositional_repository_patch(
        (base,),
        _initial_tests(),
        diagnostic_inputs=refinement,
        refinement_inputs=refinement,
        oracle=_oracle,
        final_verification_inputs=_final_inputs(),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=2,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    assert result.status == 'accept'
    assert result.exact is True
    assert result.reason == 'compositional_candidate_verified'
    assert result.expansion_round_count == 2
    assert result.refinement_counterexamples == 2
    assert result.refinement_oracle_calls == 2
    assert result.final_verification_oracle_calls == 4
    assert result.accepted_edit_count == 2
    assert len(result.accepted_mutation_chain) == 2
    assert len(set(result.accepted_mutation_chain)) == 2
    assert result.generation_used_target_outputs is False
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0
    assert result.trainable_parameter_count == 0


def test_r263_is_invariant_to_duplicate_candidate_ids_and_order() -> None:
    first = _base_candidate('caller:first')
    duplicate = replace(first, candidate_id='caller:renamed')
    kwargs = dict(
        initial_tests=_initial_tests(),
        diagnostic_inputs=_refinement_inputs(),
        refinement_inputs=_refinement_inputs(),
        oracle=_oracle,
        final_verification_inputs=_final_inputs(),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=2,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    left = solve_compositional_repository_patch((first, duplicate), **kwargs)
    right = solve_compositional_repository_patch((duplicate, first), **kwargs)
    assert left.status == right.status == 'accept'
    assert left.accepted_content_digest == right.accepted_content_digest
    assert left.initial_unique_candidates == right.initial_unique_candidates == 1
    assert left.expansion_round_count == right.expansion_round_count == 2


def test_r263_refinement_budget_exhaustion_abstains_after_first_composed_edit() -> None:
    result = solve_compositional_repository_patch(
        (_base_candidate(),),
        _initial_tests(),
        diagnostic_inputs=_refinement_inputs(),
        refinement_inputs=_refinement_inputs(),
        oracle=_oracle,
        final_verification_inputs=_final_inputs(),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    assert result.status == 'abstain'
    assert result.reason == 'refinement_oracle_budget_exhausted'
    assert result.expansion_round_count == 1
    assert result.refinement_counterexamples == 1
    assert result.false_terminal_accepts == 0


def test_r263_final_verification_is_terminal_and_cannot_trigger_extra_expansion() -> None:
    final = _final_inputs()

    def adversarial_oracle(x, y, a, b):
        value = _oracle(x, y, a, b)
        if (x, y, a, b) == final[-1].args:
            return value + 1
        return value

    result = solve_compositional_repository_patch(
        (_base_candidate(),),
        _initial_tests(),
        diagnostic_inputs=_refinement_inputs(),
        refinement_inputs=_refinement_inputs(),
        oracle=adversarial_oracle,
        final_verification_inputs=final,
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=2,
        max_expansion_rounds=4,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    assert result.status == 'abstain'
    assert result.reason == 'independent_final_verification_failed'
    assert result.expansion_round_count == 2
    assert result.verification_failures == 1
    assert result.false_terminal_accepts == 0


def test_r263_requires_final_verification_inputs_disjoint_from_learning_inputs() -> None:
    repeated = _refinement_inputs()[0]
    with pytest.raises(ValueError, match='final verification inputs must be disjoint'):
        solve_compositional_repository_patch(
            (_base_candidate(),),
            _initial_tests(),
            diagnostic_inputs=_refinement_inputs(),
            refinement_inputs=_refinement_inputs(),
            oracle=_oracle,
            final_verification_inputs=(repeated,),
            expansion_macros=(_macro(),),
        )
