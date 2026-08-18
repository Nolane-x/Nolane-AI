from research.r263_external_subtract_transfer import run_external_subtract_transfer


def test_r263_external_subtract_io_only_transfer_composes_two_refinement_edits() -> None:
    result = run_external_subtract_transfer(lambda x, y: x - y, source_id='local.subtract', source_version='test')
    assert result['passed'] is True
    assert result['milestone'] == 'R2.63'
    assert result['source_exposure'] == 'io_only'
    assert result['source_implementation_inspected'] is False
    assert result['external_function_family'] == 'binary_subtract_composed_twice'
    assert result['correct_target_absent_initial'] is True
    assert result['correct_target_absent_complete_one_step_space'] is True
    assert result['exact_target_supplied_to_solver'] is False
    assert result['r261_baseline']['status'] == 'abstain'
    assert result['r261_baseline']['reason'] == 'independent_verification_failed'
    assert result['r261_baseline']['expansion_rounds'] == 0
    assert result['r263']['status'] == 'accept'
    assert result['r263']['reason'] == 'compositional_candidate_verified'
    assert result['r263']['composition_depth'] == 2
    assert result['r263']['expansion_rounds'] == 2
    assert result['r263']['refinement_counterexamples'] == 2
    assert result['r263']['accepted_edit_count'] == 2
    assert len(result['r263']['accepted_mutation_chain']) == 2
    assert len(set(result['r263']['accepted_mutation_chain'])) == 2
    assert result['r263']['generation_used_target_outputs'] is False
    assert result['verification_exact'] == result['verification_cases'] == 256
    assert result['total_external_oracle_calls'] == (
        result['initial_label_oracle_calls']
        + result['r261_baseline']['oracle_calls']
        + result['r263']['oracle_calls']
    )
    assert result['host_authored_exact_candidate'] is False
    assert result['trainable_parameter_count'] == 0
