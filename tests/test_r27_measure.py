from pathlib import Path

from scripts.measure_r27_codeworld import evaluate_bundle
from scripts.train_r27_codeworld_controller import train_controller, save_r27_bundle


def test_evaluate_bundle_reconstructs_controller_and_reports_transfer(tmp_path: Path):
    result = train_controller(seed=27, epochs=6, episodes_per_pair=8)
    parent = tmp_path / "parent.pt"
    parent.write_bytes(b"parent")
    bundle = tmp_path / "bundle.pt"
    save_r27_bundle(parent, bundle, result)
    report = evaluate_bundle(bundle, seed=27, episodes_per_pair=8)
    assert report["controller_parameters"] == result.controller_parameters
    assert report["train_accuracy"] >= 0.85
    assert report["heldout_pair_accuracy"] >= 0.75
    assert report["parameter_increase_fraction"] < 0.02
