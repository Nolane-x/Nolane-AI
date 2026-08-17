from __future__ import annotations

import hashlib
import itertools
import random
import re

from benchmarks.kfigg.r244_recursive_abstraction_ladder import (
    BASE_MACROS,
    HELDOUT_EPISODES,
    learn_stage2_record,
)
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
from cogcoder.r244_recursive_abstraction import flat_unique_binding_count
from cogcoder.r245_role_free_binding import solve_role_free_recursive_macro


def _opaque_atom(seed: int, slot: int) -> str:
    digest = hashlib.sha256(f"r245|{int(seed)}|{int(slot)}".encode()).hexdigest()[:14]
    return f"r245:a:{digest}"


def _role_free_world(seed: int):
    atoms = tuple(_opaque_atom(seed, i) for i in range(8))
    role_atoms = list(atoms)
    random.Random(int(seed) ^ 0x524F4C45).shuffle(role_atoms)
    assignments = tuple(itertools.product((False, True), repeat=len(atoms)))
    values = {
        f"r245h:{seed}:{i:03d}": {atom: bit for atom, bit in zip(atoms, bits)}
        for i, bits in enumerate(assignments)
    }
    posterior = {hid: 1.0 / len(values) for hid in values}
    a, b, c, d, e, f, g, h = map(bool_atom, role_atoms)
    g1a = xor_probe(and_probe(a, b), or_probe(c, d))
    g1b = and_probe(xor_probe(e, f), equiv_probe(g, h))
    target = equiv_probe(g1a, g1b)
    return atoms, tuple(role_atoms), posterior, values, target


def run_heldout_episode(seed: int):
    if int(seed) not in HELDOUT_EPISODES:
        raise ValueError('seed outside frozen R2.45 heldout block')
    stage1, stage2, *_ = learn_stage2_record()
    records = stage1 + (stage2,)
    atoms, role_atoms, posterior, values, target = _role_free_world(seed)
    target_labels = typed_prediction_row(target, values)
    receipt = solve_role_free_recursive_macro(
        stage2.macro.macro_id,
        base_macros=BASE_MACROS,
        records=records,
        atom_ids=atoms,
        posterior=posterior,
        atom_values_by_hypothesis=values,
        target_labels=target_labels,
        beam_width=8,
    )
    exact_rows = 0
    if receipt.program is not None:
        for assignment in values.values():
            if bool(evaluate_typed_probe(receipt.program, assignment)) == bool(evaluate_typed_probe(target, assignment)):
                exact_rows += 1
    flat = flat_unique_binding_count(stage2.macro, {ProbeType.BOOL: len(atoms)})
    return {
        'seed': int(seed),
        'exact': receipt.exact and exact_rows == len(values),
        'exact_rows': exact_rows,
        'exhaustive_rows': len(values),
        'stage2_macro_id': stage2.macro.macro_id,
        'generation': stage2.generation,
        'arity': stage2.macro.arity,
        'shared_atom_count': receipt.shared_atom_count,
        'base_macro_count': receipt.base_macro_count,
        'privileged_role_scopes_used': receipt.privileged_role_scopes_used,
        'opaque_atom_ids': all(re.fullmatch(r'r245:a:[0-9a-f]{14}', atom) is not None for atom in atoms),
        'role_permutation_scrambled': tuple(atoms) != tuple(role_atoms),
        'beam_width': receipt.beam_width,
        'base_bindings_evaluated': receipt.base_bindings_evaluated,
        'recursive_pairs_evaluated': receipt.recursive_pairs_evaluated,
        'candidates_evaluated': receipt.candidates_evaluated,
        'flat_unique_bindings': flat,
        'binding_contraction': float(flat) / receipt.candidates_evaluated,
        'frontier_sizes': list(receipt.frontier_sizes),
    }


def run_frozen_heldout():
    rows = [run_heldout_episode(seed) for seed in HELDOUT_EPISODES]
    summary = {
        'episodes': len(rows),
        'exact': sum(row['exact'] for row in rows),
        'false_accepts': sum(not row['exact'] for row in rows),
        'generation': rows[0]['generation'],
        'arity': rows[0]['arity'],
        'shared_atom_count': rows[0]['shared_atom_count'],
        'base_macro_count': rows[0]['base_macro_count'],
        'privileged_role_scopes_used': any(row['privileged_role_scopes_used'] for row in rows),
        'opaque_atom_ids': all(row['opaque_atom_ids'] for row in rows),
        'role_permutation_scrambled': all(row['role_permutation_scrambled'] for row in rows),
        'base_bindings_evaluated': rows[0]['base_bindings_evaluated'],
        'max_candidates_evaluated': max(row['candidates_evaluated'] for row in rows),
        'min_binding_contraction': min(row['binding_contraction'] for row in rows),
        'flat_unique_bindings': rows[0]['flat_unique_bindings'],
        'exhaustive_truth_table_rows_per_episode': rows[0]['exhaustive_rows'],
        'target_feedback': 'observable truth-table/test labels only',
    }
    gates = {
        'all_exact': summary['exact'] == summary['episodes'],
        'zero_false_accepts': summary['false_accepts'] == 0,
        'no_privileged_role_scopes': summary['privileged_role_scopes_used'] is False,
        'opaque_atom_ids': summary['opaque_atom_ids'],
        'role_permutation_scrambled': summary['role_permutation_scrambled'],
        'all_base_macros_share_all_atoms': summary['base_bindings_evaluated'] == 4 * 8 * 7,
        'recursive_generation_at_least_2': summary['generation'] >= 2,
        'wide_promoted_macro': summary['arity'] >= 8,
        'binding_contraction_over_35x': summary['min_binding_contraction'] >= 35.0,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.45 Role-Free Goal-Directed Recursive Binding',
        'heldout_episodes': list(HELDOUT_EPISODES),
        'rows': rows,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
    }
