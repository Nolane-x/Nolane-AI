from __future__ import annotations

import numpy as np

from research.r261_external_version_space_expansion import run_external_transfer


def test_r261_pinned_numpy_remainder_io_only_transfer() -> None:
    result = run_external_transfer(
        np.remainder,
        source_id='numpy.remainder',
        source_version=np.__version__,
    )

    assert result['source_id'] == 'numpy.remainder'
    assert result['source_version'] == '2.4.6'
    assert result['source_code_inspected'] is False
    assert result['correct_candidate_initially_absent'] is True
    assert result['r260_baseline']['status'] == 'abstain'
    assert result['r260_baseline']['reason'] == 'oracle_outside_candidate_version_space'
    assert result['r261']['status'] == 'accept'
    assert result['r261']['exact'] is True
    assert result['r261']['reason'] == 'expanded_candidate_verified'
    assert result['r261']['expansion_round_count'] == 1
    assert result['r261']['generated_candidates'] >= 2
    assert result['r261']['admitted_generated_candidates'] == 1
    assert result['r261']['false_terminal_accepts'] == 0
    assert result['verification_cases'] >= 400
    assert result['external_oracle_calls'] >= result['verification_cases'] + 1
    assert result['trainable_parameter_count'] == 0
    assert result['all_gates_pass'] is True
