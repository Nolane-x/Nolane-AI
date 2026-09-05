from __future__ import annotations

import pytest

from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.live_fabric import handoff_frontier_digest, work_trace_frontier_digest
from nolane.external_core.registry import CapabilityCatalogBindingReceipt, ManifestAdapter


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
