from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from cogcoder.organization.foundry_profiles import EphemeralIdentityManifest
from nolane.core.canonical_digest import canonical_digest


@dataclass(frozen=True, slots=True)
class TemporaryWorkUnitManifest:
    """Canonical Epoch-0 view of a historical Foundry ephemeral worker.

    This preserves Foundry's bounded execution envelope and provenance without
    admitting the work unit into the permanent 67-identity AgentRegistry.
    """

    work_unit_id: str
    legacy_request_id: str
    team_id: str
    sponsor_agent_id: str
    parent_task_id: str | None
    template_id: str
    mission: str
    allowed_tools: tuple[str, ...]
    allowed_external_cores: tuple[str, ...]
    allowed_artifact_kinds: tuple[str, ...]
    memory_namespace: str
    generation: int
    created_token: int
    expires_token: int
    parent_lease_id: str | None
    parent_lease_epoch: int | None
    legacy_manifest_digest: str
    identity_kind: str = "temporary_work_unit"
    permanent_identity: bool = False
    agent_registry_membership: bool = False
    owns_personal_lifelong_lineage: bool = False
    digest: str = ""

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (
            self.work_unit_id, self.legacy_request_id, self.team_id,
            self.sponsor_agent_id, self.template_id, self.mission, self.memory_namespace,
            self.legacy_manifest_digest,
        )):
            raise ValueError("temporary work-unit identity, sponsor, mission and provenance must be explicit")
        if self.identity_kind != "temporary_work_unit":
            raise ValueError("canonical Foundry replacement must remain a temporary work unit")
        if self.permanent_identity or self.agent_registry_membership or self.owns_personal_lifelong_lineage:
            raise ValueError("temporary work unit cannot acquire permanent AI identity semantics")
        if self.generation <= 0 or self.created_token < 0 or self.expires_token <= self.created_token:
            raise ValueError("temporary work-unit generation/lifetime is invalid")
        if (self.parent_lease_id is None) != (self.parent_lease_epoch is None):
            raise ValueError("parent lease id and epoch must appear together")
        expected = canonical_digest(self.payload())
        if self.digest and self.digest != expected:
            raise ValueError("temporary work-unit digest mismatch")
        if not self.digest:
            object.__setattr__(self, "digest", expected)

    def payload(self) -> dict[str, Any]:
        return {
            "work_unit_id": self.work_unit_id,
            "legacy_request_id": self.legacy_request_id,
            "team_id": self.team_id,
            "sponsor_agent_id": self.sponsor_agent_id,
            "parent_task_id": self.parent_task_id,
            "template_id": self.template_id,
            "mission": self.mission,
            "allowed_tools": list(self.allowed_tools),
            "allowed_external_cores": list(self.allowed_external_cores),
            "allowed_artifact_kinds": list(self.allowed_artifact_kinds),
            "memory_namespace": self.memory_namespace,
            "generation": self.generation,
            "created_token": self.created_token,
            "expires_token": self.expires_token,
            "parent_lease_id": self.parent_lease_id,
            "parent_lease_epoch": self.parent_lease_epoch,
            "legacy_manifest_digest": self.legacy_manifest_digest,
            "identity_kind": self.identity_kind,
            "permanent_identity": self.permanent_identity,
            "agent_registry_membership": self.agent_registry_membership,
            "owns_personal_lifelong_lineage": self.owns_personal_lifelong_lineage,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_legacy_foundry(cls, row: EphemeralIdentityManifest) -> "TemporaryWorkUnitManifest":
        return cls(
            work_unit_id=row.ephemeral_id,
            legacy_request_id=row.request_id,
            team_id=row.team_id,
            sponsor_agent_id=row.sponsor_agent_id,
            parent_task_id=row.parent_task_id,
            template_id=row.template_id,
            mission=row.mission,
            allowed_tools=row.allowed_tools,
            allowed_external_cores=row.allowed_external_cores,
            allowed_artifact_kinds=row.allowed_artifact_kinds,
            memory_namespace=row.memory_namespace,
            generation=row.generation,
            created_token=row.created_token,
            expires_token=row.expires_token,
            parent_lease_id=row.parent_lease_id,
            parent_lease_epoch=row.parent_lease_epoch,
            legacy_manifest_digest=row.digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TemporaryWorkUnitManifest":
        return cls(
            work_unit_id=str(state["work_unit_id"]),
            legacy_request_id=str(state["legacy_request_id"]),
            team_id=str(state["team_id"]),
            sponsor_agent_id=str(state["sponsor_agent_id"]),
            parent_task_id=None if state.get("parent_task_id") is None else str(state["parent_task_id"]),
            template_id=str(state["template_id"]),
            mission=str(state["mission"]),
            allowed_tools=tuple(str(x) for x in state.get("allowed_tools", ())),
            allowed_external_cores=tuple(str(x) for x in state.get("allowed_external_cores", ())),
            allowed_artifact_kinds=tuple(str(x) for x in state.get("allowed_artifact_kinds", ())),
            memory_namespace=str(state["memory_namespace"]),
            generation=int(state["generation"]),
            created_token=int(state["created_token"]),
            expires_token=int(state["expires_token"]),
            parent_lease_id=None if state.get("parent_lease_id") is None else str(state["parent_lease_id"]),
            parent_lease_epoch=None if state.get("parent_lease_epoch") is None else int(state["parent_lease_epoch"]),
            legacy_manifest_digest=str(state["legacy_manifest_digest"]),
            identity_kind=str(state.get("identity_kind", "temporary_work_unit")),
            permanent_identity=bool(state.get("permanent_identity", False)),
            agent_registry_membership=bool(state.get("agent_registry_membership", False)),
            owns_personal_lifelong_lineage=bool(state.get("owns_personal_lifelong_lineage", False)),
            digest=str(state.get("digest", "")),
        )
