from __future__ import annotations

import copy
import importlib

import pytest

from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily


def _a3():
    return importlib.import_module("nolane.external_core.registry")


def _manifest(component_id: str, version: str = "1.0.0", *, family: ExternalCoreFamily = ExternalCoreFamily.A):
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version=version,
        family=family,
        protocol_versions={"state": "1"},
        consumes=("evidence",),
        produces=("finding",),
        authority_capabilities=("verify",),
        forbidden_authorities=("execute",),
        mutable_resources=(),
        evidence_inputs=("evidence",),
        evidence_outputs=("finding",),
        restore_protocol="exact-v1",
        compatibility_floor="1.0.0",
        compatibility_ceiling="1.9.9",
    )


def _adapter(component_id: str, version: str = "1.0.0", *, locator: str | None = None):
    a3 = _a3()
    manifest = _manifest(component_id, version)
    return a3.ManifestAdapter.create(
        adapter_id=f"adapter:{component_id}",
        source_locator=locator or f"nolane.example:{component_id}",
        source_component_id=component_id,
        source_component_version=version,
        manifest=manifest,
    )


def test_registry_module_exists_as_explicit_a3_boundary():
    assert importlib.util.find_spec("nolane.external_core.registry") is not None


def test_manifest_adapter_is_content_addressed_and_exact_restorable():
    a3 = _a3()
    adapter = _adapter("verification")
    assert adapter.adapter_digest.startswith("adapter-v1-")
    assert a3.ManifestAdapter.from_state(adapter.to_state()) == adapter

    tampered = copy.deepcopy(adapter.to_state())
    tampered["source_component_version"] = "9.9.9"
    with pytest.raises(ValueError):
        a3.ManifestAdapter.from_state(tampered)


def test_manifest_adapter_rejects_identity_or_version_substitution():
    a3 = _a3()
    manifest = _manifest("verification", "1.2.3")
    with pytest.raises(ValueError, match="identity"):
        a3.ManifestAdapter.create(
            adapter_id="adapter:verification",
            source_locator="nolane.truth:VerificationAuthority",
            source_component_id="forged-verification",
            source_component_version="1.2.3",
            manifest=manifest,
        )
    with pytest.raises(ValueError, match="version"):
        a3.ManifestAdapter.create(
            adapter_id="adapter:verification",
            source_locator="nolane.truth:VerificationAuthority",
            source_component_id="verification",
            source_component_version="9.9.9",
            manifest=manifest,
        )


def test_registry_digest_is_order_independent_and_lookup_is_read_only():
    a3 = _a3()
    first = _adapter("verification")
    second = _adapter("planning", locator="nolane.goal:PlanningAuthority")
    left = a3.CanonicalComponentRegistry.create((first, second))
    right = a3.CanonicalComponentRegistry.create((second, first))
    assert left.registry_digest == right.registry_digest
    assert left.component_ids == ("planning", "verification")
    assert left.manifest_for("verification") == first.manifest
    assert left.adapter_for("planning") == second
    for forbidden in ("invoke", "execute", "authorize", "promote", "repair", "register_runtime"):
        assert not hasattr(left, forbidden)


def test_registry_rejects_duplicate_component_and_adapter_identity():
    a3 = _a3()
    first = _adapter("verification")
    duplicate_component = a3.ManifestAdapter.create(
        adapter_id="adapter:verification:other",
        source_locator="nolane.other:VerificationAuthority",
        source_component_id="verification",
        source_component_version="1.0.0",
        manifest=_manifest("verification"),
    )
    with pytest.raises(ValueError, match="duplicate component"):
        a3.CanonicalComponentRegistry.create((first, duplicate_component))

    duplicate_adapter_id = a3.ManifestAdapter.create(
        adapter_id=first.adapter_id,
        source_locator="nolane.other:PlanningAuthority",
        source_component_id="planning",
        source_component_version="1.0.0",
        manifest=_manifest("planning"),
    )
    with pytest.raises(ValueError, match="duplicate adapter"):
        a3.CanonicalComponentRegistry.create((first, duplicate_adapter_id))


def test_registry_exact_restore_rejects_noncanonical_order_and_digest_tamper():
    a3 = _a3()
    registry = a3.CanonicalComponentRegistry.create((_adapter("verification"), _adapter("planning")))
    assert a3.CanonicalComponentRegistry.from_state(registry.to_state()) == registry

    reordered = copy.deepcopy(registry.to_state())
    reordered["adapters"].reverse()
    with pytest.raises(ValueError):
        a3.CanonicalComponentRegistry.from_state(reordered)

    tampered = copy.deepcopy(registry.to_state())
    tampered["registry_digest"] = "registry-v1-forged"
    with pytest.raises(ValueError):
        a3.CanonicalComponentRegistry.from_state(tampered)


def test_registry_coverage_is_categorical_for_missing_orphan_identity_and_version_drift():
    a3 = _a3()
    registry = a3.CanonicalComponentRegistry.create(
        (_adapter("verification", "1.0.0", locator="nolane.a:Verification"), _adapter("orphan", locator="nolane.x:Orphan"))
    )
    report = registry.validate_coverage(
        {
            "nolane.a:Verification": ("verification", "1.1.0"),
            "nolane.c:Planning": ("planning", "1.0.0"),
            "nolane.x:Orphan": ("different-id", "1.0.0"),
        }
    )
    codes = {finding.code for finding in report.findings}
    assert {"MISSING_ADAPTER", "IDENTITY_DRIFT", "VERSION_DRIFT"} <= codes
    assert report.coherent is False

    clean = registry.validate_coverage(
        {
            "nolane.a:Verification": ("verification", "1.0.0"),
            "nolane.x:Orphan": ("orphan", "1.0.0"),
        }
    )
    assert clean.coherent is True
    assert clean.findings == ()


def test_registry_coverage_surfaces_unexpected_orphan_adapter():
    a3 = _a3()
    registry = a3.CanonicalComponentRegistry.create((_adapter("verification", locator="nolane.a:Verification"),))
    report = registry.validate_coverage({}, reject_unexpected=True)
    assert [finding.code for finding in report.findings] == ["ORPHAN_ADAPTER"]


def test_capability_catalog_binding_is_descriptive_only_and_content_addressed():
    a3 = _a3()
    registry = a3.CanonicalComponentRegistry.create((_adapter("verification"),))
    receipt = a3.CapabilityCatalogBindingReceipt.create(
        catalog_version="1.0.0",
        catalog_digest="catalog-sha256-deadbeef",
        registry_digest=registry.registry_digest,
    )
    assert receipt.descriptive_only is True
    assert receipt.receipt_id.startswith("capability-binding-v1-")
    assert a3.CapabilityCatalogBindingReceipt.from_state(receipt.to_state()) == receipt
    assert not hasattr(receipt, "authorize")
    assert not hasattr(receipt, "invoke")

    forged = copy.deepcopy(receipt.to_state())
    forged["descriptive_only"] = False
    with pytest.raises(ValueError):
        a3.CapabilityCatalogBindingReceipt.from_state(forged)


def test_capability_binding_rejects_empty_or_noncanonical_identity_fields():
    a3 = _a3()
    with pytest.raises(ValueError):
        a3.CapabilityCatalogBindingReceipt.create(
            catalog_version="",
            catalog_digest="catalog",
            registry_digest="registry",
        )
