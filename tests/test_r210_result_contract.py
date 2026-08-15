import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_committed_r210_result_satisfies_frozen_lock_and_claim_boundary():
    lock = json.loads((ROOT / 'research/R2_10_PRETRAIN_LOCK.json').read_text())
    result = json.loads((ROOT / 'research/R2_10_PHASE_A_RESULT.json').read_text())
    acc = lock['acceptance']
    assert result['cases'] == lock['protocol']['heldout_cases'] == 48
    assert result['top1_gold_candidate_accuracy'] >= acc['top1_gold_candidate_accuracy_min']
    assert result['integrated_verified_solve_rate'] >= acc['integrated_verified_solve_rate_min']
    assert result['improvement_over_unranked_baseline_pp'] >= acc['improvement_over_unranked_baseline_pp_min']
    assert result['rename_invariance'] >= acc['rename_invariance_min']
    assert result['false_terminal_accepts'] <= acc['false_terminal_accepts_max']
    assert result['new_r210_neural_parameters'] <= lock['new_r210_parameter_ceiling']
    assert result['candidate_effective_parameters'] < lock['candidate_total_parameter_ceiling']
    assert result['external_coding_claim_allowed'] is False
    assert result['agi_claim_allowed'] is False
    assert result['phase_a_gate_pass'] is True
