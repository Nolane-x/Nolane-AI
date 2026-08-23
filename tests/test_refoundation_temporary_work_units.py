from __future__ import annotations

from cogcoder.organization.foundry_profiles import EphemeralIdentityManifest
from cogcoder.organization.types import canonical_digest
from cogcoder.refoundation.temporary_work_units import TemporaryWorkUnitManifest


def _legacy_manifest() -> EphemeralIdentityManifest:
    payload = {
        "ephemeral_id": "ephemeral-00000001",
        "request_id": "foundry-request-abc",
        "team_id": "team-refactor",
        "sponsor_agent_id": "coding.chief",
        "parent_task_id": "task-refactor-1",
        "template_id": "repository-archaeologist",
        "mission": "inspect historical source without mutating it",
        "allowed_tools": ["filesystem", "git", "code-search", "evidence-store"],
        "allowed_external_cores": ["github-research", "repo-graph"],
        "allowed_artifact_kinds": ["research-note", "evidence"],
        "memory_namespace": "foundry/team-refactor/ephemeral-00000001",
        "generation": 1,
        "created_token": 10,
        "expires_token": 110,
        "parent_lease_id": "lease-00000001",
        "parent_lease_epoch": 3,
    }
    return EphemeralIdentityManifest(
        ephemeral_id=payload["ephemeral_id"],
        request_id=payload["request_id"],
        team_id=payload["team_id"],
        sponsor_agent_id=payload["sponsor_agent_id"],
        parent_task_id=payload["parent_task_id"],
        template_id=payload["template_id"],
        mission=payload["mission"],
        allowed_tools=tuple(payload["allowed_tools"]),
        allowed_external_cores=tuple(payload["allowed_external_cores"]),
        allowed_artifact_kinds=tuple(payload["allowed_artifact_kinds"]),
        memory_namespace=payload["memory_namespace"],
        generation=payload["generation"],
        created_token=payload["created_token"],
        expires_token=payload["expires_token"],
        parent_lease_id=payload["parent_lease_id"],
        parent_lease_epoch=payload["parent_lease_epoch"],
        digest=canonical_digest(payload),
    )


def test_legacy_foundry_manifest_maps_losslessly_to_temporary_work_unit() -> None:
    legacy = _legacy_manifest()
    unit = TemporaryWorkUnitManifest.from_legacy_foundry(legacy)

    assert unit.work_unit_id == legacy.ephemeral_id
    assert unit.legacy_request_id == legacy.request_id
    assert unit.sponsor_agent_id == legacy.sponsor_agent_id
    assert unit.parent_task_id == legacy.parent_task_id
    assert unit.parent_lease_id == legacy.parent_lease_id
    assert unit.parent_lease_epoch == legacy.parent_lease_epoch
    assert unit.allowed_tools == legacy.allowed_tools
    assert unit.allowed_external_cores == legacy.allowed_external_cores
    assert unit.allowed_artifact_kinds == legacy.allowed_artifact_kinds
    assert unit.memory_namespace == legacy.memory_namespace
    assert unit.created_token == legacy.created_token
    assert unit.expires_token == legacy.expires_token
    assert unit.legacy_manifest_digest == legacy.digest


def test_temporary_work_unit_is_explicitly_not_a_permanent_agent_identity() -> None:
    unit = TemporaryWorkUnitManifest.from_legacy_foundry(_legacy_manifest())
    assert unit.permanent_identity is False
    assert unit.agent_registry_membership is False
    assert unit.owns_personal_lifelong_lineage is False
    assert unit.identity_kind == "temporary_work_unit"


def test_temporary_work_unit_retains_bounded_lifetime_and_parent_lease_lineage() -> None:
    unit = TemporaryWorkUnitManifest.from_legacy_foundry(_legacy_manifest())
    assert unit.generation == 1
    assert unit.expires_token > unit.created_token
    assert unit.parent_task_id is not None
    assert unit.parent_lease_id is not None
    assert unit.parent_lease_epoch is not None


def test_temporary_work_unit_state_is_content_bound() -> None:
    unit = TemporaryWorkUnitManifest.from_legacy_foundry(_legacy_manifest())
    restored = TemporaryWorkUnitManifest.from_state(unit.to_state())
    assert restored == unit
    assert len(unit.digest) == 64
