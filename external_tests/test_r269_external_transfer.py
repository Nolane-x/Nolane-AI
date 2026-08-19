from __future__ import annotations

import numpy as np

from research.r269_external_transfer import run_external_meta_transfer


def test_external_numpy_subtract_transfer_is_verifier_backed_and_bounded():
    result = run_external_meta_transfer(
        np.subtract,
        source_id="numpy.subtract",
        source_version=np.__version__,
    )

    assert result["schema_version"] == 1
    assert result["milestone"] == "R2.69"
    assert result["source_exposure"] == "io_only"
    assert result["target_exposure"] == "io_only"
    assert result["trainable_parameter_count"] == 0
    assert result["source"]["r268_receipt_passed"] is True
    assert result["source"]["portable_compiled"] is True
    assert result["source"]["false_accepts"] == 0

    related = result["related_target"]
    assert related["transfer_passed"] is True
    assert related["transfer_mode"] == "transfer"
    assert related["cold_scratch_passed"] is True
    assert related["terminal_verified"] is True
    assert related["oracle_accounting_exact"] is True
    assert related["transfer_physical_diagnostic_calls"] < related["cold_scratch_physical_diagnostic_calls"]

    ablation = result["source_prior_ablation"]
    assert ablation["same_target"] is True
    assert ablation["prior_removed"] is True
    assert ablation["advantage_removed"] is True

    negative = result["negative_control"]
    assert negative["false_accepts"] == 0
    assert negative["cold_scratch_passed"] is True
    assert negative["transfer_path_correct"] is True
    assert negative["extra_physical_oracle_regret"] <= 1

    assert result["passed"] is True
