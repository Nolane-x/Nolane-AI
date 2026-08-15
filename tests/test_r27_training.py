from pathlib import Path

from cogcoder.r27_codeworld_controller import CodeWorldControllerConfig
from scripts.train_r27_codeworld_controller import train_controller, save_r27_bundle


def test_training_reaches_heldout_pair_transfer_and_bundle_is_parent_bound(tmp_path: Path):
    result = train_controller(seed=27, epochs=8, episodes_per_pair=12)
    assert result.train_accuracy >= 0.90
    assert result.heldout_accuracy >= 0.80
    assert 200_000 <= result.controller_parameters < 1_000_000

    parent = tmp_path / "parent.pt"
    parent.write_bytes(b"parent-weight-test")
    output = tmp_path / "r27.pt"
    meta = save_r27_bundle(parent, output, result)
    assert output.is_file()
    assert meta["parent_sha256"]
    assert meta["candidate_effective_parameters"] == 78_779_253 + result.controller_parameters
