from benchmarks.kfigg.r263_compositional_version_space_expansion import run_benchmark


def test_r263_phase_a_causally_requires_two_expansion_steps() -> None:
    result = run_benchmark()
    summary = result['summary']
    assert result['all_gates_pass'] is True
    assert summary['episodes'] == 6
    assert summary['r261_partial_repair_failures'] == 6
    assert summary['r263_exact'] == 6
    assert summary['target_absent_initial'] == 6
    assert summary['target_absent_complete_one_step_space'] == 6
    assert summary['two_expansion_rounds'] == 6
    assert summary['public_observations_preserved'] == 6
    assert summary['min_final_verification_cases'] >= 24
    assert summary['negative_abstains'] >= 5
    assert summary['false_terminal_accepts'] == 0
    assert summary['verification_failures_on_positive'] == 0
    assert summary['candidate_order_invariant'] is True
    assert summary['generation_uses_target_outputs'] is False
    assert result['trainable_parameter_count'] == 0
