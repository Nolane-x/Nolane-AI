from __future__ import annotations

import pytest

from nolane.external_core.authority_graph import ExternalAuthorityGraph
from nolane.external_core.capability_discovery import RegistryCapabilityDiscoveryIndex
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.live_fabric import (
    LiveExternalCoreSnapshot,
    LiveRestoreDisposition,
    assess_live_restore,
    handoff_frontier_digest,
    work_trace_frontier_digest,
)
from nolane.external_core.registry import (
    CapabilityCatalogBindingReceipt,
    CanonicalComponentRegistry,
    ManifestAdapter,
)


def _manifest() -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id="hardening-component",
        component_version="1.0.0",
        family=ExternalCoreFamily.G,
        protocol_versions={"state": "1"},
        consumes_contracts=(),
        produces_contracts=(),
        authority_capabilities=("observe",),
        forbidden_authorities=("execute",),
        mutable_resources=(),
        evidence_inputs=(),
        evidence_outputs=(),
        restore_protocol="exact-v1",
        compatibility_floor="1.0.0",
        compatibility_ceiling="1.0.0",
    )


def _registry() -> CanonicalComponentRegistry:
    manifest = _manifest()
    adapter = ManifestAdapter.create(
        adapter_id="adapter:hardening",
        source_locator="nolane.example.hardening",
        source_component_id=manifest.component_id,
        source_component_version=manifest.component_version,
        manifest=manifest,
    )
    return CanonicalComponentRegistry.create((adapter,))


def test_handoff_frontier_rejects_same_identity_with_different_payloads():
    with pytest.raises(ValueError, match="duplicate handoff.*identity"):
        handoff_frontier_digest(
            (
                {"handoff_id": "handoff-1", "payload_digest": "a"},
                {"handoff_id": "handoff-1", "payload_digest": "b"},
            )
        )


def test_work_trace_frontier_rejects_same_identity_with_different_payloads():
    with pytest.raises(ValueError, match="duplicate work-trace.*identity"):
        work_trace_frontier_digest(
            (
                {"trace_id": "trace-1", "node": "a"},
                {"trace_id": "trace-1", "node": "b"},
            )
        )


def test_manifest_adapter_identity_fields_are_strict_strings_not_stringified_values():
    manifest = _manifest()
    with pytest.raises(ValueError, match="adapter id"):
        ManifestAdapter.create(
            adapter_id=True,  # type: ignore[arg-type]
            source_locator="nolane.example",
            source_component_id=manifest.component_id,
            source_component_version=manifest.component_version,
            manifest=manifest,
        )
    with pytest.raises(ValueError, match="source locator"):
        ManifestAdapter.create(
            adapter_id="adapter:hardening",
            source_locator=7,  # type: ignore[arg-type]
            source_component_id=manifest.component_id,
            source_component_version=manifest.component_version,
            manifest=manifest,
        )


def test_capability_binding_identity_fields_are_strict_strings():
    with pytest.raises(ValueError, match="catalog version"):
        CapabilityCatalogBindingReceipt.create(
            catalog_version=True,  # type: ignore[arg-type]
            catalog_digest="catalog",
            registry_digest="registry",
        )
    with pytest.raises(ValueError, match="registry digest"):
        CapabilityCatalogBindingReceipt.create(
            catalog_version="1.0.0",
            catalog_digest="catalog",
            registry_digest={"forged": "digest"},  # type: ignore[arg-type]
        )


def test_assess_live_restore_revalidates_directly_constructed_snapshot_integrity():
    valid = LiveExternalCoreSnapshot.create(
        registry_digest="registry-current",
        authority_graph_digest="graph-current",
        artifact_graph_digest="artifact-current",
        handoff_frontier_digest="handoff-current",
        work_trace_frontier_digest="trace-current",
        source_state_frontier_digest="source-current",
        component_versions={"hardening-component": "1.0.0"},
    )
    forged = LiveExternalCoreSnapshot(
        registry_digest=valid.registry_digest,
        authority_graph_digest=valid.authority_graph_digest,
        artifact_graph_digest=valid.artifact_graph_digest,
        handoff_frontier_digest=valid.handoff_frontier_digest,
        work_trace_frontier_digest=valid.work_trace_frontier_digest,
        source_state_frontier_digest=valid.source_state_frontier_digest,
        component_versions=valid.component_versions,
        snapshot_id="live-fabric-v1-forged",
    )
    result = assess_live_restore(
        forged,
        current_registry_digest=valid.registry_digest,
        current_authority_graph_digest=valid.authority_graph_digest,
        current_artifact_graph_digest=valid.artifact_graph_digest,
        current_handoff_frontier_digest=valid.handoff_frontier_digest,
        current_work_trace_frontier_digest=valid.work_trace_frontier_digest,
        current_source_state_frontier_digest=valid.source_state_frontier_digest,
        current_component_versions=dict(valid.component_versions),
    )
    assert result.disposition is LiveRestoreDisposition.QUARANTINED
    assert result.authoritative is False
    assert "invalid-snapshot" in result.reasons


def test_registry_bound_discovery_revalidates_directly_constructed_registry_integrity():
    valid = _registry()
    forged = CanonicalComponentRegistry(adapters=valid.adapters, registry_digest="registry-v1-forged")
    graph = ExternalAuthorityGraph(valid.manifests, ())
    with pytest.raises(ValueError, match="registry integrity"):
        RegistryCapabilityDiscoveryIndex.create(forged, graph)


def test_canonical_live_snapshot_builder_rejects_direct_registry_digest_forgery():
    from nolane.external_core.audit import build_canonical_fabric_profile, build_canonical_live_snapshot, build_canonical_registry

    valid = build_canonical_registry()
    forged = CanonicalComponentRegistry(adapters=valid.adapters, registry_digest="registry-v1-forged")
    profile = build_canonical_fabric_profile()
    with pytest.raises(ValueError, match="registry integrity"):
        build_canonical_live_snapshot(registry=forged, profile=profile)
