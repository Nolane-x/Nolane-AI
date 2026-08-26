from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.schemas.identity import AgentRank
from nolane.organization.events import EventKind

from .events import EventLedger
from .identity import AgentRegistry
from .tasks import TaskGraph, TaskRecord

COMPONENT_ID = "organization.coordination.leases"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.coordination_leases"


class LeaseStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    COMPLETED = "completed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class TaskLeaseReceipt:
    lease_id: str
    task_id: str
    agent_id: str
    epoch: int
    status: LeaseStatus
    granted_event_id: str | None
    supersedes_lease_id: str | None
    evidence_refs: tuple[str, ...]
    last_heartbeat_token: int
    stale_after_tokens: int
    renewal_count: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "epoch": self.epoch,
            "status": self.status.value,
            "granted_event_id": self.granted_event_id,
            "supersedes_lease_id": self.supersedes_lease_id,
            "evidence_refs": list(self.evidence_refs),
            "last_heartbeat_token": self.last_heartbeat_token,
            "stale_after_tokens": self.stale_after_tokens,
            "renewal_count": self.renewal_count,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TaskLeaseReceipt":
        row = cls(
            lease_id=str(state["lease_id"]),
            task_id=str(state["task_id"]),
            agent_id=str(state["agent_id"]),
            epoch=int(state["epoch"]),
            status=LeaseStatus(str(state["status"])),
            granted_event_id=None if state.get("granted_event_id") is None else str(state["granted_event_id"]),
            supersedes_lease_id=None if state.get("supersedes_lease_id") is None else str(state["supersedes_lease_id"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            last_heartbeat_token=int(state.get("last_heartbeat_token", 0)),
            stale_after_tokens=int(state.get("stale_after_tokens", 3)),
            renewal_count=int(state.get("renewal_count", 0)),
            digest=str(state["digest"]),
        )
        if row.epoch <= 0 or row.stale_after_tokens <= 0 or row.last_heartbeat_token < 0 or row.renewal_count < 0:
            raise ValueError("invalid lease counters")
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("lease receipt digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class StaleAgentReceipt:
    stale_id: str
    lease_id: str
    task_id: str
    agent_id: str
    detection_token: int
    last_heartbeat_token: int
    region_chief_id: str | None
    escalation_recipients: tuple[str, ...]
    status: str
    event_id: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "stale_id": self.stale_id,
            "lease_id": self.lease_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "detection_token": self.detection_token,
            "last_heartbeat_token": self.last_heartbeat_token,
            "region_chief_id": self.region_chief_id,
            "escalation_recipients": list(self.escalation_recipients),
            "status": self.status,
            "event_id": self.event_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "StaleAgentReceipt":
        row = cls(
            stale_id=str(state["stale_id"]),
            lease_id=str(state["lease_id"]),
            task_id=str(state["task_id"]),
            agent_id=str(state["agent_id"]),
            detection_token=int(state["detection_token"]),
            last_heartbeat_token=int(state["last_heartbeat_token"]),
            region_chief_id=None if state.get("region_chief_id") is None else str(state["region_chief_id"]),
            escalation_recipients=tuple(str(x) for x in state.get("escalation_recipients", ())),
            status=str(state.get("status", "detected")),
            event_id=str(state["event_id"]),
            digest=str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("stale-agent receipt digest mismatch")
        return row


class LeaseCoordinator:
    """Canonical task-lease epoch, fencing and stale-agent authority."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        tasks: TaskGraph,
        events: EventLedger,
        receipts: tuple[TaskLeaseReceipt, ...] = (),
        stale_receipts: tuple[StaleAgentReceipt, ...] = (),
        lease_counter: int = 0,
        stale_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.tasks = tasks
        self.events = events
        self._receipts: dict[str, TaskLeaseReceipt] = {}
        self._active_by_task: dict[str, str] = {}
        self._last_by_task: dict[str, str] = {}
        self._epochs: dict[str, int] = {}
        self._stale: dict[str, StaleAgentReceipt] = {}
        for row in receipts:
            self._install(row)
        for row in stale_receipts:
            self.registry.get(row.agent_id)
            self.events.get(row.event_id)
            if row.lease_id not in self._receipts:
                raise ValueError("stale receipt references unknown lease")
            self._stale[row.lease_id] = row
        self._lease_counter = int(lease_counter)
        self._stale_counter = int(stale_counter)
        if self._lease_counter < len(self._receipts) or self._stale_counter < len(self._stale):
            raise ValueError("lease counters are not canonical")
        self._validate_active_truth()

    def _install(self, row: TaskLeaseReceipt) -> None:
        if row.lease_id in self._receipts:
            raise ValueError(f"duplicate lease id: {row.lease_id}")
        self.registry.get(row.agent_id)
        self.tasks.get(row.task_id)
        if row.granted_event_id is not None:
            self.events.get(row.granted_event_id)
        prior_epoch = self._epochs.get(row.task_id, 0)
        if row.epoch < prior_epoch:
            raise ValueError("lease epochs are not monotonic")
        self._epochs[row.task_id] = max(prior_epoch, row.epoch)
        self._receipts[row.lease_id] = row
        self._last_by_task[row.task_id] = row.lease_id
        if row.status is LeaseStatus.ACTIVE:
            existing = self._active_by_task.get(row.task_id)
            if existing is not None:
                raise ValueError(f"task {row.task_id} has multiple active leases")
            self._active_by_task[row.task_id] = row.lease_id

    def _validate_active_truth(self) -> None:
        for task in self.tasks.tasks():
            active_id = self._active_by_task.get(task.task_id)
            if active_id is None:
                if task.leased_to is not None and self._receipts:
                    raise ValueError(f"task {task.task_id} lease truth missing from coordinator")
                continue
            row = self._receipts[active_id]
            if task.leased_to != row.agent_id:
                raise ValueError(f"task {task.task_id} lease disagrees with TaskGraph")

    @staticmethod
    def _digest_row(**kwargs: Any) -> TaskLeaseReceipt:
        temp = TaskLeaseReceipt(digest="", **kwargs)
        return replace(temp, digest=canonical_digest(temp.payload()))

    def grant(
        self,
        task_id: str,
        agent_id: str,
        *,
        token: int = 0,
        stale_after_tokens: int = 3,
        evidence_refs: tuple[str, ...] = (),
    ) -> TaskLeaseReceipt:
        task = self.tasks.get(task_id)
        identity = self.registry.get(agent_id)
        if token < 0 or stale_after_tokens <= 0:
            raise ValueError("lease tokens must be non-negative and stale budget positive")
        active_id = self._active_by_task.get(task.task_id)
        if active_id is not None:
            active = self._receipts[active_id]
            if active.agent_id == identity.agent_id:
                return active
            raise ValueError(f"task {task.task_id} already has active lease {active.lease_id}")
        if task.completed_by is not None or task.aborted_by is not None:
            raise ValueError(f"task {task.task_id} is terminal")
        if task.leased_to is not None and task.leased_to != identity.agent_id:
            raise ValueError(f"task {task.task_id} is already leased to {task.leased_to}")
        self.tasks.lease(task.task_id, identity.agent_id)
        epoch = self._epochs.get(task.task_id, 0) + 1
        prior_id = self._last_by_task.get(task.task_id)
        event = self.events.append(
            EventKind.TASK_LEASE_GRANTED,
            source_agent_id=identity.agent_id,
            target_agent_id=identity.agent_id,
            region=identity.region,
            object_refs=(task.task_id,),
            evidence_refs=tuple(str(x) for x in evidence_refs),
            payload={"task_id": task.task_id, "agent_id": identity.agent_id, "epoch": epoch},
        )
        self._lease_counter += 1
        row = self._digest_row(
            lease_id=f"lease-{self._lease_counter:08d}",
            task_id=task.task_id,
            agent_id=identity.agent_id,
            epoch=epoch,
            status=LeaseStatus.ACTIVE,
            granted_event_id=event.event_id,
            supersedes_lease_id=prior_id,
            evidence_refs=tuple(str(x) for x in evidence_refs),
            last_heartbeat_token=int(token),
            stale_after_tokens=int(stale_after_tokens),
            renewal_count=0,
        )
        self._receipts[row.lease_id] = row
        self._active_by_task[row.task_id] = row.lease_id
        self._last_by_task[row.task_id] = row.lease_id
        self._epochs[row.task_id] = row.epoch
        return row

    def heartbeat(
        self,
        task_id: str,
        agent_id: str,
        *,
        lease_id: str,
        epoch: int,
        token: int,
    ) -> TaskLeaseReceipt:
        current = self.current(task_id)
        if current.lease_id != str(lease_id) or current.epoch != int(epoch) or current.agent_id != str(agent_id):
            raise PermissionError("heartbeat does not match current lease holder and epoch")
        if token < current.last_heartbeat_token:
            raise ValueError("heartbeat token cannot move backwards")
        self.events.append(
            EventKind.TASK_LEASE_RENEWED,
            source_agent_id=current.agent_id,
            target_agent_id=current.agent_id,
            region=self.registry.get(current.agent_id).region,
            causal_parent_ids=() if current.granted_event_id is None else (current.granted_event_id,),
            object_refs=(current.task_id,),
            payload={"lease_id": current.lease_id, "epoch": current.epoch, "token": int(token)},
        )
        row = self._digest_row(
            lease_id=current.lease_id,
            task_id=current.task_id,
            agent_id=current.agent_id,
            epoch=current.epoch,
            status=current.status,
            granted_event_id=current.granted_event_id,
            supersedes_lease_id=current.supersedes_lease_id,
            evidence_refs=current.evidence_refs,
            last_heartbeat_token=int(token),
            stale_after_tokens=current.stale_after_tokens,
            renewal_count=current.renewal_count + 1,
        )
        self._receipts[row.lease_id] = row
        return row

    def revoke(
        self,
        task_id: str,
        actor_agent_id: str,
        *,
        reason: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> TaskLeaseReceipt:
        current = self.current(task_id)
        actor = self.registry.get(actor_agent_id)
        holder = self.registry.get(current.agent_id)
        reason = str(reason).strip()
        if not reason:
            raise ValueError("lease revocation requires explicit reason")
        if actor.agent_id != "nolane.central":
            if actor.rank is not AgentRank.CHIEF or holder.region_chief_id != actor.agent_id:
                raise PermissionError("lease revocation requires Central or the holder Regional Chief")
        self.tasks.release_lease(current.task_id, current.agent_id)
        self.events.append(
            EventKind.TASK_LEASE_REVOKED,
            source_agent_id=actor.agent_id,
            target_agent_id=current.agent_id,
            region=holder.region,
            object_refs=(current.task_id,),
            evidence_refs=tuple(str(x) for x in evidence_refs),
            payload={"lease_id": current.lease_id, "epoch": current.epoch, "reason": reason},
        )
        row = self._digest_row(
            lease_id=current.lease_id,
            task_id=current.task_id,
            agent_id=current.agent_id,
            epoch=current.epoch,
            status=LeaseStatus.REVOKED,
            granted_event_id=current.granted_event_id,
            supersedes_lease_id=current.supersedes_lease_id,
            evidence_refs=current.evidence_refs,
            last_heartbeat_token=current.last_heartbeat_token,
            stale_after_tokens=current.stale_after_tokens,
            renewal_count=current.renewal_count,
        )
        self._receipts[row.lease_id] = row
        self._active_by_task.pop(row.task_id, None)
        return row

    def complete(
        self,
        task_id: str,
        agent_id: str,
        *,
        lease_id: str,
        epoch: int,
        output_artifact_ids: tuple[str, ...] = (),
    ) -> TaskRecord:
        current = self.current(task_id)
        if current.lease_id != str(lease_id) or current.epoch != int(epoch) or current.agent_id != str(agent_id):
            raise PermissionError("completion requires current lease holder and epoch")
        if self.tasks.get(task_id).leased_to != current.agent_id:
            raise PermissionError("TaskGraph no longer recognizes this lease holder")
        completed = self.tasks.complete(task_id, agent_id, output_artifact_ids=output_artifact_ids)
        row = self._digest_row(
            lease_id=current.lease_id,
            task_id=current.task_id,
            agent_id=current.agent_id,
            epoch=current.epoch,
            status=LeaseStatus.COMPLETED,
            granted_event_id=current.granted_event_id,
            supersedes_lease_id=current.supersedes_lease_id,
            evidence_refs=current.evidence_refs,
            last_heartbeat_token=current.last_heartbeat_token,
            stale_after_tokens=current.stale_after_tokens,
            renewal_count=current.renewal_count,
        )
        self._receipts[row.lease_id] = row
        self._active_by_task.pop(row.task_id, None)
        return completed

    def detect_stale(self, current_token: int) -> tuple[StaleAgentReceipt, ...]:
        if current_token < 0:
            raise ValueError("stale detection token must be non-negative")
        rows: list[StaleAgentReceipt] = []
        for task_id in sorted(self._active_by_task):
            lease = self._receipts[self._active_by_task[task_id]]
            if current_token - lease.last_heartbeat_token < lease.stale_after_tokens:
                continue
            existing = self._stale.get(lease.lease_id)
            if existing is not None:
                rows.append(existing)
                continue
            identity = self.registry.get(lease.agent_id)
            if identity.rank is AgentRank.CENTRAL:
                recipients: tuple[str, ...] = ()
            elif identity.rank is AgentRank.CHIEF:
                recipients = ("nolane.central",)
            else:
                recipients = () if identity.region_chief_id is None else (identity.region_chief_id,)
            event = self.events.append(
                EventKind.STALE_AGENT_DETECTED,
                source_agent_id="nolane.central",
                target_agent_id=recipients[0] if recipients else lease.agent_id,
                region=identity.region,
                object_refs=(lease.task_id,),
                payload={
                    "lease_id": lease.lease_id,
                    "agent_id": lease.agent_id,
                    "detection_token": int(current_token),
                    "last_heartbeat_token": lease.last_heartbeat_token,
                    "escalation_recipients": list(recipients),
                },
            )
            self._stale_counter += 1
            temp = StaleAgentReceipt(
                stale_id=f"stale-{self._stale_counter:08d}",
                lease_id=lease.lease_id,
                task_id=lease.task_id,
                agent_id=lease.agent_id,
                detection_token=int(current_token),
                last_heartbeat_token=lease.last_heartbeat_token,
                region_chief_id=identity.region_chief_id,
                escalation_recipients=recipients,
                status="detected",
                event_id=event.event_id,
                digest="",
            )
            row = replace(temp, digest=canonical_digest(temp.payload()))
            self._stale[lease.lease_id] = row
            rows.append(row)
        return tuple(rows)

    def current(self, task_id: str) -> TaskLeaseReceipt:
        try:
            return self._receipts[self._active_by_task[str(task_id)]]
        except KeyError as exc:
            raise KeyError(f"task {task_id} has no active coordination lease") from exc

    def receipts(self) -> tuple[TaskLeaseReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def stale_receipts(self) -> tuple[StaleAgentReceipt, ...]:
        return tuple(self._stale[key] for key in sorted(self._stale))

    def to_state(self) -> dict[str, Any]:
        return {
            "receipts": [row.to_state() for row in self.receipts()],
            "stale_receipts": [row.to_state() for row in self.stale_receipts()],
            "lease_counter": self._lease_counter,
            "stale_counter": self._stale_counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        tasks: TaskGraph,
        events: EventLedger,
        state: Mapping[str, Any],
    ) -> "LeaseCoordinator":
        if not state:
            rows: list[TaskLeaseReceipt] = []
            counter = 0
            for task in tasks.tasks():
                if task.leased_to is None or task.completed_by is not None or task.aborted_by is not None:
                    continue
                counter += 1
                temp = TaskLeaseReceipt(
                    lease_id=f"lease-{counter:08d}",
                    task_id=task.task_id,
                    agent_id=task.leased_to,
                    epoch=1,
                    status=LeaseStatus.ACTIVE,
                    granted_event_id=None,
                    supersedes_lease_id=None,
                    evidence_refs=(),
                    last_heartbeat_token=0,
                    stale_after_tokens=3,
                    renewal_count=0,
                    digest="",
                )
                rows.append(replace(temp, digest=canonical_digest(temp.payload())))
            return cls(
                registry=registry,
                tasks=tasks,
                events=events,
                receipts=tuple(rows),
                lease_counter=counter,
            )
        receipts = tuple(TaskLeaseReceipt.from_state(x) for x in state.get("receipts", ()))
        stale = tuple(StaleAgentReceipt.from_state(x) for x in state.get("stale_receipts", ()))
        return cls(
            registry=registry,
            tasks=tasks,
            events=events,
            receipts=receipts,
            stale_receipts=stale,
            lease_counter=int(state.get("lease_counter", len(receipts))),
            stale_counter=int(state.get("stale_counter", len(stale))),
        )


__all__ = (
    "LeaseCoordinator",
    "LeaseStatus",
    "StaleAgentReceipt",
    "TaskLeaseReceipt",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
