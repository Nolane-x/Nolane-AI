from benchmarks.kfigg.r252_repository_multifile_transfer import run_frozen_heldout


def test_r252_frozen_repository_multifile_transfer():
    result = run_frozen_heldout(); s = result['summary']
    assert result['all_gates_pass'] is True
    assert s['exact'] == 6 and s['false_accepts'] == 0
    assert s['learned_macros'] == 10
    assert s['selected_exact_macro_set'] == 6
    assert s['selected_three_file_transaction'] == 6
    assert s['r251_independent_baseline_exact'] == 0
    assert s['global_apply_baseline_exact'] == 0
    assert s['direct_essential_patch_exact'] == 6
    assert s['initial_candidates'] == 75
    assert s['max_counterexamples_revealed'] <= 2
    assert s['max_observed_tests'] <= 6
    assert s['max_feedback_fraction'] <= 0.003
    assert s['exhaustive_tests_per_episode'] == 2401
    assert s['opaque_identifiers'] is True
    assert s['min_file_count'] == 5 and s['max_file_count'] == 6
    assert s['min_call_depth'] == 4 and s['max_call_depth'] == 5
    assert s['learned_query_patterns'] >= 1
