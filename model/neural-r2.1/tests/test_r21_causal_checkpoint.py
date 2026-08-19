from __future__ import annotations

from pathlib import Path

import pytest
import torch

from cogcoder.r21_causal_checkpoint import (
    R20I_EFFECTIVE_PARAMETERS,
    build_r21a_one_weight,
    load_r21a_delta,
    save_r21a_delta,
)
from cogcoder.r21_causal_router import CausalEvidenceRouter


def _p(path: Path, marker: float = 1.0) -> Path:
    torch.save({
        "format": "nolane-r2.0i-hybrid-standalone-bundle-v1",
        "effective_parameters": R20I_EFFECTIVE_PARAMETERS,
        "marker": torch.tensor(marker),
    }, path)
    return path


def test_roundtrip_and_bundle_accounting_is_explicit(tmp_path: Path):
    parent = _p(tmp_path / "p.pt")
    delta_path = tmp_path / "d.pt"
    saved = save_r21a_delta(delta_path, CausalEvidenceRouter(), parent_checkpoint=parent)
    assert saved["delta_parameters"] == 120_151
    assert saved["candidate_effective_parameters"] == 78_899_404
    assert saved["candidate_legacy_effective_parameters"] == 78_899_404
    assert saved["parameter_accounting_mode"] == "legacy_effective_compatibility_only"

    _, metadata = load_r21a_delta(delta_path, expected_parent_checkpoint=parent)
    assert metadata["candidate_effective_parameters"] == 78_899_404
    assert metadata["candidate_legacy_effective_parameters"] == 78_899_404
    assert metadata["parameter_accounting_mode"] == "legacy_effective_compatibility_only"
    assert metadata["physical_loaded_parameters"] is None
    assert metadata["physical_parameter_count_status"] == "requires_artifact_specific_audit"

    one_weight = tmp_path / "one.pt"
    built = build_r21a_one_weight(parent, delta_path, one_weight)
    assert built["effective_parameters"] == 78_899_404
    assert built["legacy_effective_parameters"] == 78_899_404
    assert built["parameter_accounting_mode"] == "legacy_effective_compatibility_only"
    assert built["physical_loaded_parameters"] is None
    payload = torch.load(one_weight, map_location="cpu", weights_only=True)
    assert payload["effective_parameters"] == payload["legacy_effective_parameters"] == 78_899_404
    assert payload["effective_parameters_note"].startswith("Compatibility alias")
    assert payload["parameter_accounting"]["physical_loaded_parameters"] is None


def test_wrong_parent_fails_closed(tmp_path: Path):
    parent = _p(tmp_path / "p.pt", 1.0)
    wrong = _p(tmp_path / "q.pt", 2.0)
    delta_path = tmp_path / "d.pt"
    save_r21a_delta(delta_path, CausalEvidenceRouter(), parent_checkpoint=parent)
    with pytest.raises(ValueError, match="parent checkpoint SHA-256 mismatch"):
        load_r21a_delta(delta_path, expected_parent_checkpoint=wrong)
