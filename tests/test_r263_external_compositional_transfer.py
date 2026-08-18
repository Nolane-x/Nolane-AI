from research.r263_external_compositional_transfer import run_external_transfer


def _subtract(x, y):
    return int(x) - int(y)


def test_r263_external_harness_requires_two_repository_edits() -> None:
    result = run_external_transfer(
        _subtract,
        source_id='local-test:subtract',
        source_version='test-pin',
    )
    assert result['milestone'] == 'R2.63'
    assert result['passed'] is True
    assert result['source_exposure'] == 'io_only'
    assert result['initial_candidate_count'] == 1
    assert result['r261_status'] == 'abstain'
    assert result['r261_reason'] == 'independent_verification_failed'
    assert result['r263_status'] == 'accept'
    assert result['r263_expansion_rounds'] == 2
    assert result['r263_refinement_counterexamples'] == 2
    assert result['r263_accepted_edit_count'] == 2
    assert result['r263_mutation_chain_length'] == 2
    assert result['r263_generation_used_target_outputs'] is False
    assert result['r263_false_terminal_accepts'] == 0
    assert result['verification_exact'] == result['verification_cases'] == 256
    assert result['trainable_parameter_count'] == 0
