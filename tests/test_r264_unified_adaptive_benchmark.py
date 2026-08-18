from benchmarks.kfigg.r264_unified_adaptive_repository_search import run_benchmark


def test_r264_phase_a_requires_diagnostic_and_refinement_expansion_modes() -> None:
    result = run_benchmark()
    summary = result['summary']
    assert result['all_gates_pass'] is True
    assert summary['episodes'] == 6
    assert summary['r263_initial_out_of_space_abstains'] == 6
    assert summary['r264_exact'] == 6
    assert summary['target_absent_initial'] == 6
    assert summary['target_absent_complete_one_step_space'] == 6
    assert summary['diagnostic_counterexamples'] == 6
    assert summary['refinement_counterexamples'] == 6
    assert summary['two_expansion_rounds'] == 6
    assert summary['public_observations_preserved'] == 6
    assert summary['min_final_verification_cases'] >= 24
    assert summary['negative_abstains'] >= 8
    assert summary['false_terminal_accepts'] == 0
    assert summary['verification_failures_on_positive'] == 0
    assert summary['candidate_order_invariant'] is True
    assert summary['caller_id_invariant'] is True
    assert summary['generation_uses_target_outputs'] is False
    assert result['trainable_parameter_count'] == 0
