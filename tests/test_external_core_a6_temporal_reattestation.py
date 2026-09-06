from __future__ import annotations

import pytest

from nolane.external_core.integration_admission_bundle import (
    build_canonical_admission_bundle,
    run_canonical_admission_audit,
)


def test_persisted_bundle_requires_live_observation_epoch() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)

    report = run_canonical_admission_audit(bundle=bundle)

    assert {row.code for row in report.findings} == {"CURRENT_OBSERVATION_EPOCH_UNAVAILABLE"}


def test_persisted_bundle_accepts_exact_live_observation_epoch() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)

    report = run_canonical_admission_audit(bundle=bundle, current_observed_epoch=11)

    assert report.findings == ()


@pytest.mark.parametrize("live_epoch", (10, 12))
def test_persisted_bundle_rejects_observation_epoch_drift(live_epoch: int) -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)

    report = run_canonical_admission_audit(bundle=bundle, current_observed_epoch=live_epoch)

    assert {row.code for row in report.findings} == {"OBSERVATION_EPOCH_CONTEXT_MISMATCH"}


@pytest.mark.parametrize("live_epoch", (True, False, -1, 1.0, "11", b"11"))
def test_persisted_bundle_rejects_noncanonical_live_observation_epoch(live_epoch: object) -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)

    report = run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=live_epoch,  # type: ignore[arg-type]
    )

    assert {row.code for row in report.findings} == {"CURRENT_OBSERVATION_EPOCH_INVALID"}
