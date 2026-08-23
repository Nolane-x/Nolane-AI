from __future__ import annotations

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.refoundation.identity_source import (
    build_canonical_agent_identities,
    build_manifest_driven_runtime,
)
from cogcoder.refoundation.manifests import build_bootstrap_agent_manifests


def test_agent_manifest_carries_complete_agentidentity_state_without_loss() -> None:
    legacy = {row.agent_id: row for row in build_first_generation_blueprint()}
    manifests = {row.agent_id: row for row in build_bootstrap_agent_manifests()}
    assert set(manifests) == set(legacy)
    for agent_id, identity in legacy.items():
        assert manifests[agent_id].identity_state() == identity.to_state()


def test_canonical_identity_source_roundtrips_exact_67_identity_states() -> None:
    legacy = build_first_generation_blueprint()
    canonical = build_canonical_agent_identities()
    assert len(canonical) == 67
    assert [row.to_state() for row in canonical] == [row.to_state() for row in legacy]


def test_manifest_driven_runtime_bootstrap_matches_accepted_first_generation_state() -> None:
    accepted = OrganizationRuntime.first_generation()
    canonical = build_manifest_driven_runtime()

    assert canonical is not accepted
    assert canonical.to_state() == accepted.to_state()
    assert {row.agent_id for row in canonical.registry.identities()} == {
        row.agent_id for row in build_canonical_agent_identities()
    }


def test_manifest_runtime_registry_is_not_rebuilt_from_mutable_runtime_state() -> None:
    canonical = build_manifest_driven_runtime()
    before = tuple(row.to_state() for row in build_canonical_agent_identities())
    canonical.registry.bind_task("coding.backend.01", "example-task")
    after = tuple(row.to_state() for row in build_canonical_agent_identities())
    assert after == before
