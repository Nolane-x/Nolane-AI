from __future__ import annotations

import nolane.external_core as external_core


def test_a3_public_api_exposes_structural_registry_live_restore_and_discovery_types():
    required = {
        "ManifestAdapter",
        "CanonicalComponentRegistry",
        "RegistryCoverageFinding",
        "RegistryCoverageReport",
        "CapabilityCatalogBindingReceipt",
        "RegistryCapabilityDiscoveryIndex",
        "LiveExternalCoreSnapshot",
        "LiveRestoreDisposition",
        "LiveRestoreAssessment",
        "handoff_frontier_digest",
        "work_trace_frontier_digest",
        "source_state_frontier_digest",
        "assess_live_restore",
        "assess_live_restore_state",
        "artifact_state_digest",
        "audit_live_external_core",
    }
    assert required <= set(external_core.__all__)
    for name in required:
        assert hasattr(external_core, name)


def test_a3_public_api_does_not_expose_runtime_governor_or_mutation_surface():
    forbidden = {
        "invoke",
        "execute",
        "authorize",
        "promote",
        "deploy",
        "repair",
        "register_runtime",
        "build_canonical_registry",
        "build_canonical_live_snapshot",
    }
    assert forbidden.isdisjoint(set(external_core.__all__))
    for name in forbidden:
        assert not hasattr(external_core, name)
