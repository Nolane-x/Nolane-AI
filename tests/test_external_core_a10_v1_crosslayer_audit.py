from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

import nolane.external_core.audit as external_audit
import nolane.external_core.integration_admission_bundle as admission_bundle
from nolane.external_core.integration_admission_bundle import AdmissionAuditFinding
from nolane.external_core.observation import CanonicalObservationEnvelope
from nolane.external_core.observation_integration import (
    canonical_observation_scope_digests,
    canonical_observation_surface_digests,
)


ROOT = Path(__file__).resolve().parents[1]

BUNDLE_KEYS = (
    "protocol",
    "context",
    "manifests",
    "authority_graph",
    "handoffs",
    "work_traces",
    "digest",
)


def _frontiers() -> dict[str, dict[str, str]]:
    return {
        "current_source_state_digests": {},
        "current_evidence_digests": {},
        "current_artifact_digests": {},
        "current_freshness_fences": {},
        "known_handoff_digests": {},
        "current_work_trace_digests": {},
    }


def _observation(*, epoch: int = 7) -> CanonicalObservationEnvelope:
    return admission_bundle.build_canonical_observation(
        observed_epoch=epoch,
        chain_id="external-core:test",
        previous_observation_digest=None,
        **_frontiers(),
    )


def _rebuild_observation(
    envelope: CanonicalObservationEnvelope,
    **changes: object,
) -> CanonicalObservationEnvelope:
    values: dict[str, object] = {
        "surface_contract": envelope.surface_contract,
        "observed_epoch": envelope.observed_epoch,
        "registry_digest": envelope.registry_digest,
        "authority_graph_digest": envelope.authority_graph_digest,
        "source_state_frontier_digest": envelope.source_state_frontier_digest,
        "evidence_frontier_digest": envelope.evidence_frontier_digest,
        "artifact_frontier_digest": envelope.artifact_frontier_digest,
        "freshness_fence_frontier_digest": envelope.freshness_fence_frontier_digest,
        "handoff_frontier_digest": envelope.handoff_frontier_digest,
        "work_trace_frontier_digest": envelope.work_trace_frontier_digest,
        "surface_receipts": envelope.surface_receipts,
        "chain_id": envelope.chain_id,
        "previous_observation_digest": envelope.previous_observation_digest,
    }
    values.update(changes)
    return CanonicalObservationEnvelope.create(**values)


def test_surface_digest_projection_is_exact_and_matches_envelope_commitments() -> None:
    registry = external_audit.build_canonical_registry()
    profile = external_audit.build_canonical_fabric_profile()
    digests = canonical_observation_surface_digests(
        registry,
        profile,
        source={},
        evidence={},
        artifact={},
        freshness={},
        handoffs={},
        traces={},
    )
    envelope = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        **_frontiers(),
    )

    assert tuple(digests) == (
        "registry",
        "authority-graph",
        "source-state",
        "evidence",
        "artifact",
        "freshness",
        "handoff",
        "work-trace",
    )
    assert digests == {
        "registry": envelope.registry_digest,
        "authority-graph": envelope.authority_graph_digest,
        "source-state": envelope.source_state_frontier_digest,
        "evidence": envelope.evidence_frontier_digest,
        "artifact": envelope.artifact_frontier_digest,
        "freshness": envelope.freshness_fence_frontier_digest,
        "handoff": envelope.handoff_frontier_digest,
        "work-trace": envelope.work_trace_frontier_digest,
    }


def test_scope_digest_projection_is_population_sensitive_for_every_surface() -> None:
    registry = external_audit.build_canonical_registry()
    component_ids = tuple(row.component_id for row in registry.manifests)
    base = canonical_observation_scope_digests(component_ids)
    expanded = canonical_observation_scope_digests((*component_ids, "external.synthetic"))

    assert tuple(base) == (
        "artifact",
        "authority-graph",
        "evidence",
        "freshness",
        "handoff",
        "registry",
        "source-state",
        "work-trace",
    )
    assert set(base) == set(expanded)
    assert all(base[kind] != expanded[kind] for kind in base)


def test_observation_and_admission_bundle_bind_the_same_snapshot_context() -> None:
    frontiers = _frontiers()
    frontiers["current_source_state_digests"] = {"external.a": "source-a"}
    frontiers["current_evidence_digests"] = {"evidence.a": "evidence-a"}
    frontiers["current_artifact_digests"] = {"artifact.a": "artifact-a"}
    frontiers["current_freshness_fences"] = {"external.a": "fence-a"}
    frontiers["known_handoff_digests"] = {"handoff.a": "handoff-a"}
    frontiers["current_work_trace_digests"] = {"trace.a": "trace-a"}

    observation = admission_bundle.build_canonical_observation(
        observed_epoch=11,
        **frontiers,
    )
    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=11,
        **frontiers,
    )
    context = bundle.context

    assert observation.registry_digest == context.registry_digest
    assert observation.authority_graph_digest == context.authority_graph_digest
    assert observation.source_state_frontier_digest == context.source_state_frontier_digest
    assert observation.evidence_frontier_digest == context.evidence_frontier_digest
    assert observation.artifact_frontier_digest == context.artifact_frontier_digest
    assert observation.freshness_fence_frontier_digest == context.freshness_fence_frontier_digest
    assert observation.handoff_frontier_digest == context.handoff_frontier_digest
    assert observation.work_trace_frontier_digest == context.work_trace_frontier_digest
    assert observation.observed_epoch == context.observed_epoch == 11


@pytest.mark.parametrize("missing_key", BUNDLE_KEYS)
def test_bundle_restore_rejects_every_missing_top_level_key(missing_key: str) -> None:
    state = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=7,
        **_frontiers(),
    ).to_state()
    state.pop(missing_key)
    with pytest.raises(ValueError):
        admission_bundle.CanonicalAdmissionBundle.from_state(state)


def test_bundle_restore_rejects_unknown_top_level_key() -> None:
    state = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=7,
        **_frontiers(),
    ).to_state()
    state["unexpected"] = "value"
    with pytest.raises(ValueError, match="non-canonical"):
        admission_bundle.CanonicalAdmissionBundle.from_state(state)


def test_v4_audit_digest_binds_exact_observation_digest() -> None:
    left = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=True,
        observation_digest="canonical-observation-v1-left",
    )
    right = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=True,
        observation_digest="canonical-observation-v1-right",
    )
    assert left.protocol == right.protocol == "external-integration-admission-audit-v4"
    assert left.findings == right.findings == ()
    assert left.observation_digest != right.observation_digest
    assert left.digest != right.digest
    assert set(left.to_state()) == {
        "protocol",
        "findings",
        "digest",
        "observation_digest",
    }


def test_historical_v3_audit_does_not_relabel_or_bind_observation_digest() -> None:
    left = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=False,
        observation_digest="ignored-left",
    )
    right = admission_bundle.CanonicalAdmissionAuditReport.create(
        (),
        current_observation=False,
        observation_digest="ignored-right",
    )
    assert left.protocol == right.protocol == "external-integration-admission-audit-v3"
    assert left.observation_digest is right.observation_digest is None
    assert left.digest == right.digest
    assert "observation_digest" not in left.to_state()


def test_clean_current_genesis_audit_is_exact_v4_and_finding_free() -> None:
    report = admission_bundle.run_canonical_admission_audit(
        observed_epoch=7,
        observation_genesis=True,
        **_frontiers(),
    )
    assert report.findings == ()
    assert report.protocol == "external-integration-admission-audit-v4"
    assert report.digest.startswith("admission-audit-v4-")
    assert report.observation_digest is not None
    assert report.observation_digest.startswith("canonical-observation-v1-")


def test_current_audit_rejects_boolean_like_genesis_smuggling() -> None:
    report = admission_bundle.run_canonical_admission_audit(
        observed_epoch=7,
        observation_genesis=1,  # type: ignore[arg-type]
        **_frontiers(),
    )
    codes = {row.code for row in report.findings}
    assert "CURRENT_OBSERVATION_GENESIS_INVALID" in codes
    assert "CURRENT_OBSERVATION_WITNESS_UNAVAILABLE" in codes


def test_explicit_current_witness_requires_all_six_detached_live_frontiers() -> None:
    envelope = _observation()
    report = admission_bundle.run_canonical_admission_audit(
        bundle=admission_bundle.build_canonical_admission_bundle(
            observed_epoch=7,
            **_frontiers(),
        ),
        current_observed_epoch=7,
        current_observation=envelope,
        observation_genesis=True,
        current_source_state_digests=None,
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
        known_handoff_digests={},
        current_work_trace_digests={},
    )
    assert "CURRENT_OBSERVATION_SURFACE_UNAVAILABLE" in {
        row.code for row in report.findings
    }


def test_forged_current_witness_is_converted_to_audit_finding_not_exception() -> None:
    envelope = replace(_observation(), digest="canonical-observation-v1-forged")
    report = admission_bundle.run_canonical_admission_audit(
        bundle=admission_bundle.build_canonical_admission_bundle(
            observed_epoch=7,
            **_frontiers(),
        ),
        current_observed_epoch=7,
        current_observation=envelope,
        observation_genesis=True,
        **_frontiers(),
    )
    assert "CURRENT_OBSERVATION_WITNESS_INVALID" in {
        row.code for row in report.findings
    }


@pytest.mark.parametrize(
    ("subject_id", "field"),
    [
        ("registry", "registry_digest"),
        ("authority-graph", "authority_graph_digest"),
        ("source-state", "source_state_frontier_digest"),
        ("evidence", "evidence_frontier_digest"),
        ("artifact", "artifact_frontier_digest"),
        ("freshness", "freshness_fence_frontier_digest"),
        ("handoff", "handoff_frontier_digest"),
        ("work-trace", "work_trace_frontier_digest"),
    ],
)
def test_every_observation_commitment_is_cross_checked_against_admission_context(
    subject_id: str,
    field: str,
) -> None:
    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=7,
        **_frontiers(),
    )
    envelope = _rebuild_observation(_observation(), **{field: f"mutated:{field}"})
    report = admission_bundle.run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=7,
        current_observation=envelope,
        observation_genesis=True,
        **_frontiers(),
    )
    assert any(
        row.code == "OBSERVATION_ADMISSION_CONTEXT_MISMATCH"
        and row.subject_id == subject_id
        for row in report.findings
    )


def test_observation_epoch_is_cross_checked_against_admission_context() -> None:
    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=7,
        **_frontiers(),
    )
    envelope = _rebuild_observation(_observation(), observed_epoch=8)
    report = admission_bundle.run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=7,
        current_observation=envelope,
        observation_genesis=True,
        **_frontiers(),
    )
    assert any(
        row.code == "OBSERVATION_ADMISSION_CONTEXT_MISMATCH"
        and row.subject_id == "observed-epoch"
        for row in report.findings
    )


def test_audit_report_order_and_digest_are_deterministic() -> None:
    rows = (
        AdmissionAuditFinding("Z_CODE", "z-detail", "z-subject"),
        AdmissionAuditFinding("A_CODE", "a-detail", "a-subject"),
        AdmissionAuditFinding("M_CODE", "m-detail", "m-subject"),
    )
    forward = admission_bundle.CanonicalAdmissionAuditReport.create(
        rows,
        current_observation=True,
        observation_digest="canonical-observation-v1-fixed",
    )
    reverse = admission_bundle.CanonicalAdmissionAuditReport.create(
        tuple(reversed(rows)),
        current_observation=True,
        observation_digest="canonical-observation-v1-fixed",
    )
    assert forward.to_state() == reverse.to_state()
    assert forward.digest == reverse.digest
    assert [row.code for row in forward.findings] == ["A_CODE", "M_CODE", "Z_CODE"]


def test_frozen_admission_v2_has_no_back_import_from_a8_a10_layers() -> None:
    path = ROOT / "nolane" / "external_core" / "integration_admission.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert "nolane.external_core.observation" not in imported_modules
    assert "nolane.external_core.observation_integration" not in imported_modules
    assert "nolane.external_core.observation_population" not in imported_modules
    assert "nolane.external_core.integration_admission_bundle" not in imported_modules
