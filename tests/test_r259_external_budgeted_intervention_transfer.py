from __future__ import annotations

from research.r259_external_budgeted_intervention_transfer import run_external_transfer


def linearstep(x, a, b, fa, fb):
    t = min(max((float(x) - float(a)) / (float(b) - float(a)), 0.0), 1.0)
    return float(fa) + t * (float(fb) - float(fa))


def test_r259_external_fixture_preserves_accuracy_under_strict_global_budget():
    result = run_external_transfer(
        linearstep,
        source_id='fixture:linearstep',
        source_commit='fixture',
    )
    assert result['passed'] is True
    assert result['host_selected_intervention'] is False
    assert result['intervention_anchor_source'] == 'downstream_need.constants'
    assert result['derived_anchor_values'] == [0.0, 1.0]
    assert result['selected_position_set'] == [3, 4]
    assert result['no_seed_passed'] is False
    assert result['seeded_passed'] is True
    assert result['probe_validation_exact'] == result['probe_validation_cases'] == 4
    assert result['challenge_exact'] == result['challenge_cases'] == 8
    assert result['heldout_exact'] == result['heldout_cases'] == 24
    assert result['max_total_synthesis_candidates'] == 15000
    assert result['total_synthesis_candidates'] <= 15000
    assert result['r258_external_frozen_synthesis_candidates'] == 136969
    assert result['synthesis_reduction_ratio'] >= 8.0
    assert result['trainable_parameter_count'] == 0


def test_r259_external_claim_is_efficiency_not_new_distribution():
    result = run_external_transfer(linearstep, source_id='fixture:linearstep', source_commit='fixture')
    claim = result['claim_boundary'].lower()
    assert 'matched-distribution' in claim
    assert 'not new external breadth' in claim
