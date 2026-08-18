from benchmarks.kfigg.r262_complementary_experiment_program import run_benchmark


def test_r262_complementary_benchmark_is_exact_and_causal() -> None:
    result = run_benchmark()
    assert result['milestone'] == 'R2.62'
    assert result['discoveries'] == result['configurations'] == 3
    assert result['flat_baseline_failures'] == 3
    assert result['full_program_successes'] == 3
    assert result['proper_subset_failures'] == 6
    assert result['validation_exact'] == result['validation_cases'] == 30
    assert result['challenge_exact'] == result['challenge_cases'] == 24
    assert result['rename_program_id_invariant'] is True
    assert result['argument_permutation_tracks_roles'] is True
    assert result['matched_synthesis_budget_respected'] is True
    assert result['flat_baseline_candidates_total'] == 30000
    assert result['probe_synthesis_candidates_total'] == 14136
    assert result['wrong_pair_false_accepts'] == 0
    assert result['composition_ops'] == ['add']
    assert result['trainable_parameter_count'] == 0
