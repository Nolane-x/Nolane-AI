from benchmarks.kfigg.r247_executable_patch_transfer import (
    HELDOUT_EPISODES,
    learn_r247_library,
    run_frozen_heldout,
    run_heldout_episode,
)


def test_training_library_contains_multiple_competing_edit_families():
    library = learn_r247_library()
    assert len(library) == 13
    assert all(m.support == 2 for m in library)
    assert {m.slot for m in library} == {'binop', 'operand_wrapper', 'compare', 'return_wrapper'}


def test_executable_patch_transfer_is_exact_with_sparse_counterexamples():
    result = run_frozen_heldout()
    assert result['all_gates_pass'], result
    s = result['summary']
    assert s['episodes'] == len(HELDOUT_EPISODES) == 6
    assert s['exact'] == 6
    assert s['false_accepts'] == 0
    assert s['learned_macros'] == 13
    assert s['initial_candidates'] >= 100
    assert s['essential_macro_count'] == 3
    assert s['selected_exact_macro_set'] == 6
    assert s['max_feedback_fraction'] <= 0.05
    assert s['exhaustive_tests_per_episode'] == s['test_suite_size'] == 729


def test_renamed_heldout_programs_select_same_abstract_patch_set():
    first = run_heldout_episode(HELDOUT_EPISODES[0])
    last = run_heldout_episode(HELDOUT_EPISODES[-1])
    assert first['exact'] and last['exact']
    assert set(first['selected_macro_ids']) == set(first['essential_macro_ids'])
    assert set(last['selected_macro_ids']) == set(last['essential_macro_ids'])
    assert set(first['selected_macro_ids']) == set(last['selected_macro_ids'])
