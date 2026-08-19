from __future__ import annotations

from pathlib import Path

import pytest
import torch

from cogcoder.r21_checkpoint import (
    R21_BUNDLE_FORMAT,
    R21_DELTA_FORMAT,
    build_r21_one_weight_bundle,
    load_r21_delta,
    load_r21_one_weight_bundle,
    save_r21_delta,
)
from cogcoder.r21_recursive_core import R20I_EFFECTIVE_PARAMETERS, RecursiveLatentIntelligenceCore, r21_parameter_count


def _parent(path: Path, marker: float = 1.0) -> Path:
    torch.save(
        {
            "format": "nolane-r2.0i-hybrid-standalone-bundle-v1",
            "version": "R2.0i-test-parent",
            "effective_parameters": R20I_EFFECTIVE_PARAMETERS,
            "marker": torch.tensor(marker),
        },
        path,
    )
    return path


def test_delta_roundtrip_is_parent_bound_and_exact_parameter_accounting(tmp_path: Path) -> None:
    torch.manual_seed(21)
    parent = _parent(tmp_path / "parent.pt")
    core = RecursiveLatentIntelligenceCore()
    delta = tmp_path / "r21.pt"
    meta = save_r21_delta(delta, core, parent_checkpoint=parent, storage_dtype="float16")
    assert meta["format"] == R21_DELTA_FORMAT
    assert meta["delta_parameters"] == r21_parameter_count(core)
    assert meta["candidate_effective_parameters"] == R20I_EFFECTIVE_PARAMETERS + r21_parameter_count(core)
    loaded, loaded_meta = load_r21_delta(delta, expected_parent_checkpoint=parent)
    assert loaded_meta["candidate_effective_parameters"] == meta["candidate_effective_parameters"]
    for key, value in core.state_dict().items():
        torch.testing.assert_close(loaded.state_dict()[key], value, rtol=1e-3, atol=5e-4)


def test_delta_rejects_wrong_parent(tmp_path: Path) -> None:
    parent = _parent(tmp_path / "parent.pt", 1.0)
    wrong = _parent(tmp_path / "wrong.pt", 2.0)
    delta = tmp_path / "r21.pt"
    save_r21_delta(delta, RecursiveLatentIntelligenceCore(), parent_checkpoint=parent)
    with pytest.raises(ValueError, match="parent checkpoint SHA-256 mismatch"):
        load_r21_delta(delta, expected_parent_checkpoint=wrong)


def test_one_weight_bundle_embeds_parent_and_r21_delta(tmp_path: Path) -> None:
    parent = _parent(tmp_path / "parent.pt")
    delta = tmp_path / "delta.pt"
    core = RecursiveLatentIntelligenceCore()
    dmeta = save_r21_delta(delta, core, parent_checkpoint=parent)
    bundle = tmp_path / "one-weight.pt"
    meta = build_r21_one_weight_bundle(parent, delta, bundle)
    assert meta["format"] == R21_BUNDLE_FORMAT
    assert meta["effective_parameters"] == dmeta["candidate_effective_parameters"]
    loaded_core, parent_payload, loaded_meta = load_r21_one_weight_bundle(bundle)
    assert parent_payload["format"] == "nolane-r2.0i-hybrid-standalone-bundle-v1"
    assert loaded_meta["effective_parameters"] == meta["effective_parameters"]
    assert r21_parameter_count(loaded_core) == r21_parameter_count(core)
