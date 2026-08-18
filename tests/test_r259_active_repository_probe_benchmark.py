from benchmarks.kfigg.r259_active_repository_probe_transfer import run_frozen_heldout


def test_r259_frozen_active_repository_probe_transfer():
    result = run_frozen_heldout()
    summary = result['summary']

    assert result['milestone'] == 'R2.59 Active Diagnostic Repository Probe Synthesis'
    assert result['all_gates_pass'] is True
    assert summary['episodes'] == 6
    assert summary['active_exact'] == 6
    assert summary['active_false_accepts'] == 0
    assert summary['active_selected_exact_macro_set'] == 6
    assert summary['active_one_selection_query'] == 6
    assert summary['active_max_selection_oracle_calls'] == 1
    assert summary['active_full_verification_cases'] == 2401
    assert summary['random_one_probe_exact'] == 1
    assert summary['random_one_probe_false_accepts'] == 0
    assert summary['passive_initial_only_exact'] == 0
    assert summary['passive_initial_only_false_accepts'] == 0
    assert summary['active_gain_over_random'] == 5
    assert summary['initial_candidates'] == 75
    assert summary['min_initial_survivors'] >= 2
    assert summary['max_initial_survivors'] >= 4
    assert summary['zero_trainable_parameters'] is True
    assert summary['probe_generation_uses_target_outputs'] is False
    assert summary['candidate_identity_invariant'] is True
    assert 'not general repository coding' in result['claim_boundary']
