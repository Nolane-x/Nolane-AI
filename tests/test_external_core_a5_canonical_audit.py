from __future__ import annotations

from dataclasses import replace

from nolane.external_core.integration_admission_bundle import (
    build_canonical_admission_bundle,
    run_canonical_admission_audit,
)


def test_canonical_admission_audit_is_clean_for_exact_current_bundle() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)
    report = run_canonical_admission_audit(bundle=bundle)
    assert report.findings == ()
    assert report.digest


def test_canonical_admission_audit_reports_forged_bundle_without_repairing_it() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)
    forged = replace(bundle, digest="forged-bundle-digest")
    report = run_canonical_admission_audit(bundle=forged)
    assert {row.code for row in report.findings} == {"FORGED_ADMISSION_BUNDLE"}
    assert forged.digest == "forged-bundle-digest"


def test_canonical_admission_audit_default_builder_is_read_only_and_clean() -> None:
    report = run_canonical_admission_audit(observed_epoch=0)
    assert report.findings == ()
    assert report.protocol == "external-integration-admission-audit-v1"
