from __future__ import annotations

import inspect
from dataclasses import replace
from typing import Callable

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import repository_content_digest
from cogcoder.r261_version_space_expansion import expand_repository_candidates
from cogcoder.r263_compositional_repository_repair import solve_compositional_repository_patch
from cogcoder.r264_unified_adaptive_repository_search import (
    expand_adaptive_repository_frontier,
    solve_unified_adaptive_repository_patch,
)


EPISODES = (
    (6101, 0, 2, 3, 5),
    (6113, 1, 3, 4, 6),
    (6127, 2, 4, 5, 7),
    (6139, 0, 5, 2, 8),
    (6151, 1, 6, 4, 9),
    (6173, 2, 7, 5, 11),
)


def _candidate(candidate_id: str, files: dict[str, str], *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _macro() -> PatchMacro:
    return PatchMacro('pm:r264:floor-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=5)


def _repository(
    relays: int,
    pos_divisor: int,
    neg_divisor: int,
    decoy_divisor: int,
    *,
    pos_op: str,
    neg_op: str,
    decoy_op: str = 'floor',
) -> dict[str, str]:
    def expr(op: str, divisor: int) -> str:
        if op == 'floor': return f'x // {divisor}'
        if op == 'mod': return f'x % {divisor}'
        if op == 'add': return f'x + {divisor}'
        raise ValueError(op)

    files: dict[str, str] = {
        'pos0.py': f'def pos0(x):\n    return {expr(pos_op, pos_divisor)}\n',
        'neg0.py': f'def neg0(x):\n    return {expr(neg_op, neg_divisor)}\n',
        'aux.py': f'def aux(x):\n    return {expr(decoy_op, decoy_divisor)}\n',
    }
    pos_name, neg_name = 'pos0', 'neg0'
    for index in range(1, relays + 1):
        files[f'pos{index}.py'] = (
            f'from pos{index - 1} import {pos_name}\n\n'
            f'def pos{index}(x):\n    return {pos_name}(x)\n'
        )
        files[f'neg{index}.py'] = (
            f'from neg{index - 1} import {neg_name}\n\n'
            f'def neg{index}(x):\n    return {neg_name}(x)\n'
        )
        pos_name, neg_name = f'pos{index}', f'neg{index}'
    files['entry.py'] = (
        f'from neg{relays} import {neg_name}\n'
        f'from pos{relays} import {pos_name}\n'
        'from aux import aux\n\n'
        'def solve(x):\n'
        '    aux(x)\n'
        '    if x >= 0:\n'
        f'        return {pos_name}(x)\n'
        f'    return {neg_name}(-x)\n'
    )
    return files


def _oracle(pos_divisor: int, neg_divisor: int) -> Callable[[int], int]:
    def oracle(x: int) -> int:
        return x % pos_divisor if x >= 0 else (-x) % neg_divisor
    return oracle


def _verification_inputs(diagnostic_x: int, refinement_x: int) -> tuple[RepositoryProbe, ...]:
    values = (
        -43, -37, -31, -29, -26, -23, -19, -17, -14, -11, -8, -7, -4, -2,
        1, 2, 4, 6, 8, 11, 13, 16, 19, 22, 25, 28, 31, 34, 37, 41, 43, 47,
    )
    return tuple(RepositoryProbe((value,)) for value in values if value not in {diagnostic_x, refinement_x})


def _run_positive(seed: int, relays: int, pos_divisor: int, neg_divisor: int, decoy_divisor: int) -> dict[str, object]:
    source = _candidate(
        f'r264:source:{seed}',
        _repository(relays, pos_divisor, neg_divisor, decoy_divisor, pos_op='floor', neg_op='floor'),
    )
    wrong = _candidate(
        f'r264:wrong:{seed}',
        _repository(relays, pos_divisor, neg_divisor, decoy_divisor, pos_op='add', neg_op='floor'),
        edits=1,
    )
    target = _candidate(
        f'r264:target-eval:{seed}',
        _repository(relays, pos_divisor, neg_divisor, decoy_divisor, pos_op='mod', neg_op='mod'),
        edits=2,
    )
    target_digest = repository_content_digest(target)
    initial_digests = {repository_content_digest(source), repository_content_digest(wrong)}
    one_step = expand_repository_candidates(
        (source,), (_macro(),), max_generated_candidates=32, max_sites_per_macro=32,
    )
    one_step_digests = {repository_content_digest(row.candidate) for row in one_step}

    diagnostic_x = 2 * pos_divisor + 1
    refinement_x = -(2 * neg_divisor + 1)
    diagnostic = (RepositoryProbe((diagnostic_x,)),)
    refinement = (RepositoryProbe((refinement_x,)),)
    final = _verification_inputs(diagnostic_x, refinement_x)
    oracle = _oracle(pos_divisor, neg_divisor)

    r263 = solve_compositional_repository_patch(
        (source, wrong), (), diagnostic, refinement, oracle,
        final_verification_inputs=final,
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=32,
        max_sites_per_macro=32,
    )
    r264 = solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle,
        refinement_inputs=refinement,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=2,
        max_composition_depth=2,
        max_generated_candidates_per_round=32,
        max_sites_per_macro=32,
    )
    reordered = solve_unified_adaptive_repository_patch(
        (wrong, source), (), diagnostic, oracle,
        refinement_inputs=refinement,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=2,
        max_composition_depth=2,
        max_generated_candidates_per_round=32,
        max_sites_per_macro=32,
    )
    renamed_source = replace(source, candidate_id=f'caller:renamed-source:{seed}')
    renamed_wrong = replace(wrong, candidate_id=f'caller:renamed-wrong:{seed}')
    renamed = solve_unified_adaptive_repository_patch(
        (renamed_source, renamed_wrong), (), diagnostic, oracle,
        refinement_inputs=refinement,
        final_verification_inputs=final,
        expansion_seeds=(renamed_source,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=2,
        max_composition_depth=2,
        max_generated_candidates_per_round=32,
        max_sites_per_macro=32,
    )

    accepted_digest = r264.accepted_content_digest
    return {
        'seed': seed,
        'file_count': len(source.files),
        'relay_depth': relays,
        'positive_divisor': pos_divisor,
        'negative_divisor': neg_divisor,
        'decoy_divisor': decoy_divisor,
        'diagnostic_args': list(diagnostic[0].args),
        'refinement_args': list(refinement[0].args),
        'final_verification_cases': len(final),
        'target_absent_initial': target_digest not in initial_digests,
        'target_absent_complete_one_step_space': target_digest not in one_step_digests,
        'complete_one_step_candidates': len(one_step),
        'r263_status': r263.status,
        'r263_reason': r263.reason,
        'r263_expansion_rounds': r263.expansion_round_count,
        'r264_status': r264.status,
        'r264_reason': r264.reason,
        'r264_exact': bool(r264.status == 'accept' and r264.exact and accepted_digest == target_digest),
        'r264_expansion_rounds': r264.expansion_round_count,
        'r264_diagnostic_counterexamples': r264.diagnostic_counterexamples,
        'r264_refinement_counterexamples': r264.refinement_counterexamples,
        'r264_max_depth': r264.max_composition_depth_reached,
        'r264_generated_candidates': r264.generated_candidates,
        'r264_admitted_candidates': r264.admitted_generated_candidates,
        'r264_selection_oracle_calls': r264.selection_oracle_calls,
        'r264_refinement_oracle_calls': r264.refinement_oracle_calls,
        'r264_final_verification_oracle_calls': r264.final_verification_oracle_calls,
        'r264_oracle_calls_total': r264.oracle_calls_total,
        'accepted_edit_count': r264.accepted_edit_count,
        'accepted_mutation_chain': list(r264.accepted_mutation_chain),
        'public_observation_count': r264.observed_test_count,
        'public_observation_ids': list(r264.observed_probe_ids),
        'public_observations_preserved': r264.observed_probe_ids == (diagnostic[0].probe_id, refinement[0].probe_id),
        'candidate_order_invariant': bool(
            r264.candidate is not None and reordered.candidate is not None
            and r264.candidate.files == reordered.candidate.files
            and r264.accepted_mutation_chain == reordered.accepted_mutation_chain
        ),
        'caller_id_invariant': bool(
            r264.candidate is not None and renamed.candidate is not None
            and r264.candidate.files == renamed.candidate.files
            and r264.accepted_mutation_chain == renamed.accepted_mutation_chain
        ),
        'generation_used_target_outputs': r264.generation_used_target_outputs,
        'false_terminal_accepts': r264.false_terminal_accepts,
        'verification_failures': r264.verification_failures,
        'target_digest': target_digest,
        'accepted_digest': accepted_digest,
    }


def _negative_cases() -> list[dict[str, object]]:
    seed, relays, pos_divisor, neg_divisor, decoy_divisor = EPISODES[0]
    source = _candidate(
        'r264:negative:source',
        _repository(relays, pos_divisor, neg_divisor, decoy_divisor, pos_op='floor', neg_op='floor'),
    )
    wrong = _candidate(
        'r264:negative:wrong',
        _repository(relays, pos_divisor, neg_divisor, decoy_divisor, pos_op='add', neg_op='floor'),
        edits=1,
    )
    diagnostic = (RepositoryProbe((2 * pos_divisor + 1,)),)
    refinement = (RepositoryProbe((-(2 * neg_divisor + 1),)),)
    final = _verification_inputs(diagnostic[0].args[0], refinement[0].args[0])
    oracle = _oracle(pos_divisor, neg_divisor)
    base = dict(
        refinement_inputs=refinement,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=2,
        max_composition_depth=2,
        max_generated_candidates_per_round=32,
        max_sites_per_macro=32,
    )
    rows: list[dict[str, object]] = []

    def add(case: str, result) -> None:
        rows.append({
            'case': case,
            'status': result.status,
            'reason': result.reason,
            'expansion_rounds': result.expansion_round_count,
            'false_accepts': result.false_terminal_accepts,
            'verification_failures': result.verification_failures,
        })

    add('round_budget', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle, **{**base, 'max_expansion_rounds': 0},
    ))
    add('depth_budget', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle, **{**base, 'max_composition_depth': 1},
    ))
    add('missing_macro', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle, **{**base, 'expansion_macros': ()},
    ))
    add('selection_budget', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle, **{**base, 'max_selection_oracle_calls': 0},
    ))
    add('refinement_budget', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle, **{**base, 'max_refinement_oracle_calls': 0},
    ))
    add('generation_budget', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle, **{**base, 'max_generated_candidates_per_round': 0},
    ))

    def diagnostic_error(x: int) -> int:
        if x == diagnostic[0].args[0]:
            raise RuntimeError('diagnostic unavailable')
        return oracle(x)
    add('diagnostic_oracle_error', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, diagnostic_error, **base,
    ))

    def refinement_error(x: int) -> int:
        if x == refinement[0].args[0]:
            raise RuntimeError('refinement unavailable')
        return oracle(x)
    add('refinement_oracle_error', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, refinement_error, **base,
    ))

    poisoned = final[0].args[0]
    def final_contradiction(x: int) -> int:
        value = oracle(x)
        return value + 101 if x == poisoned else value
    add('terminal_final_verification', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, final_contradiction,
        **{**base, 'max_expansion_rounds': 4, 'max_composition_depth': 4},
    ))

    wrong_macro = PatchMacro('pm:r264:floor-to-add', 'binop', 'replace', 'FloorDiv', 'Add', support=1)
    add('unexpressible_target', solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle, **{**base, 'expansion_macros': (wrong_macro,)},
    ))
    return rows


def run_benchmark() -> dict[str, object]:
    rows = [_run_positive(*episode) for episode in EPISODES]
    negatives = _negative_cases()
    summary = {
        'episodes': len(rows),
        'r263_initial_out_of_space_abstains': sum(
            row['r263_status'] == 'abstain'
            and row['r263_reason'] == 'oracle_outside_initial_candidate_version_space'
            and row['r263_expansion_rounds'] == 0
            for row in rows
        ),
        'r264_exact': sum(bool(row['r264_exact']) for row in rows),
        'target_absent_initial': sum(bool(row['target_absent_initial']) for row in rows),
        'target_absent_complete_one_step_space': sum(bool(row['target_absent_complete_one_step_space']) for row in rows),
        'diagnostic_counterexamples': sum(row['r264_diagnostic_counterexamples'] == 1 for row in rows),
        'refinement_counterexamples': sum(row['r264_refinement_counterexamples'] == 1 for row in rows),
        'two_expansion_rounds': sum(row['r264_expansion_rounds'] == 2 and row['r264_max_depth'] == 2 for row in rows),
        'public_observations_preserved': sum(bool(row['public_observations_preserved']) for row in rows),
        'min_final_verification_cases': min(int(row['final_verification_cases']) for row in rows),
        'max_file_count': max(int(row['file_count']) for row in rows),
        'max_relay_depth': max(int(row['relay_depth']) for row in rows),
        'max_generated_candidates': max(int(row['r264_generated_candidates']) for row in rows),
        'negative_abstains': sum(row['status'] == 'abstain' for row in negatives),
        'false_terminal_accepts': sum(int(row['false_terminal_accepts']) for row in rows) + sum(int(row['false_accepts']) for row in negatives),
        'verification_failures_on_positive': sum(int(row['verification_failures']) for row in rows),
        'candidate_order_invariant': all(bool(row['candidate_order_invariant']) for row in rows),
        'caller_id_invariant': all(bool(row['caller_id_invariant']) for row in rows),
        'generation_uses_target_outputs': (
            'oracle' in inspect.signature(expand_adaptive_repository_frontier).parameters
            or 'target' in inspect.signature(expand_adaptive_repository_frontier).parameters
            or 'expected' in inspect.signature(expand_adaptive_repository_frontier).parameters
        ),
    }
    gates = {
        'r263_causal_baseline_all_initial_out_of_space': summary['r263_initial_out_of_space_abstains'] == len(rows),
        'r264_all_exact': summary['r264_exact'] == len(rows),
        'exact_target_absent_initial': summary['target_absent_initial'] == len(rows),
        'exact_target_absent_one_step': summary['target_absent_complete_one_step_space'] == len(rows),
        'all_use_diagnostic_counterexample': summary['diagnostic_counterexamples'] == len(rows),
        'all_use_refinement_counterexample': summary['refinement_counterexamples'] == len(rows),
        'all_require_two_expansion_rounds': summary['two_expansion_rounds'] == len(rows),
        'all_public_observations_preserved': summary['public_observations_preserved'] == len(rows),
        'at_least_24_final_heldouts': summary['min_final_verification_cases'] >= 24,
        'at_least_8_negative_abstains': summary['negative_abstains'] >= 8,
        'zero_false_terminal_accepts': summary['false_terminal_accepts'] == 0,
        'zero_positive_verification_failures': summary['verification_failures_on_positive'] == 0,
        'candidate_order_invariant': summary['candidate_order_invariant'] is True,
        'caller_id_invariant': summary['caller_id_invariant'] is True,
        'target_output_free_generation_api': summary['generation_uses_target_outputs'] is False,
        'zero_trainable_parameters': True,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.64 Unified Adaptive Repository Search Phase A',
        'capability': 'diagnostic-out-of-space-expansion-plus-compositional-refinement',
        'claim_boundary': (
            'Causal evidence for a bounded repository search loop that first expands after an active diagnostic '
            'oracle outcome falls outside the initial candidate version space and later composes a second trusted '
            'PatchMacro edit after a separate refinement counterexample. The repository representation, probe pools '
            'and patch vocabulary remain host supplied. This does not establish arbitrary code generation, patch '
            'language invention, effectful experimentation, broad real-repository autonomy, or AGI.'
        ),
        'rows': rows,
        'negative_rows': negatives,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
        'trainable_parameter_count': 0,
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
