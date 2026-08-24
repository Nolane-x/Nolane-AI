from __future__ import annotations

from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from cogcoder.refoundation.manifests import build_component_manifests


# These are the accepted native implementation owners at the current
# refoundation head. The contract is intentionally wave-independent: future
# native cutovers extend this authority set instead of preserving a stale
# migration-wave worldview.
ACCEPTED_CANONICAL_NATIVE_COMPONENTS = {
    "schemas.identity",
    "core.canonical_digest",
    "organization.identity",
    "organization.authority",
    "organization.events",
    "organization.tasks",
    "organization.lifecycle",
    "organization.coordination.leases",
    "organization.coordination.delivery",
    "organization.coordination.conflicts",
    "organization.coordination",
    "organization.central",
    "organization.runtime",
    "organization.temporary_work_units",
    "external.artifacts",
    "external.verification",
    "external.evidence",
    "external.memory.fabric",
    "external.memory.lifecycle",
    "external.memory.retrieval",
}


def test_every_component_has_exactly_one_implementation_status_record() -> None:
    manifests = {row.component_id: row for row in build_component_manifests()}
    ledger = build_component_implementation_ledger()
    assert set(ledger) == set(manifests)
    assert all(ledger[key].component_id == key for key in ledger)
    for key, row in ledger.items():
        assert row.component_version == str(manifests[key].version)


def test_manifest_presence_never_implies_migration_completion() -> None:
    ledger = build_component_implementation_ledger()
    for component_id in ACCEPTED_CANONICAL_NATIVE_COMPONENTS:
        assert ledger[component_id].status is ImplementationStatus.CANONICAL_NATIVE

    # Adjacent manifest-backed components remain explicit facades until their
    # own cutover receipts are accepted.
    assert ledger["external.context"].status is ImplementationStatus.COMPATIBILITY_FACADE
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
    native = {key for key, row in ledger.items() if row.status is ImplementationStatus.CANONICAL_NATIVE}

    assert native == ACCEPTED_CANONICAL_NATIVE_COMPONENTS
    assert writers == native
