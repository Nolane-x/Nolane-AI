from __future__ import annotations

import importlib.util


def test_a14_historical_provenance_surface_exists() -> None:
    assert (
        importlib.util.find_spec(
            "nolane.external_core.evidence_provenance_epoch_truth"
        )
        is not None
    )
