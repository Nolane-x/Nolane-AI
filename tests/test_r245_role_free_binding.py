import itertools

from benchmarks.kfigg.r244_recursive_abstraction_ladder import BASE_MACROS, learn_stage2_record
from cogcoder.r245_role_free_binding import (
    binary_mutual_information,
    solve_role_free_recursive_macro,
)


def _world(atom_ids):
    assignments = tuple(itertools.product((False, True), repeat=len(atom_ids)))
    values = {
        f'h{i:03d}': {atom: bit for atom, bit in zip(atom_ids, bits)}
        for i, bits in enumerate(assignments)
    }
    posterior = {hid: 1.0 / len(values) for hid in values}
    return posterior, values


def test_mutual_information_detects_dependence_and_is_zero_for_independent_bits():
    posterior, values = _world(('a', 'b'))
    target = {h: bool(v['a']) for h, v in values.items()}
    same = dict(target)
    independent = {h: bool(v['b']) for h, v in values.items()}
    assert binary_mutual_information(same, target, posterior) == 1.0
    assert binary_mutual_information(independent, target, posterior) == 0.0


def test_role_free_solver_gives_every_base_macro_the_same_full_atom_pool():
    stage1, stage2, *_ = learn_stage2_record()
    records = stage1 + (stage2,)
    atoms = tuple(f'v{i}' for i in range(8))
    posterior, values = _world(atoms)
    target_labels = {h: bool(v['v0']) == bool(v['v7']) for h, v in values.items()}
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
    assert receipt.shared_atom_count == 8
    assert receipt.base_macro_count == len(BASE_MACROS)
    assert receipt.base_bindings_evaluated == 4 * 8 * 7
    assert receipt.privileged_role_scopes_used is False


def test_role_free_solver_respects_ancestor_quarantine():
    stage1, stage2, *_ = learn_stage2_record()
    records = stage1 + (stage2,)
    atoms = tuple(f'q{i}' for i in range(8))
    posterior, values = _world(atoms)
    target_labels = {h: bool(v['q0']) for h, v in values.items()}
    blocked = stage1[0].parent_macro_ids[0]
    receipt = solve_role_free_recursive_macro(
        stage2.macro.macro_id,
        base_macros=BASE_MACROS,
        records=records,
        atom_ids=atoms,
        posterior=posterior,
        atom_values_by_hypothesis=values,
        target_labels=target_labels,
        blocked_macro_ids=(blocked,),
        beam_width=8,
    )
    assert receipt.status == 'blocked'
    assert receipt.program is None
    assert stage2.macro.macro_id in receipt.blocked_closure
