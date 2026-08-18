from benchmarks.kfigg.r264_learned_contextual_composition import run_benchmark


def test_r264_benchmark_requires_contextual_composition_and_preserves_invariance():
    result = run_benchmark()
    assert result['milestone'] == 'R2.64'
    assert result['capability'] == 'learned-contextual-causal-composition'
    assert result['configurations'] == 3
    assert result['discoveries'] == 3
    assert result['full_program_successes'] == 3
    assert result['r262_fixed_op_failures'] == 3
    assert result['singleton_composition_failures'] == 6
    assert result['selection_exact'] == result['selection_cases']
    assert result['probe_validation_exact'] == result['probe_validation_cases'] * 2
    assert result['final_validation_exact'] == result['final_validation_cases']
    assert result['heldout_exact'] == result['heldout_cases']
    assert result['rename_program_id_invariant'] is True
    assert result['argument_permutation_tracks_roles'] is True
    assert result['shared_context_only'] is True
    assert result['both_probes_used'] is True
    assert result['fixed_op_negative_rejected'] is True
    assert result['depth_zero_negative_rejected'] is True
    assert result['budget_negative_rejected'] is True
    assert result['nonfinite_negative_rejected'] is True
    assert result['terminal_contradiction_rejected'] is True
    assert result['false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
    assert 'not open-ended' in result['claim_boundary']
