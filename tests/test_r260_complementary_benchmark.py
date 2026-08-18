from benchmarks.kfigg.r260_complementary_experiment_program import run_benchmark


def test_r260_frozen_complementary_program_benchmark_contract():
    result = run_benchmark()
    assert result['milestone'] == 'R2.60'
    assert result['capability'] == 'complementary-causal-experiment-program'
    assert result['configurations'] == 3
    assert result['discoveries'] == 3
    assert result['flat_baseline_failures'] == 3
    assert result['full_program_successes'] == 3
    assert result['proper_subset_failures'] == 6
    assert result['validation_exact'] == result['validation_cases']
    assert result['challenge_exact'] == result['challenge_cases']
    assert result['rename_program_id_invariant'] is True
    assert result['argument_permutation_tracks_roles'] is True
    assert result['matched_synthesis_budget_respected'] is True
    assert result['wrong_pair_false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
    assert 'not open-ended' in result['claim_boundary']
