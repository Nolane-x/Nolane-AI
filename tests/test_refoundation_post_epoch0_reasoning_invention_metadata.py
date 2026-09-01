from __future__ import annotations

from nolane.metadata.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.metadata.manifests import build_component_manifests


COMPONENT_ID = "external.reasoning_invention"
CANONICAL_MODULE = "nolane.external_core.reasoning_invention"


def test_reasoning_invention_is_declared_as_canonical_native_v004_component() -> None:
    manifests = {row.component_id: row for row in build_component_manifests()}
    assert COMPONENT_ID in manifests
    manifest = manifests[COMPONENT_ID]
    assert str(manifest.version) == "0.0.4"
    assert manifest.layer == "external_core"
    assert manifest.state_schema == "reasoning-invention-v1"
    assert manifest.dependencies == (
        "external.cognitive_library",
        "external.candidate_synthesis",
        "external.causal",
        "external.experimentation",
        "external.evidence",
    )
    assert "external.capability_acquisition" not in manifest.dependencies
    assert "external.transfer_meta" not in manifest.dependencies
    assert "external.assurance" not in manifest.dependencies
    assert "policy evolution" in manifest.responsibility.lower()
    assert "external authorization" in manifest.responsibility.lower()

    ledger = build_component_implementation_ledger()
    record = ledger[COMPONENT_ID]
    assert record.status is ImplementationStatus.CANONICAL_NATIVE
    assert record.component_version == "0.0.4"
    assert record.canonical_module == CANONICAL_MODULE
    assert record.legacy_sources == ()
    assert record.canonical_write_authority
    assert "policy evolution" in record.notes.lower()
    assert "external authorization" in record.notes.lower()
