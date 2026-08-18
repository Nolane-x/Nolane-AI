from benchmarks.kfigg.r263_compositional_repository_repair import run_benchmark


def test_r263_multi_file_benchmark_requires_two_composed_edits() -> None:
    result = run_benchmark()
    summary = result['summary']
    assert result['all_gates_pass'] is True
    assert summary['episodes'] == 6
    assert summary['r261_terminal_verification_abstains'] == 6
    assert summary['r263_exact'] == 6
    assert summary['r263_two_round_repairs'] == 6
    assert summary['r263_two_edit_repairs'] == 6
    assert summary['refinement_counterexamples'] == 12
    assert summary['refinement_oracle_calls'] == 12
    assert summary['final_verification_cases_per_episode'] == 144
    assert summary['final_verification_calls'] == 864
    assert summary['false_terminal_accepts'] == 0
    assert summary['verification_failures'] == 0
    assert summary['target_output_leakage_into_generation'] is False
    assert summary['unique_accepted_content_digests'] == 6
    assert summary['min_file_count'] >= 5
    assert summary['max_call_depth'] >= 4
    assert result['trainable_parameter_count'] == 0
