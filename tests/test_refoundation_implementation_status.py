from __future__ import annotations

from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from cogcoder.refoundation.manifests import build_component_manifests


WAVE2_NATIVE_VERSIONS = {
    "organization.identity": "0.0.1",
    "organization.authority": "0.0.1",
    "organization.events": "0.0.1",
}


def test_every_component_has_exactly_one_implementation_status_record() -> None:
    components = {row.component_id for row in build_component_manifests()}
    ledger = build_component_implementation_ledger()
    assert set(ledger) == components
    assert all(ledger[key].component_id == key for key in ledger)
    for key in ledger:
        assert ledger[key].component_version == WAVE2_NATIVE_VERSIONS.get(key, "0.0.0")


def test_manifest_presence_never_implies_migration_completion() -> None:
    ledger = build_component_implementation_ledger()
    assert ledger["organization.identity"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["organization.authority"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["organization.events"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["organization.runtime"].status is ImplementationStatus.CANONICAL_NATIVE
    assert ledger["external.memory.fabric"].status is ImplementationStatus.COMPATIBILITY_FACADE
    assert ledger["external.planning"].status is ImplementationStatus.COMPATIBILITY_FACADE


def test_unextracted_cognitive_components_are_not_falsely_marked_canonical() -> None:
    ledger = build_component_implementation_ledger()
    for component_id in (
        "external.knowledge",
        "external.epistemic",
        "external.cognitive_library",
        "external.capability_acquisition",
        "external.causal",
        "external.experimentation",
        "external.transfer_meta",
    ):
        assert ledger[component_id].status is ImplementationStatus.HISTORICAL_ONLY
        assert not ledger[component_id].canonical_write_authority


def test_frozen_neural_asset_is_not_conflated_with_runtime_adapter() -> None:
    ledger = build_component_implementation_ledger()
    assert ledger["neural.shared"].status is ImplementationStatus.FROZEN_ASSET
    assert ledger["neural.inference_bridge"].status is ImplementationStatus.COMPATIBILITY_FACADE


def test_only_explicit_native_components_claim_canonical_write_authority() -> None:
    ledger = build_component_implementation_ledger()
    writers = {key for key, row in ledger.items() if row.canonical_write_authority}
    assert writers == {
        "organization.identity",
        "organization.authority",
        "organization.events",
        "organization.runtime",
        "organization.temporary_work_units",
    }
