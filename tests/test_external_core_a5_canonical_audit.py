from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import nolane.external_core.integration_admission_bundle as admission_bundle
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


def test_canonical_admission_audit_rejects_self_consistent_bundle_after_live_registry_drift(monkeypatch) -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)
    registry, profile = admission_bundle._strict_current_objects()
    drifted_registry = SimpleNamespace(registry_digest="drifted-current-registry")
    monkeypatch.setattr(
        admission_bundle,
        "_strict_current_objects",
        lambda: (drifted_registry, profile),
    )

    report = run_canonical_admission_audit(bundle=bundle)

    assert {row.code for row in report.findings} == {"CANONICAL_REGISTRY_CONTEXT_MISMATCH"}
    assert bundle.context.registry_digest == registry.registry_digest
