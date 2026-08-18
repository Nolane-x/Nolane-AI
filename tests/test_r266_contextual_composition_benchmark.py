from benchmarks.kfigg.r266_learned_contextual_composition import run_benchmark


def test_r266_authored_contextual_phase_a_passes_all_causal_gates():
    result = run_benchmark()
    assert result['milestone'] == 'R2.66'
    assert result['capability'] == 'learned-contextual-causal-composition'
    assert result['all_gates_pass'] is True
    assert result['configuration_successes'] == result['configurations'] == 3
    assert result['rename_program_id_invariant'] is True
    assert result['argument_permutation_tracks_roles'] is True
    assert result['no_smuggling'] is True
    assert result['both_probes_used'] is True
    assert result['fixed_op_baseline_failures'] == 3
    assert result['singleton_ablation_failures'] == 3
    assert result['selection_exact'] == result['selection_cases']
    assert result['probe_validation_exact'] == result['probe_validation_cases'] * 2
    assert result['final_validation_exact'] == result['final_validation_cases']
    assert result['heldout_exact'] == result['heldout_cases']
    assert result['fixed_op_negative_rejected'] is True
    assert result['budget_negative_rejected'] is True
    assert result['nonfinite_negative_rejected'] is True
    assert result['terminal_contradiction_rejected'] is True
    assert result['false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
