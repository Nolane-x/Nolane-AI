from pathlib import Path

from scripts.measure_r210_copy_edit import measure_r210_copy_edit
from scripts.train_r210_copy_edit_proposer import save_r210_delta, train_copy_edit_proposer


def test_small_measurement_has_required_fields_and_no_false_accepts(tmp_path: Path):
    result = train_copy_edit_proposer(seed=210, epochs=2, rows_per_family=16, batch_size=16)
    checkpoint = tmp_path / 'delta.pt'
    save_r210_delta(checkpoint, result, lock_sha256='test-lock')
    measured = measure_r210_copy_edit(checkpoint, cases_per_family=2)
    assert measured['cases'] == 4
    assert 0.0 <= measured['top1_gold_candidate_accuracy'] <= 1.0
    assert 0.0 <= measured['integrated_verified_solve_rate'] <= 1.0
    assert 0.0 <= measured['unranked_baseline_solve_rate'] <= 1.0
    assert measured['false_terminal_accepts'] == 0
    assert measured['new_r210_neural_parameters'] <= 300_000
    assert measured['candidate_effective_parameters'] < 80_000_000
    assert measured['external_coding_claim_allowed'] is False
    assert measured['agi_claim_allowed'] is False
