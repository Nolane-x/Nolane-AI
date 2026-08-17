from benchmarks.kfigg.r244_recursive_abstraction_ladder import (
    HELDOUT_EPISODES,
    learn_stage2_record,
    run_frozen_heldout,
    run_heldout_episode,
)


def test_recursive_ladder_promotes_two_generations_with_full_lineage():
    stage1, stage2, _, _, _ = learn_stage2_record()
    assert len(stage1) == 2
    assert all(r.generation == 1 for r in stage1)
    assert stage2.generation == 2
    assert stage2.macro.arity == 8
    assert set(stage2.parent_macro_ids) == {r.macro.macro_id for r in stage1}
    assert len(stage2.ancestor_macro_ids) >= 6


def test_frozen_heldout_is_exhaustive_exact_and_contracts_flat_binding_search():
    result = run_frozen_heldout()
    assert result['all_gates_pass'], result
    s = result['summary']
    assert s['exact'] == len(HELDOUT_EPISODES)
    assert s['false_accepts'] == 0
    assert s['exhaustive_truth_table_rows_per_episode'] == 256
    assert s['flat_unique_bindings'] == 40320
    assert s['max_recursive_candidates'] <= 11
    assert s['min_binding_contraction'] >= 1000.0


def test_heldout_atom_renaming_does_not_change_structural_solution():
    a = run_heldout_episode(HELDOUT_EPISODES[0])
    b = run_heldout_episode(HELDOUT_EPISODES[-1])
    assert a['exact'] and b['exact']
    assert a['stage2_macro_id'] == b['stage2_macro_id']
    assert a['recursive_candidates_evaluated'] == b['recursive_candidates_evaluated']
    assert a['stage2_ancestors'] == b['stage2_ancestors']
