from __future__ import annotations

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.refoundation.runtime_state_map import RuntimeStateMapper


def test_canonical_state_bundle_roundtrips_exact_accepted_runtime_state() -> None:
    runtime = OrganizationRuntime.first_generation()
    legacy = runtime.to_state()
    bundle = RuntimeStateMapper().bundle_state(legacy)

    assert bundle.lossless
    assert bundle.restore_legacy_state() == legacy
    assert bundle.legacy_state_digest == RuntimeStateMapper().map_state(legacy).legacy_state_digest
    assert len(bundle.digest) == 64


def test_canonical_state_bundle_groups_legacy_sections_by_versioned_owner() -> None:
    legacy = OrganizationRuntime.first_generation().to_state()
    bundle = RuntimeStateMapper().bundle_state(legacy)

    architecture = bundle.owner_state("external.architecture")
    assert set(architecture) == {"architecture", "adr"}
    assert architecture["architecture"] == legacy["architecture"]
    assert architecture["adr"] == legacy["adr"]

    coordination = bundle.owner_state("organization.coordination")
    assert set(coordination) == {"coordination"}
    assert coordination["coordination"] == legacy["coordination"]


def test_restored_bundle_is_loadable_by_accepted_runtime_without_semantic_drift() -> None:
    runtime = OrganizationRuntime.first_generation()
    bundle = RuntimeStateMapper().bundle_state(runtime.to_state())
    restored = OrganizationRuntime.from_state(bundle.restore_legacy_state())
    assert restored.to_state() == runtime.to_state()


def test_owner_projection_cannot_drop_a_legacy_section() -> None:
    legacy = OrganizationRuntime.first_generation().to_state()
    bundle = RuntimeStateMapper().bundle_state(legacy)
    flattened = {
        legacy_section
        for owner_payload in bundle.owners.values()
        for legacy_section in owner_payload
    }
    assert flattened == set(legacy)
