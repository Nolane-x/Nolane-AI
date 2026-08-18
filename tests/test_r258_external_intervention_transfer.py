from research.r258_external_intervention_transfer import run_external_transfer


def _linearstep(x, a, b, fa, fb):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return fa + t * (fb - fa)


def test_r258_external_transfer_discovers_intervention_from_io_without_host_selection():
    calls = {'count': 0}

    def counted_oracle(*args):
        calls['count'] += 1
        return _linearstep(*args)

    result = run_external_transfer(
        counted_oracle,
        source_id='local-standin:linearstep',
        source_commit='test-only',
    )

    assert result['passed'] is True
    assert result['source_exposure'] == 'io_only'
    assert result['host_selected_intervention'] is False
    assert result['candidate_interventions_considered'] > 1
    assert result['selected_position_set'] == [3, 4]
    assert result['no_seed_passed'] is False
    assert result['seeded_passed'] is True
    assert result['probe_validation_exact'] == result['probe_validation_cases']
    assert result['challenge_exact'] == result['challenge_cases'] == 8
    assert result['heldout_exact'] == result['heldout_cases'] == 24
    assert result['oracle_calls_total'] == calls['count']
    assert result['oracle_calls_total'] > result['oracle_calls_during_discovery']
    assert result['synthesis_candidates_considered'] > 0
    assert result['trainable_parameter_count'] == 0
    assert 'not open-ended' in result['claim_boundary']
