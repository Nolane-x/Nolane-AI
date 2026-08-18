import numpy as np

from research.r259_external_active_probe_transfer import run_external_transfer


def test_r259_numpy_gcd_external_active_probe_transfer():
    calls = {'count': 0}

    def oracle(a, b):
        calls['count'] += 1
        return int(np.gcd(a, b))

    result = run_external_transfer(
        oracle,
        source_id='numpy:numpy.gcd',
        source_version=np.__version__,
    )

    assert result['passed'] is True
    assert result['source_exposure'] == 'io_only'
    assert result['candidate_count'] == 4
    assert result['initial_oracle_calls'] == 2
    assert result['active_selection_oracle_calls'] == 1
    assert result['active_exact'] is True
    assert result['active_false_accepts'] == 0
    assert result['random_one_probe_exact'] is False
    assert result['passive_initial_only_exact'] is False
    assert result['active_gain_over_random'] is True
    assert result['selected_probe_partition_count'] == 4
    assert result['selected_probe_largest_partition'] == 1
    assert result['verification_exact'] == result['verification_cases'] == 625
    assert result['oracle_calls_total'] == calls['count']
    assert result['probe_generation_uses_target_outputs'] is False
    assert result['trainable_parameter_count'] == 0
    assert 'not general repository coding' in result['claim_boundary']
