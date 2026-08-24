from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.schemas.identity import AgentRank, AgentStatus
from cogcoder.organization.types import EventKind

from .authority import AuthorityGraph
from .coordination_conflicts import ConflictClaim, ConflictCoordinator, ConflictPacket, ConflictResolutionReceipt
from .coordination_delivery import AckStatus, DeliveryCoordinator, DeliveryReceipt
from .coordination_leases import LeaseCoordinator, StaleAgentReceipt, TaskLeaseReceipt
from .events import EventLedger
from .identity import AgentRegistry
from .lifecycle import WakeSleepScheduler
from .tasks import TaskGraph, TaskRecord

COMPONENT_ID = "organization.coordination"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.coordination"


class WakeDisposition(str, Enum):
    RESERVED = "reserved"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class CoordinationBudget:
    max_active_agents: int = 8
    max_region_active_agents: int = 4
    high_severity_max_active_agents: int = 18
    max_pending_acks: int = 64
    max_unresolved_conflicts: int = 32
    max_coordination_events_per_window: int = 256

    def __post_init__(self) -> None:
        values = (
            self.max_active_agents,
            self.max_region_active_agents,
            self.high_severity_max_active_agents,
            self.max_pending_acks,
            self.max_unresolved_conflicts,
            self.max_coordination_events_per_window,
        )
        if any(isinstance(x, bool) or int(x) <= 0 for x in values):
            raise ValueError("coordination budgets must be positive integers")
        if self.high_severity_max_active_agents < self.max_active_agents:
            raise ValueError("high-severity ceiling cannot be lower than normal ceiling")
        if self.high_severity_max_active_agents > 18:
            raise ValueError("first-generation high-severity active-agent ceiling is 18")

    def to_state(self) -> dict[str, int]:
        return {
            "max_active_agents": self.max_active_agents,
            "max_region_active_agents": self.max_region_active_agents,
            "high_severity_max_active_agents": self.high_severity_max_active_agents,
            "max_pending_acks": self.max_pending_acks,
            "max_unresolved_conflicts": self.max_unresolved_conflicts,
            "max_coordination_events_per_window": self.max_coordination_events_per_window,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CoordinationBudget":
        return cls(
            max_active_agents=int(state.get("max_active_agents", 8)),
            max_region_active_agents=int(state.get("max_region_active_agents", 4)),
            high_severity_max_active_agents=int(state.get("high_severity_max_active_agents", 18)),
            max_pending_acks=int(state.get("max_pending_acks", 64)),
            max_unresolved_conflicts=int(state.get("max_unresolved_conflicts", 32)),
            max_coordination_events_per_window=int(state.get("max_coordination_events_per_window", 256)),
        )


@dataclass(frozen=True, slots=True)
class WakeReservation:
    reservation_id: str
    event_id: str
    agent_id: str
    region: str
    disposition: WakeDisposition
    priority: int
    reason: str
    coordination_event_id: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "region": self.region,
            "disposition": self.disposition.value,
            "priority": self.priority,
            "reason": self.reason,
            "coordination_event_id": self.coordination_event_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "WakeReservation":
        row = cls(
            reservation_id=str(state["reservation_id"]),
            event_id=str(state["event_id"]),
            agent_id=str(state["agent_id"]),
            region=str(state["region"]),
            disposition=WakeDisposition(str(state["disposition"])),
            priority=int(state["priority"]),
            reason=str(state["reason"]),
            coordination_event_id=str(state["coordination_event_id"]),
            digest=str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("wake reservation digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class CoordinationEscalation:
    escalation_id: str
    reason: str
    target_agent_id: str | None
    source_event_id: str | None
    event_id: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "escalation_id": self.escalation_id,
            "reason": self.reason,
            "target_agent_id": self.target_agent_id,
            "source_event_id": self.source_event_id,
            "event_id": self.event_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CoordinationEscalation":
        row = cls(
            escalation_id=str(state["escalation_id"]),
            reason=str(state["reason"]),
            target_agent_id=None if state.get("target_agent_id") is None else str(state["target_agent_id"]),
            source_event_id=None if state.get("source_event_id") is None else str(state["source_event_id"]),
            event_id=str(state["event_id"]),
            digest=str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("coordination escalation digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class CoordinationMetrics:
    source_workload_events: int
    generated_coordination_events: int
    delivery_count: int
    acknowledgement_count: int
    wake_reserved_count: int
    wake_deferred_count: int
    lease_transition_count: int
    open_conflicts: int
    resolved_conflicts: int
    peak_active_agents: int
    coordination_event_ratio: float


_COORDINATION_EVENT_KINDS = {
    EventKind.TASK_LEASE_GRANTED,
    EventKind.TASK_LEASE_RENEWED,
    EventKind.TASK_LEASE_REVOKED,
    EventKind.COORDINATION_ACK,
    EventKind.COORDINATION_ESCALATED,
    EventKind.CONFLICT_OPENED,
    EventKind.CONFLICT_CLAIM_ADDED,
    EventKind.CONFLICT_RESOLVED,
    EventKind.WAKE_RESERVED,
    EventKind.WAKE_DEFERRED,
    EventKind.STALE_AGENT_DETECTED,
    EventKind.AGENT_WAKE,
}

_CENTRAL_DIRECT_KINDS = {
    EventKind.CENTRAL_INTERVENTION,
    EventKind.CENTRAL_QUESTION,
    EventKind.CENTRAL_CORRECTION,
    EventKind.CENTRAL_REDIRECT,
    EventKind.CENTRAL_PAUSE,
    EventKind.CENTRAL_ABORT,
    EventKind.CENTRAL_REQUEST_EVIDENCE,
}


class CoordinationControlPlane:
    """Canonical bounded multi-agent coordination composition."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        events: EventLedger,
        authority: AuthorityGraph,
        tasks: TaskGraph,
        scheduler: WakeSleepScheduler,
        leases: LeaseCoordinator | None = None,
        deliveries: DeliveryCoordinator | None = None,
        conflicts: ConflictCoordinator | None = None,
        budget: CoordinationBudget | None = None,
        reservations: tuple[WakeReservation, ...] = (),
        escalations: tuple[CoordinationEscalation, ...] = (),
        reservation_counter: int = 0,
        escalation_counter: int = 0,
        peak_active_agents: int = 0,
    ) -> None:
        self.registry = registry
        self.events = events
        self.authority = authority
        self.tasks = tasks
        self.scheduler = scheduler
        self.leases = leases or LeaseCoordinator(registry=registry, tasks=tasks, events=events)
        self.deliveries_state = deliveries or DeliveryCoordinator(registry=registry, events=events)
        self.conflicts_state = conflicts or ConflictCoordinator(
            registry=registry,
            authority=authority,
            events=events,
        )
        self.budget = budget or CoordinationBudget()
        self._reservations: dict[str, WakeReservation] = {}
        self._wake_by_event: dict[str, tuple[str, ...]] = {}
        for row in reservations:
            self._validate_reservation(row)
            self._reservations[row.reservation_id] = row
            self._wake_by_event.setdefault(row.event_id, tuple())
            self._wake_by_event[row.event_id] += (row.reservation_id,)
        self._escalations: dict[str, CoordinationEscalation] = {}
        for row in escalations:
            self._validate_escalation(row)
            self._escalations[row.escalation_id] = row
        self._reservation_counter = int(reservation_counter)
        self._escalation_counter = int(escalation_counter)
        self._peak_active_agents = int(peak_active_agents)
        if self._reservation_counter < len(self._reservations) or self._escalation_counter < len(self._escalations):
            raise ValueError("coordination counters are not canonical")
        if self._peak_active_agents < 0 or self._peak_active_agents > 18:
            raise ValueError("invalid recorded peak active agents")

    def _validate_reservation(self, row: WakeReservation) -> None:
        source = self.events.get(row.event_id)
        coord = self.events.get(row.coordination_event_id)
        identity = self.registry.get(row.agent_id)
        if identity.region != row.region:
            raise ValueError("wake reservation region mismatch")
        expected = EventKind.WAKE_RESERVED if row.disposition is WakeDisposition.RESERVED else EventKind.WAKE_DEFERRED
        if coord.kind is not expected or source.event_id not in coord.causal_parent_ids:
            raise ValueError("wake reservation event lineage mismatch")

    def _validate_escalation(self, row: CoordinationEscalation) -> None:
        event = self.events.get(row.event_id)
        if event.kind is not EventKind.COORDINATION_ESCALATED:
            raise ValueError("escalation event kind mismatch")
        if row.source_event_id is not None:
            self.events.get(row.source_event_id)
        if row.target_agent_id is not None:
            self.registry.get(row.target_agent_id)

    @staticmethod
    def _rank_order(rank: AgentRank) -> int:
        return {
            AgentRank.CENTRAL: 0,
            AgentRank.CHIEF: 1,
            AgentRank.SENIOR_SPECIALIST: 2,
            AgentRank.SPECIALIST: 3,
        }[rank]

    def _recipients(self, event_id: str) -> tuple[str, ...]:
        event = self.events.get(event_id)
        direct = event.target_agent_id
        candidates: set[str] = set()
        if direct is not None:
            self.registry.get(direct)
            candidates.add(direct)
        for identity in self.registry.identities():
            if any(row.event_id == event.event_id for row in self.events.deliverable_for(identity.agent_id)):
                candidates.add(identity.agent_id)
        if event.source_agent_id == "nolane.central" and event.kind in _CENTRAL_DIRECT_KINDS and direct is not None:
            target = self.registry.get(direct)
            if target.rank is not AgentRank.CHIEF and target.region_chief_id is not None:
                candidates.add(target.region_chief_id)
        return tuple(
            sorted(
                candidates,
                key=lambda aid: (
                    0 if aid == direct else 1,
                    self._rank_order(self.registry.get(aid).rank),
                    aid,
                ),
            )
        )

    def deliver_event(self, event_id: str) -> tuple[DeliveryReceipt, ...]:
        event = self.events.get(event_id)
        rows = tuple(self.deliveries_state.deliver(event.event_id, aid) for aid in self._recipients(event.event_id))
        self._check_ack_budget(event.event_id)
        return rows

    def acknowledge(self, delivery_id: str, agent_id: str) -> DeliveryReceipt:
        row = self.deliveries_state.acknowledge(delivery_id, agent_id)
        self._maybe_coordination_budget(row.event_id)
        return row

    def delivery_for(self, event_id: str, agent_id: str) -> DeliveryReceipt:
        return self.deliveries_state.for_event_recipient(event_id, agent_id)

    def deliveries(self) -> tuple[DeliveryReceipt, ...]:
        return self.deliveries_state.receipts()

    def suppress_delivery(self, delivery_id: str, *, actor_agent_id: str) -> None:
        self.deliveries_state.get(delivery_id)
        self.registry.get(actor_agent_id)
        raise PermissionError("canonical coordination delivery cannot be suppressed by an agent")

    def grant_lease(
        self,
        task_id: str,
        agent_id: str,
        *,
        token: int = 0,
        stale_after_tokens: int = 3,
        evidence_refs: tuple[str, ...] = (),
    ) -> TaskLeaseReceipt:
        row = self.leases.grant(
            task_id,
            agent_id,
            token=token,
            stale_after_tokens=stale_after_tokens,
            evidence_refs=evidence_refs,
        )
        self._maybe_coordination_budget(row.granted_event_id)
        return row

    def heartbeat_lease(
        self,
        task_id: str,
        agent_id: str,
        *,
        lease_id: str,
        epoch: int,
        token: int,
    ) -> TaskLeaseReceipt:
        return self.leases.heartbeat(task_id, agent_id, lease_id=lease_id, epoch=epoch, token=token)

    def revoke_lease(
        self,
        task_id: str,
        actor_agent_id: str,
        *,
        reason: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> TaskLeaseReceipt:
        return self.leases.revoke(task_id, actor_agent_id, reason=reason, evidence_refs=evidence_refs)

    def complete_leased_task(
        self,
        task_id: str,
        agent_id: str,
        *,
        lease_id: str,
        epoch: int,
        output_artifact_ids: tuple[str, ...] = (),
    ) -> TaskRecord:
        return self.leases.complete(
            task_id,
            agent_id,
            lease_id=lease_id,
            epoch=epoch,
            output_artifact_ids=output_artifact_ids,
        )

    def current_lease(self, task_id: str) -> TaskLeaseReceipt:
        return self.leases.current(task_id)

    def open_conflict(
        self,
        opener_agent_id: str,
        subject_artifact_id: str,
        *,
        proposition: str,
        requested_action: str,
        evidence_refs: tuple[str, ...] = (),
        causal_event_ids: tuple[str, ...] = (),
    ) -> ConflictPacket:
        packet = self.conflicts_state.open(
            opener_agent_id,
            subject_artifact_id,
            proposition=proposition,
            requested_action=requested_action,
            evidence_refs=evidence_refs,
            causal_event_ids=causal_event_ids,
        )
        self.deliver_event(packet.opened_event_id)
        self._check_conflict_budget(packet.opened_event_id)
        return packet

    def add_claim(
        self,
        conflict_id: str,
        claimant_agent_id: str,
        *,
        proposition: str,
        requested_action: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> ConflictClaim:
        return self.conflicts_state.add_claim(
            conflict_id,
            claimant_agent_id,
            proposition=proposition,
            requested_action=requested_action,
            evidence_refs=evidence_refs,
        )

    def resolve_conflict(
        self,
        conflict_id: str,
        resolver_agent_id: str,
        *,
        decision: str,
        evidence_refs: tuple[str, ...],
        override_id: str | None = None,
    ) -> ConflictResolutionReceipt:
        return self.conflicts_state.resolve(
            conflict_id,
            resolver_agent_id,
            decision=decision,
            evidence_refs=evidence_refs,
            override_id=override_id,
        )

    def conflict(self, conflict_id: str) -> ConflictPacket:
        return self.conflicts_state.get(conflict_id)

    def conflicts(self) -> tuple[ConflictPacket, ...]:
        return self.conflicts_state.packets()

    def propose_cross_region_change(
        self,
        *,
        proposer_agent_id: str,
        subject_artifact_id: str,
        proposition: str,
        requested_action: str,
        evidence_refs: tuple[str, ...],
    ) -> ConflictPacket:
        return self.open_conflict(
            proposer_agent_id,
            subject_artifact_id,
            proposition=proposition,
            requested_action=requested_action,
            evidence_refs=evidence_refs,
        )

    def delivery_for_owner(self, conflict_id: str) -> DeliveryReceipt:
        packet = self.conflict(conflict_id)
        return self.delivery_for(packet.opened_event_id, packet.owner_agent_id)

    def set_budget(self, budget: CoordinationBudget) -> None:
        self.budget = CoordinationBudget.from_state(budget.to_state())

    def plan_wakes(self, event_id: str, *, mode: str = "normal") -> tuple[WakeReservation, ...]:
        event = self.events.get(event_id)
        if event.event_id in self._wake_by_event:
            return tuple(self._reservations[x] for x in self._wake_by_event[event.event_id])
        if mode not in ("normal", "high_severity"):
            raise ValueError("wake mode must be normal or high_severity")
        global_limit = (
            self.budget.high_severity_max_active_agents
            if mode == "high_severity"
            else self.budget.max_active_agents
        )
        active_ids = {x.agent_id for x in self.registry.identities() if x.status is AgentStatus.ACTIVE}
        active_by_region: dict[str, int] = {}
        for aid in active_ids:
            region = self.registry.get(aid).region
            active_by_region[region] = active_by_region.get(region, 0) + 1
        global_count = len(active_ids)
        result: list[WakeReservation] = []
        for aid in self._recipients(event.event_id):
            identity = self.registry.get(aid)
            if identity.status is AgentStatus.ACTIVE:
                continue
            region_count = active_by_region.get(identity.region, 0)
            reserve = global_count < global_limit and region_count < self.budget.max_region_active_agents
            disposition = WakeDisposition.RESERVED if reserve else WakeDisposition.DEFERRED
            reason = "capacity_reserved" if reserve else "coordination_backpressure"
            if reserve:
                global_count += 1
                active_by_region[identity.region] = region_count + 1
            kind = EventKind.WAKE_RESERVED if reserve else EventKind.WAKE_DEFERRED
            coord_event = self.events.append(
                kind,
                source_agent_id="nolane.central",
                target_agent_id=identity.agent_id,
                region=identity.region,
                causal_parent_ids=(event.event_id,),
                priority=event.priority,
                payload={
                    "source_event_id": event.event_id,
                    "mode": mode,
                    "disposition": disposition.value,
                    "reason": reason,
                },
            )
            self._reservation_counter += 1
            temp = WakeReservation(
                reservation_id=f"wake-reservation-{self._reservation_counter:08d}",
                event_id=event.event_id,
                agent_id=identity.agent_id,
                region=identity.region,
                disposition=disposition,
                priority=event.priority,
                reason=reason,
                coordination_event_id=coord_event.event_id,
                digest="",
            )
            row = replace(temp, digest=canonical_digest(temp.payload()))
            self._reservations[row.reservation_id] = row
            self._wake_by_event.setdefault(event.event_id, tuple())
            self._wake_by_event[event.event_id] += (row.reservation_id,)
            result.append(row)
        self._maybe_coordination_budget(event.event_id)
        return tuple(result)

    def execute_wakes(self, event_id: str) -> tuple[str, ...]:
        if event_id not in self._wake_by_event:
            self.plan_wakes(event_id)
        woke: list[str] = []
        for reservation_id in self._wake_by_event.get(str(event_id), ()):
            row = self._reservations[reservation_id]
            if row.disposition is not WakeDisposition.RESERVED:
                continue
            identity = self.registry.get(row.agent_id)
            if identity.status is AgentStatus.ACTIVE:
                continue
            self.scheduler.wake(row.agent_id, reason=f"coordination:{row.event_id}")
            woke.append(row.agent_id)
            active = sum(x.status is AgentStatus.ACTIVE for x in self.registry.identities())
            self._peak_active_agents = max(self._peak_active_agents, active)
        return tuple(woke)

    def escalate_stale(self, *, current_token: int) -> tuple[StaleAgentReceipt, ...]:
        rows = self.leases.detect_stale(current_token)
        for row in rows:
            if not any(x.source_event_id == row.event_id for x in self._escalations.values()):
                target = row.escalation_recipients[0] if row.escalation_recipients else None
                self._record_escalation(
                    reason="stale_agent",
                    target_agent_id=target,
                    source_event_id=row.event_id,
                )
        return rows

    def reconcile_delivery(self, event_id: str) -> tuple[DeliveryReceipt, ...]:
        return self.deliver_event(event_id)

    def escalations(self) -> tuple[CoordinationEscalation, ...]:
        return tuple(self._escalations[key] for key in sorted(self._escalations))

    def _record_escalation(
        self,
        *,
        reason: str,
        target_agent_id: str | None,
        source_event_id: str | None,
    ) -> CoordinationEscalation:
        if target_agent_id is not None:
            self.registry.get(target_agent_id)
        causal = () if source_event_id is None else (self.events.get(source_event_id).event_id,)
        event = self.events.append(
            EventKind.COORDINATION_ESCALATED,
            source_agent_id="nolane.central",
            target_agent_id=target_agent_id,
            region=None if target_agent_id is None else self.registry.get(target_agent_id).region,
            causal_parent_ids=causal,
            payload={"reason": str(reason), "source_event_id": source_event_id},
            priority=100,
        )
        self._escalation_counter += 1
        temp = CoordinationEscalation(
            escalation_id=f"coord-escalation-{self._escalation_counter:08d}",
            reason=str(reason),
            target_agent_id=target_agent_id,
            source_event_id=source_event_id,
            event_id=event.event_id,
            digest="",
        )
        row = replace(temp, digest=canonical_digest(temp.payload()))
        self._escalations[row.escalation_id] = row
        return row

    def _check_ack_budget(self, source_event_id: str) -> None:
        pending = sum(row.ack_status is AckStatus.PENDING for row in self.deliveries())
        if (
            pending > self.budget.max_pending_acks
            and not any(x.reason == "pending_ack_budget" for x in self._escalations.values())
        ):
            self._record_escalation(
                reason="pending_ack_budget",
                target_agent_id="nolane.central",
                source_event_id=source_event_id,
            )

    def _check_conflict_budget(self, source_event_id: str) -> None:
        unresolved = sum(row.status.value != "resolved" for row in self.conflicts())
        if (
            unresolved > self.budget.max_unresolved_conflicts
            and not any(x.reason == "conflict_budget" for x in self._escalations.values())
        ):
            self._record_escalation(
                reason="conflict_budget",
                target_agent_id="nolane.central",
                source_event_id=source_event_id,
            )

    def _maybe_coordination_budget(self, source_event_id: str | None) -> None:
        generated = sum(row.kind in _COORDINATION_EVENT_KINDS for row in self.events.events_since(None))
        if (
            generated >= self.budget.max_coordination_events_per_window
            and not any(x.reason == "coordination_event_budget" for x in self._escalations.values())
        ):
            self._record_escalation(
                reason="coordination_event_budget",
                target_agent_id="nolane.central",
                source_event_id=source_event_id,
            )

    def metrics(self) -> CoordinationMetrics:
        events = self.events.events_since(None)
        generated = sum(row.kind in _COORDINATION_EVENT_KINDS for row in events)
        source = len(events) - generated
        reservations = tuple(self._reservations.values())
        conflicts = self.conflicts()
        active = sum(row.status is AgentStatus.ACTIVE for row in self.registry.identities())
        peak = max(self._peak_active_agents, active)
        return CoordinationMetrics(
            source_workload_events=source,
            generated_coordination_events=generated,
            delivery_count=len(self.deliveries()),
            acknowledgement_count=sum(row.ack_status is AckStatus.ACKED for row in self.deliveries()),
            wake_reserved_count=sum(row.disposition is WakeDisposition.RESERVED for row in reservations),
            wake_deferred_count=sum(row.disposition is WakeDisposition.DEFERRED for row in reservations),
            lease_transition_count=sum(
                row.kind
                in {
                    EventKind.TASK_LEASE_GRANTED,
                    EventKind.TASK_LEASE_RENEWED,
                    EventKind.TASK_LEASE_REVOKED,
                }
                for row in events
            ),
            open_conflicts=sum(row.status.value != "resolved" for row in conflicts),
            resolved_conflicts=sum(row.status.value == "resolved" for row in conflicts),
            peak_active_agents=peak,
            coordination_event_ratio=generated / max(1, source),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "leases": self.leases.to_state(),
            "deliveries": self.deliveries_state.to_state(),
            "conflicts": self.conflicts_state.to_state(),
            "budget": self.budget.to_state(),
            "reservations": [self._reservations[key].to_state() for key in sorted(self._reservations)],
            "escalations": [self._escalations[key].to_state() for key in sorted(self._escalations)],
            "reservation_counter": self._reservation_counter,
            "escalation_counter": self._escalation_counter,
            "peak_active_agents": self._peak_active_agents,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        events: EventLedger,
        authority: AuthorityGraph,
        tasks: TaskGraph,
        scheduler: WakeSleepScheduler,
        state: Mapping[str, Any],
    ) -> "CoordinationControlPlane":
        leases = LeaseCoordinator.from_state(
            registry=registry,
            tasks=tasks,
            events=events,
            state=state.get("leases", {}),
        )
        deliveries = DeliveryCoordinator.from_state(
            registry=registry,
            events=events,
            state=state.get("deliveries", {}),
        )
        conflicts = ConflictCoordinator.from_state(
            registry=registry,
            authority=authority,
            events=events,
            state=state.get("conflicts", {}),
        )
        reservations = tuple(WakeReservation.from_state(x) for x in state.get("reservations", ()))
        escalations = tuple(CoordinationEscalation.from_state(x) for x in state.get("escalations", ()))
        return cls(
            registry=registry,
            events=events,
            authority=authority,
            tasks=tasks,
            scheduler=scheduler,
            leases=leases,
            deliveries=deliveries,
            conflicts=conflicts,
            budget=CoordinationBudget.from_state(state.get("budget", {})),
            reservations=reservations,
            escalations=escalations,
            reservation_counter=int(state.get("reservation_counter", len(reservations))),
            escalation_counter=int(state.get("escalation_counter", len(escalations))),
            peak_active_agents=int(state.get("peak_active_agents", 0)),
        )


__all__ = (
    "CoordinationBudget",
    "CoordinationControlPlane",
    "CoordinationEscalation",
    "CoordinationMetrics",
    "WakeDisposition",
    "WakeReservation",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
