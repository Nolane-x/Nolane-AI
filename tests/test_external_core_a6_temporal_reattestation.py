from __future__ import annotations

import pytest

from nolane.external_core import compatibility, integration
from nolane.external_core import integration_admission
from nolane.external_core import integration_admission_bundle as admission_bundle
from nolane.external_core.integration_admission_bundle import (
    build_canonical_admission_bundle,
    run_canonical_admission_audit,
)
from nolane.metadata.component_versions import component_revision_map


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


def test_fresh_canonical_audit_reuses_builder_epoch_as_live_proof() -> None:
    report = run_canonical_admission_audit(observed_epoch=11)

    assert report.findings == ()


def test_fresh_canonical_audit_rejects_explicit_live_epoch_mismatch() -> None:
    report = run_canonical_admission_audit(observed_epoch=11, current_observed_epoch=12)

    assert {row.code for row in report.findings} == {"OBSERVATION_EPOCH_CONTEXT_MISMATCH"}


def test_a6_temporal_contract_survives_dependency_revision_without_rewriting_a5_artifacts() -> None:
    assert integration.COMPONENT_ID == "external.integration"
    assert integration.COMPONENT_VERSION == "0.0.8"
    assert compatibility.SEMANTIC_SURFACE_VERSION == "0.0.8"
    assert admission_bundle.COMPONENT_ID == "external.integration"
    assert admission_bundle.COMPONENT_VERSION == "0.0.8"
    assert component_revision_map()["external.integration"] == 13

    assert admission_bundle.ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v4"
    assert admission_bundle.HISTORICAL_ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v3"
    assert admission_bundle.ADMISSION_BUNDLE_PROTOCOL == "external-integration-admission-bundle-v2"
    assert integration_admission.ADMISSION_PROTOCOL == "external-integration-admission-v2"
    assert integration_admission.COMPONENT_VERSION == "0.0.4"


def test_current_audit_report_identity_supersedes_a6_with_v3_protocol_and_digest_namespace() -> None:
    report = run_canonical_admission_audit(observed_epoch=11)

    assert report.protocol == "external-integration-admission-audit-v3"
    assert report.digest.startswith("admission-audit-v3-")
