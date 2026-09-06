from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

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


_FRONTIER_CASES = (
    ("current_source_state_digests", "CURRENT_SOURCE_STATE_FRONTIER_UNAVAILABLE", "SOURCE_STATE_FRONTIER_CONTEXT_MISMATCH"),
    ("current_evidence_digests", "CURRENT_EVIDENCE_FRONTIER_UNAVAILABLE", "EVIDENCE_FRONTIER_CONTEXT_MISMATCH"),
    ("current_artifact_digests", "CURRENT_ARTIFACT_FRONTIER_UNAVAILABLE", "ARTIFACT_FRONTIER_CONTEXT_MISMATCH"),
    ("current_freshness_fences", "CURRENT_FRESHNESS_FRONTIER_UNAVAILABLE", "FRESHNESS_FRONTIER_CONTEXT_MISMATCH"),
    ("known_handoff_digests", "CURRENT_HANDOFF_FRONTIER_UNAVAILABLE", "HANDOFF_FRONTIER_CONTEXT_MISMATCH"),
    ("current_work_trace_digests", "CURRENT_WORK_TRACE_FRONTIER_UNAVAILABLE", "WORK_TRACE_FRONTIER_CONTEXT_MISMATCH"),
)


@pytest.mark.parametrize(("frontier_arg", "unavailable_code", "mismatch_code"), _FRONTIER_CASES)
def test_canonical_admission_audit_fails_closed_when_bound_frontier_is_not_reobserved(
    frontier_arg: str,
    unavailable_code: str,
    mismatch_code: str,
) -> None:
    del mismatch_code
    values = {"subject": "digest"}
    bundle = build_canonical_admission_bundle(observed_epoch=11, **{frontier_arg: values})

    report = run_canonical_admission_audit(bundle=bundle)

    assert {row.code for row in report.findings} == {unavailable_code}


@pytest.mark.parametrize(("frontier_arg", "unavailable_code", "mismatch_code"), _FRONTIER_CASES)
def test_canonical_admission_audit_accepts_exact_live_frontier_reobservation(
    frontier_arg: str,
    unavailable_code: str,
    mismatch_code: str,
) -> None:
    del unavailable_code, mismatch_code
    values = {"subject": "digest"}
    bundle = build_canonical_admission_bundle(observed_epoch=11, **{frontier_arg: values})

    report = run_canonical_admission_audit(bundle=bundle, **{frontier_arg: values})

    assert report.findings == ()


@pytest.mark.parametrize(("frontier_arg", "unavailable_code", "mismatch_code"), _FRONTIER_CASES)
def test_canonical_admission_audit_rejects_live_frontier_drift(
    frontier_arg: str,
    unavailable_code: str,
    mismatch_code: str,
) -> None:
    del unavailable_code
    bundle = build_canonical_admission_bundle(
        observed_epoch=11,
        **{frontier_arg: {"subject": "admitted-digest"}},
    )

    report = run_canonical_admission_audit(
        bundle=bundle,
        **{frontier_arg: {"subject": "drifted-digest"}},
    )

    assert {row.code for row in report.findings} == {mismatch_code}
