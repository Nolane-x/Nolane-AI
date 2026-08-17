from benchmarks.kfigg.r251_interprocedural_query_transfer import run_frozen_heldout


def test_r251_frozen_interprocedural_transfer():
    result = run_frozen_heldout(); s = result['summary']
    assert result['all_gates_pass'] is True
    assert s['exact'] == 6 and s['false_accepts'] == 0
    assert s['learned_macros'] == 10
    assert s['selected_exact_macro_set'] == 6
    assert s['r250_scope_rejected_episodes'] == 6
    assert s['global_apply_baseline_exact'] == 0
    assert s['direct_essential_patch_exact'] == 6
    assert s['initial_candidates'] == 75
    assert s['max_counterexamples_revealed'] <= 4
    assert s['max_feedback_fraction'] <= 0.01
    assert s['exhaustive_tests_per_episode'] == 2401
    assert s['opaque_identifiers'] is True
    assert s['min_call_depth'] >= 3
