import hashlib
import json
from pathlib import Path

LOCK = Path('research/R2_12_PRE_MEASURE_LOCK.json')


def test_r212_lock_freezes_external_panel_thresholds_and_source_hashes():
    lock = json.loads(LOCK.read_text())
    assert lock['dataset']['repository'] == 'SWE-rebench/SWE-rebench-V2'
    assert lock['dataset']['path'] == 'sample.json'
    assert lock['dataset']['commit'] == 'dd8b58f385783b189a96dd09c22153c843b0e2f9'
    assert lock['dataset']['git_blob_sha1'] == 'a44529e3f7510353a0de8f90ae22c0e9bc7c6fc1'
    assert lock['dataset']['expected_tasks'] == 20
    assert lock['acceptance'] == {
        'materialized_tasks_exact': 20,
        'hybrid_hit5_min': 0.55,
        'hybrid_mrr_min': 0.30,
        'hit5_improvement_over_path_pp_min': 10.0,
        'mrr_improvement_over_path_min': 0.05,
        'recall5_improvement_over_path_min': 0.0,
        'prediction_determinism_min': 1.0,
        'new_r212_neural_parameters_exact': 0,
        'candidate_effective_parameters_exact': 79450489,
    }
    for rel, expected in lock['source_sha256'].items():
        assert hashlib.sha256(Path(rel).read_bytes()).hexdigest() == expected
    assert lock['claim_boundary']['external_issue_resolution_claim_allowed'] is False
    assert lock['claim_boundary']['agi_claim_allowed'] is False
