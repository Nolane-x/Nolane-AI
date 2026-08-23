from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cogcoder.organization.foundry import FoundryControlPlane
from cogcoder.organization.foundry_profiles import SpawnRequest
from cogcoder.organization.foundry_resources import FoundryBudget
from cogcoder.organization.types import canonical_digest

from .temporary_work_units import TemporaryWorkUnitManifest


@dataclass(frozen=True, slots=True)
class TemporaryWorkUnitBudget:
    compute_units: int
    tool_calls: int
    external_core_calls: int
    max_workers: int
    lifetime_tokens: int

    def __post_init__(self) -> None:
        # Delegate first-generation limits to the accepted budget contract.
        self.to_legacy_budget()

    def to_legacy_budget(self) -> FoundryBudget:
        return FoundryBudget(
            compute_units=int(self.compute_units),
            tool_calls=int(self.tool_calls),
            external_core_calls=int(self.external_core_calls),
            max_workers=int(self.max_workers),
            lifetime_tokens=int(self.lifetime_tokens),
        )

    def to_state(self) -> dict[str, int]:
        return self.to_legacy_budget().to_state()


@dataclass(frozen=True, slots=True)
class TemporaryWorkUnitRequest:
    request_id: str
    sponsor_agent_id: str
    parent_task_id: str | None
    template_id: str
    mission: str
    team_id: str
    budget: TemporaryWorkUnitBudget
    requested_tools: tuple[str, ...]
    requested_external_cores: tuple[str, ...]
    allowed_artifact_kinds: tuple[str, ...]
    created_token: int
    status: str
    approved_by: str | None
    legacy_request_digest: str
    kind: str = "temporary_work_unit_request"
    digest: str = ""

    def __post_init__(self) -> None:
        if self.kind != "temporary_work_unit_request":
            raise ValueError("canonical request kind must be temporary_work_unit_request")
        if not self.request_id.strip() or not self.sponsor_agent_id.strip() or not self.mission.strip():
            raise ValueError("work-unit request identity, sponsor and mission must be explicit")
        expected = canonical_digest(self.payload())
        if self.digest and self.digest != expected:
            raise ValueError("temporary work-unit request digest mismatch")
        if not self.digest:
            object.__setattr__(self, "digest", expected)

    def payload(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "sponsor_agent_id": self.sponsor_agent_id,
            "parent_task_id": self.parent_task_id,
            "template_id": self.template_id,
            "mission": self.mission,
            "team_id": self.team_id,
            "budget": self.budget.to_state(),
            "requested_tools": list(self.requested_tools),
            "requested_external_cores": list(self.requested_external_cores),
            "allowed_artifact_kinds": list(self.allowed_artifact_kinds),
            "created_token": self.created_token,
            "status": self.status,
            "approved_by": self.approved_by,
            "legacy_request_digest": self.legacy_request_digest,
            "kind": self.kind,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_legacy(cls, row: SpawnRequest) -> "TemporaryWorkUnitRequest":
        budget = TemporaryWorkUnitBudget(**row.budget.to_state())
        return cls(
            request_id=row.request_id,
            sponsor_agent_id=row.sponsor_agent_id,
            parent_task_id=row.parent_task_id,
            template_id=row.template_id,
            mission=row.mission,
            team_id=row.team_id,
            budget=budget,
            requested_tools=row.requested_tools,
            requested_external_cores=row.requested_external_cores,
            allowed_artifact_kinds=row.allowed_artifact_kinds,
            created_token=row.created_token,
            status=row.status.value,
            approved_by=row.approved_by,
            legacy_request_digest=row.digest,
        )


class TemporaryWorkUnitService:
    """Canonical non-agent API over the accepted bounded Foundry engine."""

    def __init__(self, foundry: FoundryControlPlane) -> None:
        self._foundry = foundry

    def request(
        self,
        *,
        sponsor_agent_id: str,
        parent_task_id: str | None,
        template_id: str,
        mission: str,
        team_id: str,
        budget: TemporaryWorkUnitBudget,
        requested_tools: tuple[str, ...] = (),
        requested_external_cores: tuple[str, ...] = (),
        allowed_artifact_kinds: tuple[str, ...] = (),
        current_token: int = 0,
    ) -> TemporaryWorkUnitRequest:
        row = self._foundry.request_spawn(
            sponsor_agent_id=sponsor_agent_id,
            parent_task_id=parent_task_id,
            template_id=template_id,
            mission=mission,
            team_id=team_id,
            budget=budget.to_legacy_budget(),
            requested_tools=requested_tools,
            requested_external_cores=requested_external_cores,
            allowed_artifact_kinds=allowed_artifact_kinds,
            current_token=current_token,
        )
        return TemporaryWorkUnitRequest.from_legacy(row)

    def approve(self, request_id: str, *, actor_agent_id: str) -> TemporaryWorkUnitRequest:
        return TemporaryWorkUnitRequest.from_legacy(
            self._foundry.approve_spawn(request_id, actor_agent_id=actor_agent_id)
        )

    def instantiate(self, request_id: str, *, current_token: int) -> TemporaryWorkUnitManifest:
        return TemporaryWorkUnitManifest.from_legacy_foundry(
            self._foundry.instantiate(request_id, current_token=current_token)
        )

    def requests(self) -> tuple[TemporaryWorkUnitRequest, ...]:
        return tuple(TemporaryWorkUnitRequest.from_legacy(row) for row in self._foundry.spawn_requests())

    def manifests(self) -> tuple[TemporaryWorkUnitManifest, ...]:
        return tuple(TemporaryWorkUnitManifest.from_legacy_foundry(row) for row in self._foundry.manifests())

    def activate(self, work_unit_id: str, *, actor_agent_id: str):
        return self._foundry.activate(work_unit_id, actor_agent_id=actor_agent_id)

    def begin_verification(self, work_unit_id: str, *, actor_agent_id: str):
        return self._foundry.begin_verification(work_unit_id, actor_agent_id=actor_agent_id)

    def quarantine(self, work_unit_id: str, *, actor_agent_id: str, reason: str):
        return self._foundry.quarantine(work_unit_id, actor_agent_id=actor_agent_id, reason=reason)
