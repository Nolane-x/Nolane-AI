from benchmarks.kfigg.r265_patch_primitive_induction import run_benchmark


def test_r265_phase_a_learns_missing_repository_patch_primitives() -> None:
    result = run_benchmark()
    summary = result['summary']
    assert result['all_gates_pass'] is True
    assert summary['episodes'] == 6
    assert summary['r264_missing_macro_abstains'] == 6
    assert summary['r265_exact'] == 6
    assert summary['learned_expected_primitive'] == 6
    assert summary['primitive_promoted'] == 6
    assert summary['min_independent_challenges'] >= 4
    assert summary['min_final_verification_cases'] >= 24
    assert summary['target_absent_initial'] == 6
    assert summary['connected_decoy_present'] == 6
    assert summary['caller_id_invariant'] is True
    assert summary['candidate_order_invariant'] is True
    assert summary['enumeration_uses_target_outputs'] is False
    assert summary['negative_abstains'] >= 8
    assert summary['false_terminal_accepts'] == 0
    assert summary['positive_verification_failures'] == 0
    assert result['trainable_parameter_count'] == 0
