import math

from cogcoder.r256_operator_dsl import evaluate_expr
from research.r264_external_contextual_transfer import run_external_transfer


def _step(x, a, flow, fa, fhigh):
    if x < a:
        return flow
    if x > a:
        return fhigh
    return fa


def test_external_shaped_step_transfer_requires_contextual_composition():
    result = run_external_transfer(
        _step,
        source_id='local-test:step',
        source_commit='local-test',
    )
    assert result['passed'] is True
    assert result['source_exposure'] == 'io_only'
    assert result['host_selected_intervention'] is False
    assert result['r262_fixed_op_passed'] is False
    assert result['singleton_composition_passed'] == [False, False]
    assert result['challenge_exact'] == result['challenge_cases'] == 12
    assert result['heldout_exact'] == result['heldout_cases'] == 36
    assert result['probe_validation_exact'] == result['probe_validation_cases'] * 2
    assert result['trainable_parameter_count'] == 0
