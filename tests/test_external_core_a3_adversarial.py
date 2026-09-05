from __future__ import annotations

import copy

import pytest

from nolane.external_core import artifacts, assurance, candidate_synthesis, capability_acquisition, coding, evidence, execution, planning, research
from nolane.memory import skills
from nolane.external_core.audit import build_canonical_fabric_profile
from nolane.external_core.authority_graph import ExternalAuthorityGraph
from nolane.external_core.capability_discovery import CapabilityDiscoveryIndex
from nolane.external_core.live_fabric import LiveExternalCoreSnapshot
from nolane.external_core.registry import CanonicalComponentRegistry


def _canonical_sources():
    return (
        evidence,
        assurance,
        skills,
        candidate_synthesis,
        capability_acquisition,
        planning,
        execution,
        coding,
        research,
        artifacts,
    )


def test_canonical_registry_is_built_from_live_component_identity_and_version():
    from nolane.external_core.audit import build_canonical_registry

    registry = build_canonical_registry()
    assert isinstance(registry, CanonicalComponentRegistry)
    assert len(registry.adapters) == 10
    assert set(registry.component_ids) == {source.COMPONENT_ID for source in _canonical_sources()}
    for source in _canonical_sources():
        adapter = registry.adapter_for(source.COMPONENT_ID)
        assert adapter.source_component_id == source.COMPONENT_ID
        assert adapter.source_component_version == source.COMPONENT_VERSION
        assert adapter.manifest.component_version == source.COMPONENT_VERSION
        assert adapter.source_locator == source.__name__


def test_compatibility_profile_is_derived_from_registry_not_a_second_manifest_population():
    from nolane.external_core.audit import build_canonical_registry

    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    assert profile.manifests == registry.manifests
    assert tuple(row.manifest_digest for row in profile.authority_graph.manifests) == tuple(
        row.manifest_digest for row in registry.manifests
    )


def test_canonical_capability_catalog_binding_is_descriptive_and_registry_bound():
    from nolane.external_core.audit import build_canonical_capability_binding, build_canonical_registry

    registry = build_canonical_registry()
    left = build_canonical_capability_binding(registry)
    right = build_canonical_capability_binding(registry)
    assert left == right
    assert left.registry_digest == registry.registry_digest
    assert left.descriptive_only is True
    assert left.catalog_digest
    assert left.catalog_version == "metadata-external-core-catalog-v1"
    for forbidden in ("authorize", "invoke", "execute", "promote", "grant"):
        assert not hasattr(left, forbidden)


def test_registry_backed_discovery_binds_registry_and_authority_graph_exactly():
    from nolane.external_core.audit import build_canonical_registry
    from nolane.external_core.capability_discovery import RegistryCapabilityDiscoveryIndex

    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    index = RegistryCapabilityDiscoveryIndex.create(registry, profile.authority_graph)
    assert index.registry_digest == registry.registry_digest
    assert index.authority_graph_digest == profile.authority_graph.digest
    assert len(index.components()) == 10
    restored = RegistryCapabilityDiscoveryIndex.from_state(index.to_state())
    assert restored.to_state() == index.to_state()
    for forbidden in ("invoke", "execute", "authorize", "promote", "repair", "register_runtime"):
        assert not hasattr(index, forbidden)


def test_registry_backed_discovery_rejects_graph_from_a_different_manifest_population():
    from nolane.external_core.audit import build_canonical_registry
    from nolane.external_core.capability_discovery import RegistryCapabilityDiscoveryIndex

    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    forged_registry = CanonicalComponentRegistry.create(registry.adapters[:-1])
    with pytest.raises(ValueError, match="registry"):
        RegistryCapabilityDiscoveryIndex.create(forged_registry, profile.authority_graph)


def test_registry_backed_discovery_restore_rejects_registry_digest_substitution():
    from nolane.external_core.audit import build_canonical_registry
    from nolane.external_core.capability_discovery import RegistryCapabilityDiscoveryIndex

    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    index = RegistryCapabilityDiscoveryIndex.create(registry, profile.authority_graph)
    state = copy.deepcopy(index.to_state())
    state["registry_digest"] = "registry-v1-forged"
    with pytest.raises(ValueError):
        RegistryCapabilityDiscoveryIndex.from_state(state)


def test_canonical_live_snapshot_binds_registry_graph_frontiers_and_exact_versions():
    from nolane.external_core.audit import build_canonical_live_snapshot, build_canonical_registry

    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    snapshot = build_canonical_live_snapshot(registry=registry, profile=profile)
    assert isinstance(snapshot, LiveExternalCoreSnapshot)
    assert snapshot.registry_digest == registry.registry_digest
    assert snapshot.authority_graph_digest == profile.authority_graph.digest
    assert dict(snapshot.component_versions) == registry.component_versions
    assert snapshot.handoff_frontier_digest.startswith("handoff-frontier-v1-")
    assert snapshot.work_trace_frontier_digest.startswith("work-trace-frontier-v1-")
    assert snapshot.source_state_frontier_digest.startswith("source-state-frontier-v1-")


def test_live_audit_is_clean_for_canonical_registry_and_detects_registry_substitution():
    from nolane.external_core.audit import (
        build_canonical_fabric_profile,
        build_canonical_live_snapshot,
        build_canonical_registry,
        run_canonical_live_audit,
    )
    from nolane.external_core.coherence_audit import audit_live_external_core

    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    snapshot = build_canonical_live_snapshot(registry=registry, profile=profile)
    clean = run_canonical_live_audit()
    assert clean.clean is True

    forged = CanonicalComponentRegistry.create(registry.adapters[:-1])
    report = audit_live_external_core(
        registry=forged,
        authority_graph=profile.authority_graph,
        snapshot=snapshot,
        handoffs=(),
        traces=(),
        current_source_state_digests={},
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
    )
    codes = {finding.code for finding in report.findings}
    assert "REGISTRY_GRAPH_DRIFT" in codes
    assert "LIVE_REGISTRY_DIGEST_DRIFT" in codes


def test_live_audit_detects_authority_graph_and_frontier_substitution():
    from nolane.external_core.audit import build_canonical_fabric_profile, build_canonical_live_snapshot, build_canonical_registry
    from nolane.external_core.coherence_audit import audit_live_external_core

    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    snapshot = build_canonical_live_snapshot(registry=registry, profile=profile)
    forged_snapshot = LiveExternalCoreSnapshot.create(
        registry_digest=snapshot.registry_digest,
        authority_graph_digest="authority-graph-forged",
        artifact_graph_digest=snapshot.artifact_graph_digest,
        handoff_frontier_digest="handoff-frontier-v1-forged",
        work_trace_frontier_digest="work-trace-frontier-v1-forged",
        source_state_frontier_digest="source-state-frontier-v1-forged",
        component_versions=dict(snapshot.component_versions),
    )
    report = audit_live_external_core(
        registry=registry,
        authority_graph=profile.authority_graph,
        snapshot=forged_snapshot,
        handoffs=(),
        traces=(),
        current_source_state_digests={},
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
    )
    codes = {finding.code for finding in report.findings}
    assert {
        "LIVE_AUTHORITY_GRAPH_DIGEST_DRIFT",
        "LIVE_HANDOFF_FRONTIER_DRIFT",
        "LIVE_WORK_TRACE_FRONTIER_DRIFT",
        "LIVE_SOURCE_STATE_FRONTIER_DRIFT",
    } <= codes


def test_existing_a2_discovery_still_round_trips_after_a3_extension():
    profile = build_canonical_fabric_profile()
    index = CapabilityDiscoveryIndex(profile.manifests, profile.authority_graph)
    assert CapabilityDiscoveryIndex.from_state(index.to_state()).to_state() == index.to_state()


def test_a3_registry_cannot_make_an_invalid_authority_graph_coherent():
    from nolane.external_core.audit import build_canonical_registry

    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    # Registration is descriptive: dropping graph authority cannot be repaired by registry presence.
    reduced_graph = ExternalAuthorityGraph(registry.manifests, ())
    assert reduced_graph.digest != profile.authority_graph.digest
    assert registry.registry_digest
