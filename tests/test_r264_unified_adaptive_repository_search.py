from __future__ import annotations

import inspect

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r263_compositional_repository_repair import solve_compositional_repository_patch
from cogcoder.r264_unified_adaptive_repository_search import (
    expand_adaptive_repository_frontier,
    solve_unified_adaptive_repository_patch,
)


def _candidate(candidate_id: str, files: dict[str, str], *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _macro() -> PatchMacro:
    return PatchMacro('pm:r264:floor-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=4)


def _files(*, pos: str = 'floor', neg: str = 'floor', decoy: bool = False) -> dict[str, str]:
    pos_expr = {'floor': 'x // 2', 'mod': 'x % 2', 'add': 'x + 2'}[pos]
    neg_expr = {'floor': 'x // 3', 'mod': 'x % 3', 'add': 'x + 3'}[neg]
    decoy_expr = 'x % 5' if decoy else 'x // 5'
    return {
        'entry.py': (
            'from neg import neg\n'
            'from pos import pos\n'
            'from aux import aux\n\n'
            'def solve(x):\n'
            '    aux(x)\n'
            '    if x >= 0:\n'
            '        return pos(x)\n'
            '    return neg(-x)\n'
        ),
        'pos.py': f'def pos(x):\n    return {pos_expr}\n',
        'neg.py': f'def neg(x):\n    return {neg_expr}\n',
        'aux.py': f'def aux(x):\n    return {decoy_expr}\n',
    }


def _oracle(x: int) -> int:
    return x % 2 if x >= 0 else (-x) % 3


def _case():
    source = _candidate('caller:source', _files())
    wrong = _candidate('caller:wrong-positive', _files(pos='add'), edits=1)
    diagnostic = (RepositoryProbe((5,)),)
    refinement = (RepositoryProbe((-5,)),)
    final = tuple(RepositoryProbe((x,)) for x in (-23, -17, -11, -8, -4, 1, 2, 7, 10, 13, 19, 22))
    return source, wrong, diagnostic, refinement, final


def test_r264_expands_outside_initial_space_then_continues_compositional_refinement() -> None:
    source, wrong, diagnostic, refinement, final = _case()
    r263 = solve_compositional_repository_patch(
        (source, wrong), (), diagnostic, refinement, _oracle,
        final_verification_inputs=final, expansion_macros=(_macro(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1,
        max_expansion_rounds=2, max_generated_candidates_per_round=16,
        max_sites_per_macro=16,
    )
    assert r263.status == 'abstain'
    assert r263.reason == 'oracle_outside_initial_candidate_version_space'
    assert r263.expansion_round_count == 0

    r264 = solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, _oracle,
        refinement_inputs=refinement, final_verification_inputs=final,
        expansion_seeds=(source,), expansion_macros=(_macro(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1,
        max_expansion_rounds=2, max_composition_depth=2,
        max_generated_candidates_per_round=16, max_sites_per_macro=16,
    )
    assert r264.status == 'accept'
    assert r264.exact is True
    assert r264.candidate is not None
    files = dict(r264.candidate.files)
    assert 'x % 2' in files['pos.py']
    assert 'x % 3' in files['neg.py']
    assert 'x // 5' in files['aux.py']
    assert r264.expansion_round_count == 2
    assert r264.diagnostic_counterexamples == 1
    assert r264.refinement_counterexamples == 1
    assert r264.max_composition_depth_reached == 2
    assert r264.accepted_edit_count == 2
    assert len(r264.accepted_mutation_chain) == 2
    assert r264.generation_used_target_outputs is False
    assert r264.false_terminal_accepts == 0
    assert r264.verification_failures == 0
    assert r264.reason == 'unified_candidate_verified'


def test_r264_preserves_diagnostic_and_refinement_evidence_across_both_expansion_modes() -> None:
    source, wrong, diagnostic, refinement, final = _case()
    calls: list[int] = []
    def traced(x: int) -> int:
        calls.append(x)
        return _oracle(x)
    result = solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, traced,
        refinement_inputs=refinement, final_verification_inputs=final,
        expansion_seeds=(source,), expansion_macros=(_macro(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1,
        max_expansion_rounds=2, max_composition_depth=2,
        max_generated_candidates_per_round=16, max_sites_per_macro=16,
    )
    assert result.status == 'accept'
    assert result.observed_test_count == 2
    assert result.observed_probe_ids == (diagnostic[0].probe_id, refinement[0].probe_id)
    assert calls[:2] == [5, -5]
    assert set(calls[2:]) == {probe.args[0] for probe in final}


def test_r264_generation_api_has_no_oracle_or_target_output_channel() -> None:
    params = inspect.signature(expand_adaptive_repository_frontier).parameters
    assert 'oracle' not in params
    assert 'target' not in params
    assert 'expected' not in params


def test_r264_diagnostic_expansion_budget_zero_fails_closed_before_refinement() -> None:
    source, wrong, diagnostic, refinement, final = _case()
    result = solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, _oracle,
        refinement_inputs=refinement, final_verification_inputs=final,
        expansion_seeds=(source,), expansion_macros=(_macro(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1,
        max_expansion_rounds=0, max_composition_depth=2,
        max_generated_candidates_per_round=16, max_sites_per_macro=16,
    )
    assert result.status == 'abstain'
    assert result.reason == 'expansion_round_budget_exhausted'
    assert result.refinement_oracle_calls == 0
    assert result.final_verification_oracle_calls == 0
    assert result.false_terminal_accepts == 0


def test_r264_final_verification_is_disjoint_and_never_recycled() -> None:
    source, wrong, diagnostic, refinement, final = _case()
    poisoned = final[0]
    def oracle_with_final_only_contradiction(x: int) -> int:
        value = _oracle(x)
        return value + 100 if x == poisoned.args[0] else value
    result = solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle_with_final_only_contradiction,
        refinement_inputs=refinement, final_verification_inputs=final,
        expansion_seeds=(source,), expansion_macros=(_macro(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1,
        max_expansion_rounds=4, max_composition_depth=4,
        max_generated_candidates_per_round=16, max_sites_per_macro=16,
    )
    assert result.status == 'abstain'
    assert result.reason == 'independent_final_verification_failed'
    assert result.expansion_round_count == 2
    assert result.verification_failures == 1
    assert result.observed_test_count == 2
    assert result.observed_probe_ids == (diagnostic[0].probe_id, refinement[0].probe_id)


def test_r264_rejects_duplicate_final_verification_inputs() -> None:
    source, wrong, diagnostic, refinement, final = _case()
    duplicate = (final[0], final[0], *final[1:])
    try:
        solve_unified_adaptive_repository_patch(
            (source, wrong), (), diagnostic, _oracle,
            refinement_inputs=refinement, final_verification_inputs=duplicate,
            expansion_seeds=(source,), expansion_macros=(_macro(),),
        )
    except ValueError as exc:
        assert 'final verification inputs must be unique' in str(exc)
    else:
        raise AssertionError('duplicate final verification inputs must fail closed')
