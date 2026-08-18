from research.r257_external_vocabulary_transfer import run_external_transfer


def _linearstep(x, a, b, fa, fb):
    if b <= a:
        raise ValueError('b must exceed a')
    if x <= a:
        return float(fa)
    if x >= b:
        return float(fb)
    t = (x - a) / (b - a)
    return float(fa + t * (fb - fa))


def test_external_harness_uses_io_only_and_learned_vocabulary_beats_base_budget():
    result = run_external_transfer(
        _linearstep,
        source_id='unit://linearstep-contract',
        source_commit='unit-pinned',
    )
    assert result['passed'] is True
    assert result['source_exposure'] == 'io_only'
    assert result['base_passed'] is False
    assert result['extended_passed'] is True
    assert result['challenge_exact'] == result['challenge_cases']
    assert result['heldout_exact'] == result['heldout_cases']
    assert result['heldout_cases'] >= 24
    assert len(result['learned_abstraction_digests']) == 3
    assert result['trainable_parameter_count'] == 0
