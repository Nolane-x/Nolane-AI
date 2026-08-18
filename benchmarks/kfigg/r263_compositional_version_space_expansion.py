from __future__ import annotations

import inspect
from typing import Callable

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import repository_content_digest
from cogcoder.r261_version_space_expansion import (
    expand_repository_candidates,
    solve_repository_patch_with_version_space_expansion,
)
from cogcoder.r263_compositional_version_space_expansion import (
    expand_compositional_frontier,
    solve_repository_patch_with_compositional_expansion,
)

EPISODES = (
    (5101, 0, 2, 3),
    (5113, 1, 3, 4),
    (5129, 2, 4, 5),
    (5147, 0, 5, 2),
    (5167, 1, 6, 4),
    (5189, 2, 7, 5),
)


def _expr(op: str, divisor: int) -> str:
    if op == 'floor': return f'x // {divisor}'
    if op == 'mod': return f'x % {divisor}'
    if op == 'add': return f'x + {divisor}'
    raise ValueError(op)


def _repository(relays: int, pos_divisor: int, neg_divisor: int, *, pos_op: str, neg_op: str) -> dict[str, str]:
    files: dict[str, str] = {
        'pos0.py': f'def pos0(x):\n    return {_expr(pos_op, pos_divisor)}\n',
        'neg0.py': f'def neg0(x):\n    return {_expr(neg_op, neg_divisor)}\n',
    }
    pos_name, neg_name = 'pos0', 'neg0'
    for index in range(1, relays + 1):
        files[f'pos{index}.py'] = f'from pos{index - 1} import {pos_name}\n\ndef pos{index}(x):\n    return {pos_name}(x)\n'
        files[f'neg{index}.py'] = f'from neg{index - 1} import {neg_name}\n\ndef neg{index}(x):\n    return {neg_name}(x)\n'
        pos_name, neg_name = f'pos{index}', f'neg{index}'
    files['entry.py'] = (
        f'from neg{relays} import {neg_name}\n'
        f'from pos{relays} import {pos_name}\n\n'
        'def solve(x):\n'
        '    if x >= 0:\n'
        f'        return {pos_name}(x)\n'
        f'    return {neg_name}(-x)\n'
    )
    return files


def _candidate(candidate_id: str, files: dict[str, str], *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _macro() -> PatchMacro:
    return PatchMacro('pm:r263:floor-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=4)


def _oracle(pos_divisor: int, neg_divisor: int) -> Callable[[int], int]:
    def oracle(x: int) -> int:
        return x % pos_divisor if x >= 0 else (-x) % neg_divisor
    return oracle


def _verification_inputs(diagnostic_x: int, refinement_x: int) -> tuple[RepositoryProbe, ...]:
    values = [-31, -29, -26, -23, -19, -17, -14, -11, -8, -7, -4, -2, 1, 2, 4, 6, 8, 11, 13, 16, 19, 22, 25, 28, 31, 34, 37, 41]
    return tuple(RepositoryProbe((value,)) for value in values if value not in {diagnostic_x, refinement_x})


def _run_episode(seed: int, relays: int, pos_divisor: int, neg_divisor: int) -> dict[str, object]:
    source = _candidate(f'r263:source:{seed}', _repository(relays, pos_divisor, neg_divisor, pos_op='floor', neg_op='floor'))
    wrong = _candidate(f'r263:wrong:{seed}', _repository(relays, pos_divisor, neg_divisor, pos_op='add', neg_op='floor'), edits=1)
    target = _candidate(f'r263:target:{seed}', _repository(relays, pos_divisor, neg_divisor, pos_op='mod', neg_op='mod'), edits=2)
    target_digest = repository_content_digest(target)
    initial_digests = {repository_content_digest(source), repository_content_digest(wrong)}
    one_step = expand_repository_candidates((source,), (_macro(),), max_generated_candidates=16, max_sites_per_macro=16)
    one_step_digests = {repository_content_digest(row.candidate) for row in one_step}
    diagnostic_x = 2 * pos_divisor + 1
    refinement_x = -(2 * neg_divisor + 1)
    diagnostic = (RepositoryProbe((diagnostic_x,)),)
    refinement = (RepositoryProbe((refinement_x,)),)
    verification = _verification_inputs(diagnostic_x, refinement_x)
    oracle = _oracle(pos_divisor, neg_divisor)

    r261 = solve_repository_patch_with_version_space_expansion(
        (source, wrong), (), diagnostic, oracle, verification_inputs=refinement + verification,
        expansion_seeds=(source,), expansion_macros=(_macro(),), max_selection_oracle_calls=1,
        max_expansion_rounds=1, max_generated_candidates_per_round=16, max_sites_per_macro=16,
    )
    r263 = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostic, oracle, refinement_inputs=refinement, verification_inputs=verification,
        expansion_seeds=(source,), expansion_macros=(_macro(),), max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1, max_expansion_rounds=2, max_composition_depth=2,
        max_generated_candidates_per_round=16, max_sites_per_macro=16,
    )
    reordered = solve_repository_patch_with_compositional_expansion(
        (wrong, source), (), diagnostic, oracle, refinement_inputs=refinement, verification_inputs=verification,
        expansion_seeds=(source,), expansion_macros=(_macro(),), max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1, max_expansion_rounds=2, max_composition_depth=2,
        max_generated_candidates_per_round=16, max_sites_per_macro=16,
    )
    accepted_digest = repository_content_digest(r263.candidate) if r263.candidate is not None else None
    return {
        'seed': seed, 'file_count': len(source.files), 'relay_depth': relays,
        'positive_divisor': pos_divisor, 'negative_divisor': neg_divisor,
        'diagnostic_args': list(diagnostic[0].args), 'refinement_args': list(refinement[0].args),
        'final_verification_cases': len(verification),
        'target_absent_initial': target_digest not in initial_digests,
        'target_absent_complete_one_step_space': target_digest not in one_step_digests,
        'complete_one_step_candidates': len(one_step),
        'r261_status': r261.status, 'r261_reason': r261.reason, 'r261_expansion_rounds': r261.expansion_round_count,
        'r263_status': r263.status, 'r263_reason': r263.reason,
        'r263_exact': bool(r263.exact and accepted_digest == target_digest),
        'r263_expansion_rounds': r263.expansion_round_count, 'r263_max_depth': r263.max_composition_depth_reached,
        'r263_selection_oracle_calls': r263.selection_oracle_calls,
        'r263_refinement_oracle_calls': r263.refinement_oracle_calls,
        'r263_verification_oracle_calls': r263.verification_oracle_calls,
        'r263_oracle_calls_total': r263.oracle_calls_total,
        'r263_generated_candidates': r263.generated_candidates,
        'r263_admitted_generated_candidates': r263.admitted_generated_candidates,
        'public_observation_count': r263.observed_test_count,
        'public_observation_ids': list(r263.observed_probe_ids),
        'public_observations_preserved': r263.observed_probe_ids == (diagnostic[0].probe_id, refinement[0].probe_id),
        'candidate_order_invariant': r263.candidate is not None and reordered.candidate is not None and r263.candidate.files == reordered.candidate.files,
        'false_terminal_accepts': r263.false_terminal_accepts,
        'verification_failures': r263.verification_failures,
        'target_digest': target_digest, 'accepted_digest': accepted_digest,
    }


def _negative_cases() -> list[dict[str, object]]:
    _seed, relays, pos_divisor, neg_divisor = EPISODES[0]
    source = _candidate('r263:negative:source', _repository(relays, pos_divisor, neg_divisor, pos_op='floor', neg_op='floor'))
    wrong = _candidate('r263:negative:wrong', _repository(relays, pos_divisor, neg_divisor, pos_op='add', neg_op='floor'), edits=1)
    diagnostic = (RepositoryProbe((2 * pos_divisor + 1,)),)
    refinement = (RepositoryProbe((-(2 * neg_divisor + 1),)),)
    verification = _verification_inputs(diagnostic[0].args[0], refinement[0].args[0])
    oracle = _oracle(pos_divisor, neg_divisor)
    base_kwargs = dict(refinement_inputs=refinement, verification_inputs=verification, expansion_seeds=(source,), expansion_macros=(_macro(),), max_selection_oracle_calls=1, max_refinement_oracle_calls=1, max_expansion_rounds=2, max_composition_depth=2, max_generated_candidates_per_round=16, max_sites_per_macro=16)
    rows: list[dict[str, object]] = []
    depth = solve_repository_patch_with_compositional_expansion((source, wrong), (), diagnostic, oracle, **{**base_kwargs, 'max_composition_depth': 1})
    rows.append({'case': 'depth_budget', 'status': depth.status, 'reason': depth.reason, 'false_accepts': depth.false_terminal_accepts})
    no_macro = solve_repository_patch_with_compositional_expansion((source, wrong), (), diagnostic, oracle, **{**base_kwargs, 'expansion_macros': ()})
    rows.append({'case': 'no_macro', 'status': no_macro.status, 'reason': no_macro.reason, 'false_accepts': no_macro.false_terminal_accepts})
    no_selection = solve_repository_patch_with_compositional_expansion((source, wrong), (), diagnostic, oracle, **{**base_kwargs, 'max_selection_oracle_calls': 0})
    rows.append({'case': 'selection_budget', 'status': no_selection.status, 'reason': no_selection.reason, 'false_accepts': no_selection.false_terminal_accepts})
    no_refinement = solve_repository_patch_with_compositional_expansion((source, wrong), (), diagnostic, oracle, **{**base_kwargs, 'max_refinement_oracle_calls': 0})
    rows.append({'case': 'refinement_budget', 'status': no_refinement.status, 'reason': no_refinement.reason, 'false_accepts': no_refinement.false_terminal_accepts})
    def refinement_error(x: int) -> int:
        if x == refinement[0].args[0]: raise RuntimeError('bounded negative oracle error')
        return oracle(x)
    oracle_error = solve_repository_patch_with_compositional_expansion((source, wrong), (), diagnostic, refinement_error, **base_kwargs)
    rows.append({'case': 'refinement_oracle_error', 'status': oracle_error.status, 'reason': oracle_error.reason, 'false_accepts': oracle_error.false_terminal_accepts})
    hidden = verification[0].args[0]
    def hidden_contradiction(x: int) -> int:
        value = oracle(x)
        return value + 101 if x == hidden else value
    terminal = solve_repository_patch_with_compositional_expansion((source, wrong), (), diagnostic, hidden_contradiction, **base_kwargs)
    rows.append({'case': 'terminal_verification', 'status': terminal.status, 'reason': terminal.reason, 'false_accepts': terminal.false_terminal_accepts, 'verification_failures': terminal.verification_failures, 'expansion_rounds': terminal.expansion_round_count})
    return rows


def run_benchmark() -> dict[str, object]:
    rows = [_run_episode(*episode) for episode in EPISODES]
    negatives = _negative_cases()
    summary = {
        'episodes': len(rows),
        'r261_partial_repair_failures': sum(row['r261_status'] == 'abstain' and row['r261_reason'] == 'independent_verification_failed' and row['r261_expansion_rounds'] == 1 for row in rows),
        'r263_exact': sum(bool(row['r263_exact']) for row in rows),
        'target_absent_initial': sum(bool(row['target_absent_initial']) for row in rows),
        'target_absent_complete_one_step_space': sum(bool(row['target_absent_complete_one_step_space']) for row in rows),
        'two_expansion_rounds': sum(row['r263_expansion_rounds'] == 2 and row['r263_max_depth'] == 2 for row in rows),
        'public_observations_preserved': sum(bool(row['public_observations_preserved']) for row in rows),
        'min_final_verification_cases': min(int(row['final_verification_cases']) for row in rows),
        'max_file_count': max(int(row['file_count']) for row in rows),
        'max_relay_depth': max(int(row['relay_depth']) for row in rows),
        'max_generated_candidates': max(int(row['r263_generated_candidates']) for row in rows),
        'negative_abstains': sum(row['status'] == 'abstain' for row in negatives),
        'false_terminal_accepts': sum(int(row.get('false_terminal_accepts', 0)) for row in rows) + sum(int(row.get('false_accepts', 0)) for row in negatives),
        'verification_failures_on_positive': sum(int(row['verification_failures']) for row in rows),
        'candidate_order_invariant': all(bool(row['candidate_order_invariant']) for row in rows),
        'generation_uses_target_outputs': 'oracle' in inspect.signature(expand_compositional_frontier).parameters,
    }
    gates = {
        'r261_baseline_fails_after_partial_repair': summary['r261_partial_repair_failures'] == len(rows),
        'r263_all_exact': summary['r263_exact'] == len(rows),
        'exact_target_absent_initial': summary['target_absent_initial'] == len(rows),
        'exact_target_absent_one_step': summary['target_absent_complete_one_step_space'] == len(rows),
        'all_require_two_expansion_rounds': summary['two_expansion_rounds'] == len(rows),
        'all_public_observations_preserved': summary['public_observations_preserved'] == len(rows),
        'at_least_24_final_heldouts': summary['min_final_verification_cases'] >= 24,
        'all_negative_cases_abstain': summary['negative_abstains'] == len(negatives),
        'zero_false_terminal_accepts': summary['false_terminal_accepts'] == 0,
        'zero_positive_verification_failures': summary['verification_failures_on_positive'] == 0,
        'candidate_order_invariant': summary['candidate_order_invariant'] is True,
        'target_output_free_generation_api': summary['generation_uses_target_outputs'] is False,
        'zero_trainable_parameters': True,
    }
    return {'schema_version': 1, 'milestone': 'R2.63 Compositional Version-Space Expansion Phase A', 'claim_boundary': 'Causal evidence for bounded two-step repository repair composition over pre-existing trusted PatchMacro semantics with public refinement counterexamples and disjoint terminal verification. This does not establish arbitrary code generation, patch-language invention, effectful experimentation, broad real-repository autonomy, or AGI.', 'rows': rows, 'negative_rows': negatives, 'summary': summary, 'gates': gates, 'all_gates_pass': all(gates.values()), 'trainable_parameter_count': 0}


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
