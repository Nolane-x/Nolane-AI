from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.authority_graph import ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest
import nolane.external_core.integration_admission as admission
from nolane.external_core.integration_admission import (
    AdmissionDisposition,
    AdmissionSubjectKind,
    AdmittedAuthorityGraph,
    AdmittedManifest,
    ProtocolAdmissionReceipt,
)
import nolane.external_core.integration_admission_bundle as admission_bundle
from nolane.external_core.integration_admission_bundle import (
    CanonicalAdmissionBundle,
    build_canonical_admission_bundle,
    run_canonical_admission_audit,
)


def test_canonical_admission_audit_is_clean_for_exact_current_bundle() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)
    report = run_canonical_admission_audit(bundle=bundle, current_observed_epoch=11)
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
    assert report.protocol == "external-integration-admission-audit-v3"


def test_canonical_admission_audit_rejects_self_consistent_bundle_after_live_registry_drift(monkeypatch) -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)
    registry, profile = admission_bundle._strict_current_objects()
    drifted_registry = SimpleNamespace(
        registry_digest="drifted-current-registry",
        manifests=registry.manifests,
        manifest_for=registry.manifest_for,
    )
    monkeypatch.setattr(
        admission_bundle,
        "_strict_current_objects",
        lambda: (drifted_registry, profile),
    )

    report = run_canonical_admission_audit(bundle=bundle, current_observed_epoch=11)

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

    report = run_canonical_admission_audit(bundle=bundle, current_observed_epoch=11)

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

    report = run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=11,
        **{frontier_arg: values},
    )

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
        current_observed_epoch=11,
        **{frontier_arg: {"subject": "drifted-digest"}},
    )

    assert {row.code for row in report.findings} == {mismatch_code}


def _self_issued_admitted_manifest(manifest: ExternalComponentManifest, context_digest: str) -> AdmittedManifest:
    state = manifest.to_state()
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.COMPONENT_MANIFEST,
        subject_protocol=AdmissionSubjectKind.COMPONENT_MANIFEST.value,
        subject_id=manifest.component_id,
        subject_state_digest=canonical_digest(state),
        semantic_digest=manifest.manifest_digest,
        context_digest=context_digest,
        disposition=AdmissionDisposition.ADMITTED,
        reason_codes=(),
        limitations=("structural-currentness-only", "no-semantic-authority"),
    )
    subject_json = canonical_json(state)
    wrapper = AdmittedManifest(
        subject_json,
        receipt,
        admission._wrapper_digest(AdmissionSubjectKind.COMPONENT_MANIFEST, subject_json, receipt),
    )
    wrapper.validate_integrity()
    return wrapper


def _self_issued_admitted_graph(graph: ExternalAuthorityGraph, context_digest: str) -> AdmittedAuthorityGraph:
    state = graph.to_state()
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.AUTHORITY_GRAPH,
        subject_protocol=AdmissionSubjectKind.AUTHORITY_GRAPH.value,
        subject_id="canonical-authority-graph",
        subject_state_digest=canonical_digest(state),
        semantic_digest=graph.digest,
        context_digest=context_digest,
        disposition=AdmissionDisposition.ADMITTED,
        reason_codes=(),
        limitations=("structural-currentness-only", "no-semantic-authority"),
    )
    subject_json = canonical_json(state)
    wrapper = AdmittedAuthorityGraph(
        subject_json,
        receipt,
        admission._wrapper_digest(AdmissionSubjectKind.AUTHORITY_GRAPH, subject_json, receipt),
    )
    wrapper.validate_integrity()
    return wrapper


def test_canonical_admission_audit_replays_admission_instead_of_trusting_self_issued_admitted_receipts() -> None:
    current_bundle = build_canonical_admission_bundle(observed_epoch=11)
    registry, profile = admission_bundle._strict_current_objects()
    current = registry.manifests[0]
    stale = ExternalComponentManifest.create(
        component_id=current.component_id,
        component_version="9.9.9",
        family=current.family,
        protocol_versions=dict(current.protocol_versions),
        consumes_contracts=current.consumes_contracts,
        produces_contracts=current.produces_contracts,
        authority_capabilities=current.authority_capabilities,
        forbidden_authorities=current.forbidden_authorities,
        mutable_resources=current.mutable_resources,
        evidence_inputs=current.evidence_inputs,
        evidence_outputs=current.evidence_outputs,
        restore_protocol=current.restore_protocol,
        compatibility_floor="9.9.9",
        compatibility_ceiling="9.9.9",
    )
    forged_manifests = tuple(stale if row.component_id == current.component_id else row for row in registry.manifests)
    forged_graph = ExternalAuthorityGraph(forged_manifests, profile.authority_graph.edges)
    forged_graph.validate()

    admitted_manifests = tuple(
        _self_issued_admitted_manifest(row, current_bundle.context.digest)
        for row in forged_manifests
    )
    admitted_graph = _self_issued_admitted_graph(forged_graph, current_bundle.context.digest)
    forged_bundle = CanonicalAdmissionBundle.create(
        context=current_bundle.context,
        manifests=admitted_manifests,
        authority_graph=admitted_graph,
    )
    forged_bundle.validate_integrity()

    report = run_canonical_admission_audit(bundle=forged_bundle, current_observed_epoch=11)
    codes = {row.code for row in report.findings}

    assert "CANONICAL_MANIFEST_MISMATCH" in codes
    assert "CANONICAL_AUTHORITY_GRAPH_MISMATCH" in codes
    assert "CANONICAL_GRAPH_REGISTRY_POPULATION_MISMATCH" in codes
