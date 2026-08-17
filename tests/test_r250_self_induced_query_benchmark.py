from benchmarks.kfigg.r250_self_induced_query_transfer import run_frozen_heldout


def test_r250_frozen_self_induced_query_transfer():
    result = run_frozen_heldout()
    assert result['all_gates_pass'] is True
    summary = result['summary']
    assert summary['episodes'] == 6
    assert summary['exact'] == 6
    assert summary['false_accepts'] == 0
    assert summary['learned_macros'] == 10
    assert summary['selected_exact_macro_set'] == 6
    assert summary['r249_feature_collision_episodes'] == 6
    assert summary['r249_baseline_exact'] == 0
    assert summary['global_apply_baseline_exact'] == 0
    assert summary['initial_candidates'] == 75
    assert summary['initial_tests_per_episode'] == 4
    assert summary['max_feedback_fraction'] <= 0.01
    assert summary['exhaustive_tests_per_episode'] == 2401
    assert summary['opaque_identifiers'] is True
    assert summary['raw_identifier_leaks'] == 0
    assert summary['learned_query_patterns'] >= 2


def test_r250_frozen_evidence_is_deterministic():
    a = run_frozen_heldout()
    b = run_frozen_heldout()
    assert a['summary'] == b['summary']
    assert a['rows'] == b['rows']
