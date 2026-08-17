from __future__ import annotations

import hashlib

from benchmarks.kfigg.r244_recursive_abstraction_ladder import BASE_MACROS, HELDOUT_EPISODES, learn_stage2_record
from benchmarks.kfigg.r245_role_free_recursive_binding import _role_free_world
from cogcoder.r239_typed_probe_dsl import ProbeType, typed_prediction_row
from cogcoder.r244_recursive_abstraction import flat_unique_binding_count
from cogcoder.r246_sparse_feedback import solve_with_sparse_counterexamples


def _feedback_order(seed: int, test_ids):
    return tuple(sorted(
        map(str, test_ids),
        key=lambda tid: hashlib.sha256(f'r246|{int(seed)}|{tid}'.encode()).hexdigest(),
    ))


def run_heldout_episode(seed: int):
    if int(seed) not in HELDOUT_EPISODES:
        raise ValueError('seed outside frozen R2.46 heldout block')
    stage1, stage2, *_ = learn_stage2_record()
    records = stage1 + (stage2,)
    atoms, _role_atoms, _posterior, values, target = _role_free_world(seed)
    labels = typed_prediction_row(target, values)
    order = _feedback_order(seed, values)
    initial = order[:8]
    receipt = solve_with_sparse_counterexamples(
        stage2.macro.macro_id,
        base_macros=BASE_MACROS,
        records=records,
        atom_ids=atoms,
        atom_values_by_test=values,
        hidden_target_labels=labels,
        initial_test_ids=initial,
        oracle_order=order,
        beam_width=8,
        max_counterexamples=48,
    )
    flat = flat_unique_binding_count(stage2.macro, {ProbeType.BOOL: len(atoms)})
    return {
        'seed': int(seed),
        'exact': receipt.exact,
        'status': receipt.status,
        'initial_tests': receipt.initial_test_count,
        'counterexamples_revealed': receipt.counterexamples_revealed,
        'observed_tests': len(receipt.observed_test_ids),
        'feedback_fraction': receipt.feedback_fraction,
        'rounds': len(receipt.rounds),
        'total_candidates_evaluated': receipt.total_candidates_evaluated,
        'final_hidden_tests_exhaustively_verified': receipt.final_hidden_tests_exhaustively_verified,
        'privileged_role_scopes_used': receipt.privileged_role_scopes_used,
        'flat_unique_bindings': flat,
        'generation': stage2.generation,
        'arity': stage2.macro.arity,
    }


def run_frozen_heldout():
    rows = [run_heldout_episode(seed) for seed in HELDOUT_EPISODES]
    summary = {
        'episodes': len(rows),
        'exact': sum(row['exact'] for row in rows),
        'false_accepts': sum(not row['exact'] for row in rows),
        'initial_tests_per_episode': 8,
        'max_counterexamples_revealed': max(row['counterexamples_revealed'] for row in rows),
        'max_observed_tests': max(row['observed_tests'] for row in rows),
        'max_feedback_fraction': max(row['feedback_fraction'] for row in rows),
        'mean_feedback_fraction': sum(row['feedback_fraction'] for row in rows) / len(rows),
        'max_rounds': max(row['rounds'] for row in rows),
        'max_total_candidates_evaluated': max(row['total_candidates_evaluated'] for row in rows),
        'final_exhaustive_rows_per_episode': min(row['final_hidden_tests_exhaustively_verified'] for row in rows),
        'privileged_role_scopes_used': any(row['privileged_role_scopes_used'] for row in rows),
        'flat_unique_bindings': rows[0]['flat_unique_bindings'],
        'generation': rows[0]['generation'],
        'arity': rows[0]['arity'],
        'feedback_protocol': '8 target-independent anchor tests + one fail-fast counterexample revealed per round; hidden suite only certifies candidate/failure',
    }
    gates = {
        'all_exact': summary['exact'] == summary['episodes'],
        'zero_false_accepts': summary['false_accepts'] == 0,
        'sparse_feedback_at_most_25_percent': summary['max_feedback_fraction'] <= 0.25,
        'counterexamples_at_most_56': summary['max_counterexamples_revealed'] <= 56,
        'final_exhaustive_verification': summary['final_exhaustive_rows_per_episode'] == 256,
        'no_privileged_role_scopes': summary['privileged_role_scopes_used'] is False,
        'recursive_generation_at_least_2': summary['generation'] >= 2,
        'wide_promoted_macro': summary['arity'] >= 8,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.46 Sparse-Feedback Active Counterexample Binding',
        'heldout_episodes': list(HELDOUT_EPISODES),
        'rows': rows,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
    }
