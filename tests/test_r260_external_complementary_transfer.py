from research.r260_external_complementary_transfer import run_external_transfer


def _deadzone(x, low, high):
    x = float(x)
    low = float(low)
    high = float(high)
    if x < low:
        return x - low
    if x > high:
        return x - high
    return 0.0


def test_r260_external_harness_discovers_two_complementary_experiments_without_selected_pair():
    result = run_external_transfer(
        _deadzone,
        source_id='local-test:deadzone',
        source_commit='test-pin',
    )
    assert result['passed'] is True
    assert result['source_exposure'] == 'io_only'
    assert result['host_selected_intervention'] is False
    assert result['researcher_selected_function_family'] is True
    assert result['derived_anchor_values'] == [-10.0, 10.0]
    assert result['composition_op'] == 'add'
    assert {tuple(map(tuple, bindings)) for bindings in result['selected_bindings']} == {
        ((1, -10.0),),
        ((2, 10.0),),
    }
    assert result['flat_baseline_passed'] is False
    assert result['flat_baseline_candidates'] == 10000
    assert result['probe_synthesis_candidates_total'] <= result['flat_baseline_candidates']
    assert result['matched_synthesis_budget_respected'] is True
    assert result['validation_exact'] == result['validation_cases'] == 10
    assert result['challenge_exact'] == result['challenge_cases'] == 8
    assert result['heldout_exact'] == result['heldout_cases'] == 24
    assert all(value < result['challenge_cases'] for value in result['singleton_challenge_exact'])
    assert result['proper_subset_failures'] == 2
    assert result['trainable_parameter_count'] == 0
