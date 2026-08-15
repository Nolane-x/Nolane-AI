import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_r214_preheldout_lock_freezes_sources_protocol_and_strict_gate():
    root = Path(__file__).resolve().parents[1]
    lock_path = root / 'research' / 'R2_14_PRE_HELDOUT_LOCK.json'
    lock = json.loads(lock_path.read_text())
    assert lock['milestone'] == 'R2.14'
    assert lock['state'] == 'pre_heldout_frozen'
    assert lock['heldout']['seed'] == 32001
    assert lock['heldout']['main_cases_per_family'] == 40
    assert lock['heldout']['depth3_cases_per_family'] == 16
    assert lock['heldout']['old_regime_count'] == 64
    assert lock['heldout']['out_of_class_count'] == 40
    assert lock['heldout']['oracle_budget'] == 3
    assert lock['gate']['main_active_accuracy_min'] == 0.95
    assert lock['gate']['depth3_active_accuracy_min'] == 0.90
    assert lock['gate']['retention_accuracy_min'] == 0.95
    assert lock['gate']['out_of_class_abstention_min'] == 1.0
    assert lock['gate']['identity_permutation_invariance_min'] == 1.0
    assert lock['gate']['false_resolved_accepts_max'] == 0
    assert lock['gate']['max_active_oracle_calls'] == 3
    assert lock['new_neural_parameters'] == 0
    assert lock['effective_neural_parameters'] == 79_450_489
    for rel, expected in lock['frozen_source_sha256'].items():
        assert _sha256(root / rel) == expected
