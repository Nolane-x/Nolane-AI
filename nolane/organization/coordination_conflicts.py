from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from cogcoder.organization.types import EventKind, canonical_digest

from .authority import AuthorityGraph
from .events import EventLedger
from .identity import AgentRegistry

COMPONENT_ID = "organization.coordination.conflicts"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.coordination_conflicts"


class ConflictStatus(str, Enum):
    OPEN = "open"
    READY_FOR_DECISION = "ready_for_decision"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass(frozen=True, slots=True)
class ConflictClaim:
    claim_id: str
    conflict_id: str
    claimant_agent_id: str
    region: str
    proposition: str
    requested_action: str
    evidence_refs: tuple[str, ...]
    event_id: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "conflict_id": self.conflict_id,
            "claimant_agent_id": self.claimant_agent_id,
            "region": self.region,
            "proposition": self.proposition,
            "requested_action": self.requested_action,
            "evidence_refs": list(self.evidence_refs),
            "event_id": self.event_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ConflictClaim":
        row = cls(
            str(state["claim_id"]),
            str(state["conflict_id"]),
            str(state["claimant_agent_id"]),
            str(state["region"]),
            str(state["proposition"]),
            str(state["requested_action"]),
            tuple(str(x) for x in state.get("evidence_refs", ())),
            str(state["event_id"]),
            str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("conflict claim digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class ConflictResolutionReceipt:
    resolution_id: str
    conflict_id: str
    resolver_agent_id: str
    decision: str
    evidence_refs: tuple[str, ...]
    override_id: str | None
    event_id: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "resolution_id": self.resolution_id,
            "conflict_id": self.conflict_id,
            "resolver_agent_id": self.resolver_agent_id,
            "decision": self.decision,
            "evidence_refs": list(self.evidence_refs),
            "override_id": self.override_id,
            "event_id": self.event_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ConflictResolutionReceipt":
        row = cls(
            str(state["resolution_id"]),
            str(state["conflict_id"]),
            str(state["resolver_agent_id"]),
            str(state["decision"]),
            tuple(str(x) for x in state.get("evidence_refs", ())),
            None if state.get("override_id") is None else str(state["override_id"]),
            str(state["event_id"]),
            str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("conflict resolution digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class ConflictPacket:
    conflict_id: str
    subject_artifact_id: str
    owner_agent_id: str
    opener_agent_id: str
    status: ConflictStatus
    claim_ids: tuple[str, ...]
    causal_event_ids: tuple[str, ...]
    opened_event_id: str
    resolution_id: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "subject_artifact_id": self.subject_artifact_id,
            "owner_agent_id": self.owner_agent_id,
            "opener_agent_id": self.opener_agent_id,
            "status": self.status.value,
            "claim_ids": list(self.claim_ids),
            "causal_event_ids": list(self.causal_event_ids),
            "opened_event_id": self.opened_event_id,
            "resolution_id": self.resolution_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ConflictPacket":
        row = cls(
            str(state["conflict_id"]),
            str(state["subject_artifact_id"]),
            str(state["owner_agent_id"]),
            str(state["opener_agent_id"]),
            ConflictStatus(str(state["status"])),
            tuple(str(x) for x in state.get("claim_ids", ())),
            tuple(str(x) for x in state.get("causal_event_ids", ())),
            str(state["opened_event_id"]),
            None if state.get("resolution_id") is None else str(state["resolution_id"]),
            str(state["digest"]),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError("conflict packet digest mismatch")
        return row


def _signed(row):
    return replace(row, digest=canonical_digest(row.payload()))


class ConflictCoordinator:
    """Canonical artifact-authority conflict coordinator."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        authority: AuthorityGraph,
        events: EventLedger,
        packets=(),
        claims=(),
        resolutions=(),
        conflict_counter=0,
        claim_counter=0,
        resolution_counter=0,
    ) -> None:
        self.registry = registry
        self.authority = authority
        self.events = events
        self._packets = {x.conflict_id: x for x in packets}
        self._claims = {x.claim_id: x for x in claims}
        self._resolutions = {x.resolution_id: x for x in resolutions}
        self._claim_keys = {}
        self._conflict_counter = int(conflict_counter)
        self._claim_counter = int(claim_counter)
        self._resolution_counter = int(resolution_counter)
        if (
            self._conflict_counter < len(self._packets)
            or self._claim_counter < len(self._claims)
            or self._resolution_counter < len(self._resolutions)
        ):
            raise ValueError("conflict counters are not canonical")
        for packet in packets:
            registry.get(packet.owner_agent_id)
            registry.get(packet.opener_agent_id)
            events.get(packet.opened_event_id)
            if authority.owner_of(packet.subject_artifact_id) != packet.owner_agent_id:
                raise ValueError("conflict owner mismatch")
            for event_id in packet.causal_event_ids:
                events.get(event_id)
        for claim in claims:
            packet = self._packets.get(claim.conflict_id)
            if packet is None or claim.claim_id not in packet.claim_ids:
                raise ValueError("orphan conflict claim")
            if registry.get(claim.claimant_agent_id).region != claim.region:
                raise ValueError("conflict region mismatch")
            events.get(claim.event_id)
            self._claim_keys[
                (claim.conflict_id, claim.claimant_agent_id, claim.proposition, claim.requested_action, claim.evidence_refs)
            ] = claim.claim_id
        for resolution in resolutions:
            packet = self._packets.get(resolution.conflict_id)
            if packet is None or packet.resolution_id != resolution.resolution_id:
                raise ValueError("orphan conflict resolution")
            if events.get(resolution.event_id).kind is not EventKind.CONFLICT_RESOLVED:
                raise ValueError("resolution event mismatch")
            authority.require_write(
                resolution.resolver_agent_id,
                packet.subject_artifact_id,
                override_id=resolution.override_id,
            )

    def open(
        self,
        opener_agent_id,
        subject_artifact_id,
        *,
        proposition,
        requested_action,
        evidence_refs=(),
        causal_event_ids=(),
    ) -> ConflictPacket:
        opener = self.registry.get(opener_agent_id)
        artifact = str(subject_artifact_id)
        owner = self.authority.owner_of(artifact)
        if owner is None:
            raise ValueError(f"artifact {artifact} has no authoritative owner")
        self.registry.get(owner)
        proposition = str(proposition).strip()
        requested_action = str(requested_action).strip()
        if not proposition or not requested_action:
            raise ValueError("conflict claim must be explicit")
        for event_id in causal_event_ids:
            self.events.get(event_id)
        self._conflict_counter += 1
        conflict_id = f"conflict-{self._conflict_counter:08d}"
        self._claim_counter += 1
        claim_id = f"claim-{self._claim_counter:08d}"
        event = self.events.append(
            EventKind.CONFLICT_OPENED,
            source_agent_id=opener.agent_id,
            target_agent_id=owner,
            region=self.registry.get(owner).region,
            causal_parent_ids=tuple(str(x) for x in causal_event_ids),
            object_refs=(artifact,),
            evidence_refs=tuple(str(x) for x in evidence_refs),
            requires_ack=True,
            payload={
                "conflict_id": conflict_id,
                "claim_id": claim_id,
                "proposition": proposition,
                "requested_action": requested_action,
            },
        )
        claim = _signed(
            ConflictClaim(
                claim_id,
                conflict_id,
                opener.agent_id,
                opener.region,
                proposition,
                requested_action,
                tuple(str(x) for x in evidence_refs),
                event.event_id,
                "",
            )
        )
        packet = _signed(
            ConflictPacket(
                conflict_id,
                artifact,
                owner,
                opener.agent_id,
                ConflictStatus.OPEN,
                (claim_id,),
                tuple(str(x) for x in causal_event_ids),
                event.event_id,
                None,
                "",
            )
        )
        self._claims[claim_id] = claim
        self._packets[conflict_id] = packet
        self._claim_keys[
            (conflict_id, opener.agent_id, proposition, requested_action, claim.evidence_refs)
        ] = claim_id
        return packet

    def add_claim(
        self,
        conflict_id,
        claimant_agent_id,
        *,
        proposition,
        requested_action,
        evidence_refs=(),
    ) -> ConflictClaim:
        packet = self.get(conflict_id)
        if packet.status is ConflictStatus.RESOLVED:
            raise ValueError("resolved conflict packet is immutable")
        actor = self.registry.get(claimant_agent_id)
        proposition = str(proposition).strip()
        requested_action = str(requested_action).strip()
        evidence = tuple(str(x) for x in evidence_refs)
        key = (packet.conflict_id, actor.agent_id, proposition, requested_action, evidence)
        if key in self._claim_keys:
            return self._claims[self._claim_keys[key]]
        if not proposition or not requested_action:
            raise ValueError("conflict claim must be explicit")
        self._claim_counter += 1
        claim_id = f"claim-{self._claim_counter:08d}"
        event = self.events.append(
            EventKind.CONFLICT_CLAIM_ADDED,
            source_agent_id=actor.agent_id,
            target_agent_id=packet.owner_agent_id,
            region=self.registry.get(packet.owner_agent_id).region,
            causal_parent_ids=(packet.opened_event_id,),
            object_refs=(packet.subject_artifact_id,),
            evidence_refs=evidence,
            payload={
                "conflict_id": packet.conflict_id,
                "claim_id": claim_id,
                "proposition": proposition,
                "requested_action": requested_action,
            },
        )
        claim = _signed(
            ConflictClaim(
                claim_id,
                packet.conflict_id,
                actor.agent_id,
                actor.region,
                proposition,
                requested_action,
                evidence,
                event.event_id,
                "",
            )
        )
        self._claims[claim_id] = claim
        self._claim_keys[key] = claim_id
        self._packets[packet.conflict_id] = _signed(
            replace(
                packet,
                status=ConflictStatus.READY_FOR_DECISION,
                claim_ids=packet.claim_ids + (claim_id,),
                digest="",
            )
        )
        return claim

    def resolve(
        self,
        conflict_id,
        resolver_agent_id,
        *,
        decision,
        evidence_refs,
        override_id=None,
    ) -> ConflictResolutionReceipt:
        packet = self.get(conflict_id)
        if packet.status is ConflictStatus.RESOLVED:
            raise ValueError("conflict already resolved")
        resolver = self.registry.get(resolver_agent_id)
        decision = str(decision).strip()
        evidence = tuple(str(x) for x in evidence_refs if str(x).strip())
        if not decision or not evidence:
            raise ValueError("resolution requires decision and evidence")
        self.authority.require_write(
            resolver.agent_id,
            packet.subject_artifact_id,
            override_id=override_id,
        )
        self._resolution_counter += 1
        resolution_id = f"resolution-{self._resolution_counter:08d}"
        parents = tuple(
            dict.fromkeys(
                (packet.opened_event_id,) + tuple(self._claims[x].event_id for x in packet.claim_ids)
            )
        )
        event = self.events.append(
            EventKind.CONFLICT_RESOLVED,
            source_agent_id=resolver.agent_id,
            target_agent_id=packet.opener_agent_id,
            region=self.registry.get(packet.owner_agent_id).region,
            causal_parent_ids=parents,
            object_refs=(packet.subject_artifact_id,),
            evidence_refs=evidence,
            payload={
                "conflict_id": packet.conflict_id,
                "resolution_id": resolution_id,
                "decision": decision,
                "override_id": override_id,
            },
        )
        resolution = _signed(
            ConflictResolutionReceipt(
                resolution_id,
                packet.conflict_id,
                resolver.agent_id,
                decision,
                evidence,
                None if override_id is None else str(override_id),
                event.event_id,
                "",
            )
        )
        self._resolutions[resolution_id] = resolution
        self._packets[packet.conflict_id] = _signed(
            replace(
                packet,
                status=ConflictStatus.RESOLVED,
                resolution_id=resolution_id,
                digest="",
            )
        )
        return resolution

    def get(self, conflict_id) -> ConflictPacket:
        try:
            return self._packets[str(conflict_id)]
        except KeyError as exc:
            raise KeyError(f"unknown conflict id: {conflict_id}") from exc

    def packets(self) -> tuple[ConflictPacket, ...]:
        return tuple(self._packets[key] for key in sorted(self._packets))

    def to_state(self) -> dict[str, Any]:
        return {
            "packets": [x.to_state() for x in self.packets()],
            "claims": [self._claims[key].to_state() for key in sorted(self._claims)],
            "resolutions": [self._resolutions[key].to_state() for key in sorted(self._resolutions)],
            "conflict_counter": self._conflict_counter,
            "claim_counter": self._claim_counter,
            "resolution_counter": self._resolution_counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        authority: AuthorityGraph,
        events: EventLedger,
        state: Mapping[str, Any],
    ) -> "ConflictCoordinator":
        packets = tuple(ConflictPacket.from_state(x) for x in state.get("packets", ()))
        claims = tuple(ConflictClaim.from_state(x) for x in state.get("claims", ()))
        resolutions = tuple(ConflictResolutionReceipt.from_state(x) for x in state.get("resolutions", ()))
        return cls(
            registry=registry,
            authority=authority,
            events=events,
            packets=packets,
            claims=claims,
            resolutions=resolutions,
            conflict_counter=int(state.get("conflict_counter", len(packets))),
            claim_counter=int(state.get("claim_counter", len(claims))),
            resolution_counter=int(state.get("resolution_counter", len(resolutions))),
        )


__all__ = (
    "ConflictClaim",
    "ConflictCoordinator",
    "ConflictPacket",
    "ConflictResolutionReceipt",
    "ConflictStatus",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
