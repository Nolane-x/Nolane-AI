from research.r265_external_patch_primitive_transfer import run_external_transfer


def test_r265_external_numpy_multiply_induces_add_to_mult_primitive() -> None:
    result = run_external_transfer(lambda x, y: x * y, source_id='local.multiply', source_version='test')
    assert result['passed'] is True
    assert result['milestone'] == 'R2.65'
    assert result['source_exposure'] == 'io_only'
    assert result['source_implementation_inspected'] is False
    assert result['external_function_family'] == 'binary_multiply'
    assert result['exact_patch_macro_supplied'] is False
    assert result['correct_target_absent_initial'] is True
    assert result['r264_baseline']['status'] == 'abstain'
    assert result['r264_baseline']['reason'] == 'no_expansion_macros'
    assert result['r265']['status'] == 'accept'
    assert result['r265']['reason'] == 'induced_patch_primitive_verified'
    assert result['r265']['primitive_promoted'] is True
    assert result['r265']['learned_source_value'] == 'Add'
    assert result['r265']['learned_target_value'] == 'Mult'
    assert result['r265']['independent_challenges_passed'] == 8
    assert result['r265']['generation_used_target_outputs'] is False
    assert result['r265']['false_terminal_accepts'] == 0
    assert result['r265']['verification_failures'] == 0
    assert result['verification_exact'] == result['verification_cases'] == 225
    assert result['total_external_oracle_calls'] == (
        result['r264_baseline']['oracle_calls'] + result['r265']['oracle_calls']
    )
    assert result['host_authored_exact_candidate'] is False
    assert result['trainable_parameter_count'] == 0
