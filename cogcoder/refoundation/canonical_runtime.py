from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from cogcoder.organization.planning import Milestone, PlanNode, PlanRevision, PlanRisk
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.tasks import TaskRecord
from cogcoder.organization.coordination_leases import TaskLeaseReceipt
from cogcoder.organization.types import AgentIdentity, canonical_digest

from .identity_source import build_manifest_driven_runtime
from .manifests import build_bootstrap_agent_manifests


_IMMUTABLE_IDENTITY_FIELDS: tuple[str, ...] = (
    "agent_id",
    "name",
    "region",
    "role",
    "rank",
    "neural_version",
    "parameter_accounting",
    "region_chief_id",
    "direct_work_capable",
    "learning_capable",
    "cognitive_capabilities",
    "memory_namespace",
    "skill_namespace",
    "external_core_bindings",
    "tool_permissions",
    "authority_scope",
)


def _validate_registry_definition(runtime: OrganizationRuntime) -> None:
    expected = {row.agent_id: row.identity_state() for row in build_bootstrap_agent_manifests()}
    actual = {row.agent_id: row.to_state() for row in runtime.registry.identities()}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise ValueError(f"runtime permanent identity set diverges from canonical manifests: missing={missing}, extra={extra}")
    mismatches: list[str] = []
    for agent_id in sorted(expected):
        for field in _IMMUTABLE_IDENTITY_FIELDS:
            if actual[agent_id].get(field) != expected[agent_id].get(field):
                mismatches.append(f"{agent_id}:{field}")
    if mismatches:
        raise ValueError("runtime immutable identity definition diverges from canonical manifests: " + ", ".join(mismatches))


@dataclass(slots=True)
class CanonicalOrganization:
    """Canonical public runtime boundary for Refoundation.

    The accepted organization implementation remains the execution engine, but
    callers no longer receive raw plan/lease write objects. MasterPlanGraph is
    authoritative for plan revisions; LeaseCoordinator is authoritative for
    task lease epochs, heartbeat, revoke and completion. TaskGraph is retained
    as the execution projection and historical state carrier.
    """

    _runtime: OrganizationRuntime
    identity_source: str = "canonical-manifests"

    def __post_init__(self) -> None:
        if self.identity_source != "canonical-manifests":
            raise ValueError("canonical runtime identity authority must be canonical manifests")
        _validate_registry_definition(self._runtime)

    @classmethod
    def first_generation(cls) -> "CanonicalOrganization":
        return cls(build_manifest_driven_runtime())

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CanonicalOrganization":
        return cls(OrganizationRuntime.from_state(state))

    @property
    def plan_revision(self) -> int:
        return int(self._runtime.planning.graph.version)

    @property
    def state_digest(self) -> str:
        return canonical_digest(self._runtime.to_state())

    def identities(self) -> tuple[AgentIdentity, ...]:
        return self._runtime.registry.identities()

    def identity(self, agent_id: str) -> AgentIdentity:
        return self._runtime.registry.get(agent_id)

    def task(self, task_id: str) -> TaskRecord:
        return self._runtime.tasks.get(task_id)

    def current_task_lease(self, task_id: str) -> TaskLeaseReceipt:
        return self._runtime.coordination.leases.current(task_id)

    def apply_plan_revision(
        self,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        upsert_nodes: tuple[PlanNode, ...],
        milestones: tuple[Milestone, ...] = (),
        risks: tuple[PlanRisk, ...] = (),
    ) -> PlanRevision:
        return self._runtime.planning.apply_revision(
            actor_agent_id=actor_agent_id,
            reason=reason,
            evidence_refs=evidence_refs,
            upsert_nodes=upsert_nodes,
            milestones=milestones,
            risks=risks,
        )

    def rollback_plan(
        self,
        *,
        actor_agent_id: str,
        source_revision: int,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> PlanRevision:
        return self._runtime.planning.rollback(
            actor_agent_id=actor_agent_id,
            source_revision=source_revision,
            reason=reason,
            evidence_refs=evidence_refs,
        )

    def add_task(self, task_id: str, *, title: str, plan_node_id: str) -> TaskRecord:
        # Canonical task creation cannot invent an independent plan namespace.
        self._runtime.planning.graph.get(plan_node_id)
        row = self._runtime.tasks.add_task(task_id, title=title, plan_node_id=plan_node_id)
        self._runtime.planning.link_task(row.task_id, plan_node_id)
        return row

    def add_task_dependency(self, task_id: str, dependency_id: str) -> TaskRecord:
        return self._runtime.tasks.add_dependency(task_id, dependency_id)

    def grant_task_lease(
        self,
        task_id: str,
        agent_id: str,
        *,
        token: int = 0,
        stale_after_tokens: int = 3,
        evidence_refs: tuple[str, ...] = (),
    ) -> TaskLeaseReceipt:
        return self._runtime.coordination.leases.grant(
            task_id,
            agent_id,
            token=token,
            stale_after_tokens=stale_after_tokens,
            evidence_refs=evidence_refs,
        )

    def heartbeat_task_lease(
        self,
        task_id: str,
        agent_id: str,
        *,
        lease_id: str,
        epoch: int,
        token: int,
    ) -> TaskLeaseReceipt:
        return self._runtime.coordination.leases.heartbeat(
            task_id,
            agent_id,
            lease_id=lease_id,
            epoch=epoch,
            token=token,
        )

    def revoke_task_lease(
        self,
        task_id: str,
        actor_agent_id: str,
        *,
        reason: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> TaskLeaseReceipt:
        return self._runtime.coordination.leases.revoke(
            task_id,
            actor_agent_id,
            reason=reason,
            evidence_refs=evidence_refs,
        )

    def complete_task(
        self,
        task_id: str,
        agent_id: str,
        *,
        lease_id: str,
        epoch: int,
        output_artifact_ids: tuple[str, ...] = (),
    ) -> TaskRecord:
        return self._runtime.coordination.leases.complete(
            task_id,
            agent_id,
            lease_id=lease_id,
            epoch=epoch,
            output_artifact_ids=output_artifact_ids,
        )

    def detect_stale_task_leases(self, current_token: int):
        return self._runtime.coordination.leases.detect_stale(current_token)

    def to_state(self) -> dict[str, Any]:
        # Preserve the accepted serialized runtime contract during Epoch 0.
        return self._runtime.to_state()

    def canonical_metadata(self) -> dict[str, Any]:
        payload = {
            "identity_source": self.identity_source,
            "permanent_identity_count": len(self.identities()),
            "plan_authority": "MasterPlanGraph",
            "lease_authority": "LeaseCoordinator",
            "task_graph_role": "execution_projection",
            "accepted_runtime_state_digest": self.state_digest,
        }
        return {**payload, "digest": canonical_digest(payload)}
