from __future__ import annotations

import itertools

from cogcoder.r239_predicate_macros import ProbeMacro
from cogcoder.r239_typed_probe_dsl import (
    ProbeType,
    and_probe,
    bool_atom,
    equiv_probe,
    evaluate_typed_probe,
    or_probe,
    typed_prediction_row,
    xor_probe,
)
from cogcoder.r244_recursive_abstraction import (
    build_recursive_application_frontier,
    discover_recursive_composed_probe,
    flat_unique_binding_count,
    promote_composition_batch,
)

TRAIN_STAGE1_EPISODES = (1101, 1103, 1109)
TRAIN_STAGE2_EPISODES = (1201, 1213, 1217)
HELDOUT_EPISODES = (1301, 1303, 1307, 1319, 1321, 1327)


def _macro(mid, op):
    template = op(bool_atom('$p0'), bool_atom('$p1'))
    return ProbeMacro(mid, template, (ProbeType.BOOL, ProbeType.BOOL), 8, 6.0, template.mdl_cost, 2)


BASE_MACROS = (
    _macro('r244:base:and', and_probe),
    _macro('r244:base:or', or_probe),
    _macro('r244:base:xor', xor_probe),
    _macro('r244:base:equiv', equiv_probe),
)


def _atom_ids(seed: int):
    return tuple(f'r244:e{int(seed)}:v{i}' for i in range(8))


def _world(seed: int):
    atoms = _atom_ids(seed)
    assignments = tuple(itertools.product((False, True), repeat=len(atoms)))
    values = {
        f'r244h:{seed}:{i:03d}': {atom: bit for atom, bit in zip(atoms, bits)}
        for i, bits in enumerate(assignments)
    }
    posterior = {hid: 1.0 / len(values) for hid in values}
    a, b, c, d, e, f, g, h = map(bool_atom, atoms)
    g1a = xor_probe(and_probe(a, b), or_probe(c, d))
    g1b = and_probe(xor_probe(e, f), equiv_probe(g, h))
    g2 = equiv_probe(g1a, g1b)
    pools = {
        'r244:base:and': {ProbeType.BOOL: atoms[0:2]},
        'r244:base:or': {ProbeType.BOOL: atoms[2:4]},
        'r244:base:xor': {ProbeType.BOOL: atoms[4:6]},
        'r244:base:equiv': {ProbeType.BOOL: atoms[6:8]},
    }
    return atoms, posterior, values, pools, g1a, g1b, g2


def _exact_counterexample_check(target, values):
    target_row = typed_prediction_row(target, values)
    return lambda program: typed_prediction_row(program, values) == target_row


def learn_stage1_records():
    decisions_a = {}
    decisions_b = {}
    for seed in TRAIN_STAGE1_EPISODES:
        _, posterior, values, pools, g1a, g1b, _ = _world(seed)
        decisions_a[str(seed)] = discover_recursive_composed_probe(
            base_macros=BASE_MACROS, records=(), atom_pools_by_macro=pools,
            posterior=posterior, atom_values_by_hypothesis=values,
            min_conditional_novelty=0.02, max_composition_candidates=128,
            counterexample_check=_exact_counterexample_check(g1a, values),
        )
        decisions_b[str(seed)] = discover_recursive_composed_probe(
            base_macros=BASE_MACROS, records=(), atom_pools_by_macro=pools,
            posterior=posterior, atom_values_by_hypothesis=values,
            min_conditional_novelty=0.02, max_composition_candidates=128,
            counterexample_check=_exact_counterexample_check(g1b, values),
        )
    promoted_a = promote_composition_batch(decisions_a, base_macros=BASE_MACROS, min_support=3)
    promoted_b = promote_composition_batch(decisions_b, base_macros=BASE_MACROS, min_support=3)
    if len(promoted_a) != 1 or len(promoted_b) != 1:
        raise AssertionError('stage1 promotion failed')
    return promoted_a + promoted_b, decisions_a, decisions_b


def learn_stage2_record():
    stage1, decisions_a, decisions_b = learn_stage1_records()
    decisions = {}
    for seed in TRAIN_STAGE2_EPISODES:
        _, posterior, values, pools, _, _, g2 = _world(seed)
        decisions[str(seed)] = discover_recursive_composed_probe(
            base_macros=BASE_MACROS, records=stage1, atom_pools_by_macro=pools,
            posterior=posterior, atom_values_by_hypothesis=values,
            min_conditional_novelty=0.02, max_composition_candidates=256,
            counterexample_check=_exact_counterexample_check(g2, values),
        )
    promoted = promote_composition_batch(
        decisions, base_macros=BASE_MACROS, prior_records=stage1, min_support=3,
    )
    if len(promoted) != 1:
        raise AssertionError('stage2 promotion failed')
    return stage1, promoted[0], decisions, decisions_a, decisions_b


def run_heldout_episode(seed: int):
    if int(seed) not in HELDOUT_EPISODES:
        raise ValueError('seed outside frozen R2.44 heldout block')
    stage1, stage2, _, _, _ = learn_stage2_record()
    atoms, posterior, values, pools, _, _, target = _world(seed)
    all_records = stage1 + (stage2,)
    receipt = build_recursive_application_frontier(
        stage2.macro.macro_id,
        base_macros=BASE_MACROS, records=all_records,
        atom_pools_by_macro=pools, posterior=posterior,
        atom_values_by_hypothesis=values, max_applications_per_node=8,
    )
    target_row = typed_prediction_row(target, values)
    exact = [app for app in receipt.applications if typed_prediction_row(app.program, values) == target_row]
    exact_rows = 0
    if exact:
        chosen = exact[0].program
        for assignment in values.values():
            if bool(evaluate_typed_probe(chosen, assignment)) == bool(evaluate_typed_probe(target, assignment)):
                exact_rows += 1
    flat_bindings = flat_unique_binding_count(stage2.macro, {ProbeType.BOOL: len(atoms)})
    return {
        'seed': int(seed),
        'exact': bool(exact) and exact_rows == len(values),
        'exhaustive_rows': len(values),
        'exact_rows': exact_rows,
        'generation': stage2.generation,
        'stage2_arity': stage2.macro.arity,
        'recursive_candidates_evaluated': receipt.candidates_evaluated,
        'base_bindings_evaluated': receipt.base_bindings_evaluated,
        'recursive_pairs_evaluated': receipt.recursive_pairs_evaluated,
        'flat_unique_bindings': flat_bindings,
        'binding_contraction': (float(flat_bindings) / receipt.candidates_evaluated) if receipt.candidates_evaluated else 0.0,
        'stage1_macro_ids': [r.macro.macro_id for r in stage1],
        'stage2_macro_id': stage2.macro.macro_id,
        'stage2_ancestors': list(stage2.ancestor_macro_ids),
    }


def run_frozen_heldout():
    stage1, stage2, stage2_decisions, stage1a, stage1b = learn_stage2_record()
    rows = [run_heldout_episode(seed) for seed in HELDOUT_EPISODES]
    stage1_novelty = [d.conditional_novelty for d in list(stage1a.values()) + list(stage1b.values())]
    stage2_novelty = [d.conditional_novelty for d in stage2_decisions.values()]
    summary = {
        'episodes': len(rows),
        'exact': sum(row['exact'] for row in rows),
        'false_accepts': sum(not row['exact'] for row in rows),
        'generation': stage2.generation,
        'arity': stage2.macro.arity,
        'min_stage1_conditional_novelty': min(stage1_novelty),
        'min_stage2_conditional_novelty': min(stage2_novelty),
        'max_recursive_candidates': max(row['recursive_candidates_evaluated'] for row in rows),
        'flat_unique_bindings': rows[0]['flat_unique_bindings'],
        'min_binding_contraction': min(row['binding_contraction'] for row in rows),
        'renamed_atoms_per_episode': True,
        'exhaustive_truth_table_rows_per_episode': rows[0]['exhaustive_rows'],
    }
    gates = {
        'all_exact': summary['exact'] == summary['episodes'],
        'zero_false_accepts': summary['false_accepts'] == 0,
        'recursive_generation_at_least_2': summary['generation'] >= 2,
        'wide_promoted_macro': summary['arity'] >= 8,
        'conditional_novelty_positive_stage1': summary['min_stage1_conditional_novelty'] >= 0.02,
        'conditional_novelty_positive_stage2': summary['min_stage2_conditional_novelty'] >= 0.02,
        'binding_contraction_over_1000x': summary['min_binding_contraction'] >= 1000.0,
        'renamed_atoms': summary['renamed_atoms_per_episode'],
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.44 Recursive Abstraction Ladder',
        'train_stage1_episodes': list(TRAIN_STAGE1_EPISODES),
        'train_stage2_episodes': list(TRAIN_STAGE2_EPISODES),
        'heldout_episodes': list(HELDOUT_EPISODES),
        'stage1_records': [
            {
                'macro_id': r.macro.macro_id,
                'generation': r.generation,
                'connective': r.connective,
                'arity': r.macro.arity,
                'parents': list(r.parent_macro_ids),
                'ancestors': list(r.ancestor_macro_ids),
                'support': len(r.support_episode_ids),
                'mean_novelty': r.mean_novelty,
            }
            for r in stage1
        ],
        'stage2_record': {
            'macro_id': stage2.macro.macro_id,
            'generation': stage2.generation,
            'connective': stage2.connective,
            'arity': stage2.macro.arity,
            'parents': list(stage2.parent_macro_ids),
            'ancestors': list(stage2.ancestor_macro_ids),
            'support': len(stage2.support_episode_ids),
            'mean_novelty': stage2.mean_novelty,
        },
        'rows': rows,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
    }
