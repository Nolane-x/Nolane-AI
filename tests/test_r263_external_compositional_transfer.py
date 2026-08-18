from research.r263_external_compositional_transfer import run_external_transfer


def test_r263_external_square_io_only_transfer_requires_two_repository_edits() -> None:
    result = run_external_transfer(lambda x: x * x, source_id='local.square', source_version='test')
    assert result['passed'] is True
    assert result['milestone'] == 'R2.63'
    assert result['source_exposure'] == 'io_only'
    assert result['source_implementation_inspected'] is False
    assert result['external_function_family'] == 'square'
    assert result['correct_target_absent_initial'] is True
    assert result['correct_target_absent_complete_one_step_space'] is True
    assert result['r261_baseline']['status'] == 'abstain'
    assert result['r261_baseline']['reason'] == 'independent_verification_failed'
    assert result['r263']['status'] == 'accept'
    assert result['r263']['reason'] == 'compositional_candidate_verified'
    assert result['r263']['composition_depth'] == 2
    assert result['r263']['expansion_rounds'] == 2
    assert result['verification_exact'] == result['verification_cases']
    assert result['verification_cases'] >= 40
    assert result['total_external_oracle_calls'] == (
        result['r261_baseline']['oracle_calls'] + result['r263']['oracle_calls']
    )
    assert result['host_authored_exact_candidate'] is False
    assert result['trainable_parameter_count'] == 0
