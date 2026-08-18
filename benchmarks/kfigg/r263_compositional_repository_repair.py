from __future__ import annotations

import itertools
from typing import Iterable

from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import repository_content_digest
from cogcoder.r261_version_space_expansion import solve_repository_patch_with_version_space_expansion
from cogcoder.r263_compositional_repository_repair import solve_compositional_repository_patch


HELDOUT_EPISODES = (5101, 5113, 5129, 5147, 5167, 5179)


def _relay_module(name: str, dependency: str, function: str, prior_function: str) -> str:
    return (
        f'from {dependency} import {prior_function}\n\n'
        f'def {function}(x, y):\n'
        f'    return {prior_function}(x, y)\n'
    )


def _repository(seed: int, *, left_relays: int, right_relays: int, left_op: str, right_op: str) -> tuple[tuple[str, str], ...]:
    if left_op not in {'//', '%'} or right_op not in {'//', '%'}:
        raise ValueError('unsupported operator')
    files: dict[str, str] = {
        'left_core.py': f'def left_core(x, y):\n    return x {left_op} y\n',
        'right_core.py': f'def right_core(x, y):\n    return x {right_op} y\n',
    }
    left_module = 'left_core'
    left_function = 'left_core'
    for index in range(left_relays):
        module = f'left_relay_{index}'
        function = f'left_relay_{index}'
        files[f'{module}.py'] = _relay_module(module, left_module, function, left_function)
        left_module, left_function = module, function
    right_module = 'right_core'
    right_function = 'right_core'
    for index in range(right_relays):
        module = f'right_relay_{index}'
        function = f'right_relay_{index}'
        files[f'{module}.py'] = _relay_module(module, right_module, function, right_function)
        right_module, right_function = module, function
    bias = seed % 3
    files['main.py'] = (
        f'from {left_module} import {left_function}\n'
        f'from {right_module} import {right_function}\n\n'
        'def compute(x, y, a, b):\n'
        f'    return {left_function}(x, y) + {right_function}(a, b) + {bias}\n'
    )
    return tuple(sorted(files.items()))


def _candidate(candidate_id: str, files: Iterable[tuple[str, str]], *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files)), 0, int(edits))


def _macro() -> PatchMacro:
    return PatchMacro('r263:floor-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=4)


def _oracle(seed: int):
    bias = seed % 3
    return lambda x, y, a, b: x % y + a % b + bias


def _initial_test(seed: int) -> tuple[PatchTest, ...]:
    oracle = _oracle(seed)
    args = (3, 2, 3, 2)
    return (PatchTest(f'r263:init:{seed}', args, oracle(*args)),)


def _refinement_inputs() -> tuple[RepositoryProbe, ...]:
    return (RepositoryProbe((5, 2, 3, 2)), RepositoryProbe((3, 2, 5, 2)))


def _final_inputs() -> tuple[RepositoryProbe, ...]:
    rows = itertools.product((7, 8, 11, 14), (3, 4, 5), (10, 13, 17, 19), (3, 4, 5))
    return tuple(RepositoryProbe(tuple(row)) for row in rows)


def _run_episode(seed: int, index: int) -> dict[str, object]:
    left_relays = 1 + (index % 3)
    right_relays = 1 + ((index + 1) % 3)
    source = _candidate(
        f'r263:source:{seed}',
        _repository(seed, left_relays=left_relays, right_relays=right_relays, left_op='//', right_op='//'),
    )
    oracle = _oracle(seed)
    initial = _initial_test(seed)
    refinement = _refinement_inputs()
    final = _final_inputs()

    r261 = solve_repository_patch_with_version_space_expansion(
        (source,), initial, refinement, oracle,
        verification_inputs=(*refinement, *final),
        expansion_seeds=(source,), expansion_macros=(_macro(),),
        max_selection_oracle_calls=2, max_expansion_rounds=2,
        max_generated_candidates_per_round=8, max_sites_per_macro=8,
    )
    r263 = solve_compositional_repository_patch(
        (source,), initial,
        diagnostic_inputs=refinement,
        refinement_inputs=refinement,
        oracle=oracle,
        final_verification_inputs=final,
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=2,
        max_refinement_oracle_calls=2,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    return {
        'seed': seed,
        'file_count': len(source.files),
        'call_depth': max(left_relays, right_relays) + 2,
        'source_content_digest': repository_content_digest(source),
        'r261_status': r261.status,
        'r261_reason': r261.reason,
        'r261_expansion_rounds': r261.expansion_round_count,
        'r263_status': r263.status,
        'r263_exact': r263.exact,
        'r263_reason': r263.reason,
        'r263_expansion_rounds': r263.expansion_round_count,
        'r263_refinement_counterexamples': r263.refinement_counterexamples,
        'r263_refinement_oracle_calls': r263.refinement_oracle_calls,
        'r263_final_verification_calls': r263.final_verification_oracle_calls,
        'r263_accepted_edit_count': r263.accepted_edit_count,
        'r263_mutation_chain_length': len(r263.accepted_mutation_chain),
        'r263_mutation_chain_unique': len(set(r263.accepted_mutation_chain)) == len(r263.accepted_mutation_chain),
        'r263_generation_used_target_outputs': r263.generation_used_target_outputs,
        'r263_false_terminal_accepts': r263.false_terminal_accepts,
        'r263_verification_failures': r263.verification_failures,
        'r263_generated_candidates': r263.generated_candidates,
        'r263_admitted_generated_candidates': r263.admitted_generated_candidates,
        'r263_candidate_evaluations': r263.candidate_evaluations,
        'r263_accepted_content_digest': r263.accepted_content_digest,
    }


def run_benchmark() -> dict[str, object]:
    rows = tuple(_run_episode(seed, index) for index, seed in enumerate(HELDOUT_EPISODES))
    final_cases = len(_final_inputs())
    summary = {
        'episodes': len(rows),
        'r261_terminal_verification_abstains': sum(
            row['r261_status'] == 'abstain' and row['r261_reason'] == 'independent_verification_failed'
            for row in rows
        ),
        'r263_exact': sum(bool(row['r263_exact']) for row in rows),
        'r263_two_round_repairs': sum(int(row['r263_expansion_rounds']) == 2 for row in rows),
        'r263_two_edit_repairs': sum(int(row['r263_accepted_edit_count']) == 2 for row in rows),
        'refinement_counterexamples': sum(int(row['r263_refinement_counterexamples']) for row in rows),
        'refinement_oracle_calls': sum(int(row['r263_refinement_oracle_calls']) for row in rows),
        'final_verification_cases_per_episode': final_cases,
        'final_verification_calls': sum(int(row['r263_final_verification_calls']) for row in rows),
        'false_terminal_accepts': sum(int(row['r263_false_terminal_accepts']) for row in rows),
        'verification_failures': sum(int(row['r263_verification_failures']) for row in rows),
        'target_output_leakage_into_generation': any(bool(row['r263_generation_used_target_outputs']) for row in rows),
        'unique_accepted_content_digests': len({row['r263_accepted_content_digest'] for row in rows}),
        'min_file_count': min(int(row['file_count']) for row in rows),
        'max_file_count': max(int(row['file_count']) for row in rows),
        'min_call_depth': min(int(row['call_depth']) for row in rows),
        'max_call_depth': max(int(row['call_depth']) for row in rows),
        'trainable_parameter_count': 0,
    }
    gates = {
        'r261_baseline_fails_all': summary['r261_terminal_verification_abstains'] == len(rows),
        'r263_exact_all': summary['r263_exact'] == len(rows),
        'two_expansion_rounds_all': summary['r263_two_round_repairs'] == len(rows),
        'two_edits_all': summary['r263_two_edit_repairs'] == len(rows),
        'two_refinement_counterexamples_each': summary['refinement_counterexamples'] == 2 * len(rows),
        'full_disjoint_final_verification': summary['final_verification_calls'] == final_cases * len(rows),
        'zero_false_terminal_accepts': summary['false_terminal_accepts'] == 0,
        'zero_verification_failures': summary['verification_failures'] == 0,
        'target_output_free_generation': summary['target_output_leakage_into_generation'] is False,
        'episode_specific_final_repairs': summary['unique_accepted_content_digests'] == len(rows),
        'repository_scale_retained': summary['min_file_count'] >= 5 and summary['max_call_depth'] >= 4,
        'zero_trainable_parameters': True,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.63 Compositional Repository Repair',
        'capability': 'bounded-multi-round-repository-version-space-refinement',
        'claim_boundary': (
            'Bounded two-step counterexample-guided composition of trusted single-site PatchMacro mutations '
            'with disjoint terminal verification; not arbitrary code generation, patch-language invention, '
            'effectful experimentation, broad real-repository autonomy, or AGI.'
        ),
        'heldout_episodes': list(HELDOUT_EPISODES),
        'rows': list(rows),
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
        'trainable_parameter_count': 0,
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
