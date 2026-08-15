import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_committed_r211_result_satisfies_frozen_gate():
    lock = json.loads((ROOT/'research/R2_11_PRE_MEASURE_LOCK.json').read_text())
    result = json.loads((ROOT/'research/R2_11_PHASE_A_RESULT.json').read_text())
    a = lock['acceptance']
    assert result['cases'] == lock['protocol']['cases'] == 64
    assert result['localization_hit1'] >= a['localization_hit1_min']
    assert result['localization_mrr'] >= a['localization_mrr_min']
    assert result['localization_hit3'] >= a['localization_hit3_min']
    assert result['hit1_improvement_over_spectrum_pp'] >= a['hit1_improvement_over_spectrum_pp_min']
    assert result['integrated_verified_solve_rate'] >= a['integrated_verified_solve_rate_min']
    assert result['solve_improvement_over_spectrum_pp'] >= a['solve_improvement_over_spectrum_pp_min']
    assert result['identity_permutation_invariance'] >= a['identity_permutation_invariance_min']
    assert result['false_terminal_accepts'] == 0
    assert result['max_patch_evaluations_observed'] <= a['max_patch_evaluations_per_case']
    assert result['new_r211_neural_parameters'] == 0
    assert result['candidate_effective_parameters'] == 79450489
    assert result['external_coding_claim_allowed'] is False
    assert result['agi_claim_allowed'] is False
    assert result['phase_a_gate_pass'] is True
