from __future__ import annotations

import inspect

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_version_space_expansion import solve_repository_patch_with_version_space_expansion
from cogcoder.r263_compositional_version_space_expansion import (
    solve_repository_patch_with_compositional_expansion,
)


def _candidate(candidate_id: str, files: dict[str, str], *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _floor_to_mod() -> PatchMacro:
    return PatchMacro('pm:floor-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=3)


def _source_files(*, wrong_positive: bool = False) -> dict[str, str]:
    pos_expr = 'x + 2' if wrong_positive else 'x // 2'
    return {
        'entry.py': ('from neg import neg\nfrom pos import pos\n\ndef solve(x):\n    if x >= 0:\n        return pos(x)\n    return neg(-x)\n'),
        'neg.py': 'def neg(x):\n    return x // 3\n',
        'pos.py': f'def pos(x):\n    return {pos_expr}\n',
    }


def _oracle(x: int) -> int:
    return x % 2 if x >= 0 else (-x) % 3


def _case():
    source = _candidate('seed:source', _source_files())
    wrong = _candidate('candidate:wrong-positive', _source_files(wrong_positive=True), edits=1)
    diagnostics = (RepositoryProbe((5,)),)
    refinement = (RepositoryProbe((-5,)),)
    verification = tuple(RepositoryProbe((x,)) for x in (-17, -11, -8, -4, 1, 2, 7, 10, 13, 22))
    return source, wrong, diagnostics, refinement, verification


def test_r263_uses_refinement_counterexample_to_compose_second_repository_edit() -> None:
    source, wrong, diagnostics, refinement, verification = _case()
    r261 = solve_repository_patch_with_version_space_expansion(
        (source, wrong), (), diagnostics, _oracle, verification_inputs=refinement + verification,
        expansion_seeds=(source,), expansion_macros=(_floor_to_mod(),), max_selection_oracle_calls=1,
        max_expansion_rounds=1, max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    assert r261.status == 'abstain'
    assert r261.reason == 'independent_verification_failed'
    assert r261.expansion_round_count == 1
    result = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostics, _oracle, refinement_inputs=refinement,
        verification_inputs=verification, expansion_seeds=(source,), expansion_macros=(_floor_to_mod(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1, max_expansion_rounds=2,
        max_composition_depth=2, max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    assert result.status == 'accept'
    assert result.exact is True
    assert result.candidate is not None
    files = dict(result.candidate.files)
    assert 'x % 2' in files['pos.py']
    assert 'x % 3' in files['neg.py']
    assert result.expansion_round_count == 2
    assert result.max_composition_depth_reached == 2
    assert result.refinement_oracle_calls == 1
    assert result.verification_oracle_calls == len(verification)
    assert result.false_terminal_accepts == 0
    assert result.verification_failures == 0
    assert result.reason == 'compositional_candidate_verified'


def test_r263_preserves_every_public_oracle_observation_across_later_expansion() -> None:
    source, wrong, diagnostics, refinement, verification = _case()
    calls: list[int] = []
    def traced_oracle(x: int) -> int:
        calls.append(x)
        return _oracle(x)
    result = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostics, traced_oracle, refinement_inputs=refinement,
        verification_inputs=verification, expansion_seeds=(source,), expansion_macros=(_floor_to_mod(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1, max_expansion_rounds=2,
        max_composition_depth=2, max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    assert result.status == 'accept'
    assert result.observed_test_count == 2
    assert result.observed_probe_ids == (RepositoryProbe((5,)).probe_id, RepositoryProbe((-5,)).probe_id)
    assert calls[:2] == [5, -5]
    assert set(calls[2:]) == {probe.args[0] for probe in verification}


def test_r263_requires_disjoint_final_verification_pool() -> None:
    source, wrong, diagnostics, refinement, verification = _case()
    try:
        solve_repository_patch_with_compositional_expansion(
            (source, wrong), (), diagnostics, _oracle, refinement_inputs=refinement,
            verification_inputs=(RepositoryProbe((-5,)), *verification), expansion_seeds=(source,),
            expansion_macros=(_floor_to_mod(),),
        )
    except ValueError as exc:
        assert 'verification_inputs must be disjoint' in str(exc)
    else:
        raise AssertionError('overlapping refinement/final verification must fail closed')


def test_r263_depth_budget_prevents_second_edit_and_abstains() -> None:
    source, wrong, diagnostics, refinement, verification = _case()
    result = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostics, _oracle, refinement_inputs=refinement,
        verification_inputs=verification, expansion_seeds=(source,), expansion_macros=(_floor_to_mod(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1, max_expansion_rounds=2,
        max_composition_depth=1, max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    assert result.status == 'abstain'
    assert result.reason == 'composition_depth_budget_exhausted'
    assert result.expansion_round_count == 1
    assert result.false_terminal_accepts == 0


def test_r263_unexpressible_second_edit_abstains_without_final_verification() -> None:
    source, wrong, diagnostics, refinement, verification = _case()
    only_pos_macro = PatchMacro('pm:floor-to-add', 'binop', 'replace', 'FloorDiv', 'Add', support=1)
    result = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostics, _oracle, refinement_inputs=refinement,
        verification_inputs=verification, expansion_seeds=(source,), expansion_macros=(only_pos_macro,),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1, max_expansion_rounds=2,
        max_composition_depth=2, max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    assert result.status == 'abstain'
    assert result.verification_oracle_calls == 0
    assert result.false_terminal_accepts == 0


def test_r263_generator_interface_has_no_oracle_leakage_path() -> None:
    from cogcoder.r263_compositional_version_space_expansion import expand_compositional_frontier
    assert 'oracle' not in inspect.signature(expand_compositional_frontier).parameters


def test_r263_is_candidate_and_macro_order_invariant() -> None:
    source, wrong, diagnostics, refinement, verification = _case()
    macro = _floor_to_mod()
    first = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostics, _oracle, refinement_inputs=refinement,
        verification_inputs=verification, expansion_seeds=(source,), expansion_macros=(macro,),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1, max_expansion_rounds=2,
        max_composition_depth=2, max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    second = solve_repository_patch_with_compositional_expansion(
        (wrong, source), (), tuple(reversed(diagnostics)), _oracle,
        refinement_inputs=tuple(reversed(refinement)), verification_inputs=verification,
        expansion_seeds=(source,), expansion_macros=tuple(reversed((macro,))),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1, max_expansion_rounds=2,
        max_composition_depth=2, max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    assert first.status == second.status == 'accept'
    assert first.candidate is not None and second.candidate is not None
    assert first.candidate.files == second.candidate.files
    assert first.observed_probe_ids == second.observed_probe_ids


def test_r263_refinement_oracle_error_fails_closed_before_final_verification() -> None:
    source, wrong, diagnostics, refinement, verification = _case()
    def failing_refinement_oracle(x: int) -> int:
        if x == -5:
            raise RuntimeError('refinement unavailable')
        return _oracle(x)
    result = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostics, failing_refinement_oracle,
        refinement_inputs=refinement, verification_inputs=verification,
        expansion_seeds=(source,), expansion_macros=(_floor_to_mod(),), max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1, max_expansion_rounds=2, max_composition_depth=2,
        max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    assert result.status == 'abstain'
    assert result.reason == 'refinement_oracle_error'
    assert result.refinement_oracle_calls == 1
    assert result.verification_oracle_calls == 0
    assert result.false_terminal_accepts == 0


def test_r263_refinement_budget_fails_closed_without_querying_refinement() -> None:
    source, wrong, diagnostics, refinement, verification = _case()
    calls: list[int] = []
    def traced(x: int) -> int:
        calls.append(x)
        return _oracle(x)
    result = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostics, traced, refinement_inputs=refinement,
        verification_inputs=verification, expansion_seeds=(source,), expansion_macros=(_floor_to_mod(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=0, max_expansion_rounds=2,
        max_composition_depth=2, max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    assert result.status == 'abstain'
    assert result.reason == 'refinement_oracle_budget_exhausted'
    assert result.refinement_oracle_calls == 0
    assert result.verification_oracle_calls == 0
    assert calls == [5]


def test_r263_final_verification_failure_is_terminal_and_not_recycled() -> None:
    source, wrong, diagnostics, refinement, verification = _case()
    poisoned = verification[0]
    calls: list[int] = []
    def oracle_with_hidden_contradiction(x: int) -> int:
        calls.append(x)
        value = _oracle(x)
        return value + 100 if x == poisoned.args[0] else value
    result = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostics, oracle_with_hidden_contradiction,
        refinement_inputs=refinement, verification_inputs=verification,
        expansion_seeds=(source,), expansion_macros=(_floor_to_mod(),), max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1, max_expansion_rounds=4, max_composition_depth=4,
        max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    assert result.status == 'abstain'
    assert result.reason == 'independent_verification_failed'
    assert result.expansion_round_count == 2
    assert result.verification_failures == 1
    assert result.observed_test_count == 2
    assert result.observed_probe_ids == (diagnostics[0].probe_id, refinement[0].probe_id)
    assert calls == [5, -5, poisoned.args[0]]


def test_r263_frontier_rejects_seen_repository_state_cycles() -> None:
    from cogcoder.r261_expansion_proof import repository_content_digest
    from cogcoder.r263_compositional_version_space_expansion import expand_compositional_frontier
    source, _wrong, _diagnostics, _refinement, _verification = _case()
    first = expand_compositional_frontier(
        (source,), (_floor_to_mod(),), parent_depths={source.candidate_id: 0},
        max_composition_depth=2, max_generated_candidates=8, max_sites_per_macro=8,
    )
    assert len(first) == 2
    blocked = first[0]
    again = expand_compositional_frontier(
        (source,), (_floor_to_mod(),), parent_depths={source.candidate_id: 0},
        seen_content_digests=(repository_content_digest(blocked.candidate),),
        max_composition_depth=2, max_generated_candidates=8, max_sites_per_macro=8,
    )
    assert len(again) == 1
    assert repository_content_digest(again[0].candidate) != repository_content_digest(blocked.candidate)
