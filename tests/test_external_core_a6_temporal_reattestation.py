from __future__ import annotations

from nolane.external_core.integration_admission_bundle import (
    build_canonical_admission_bundle,
    run_canonical_admission_audit,
)


def test_persisted_bundle_requires_live_observation_epoch() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)

    report = run_canonical_admission_audit(bundle=bundle)

    assert {row.code for row in report.findings} == {"CURRENT_OBSERVATION_EPOCH_UNAVAILABLE"}
