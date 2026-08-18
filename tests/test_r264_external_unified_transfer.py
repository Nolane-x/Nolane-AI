from research.r264_external_unified_transfer import run_external_transfer


def test_r264_external_square_requires_diagnostic_escape_then_refinement_composition() -> None:
    result = run_external_transfer(lambda x: x * x, source_id='local.square', source_version='test')
    assert result['passed'] is True
    assert result['milestone'] == 'R2.64'
    assert result['source_exposure'] == 'io_only'
    assert result['source_implementation_inspected'] is False
    assert result['external_function_family'] == 'square'
    assert result['correct_target_absent_initial'] is True
    assert result['correct_target_absent_complete_one_step_space'] is True
    assert result['exact_target_supplied_to_solver'] is False
    assert result['r263_baseline']['status'] == 'abstain'
    assert result['r263_baseline']['reason'] == 'oracle_outside_initial_candidate_version_space'
    assert result['r263_baseline']['expansion_rounds'] == 0
    assert result['r264']['status'] == 'accept'
    assert result['r264']['reason'] == 'unified_candidate_verified'
    assert result['r264']['diagnostic_counterexamples'] == 1
    assert result['r264']['refinement_counterexamples'] == 1
    assert result['r264']['composition_depth'] == 2
    assert result['r264']['expansion_rounds'] == 2
    assert result['r264']['accepted_edit_count'] == 2
    assert len(result['r264']['accepted_mutation_chain']) == 2
    assert len(set(result['r264']['accepted_mutation_chain'])) == 2
    assert result['r264']['generation_used_target_outputs'] is False
    assert result['r264']['false_terminal_accepts'] == 0
    assert result['r264']['verification_failures'] == 0
    assert result['verification_exact'] == result['verification_cases'] == 46
    assert result['total_external_oracle_calls'] == (
        result['r263_baseline']['oracle_calls'] + result['r264']['oracle_calls']
    )
    assert result['host_authored_exact_candidate'] is False
    assert result['trainable_parameter_count'] == 0
