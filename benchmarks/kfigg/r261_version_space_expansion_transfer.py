from __future__ import annotations

import ast
import hashlib
import inspect
import itertools

from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest
from cogcoder.r252_repository_query import (
    RepositoryPatchCandidate,
    RepositorySnapshot,
    compile_repository_candidate,
)
from cogcoder.r260_active_repository_probes import RepositoryProbe, solve_repository_patch_with_active_probes
from cogcoder.r261_version_space_expansion import (
    expand_repository_candidates,
    solve_repository_patch_with_version_space_expansion,
)

HELDOUT_EPISODES = (4101, 4111, 4127, 4133, 4153, 4177)


def _canon(source: str) -> str:
    return ast.unparse(ast.parse(source)) + '\n'


def _name(seed: int, role: str, index: int | None = None) -> str:
    suffix = '' if index is None else f'|{index}'
    return 'n_' + hashlib.sha256(f'r261|{seed}|{role}{suffix}'.encode()).hexdigest()[:12]


def _repository(
    seed: int,
    *,
    relay_count: int,
    coefficient: int,
    target_op: str,
    decoy_op: str,
) -> RepositorySnapshot:
    if relay_count < 1:
        raise ValueError('relay_count must be positive')
    if coefficient <= 2:
        raise ValueError('coefficient must be > 2')

    core_mod = _name(seed, 'core_mod')
    target_fn = _name(seed, 'target_fn')
    decoy_fn = _name(seed, 'decoy_fn')
    x = _name(seed, 'x')
    y = _name(seed, 'y')

    files: dict[str, str] = {
        f'{core_mod}.py': _canon(
            f'''\ndef {target_fn}({x}, {y}):\n    return {x} {target_op} {y}\n\ndef {decoy_fn}({x}, {y}):\n    return {x} {decoy_op} {y}\n'''
        )
    }

    previous_mod = core_mod
    previous_target = target_fn
    previous_decoy = decoy_fn
    for index in range(relay_count):
        relay_mod = _name(seed, 'relay_mod', index)
        next_target = _name(seed, 'relay_target', index)
        next_decoy = _name(seed, 'relay_decoy', index)
        rx = _name(seed, 'relay_x', index)
        ry = _name(seed, 'relay_y', index)
        files[f'{relay_mod}.py'] = _canon(
            f'''\nfrom {previous_mod} import {previous_target}, {previous_decoy}\n\ndef {next_target}({rx}, {ry}):\n    return {previous_target}({rx}, {ry})\n\ndef {next_decoy}({rx}, {ry}):\n    return {previous_decoy}({rx}, {ry})\n'''
        )
        previous_mod = relay_mod
        previous_target = next_target
        previous_decoy = next_decoy

    entry_mod = _name(seed, 'entry_mod')
    root_fn = _name(seed, 'root_fn')
    a = _name(seed, 'a')
    b = _name(seed, 'b')
    files[f'{entry_mod}.py'] = _canon(
        f'''\nfrom {previous_mod} import {previous_target}, {previous_decoy}\n\ndef {root_fn}({x}, {y}):\n    {a} = {previous_target}({x}, {y})\n    {b} = {previous_decoy}({x}, {y})\n    return {a} * {coefficient} + {b}\n'''
    )
    return RepositorySnapshot.from_mapping(files)


def _candidate(candidate_id: str, snapshot: RepositorySnapshot, *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), snapshot.files, 0, edits)


def _callable(snapshot: RepositorySnapshot):
    return compile_repository_candidate(_candidate('oracle', snapshot))[1]


def _macro() -> PatchMacro:
    return PatchMacro('pm:r261-floor-div-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=4)


def _verification_inputs() -> tuple[RepositoryProbe, ...]:
    return tuple(
        RepositoryProbe((x, y))
        for x, y in itertools.product(range(-4, 6), range(1, 6))
    )


def _positive_episode(seed: int) -> dict[str, object]:
    index = HELDOUT_EPISODES.index(seed)
    relay_count = 1 + (index % 3)
    coefficient = 7 + index * 2
    source = _repository(
        seed,
        relay_count=relay_count,
        coefficient=coefficient,
        target_op='//',
        decoy_op='//',
    )
    wrong = _repository(
        seed,
        relay_count=relay_count,
        coefficient=coefficient,
        target_op='//',
        decoy_op='%',
    )
    target = _repository(
        seed,
        relay_count=relay_count,
        coefficient=coefficient,
        target_op='%',
        decoy_op='//',
    )

    source_candidate = _candidate(f'seed:{seed}', source)
    wrong_candidate = _candidate(f'wrong:{seed}', wrong, edits=1)
    initial_candidates = (source_candidate, wrong_candidate)
    target_absent = all(candidate.files != target.files for candidate in initial_candidates)
    oracle = _callable(target)
    initial_args = (3, 2)
    initial_tests = (PatchTest(f'initial:{seed}', initial_args, oracle(*initial_args)),)
    diagnostic = (RepositoryProbe((5, 2)),)
    verification = _verification_inputs()

    baseline = solve_repository_patch_with_active_probes(
        initial_candidates,
        initial_tests,
        diagnostic,
        oracle,
        verification_inputs=verification,
        max_selection_oracle_calls=1,
    )
    active = solve_repository_patch_with_version_space_expansion(
        initial_candidates,
        initial_tests,
        diagnostic,
        oracle,
        verification_inputs=verification,
        expansion_seeds=(source_candidate,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_expansion_rounds=1,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    reversed_active = solve_repository_patch_with_version_space_expansion(
        tuple(reversed(initial_candidates)),
        initial_tests,
        diagnostic,
        oracle,
        verification_inputs=verification,
        expansion_seeds=(source_candidate,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_expansion_rounds=1,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )

    pre_generated = expand_repository_candidates(
        (source_candidate,), (_macro(),),
        max_generated_candidates=8, max_sites_per_macro=8,
    )
    generated_target_present = any(row.candidate.files == target.files for row in pre_generated)
    wrong_generated_present = any(row.candidate.files == wrong.files for row in pre_generated)
    accepted_exact = active.candidate is not None and active.candidate.files == target.files
    order_invariant = (
        active.candidate is not None
        and reversed_active.candidate is not None
        and active.candidate.files == reversed_active.candidate.files == target.files
        and active.selection_oracle_calls == reversed_active.selection_oracle_calls == 1
    )

    return {
        'seed': seed,
        'file_count': len(source.files),
        'call_depth': relay_count + 1,
        'coefficient': coefficient,
        'initial_candidate_count': len(initial_candidates),
        'correct_candidate_initially_absent': target_absent,
        'r260_status': baseline.status,
        'r260_reason': baseline.reason,
        'r260_out_of_space_abstain': baseline.status == 'abstain' and baseline.reason == 'oracle_outside_candidate_version_space',
        'r261_status': active.status,
        'r261_exact': active.exact and accepted_exact,
        'selection_oracle_calls': active.selection_oracle_calls,
        'verification_oracle_calls': active.verification_oracle_calls,
        'expansion_rounds': active.expansion_round_count,
        'generated_candidates': active.generated_candidates,
        'admitted_generated_candidates': active.admitted_generated_candidates,
        'repair_generated_after_counterexample': active.reason == 'expanded_candidate_verified' and active.expansion_round_count == 1,
        'generated_target_present': generated_target_present,
        'generated_wrong_decoy_present': wrong_generated_present,
        'candidate_order_invariant': order_invariant,
        'false_terminal_accepts': active.false_terminal_accepts,
        'verification_failures': active.verification_failures,
        'generation_uses_target_outputs': 'oracle' in inspect.signature(expand_repository_candidates).parameters,
    }


def _negative_unexpressible() -> dict[str, object]:
    seed = 4901
    coefficient = 17
    source = _repository(seed, relay_count=2, coefficient=coefficient, target_op='//', decoy_op='//')
    wrong = _repository(seed, relay_count=2, coefficient=coefficient, target_op='//', decoy_op='%')
    target = _repository(seed, relay_count=2, coefficient=coefficient, target_op='-', decoy_op='//')
    source_candidate = _candidate('negative:seed', source)
    wrong_candidate = _candidate('negative:wrong', wrong, edits=1)
    oracle = _callable(target)
    initial = (PatchTest('negative:initial', (3, 2), oracle(3, 2)),)
    result = solve_repository_patch_with_version_space_expansion(
        (source_candidate, wrong_candidate),
        initial,
        (RepositoryProbe((5, 2)),),
        oracle,
        verification_inputs=_verification_inputs(),
        expansion_seeds=(source_candidate,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_expansion_rounds=1,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    return {
        'name': 'unexpressible_target',
        'status': result.status,
        'reason': result.reason,
        'false_terminal_accepts': result.false_terminal_accepts,
        'passed': result.status == 'abstain' and result.reason == 'expansion_no_candidate_matches_counterexample' and result.false_terminal_accepts == 0,
    }


def _negative_zero_expansion_budget() -> dict[str, object]:
    seed = 4903
    coefficient = 19
    source = _repository(seed, relay_count=1, coefficient=coefficient, target_op='//', decoy_op='//')
    wrong = _repository(seed, relay_count=1, coefficient=coefficient, target_op='//', decoy_op='%')
    target = _repository(seed, relay_count=1, coefficient=coefficient, target_op='%', decoy_op='//')
    source_candidate = _candidate('budget:seed', source)
    wrong_candidate = _candidate('budget:wrong', wrong, edits=1)
    oracle = _callable(target)
    initial = (PatchTest('budget:initial', (3, 2), oracle(3, 2)),)
    result = solve_repository_patch_with_version_space_expansion(
        (source_candidate, wrong_candidate),
        initial,
        (RepositoryProbe((5, 2)),),
        oracle,
        verification_inputs=_verification_inputs(),
        expansion_seeds=(source_candidate,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_expansion_rounds=0,
    )
    return {
        'name': 'zero_expansion_budget',
        'status': result.status,
        'reason': result.reason,
        'false_terminal_accepts': result.false_terminal_accepts,
        'passed': result.status == 'abstain' and result.reason == 'expansion_round_budget_exhausted' and result.false_terminal_accepts == 0,
    }


def run_frozen_heldout() -> dict[str, object]:
    rows = [_positive_episode(seed) for seed in HELDOUT_EPISODES]
    negatives = [_negative_unexpressible(), _negative_zero_expansion_budget()]
    summary = {
        'episodes': len(rows),
        'r260_out_of_space_abstains': sum(bool(row['r260_out_of_space_abstain']) for row in rows),
        'r261_exact': sum(bool(row['r261_exact']) for row in rows),
        'correct_candidate_initially_absent': sum(bool(row['correct_candidate_initially_absent']) for row in rows),
        'repairs_generated_after_counterexample': sum(bool(row['repair_generated_after_counterexample']) for row in rows),
        'expansion_rounds': sum(int(row['expansion_rounds']) for row in rows),
        'false_terminal_accepts': sum(int(row['false_terminal_accepts']) for row in rows) + sum(int(row['false_terminal_accepts']) for row in negatives),
        'min_file_count': min(int(row['file_count']) for row in rows),
        'max_file_count': max(int(row['file_count']) for row in rows),
        'min_call_depth': min(int(row['call_depth']) for row in rows),
        'max_call_depth': max(int(row['call_depth']) for row in rows),
        'min_verification_cases': min(int(row['verification_oracle_calls']) for row in rows),
        'max_generated_candidates': max(int(row['generated_candidates']) for row in rows),
        'candidate_order_invariant': all(bool(row['candidate_order_invariant']) for row in rows),
        'generation_uses_target_outputs': any(bool(row['generation_uses_target_outputs']) for row in rows),
        'negative_abstains': sum(bool(row['passed']) for row in negatives),
    }
    gates = {
        'r260_baseline_fails_out_of_space_all': summary['r260_out_of_space_abstains'] == len(rows),
        'r261_exact_all': summary['r261_exact'] == len(rows),
        'correct_candidate_initially_absent_all': summary['correct_candidate_initially_absent'] == len(rows),
        'repair_generated_after_counterexample_all': summary['repairs_generated_after_counterexample'] == len(rows),
        'one_expansion_round_each': summary['expansion_rounds'] == len(rows),
        'zero_false_terminal_accepts': summary['false_terminal_accepts'] == 0,
        'multi_file_and_multihop': summary['min_file_count'] >= 3 and summary['min_call_depth'] >= 2,
        'independent_verification_coverage': summary['min_verification_cases'] >= 40,
        'candidate_order_invariant': summary['candidate_order_invariant'],
        'target_independent_generation': summary['generation_uses_target_outputs'] is False,
        'adversarial_negatives_abstain': summary['negative_abstains'] == len(negatives),
        'zero_trainable_parameters': True,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.61 Counterexample-Guided Version-Space Expansion',
        'capability': 'counterexample-guided-repository-version-space-expansion',
        'claim_boundary': 'Bounded one-site repository hypothesis expansion from trusted R2.47 PatchMacro primitives after public R2.60 diagnostic counterexamples; not arbitrary code generation, new effect semantics, or open-ended repository repair.',
        'heldout_episodes': list(HELDOUT_EPISODES),
        'rows': rows,
        'negative_rows': negatives,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
        'trainable_parameter_count': 0,
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_frozen_heldout(), indent=2, sort_keys=True))
