from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def test_current_best_separates_physical_and_legacy_parameter_counts():
    current = _read("CURRENT_BEST.json")
    accounting = current["parameter_accounting"]
    assert accounting["legacy_effective_parameters"] == 78_899_404
    assert accounting["physical_loaded_parameters"] == 29_370_727
    assert accounting["mode"] == "legacy_effective_with_physical_tensor_audit"
    assert accounting["weights_changed_by_audit"] is False


def test_parameter_audit_is_bound_to_frozen_one_weight_and_breakdown():
    audit = _read("evidence/R2_1A_PARAMETER_ACCOUNTING_AUDIT.json")
    assert audit["status"] == "PASS"
    assert audit["one_weight_sha256"] == "4f0b366e2401127e50b7fdbca651601b0a4b972004812c9f32043b82f0e3091b"
    assert audit["delta_sha256"] == "3bbd63c9cb20e180b78588e15a21e4132b41d80118c6ce229231967a91bfc9c4"
    assert audit["serialized_tensor_count"] == 426
    assert audit["physical_loaded_parameters"] == 29_370_727
    assert audit["component_parameters"] == {
        "causal_router": 120_151,
        "evidence_effect": 565_080,
        "frontier_rollout": 1_594_754,
        "neural_system2": 27_090_742,
    }
    assert sum(audit["component_parameters"].values()) == audit["physical_loaded_parameters"]
    assert audit["legacy_effective_parameters"] == 78_899_404
    assert audit["weights_changed_by_audit"] is False


def test_architecture_labels_legacy_effective_count_unambiguously():
    architecture = _read("ARCHITECTURE.json")
    candidate = architecture["current_evidence_backed_candidate"]
    assert candidate["physical_loaded_parameters"] == 29_370_727
    assert candidate["legacy_effective_parameters"] == 78_899_404
    assert candidate["parameter_accounting_mode"] == "legacy_effective_with_physical_tensor_audit"
