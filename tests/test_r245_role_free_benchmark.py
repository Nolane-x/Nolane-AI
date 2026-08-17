from benchmarks.kfigg.r245_role_free_recursive_binding import (
    HELDOUT_EPISODES,
    run_frozen_heldout,
    run_heldout_episode,
)


def test_role_free_frozen_heldout_removes_privileged_scopes_and_stays_exact():
    result = run_frozen_heldout()
    assert result['all_gates_pass'], result
    s = result['summary']
    assert s['episodes'] == len(HELDOUT_EPISODES) == 6
    assert s['exact'] == 6
    assert s['false_accepts'] == 0
    assert s['privileged_role_scopes_used'] is False
    assert s['shared_atom_count'] == 8
    assert s['opaque_atom_ids'] is True
    assert s['role_permutation_scrambled'] is True
    assert s['base_bindings_evaluated'] == 224
    assert s['max_candidates_evaluated'] <= 1068
    assert s['flat_unique_bindings'] == 40320
    assert s['min_binding_contraction'] >= 35.0
    assert s['exhaustive_truth_table_rows_per_episode'] == 256


def test_role_free_result_is_stable_under_atom_renaming():
    first = run_heldout_episode(HELDOUT_EPISODES[0])
    last = run_heldout_episode(HELDOUT_EPISODES[-1])
    assert first['exact'] and last['exact']
    assert first['stage2_macro_id'] == last['stage2_macro_id']
    assert first['base_bindings_evaluated'] == last['base_bindings_evaluated'] == 224
    assert first['privileged_role_scopes_used'] is False
    assert last['privileged_role_scopes_used'] is False
