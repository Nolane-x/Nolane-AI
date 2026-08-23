from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from cogcoder.organization.types import canonical_digest, canonical_json

from .identity import AgentRegistry

MIGRATED_FROM = "cogcoder.organization.central_state"


@dataclass(frozen=True, slots=True)
class CentralCapabilityObservation:
    observation_id: str
    sequence: int
    agent_id: str
    readiness: int
    health: int
    evidence_refs: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "sequence": self.sequence,
            "agent_id": self.agent_id,
            "readiness": self.readiness,
            "health": self.health,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CentralCapabilityObservation":
        return cls(
            observation_id=str(state["observation_id"]),
            sequence=int(state["sequence"]),
            agent_id=str(state["agent_id"]),
            readiness=int(state["readiness"]),
            health=int(state["health"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
        )


class CentralCapabilityMap:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self._observations: list[CentralCapabilityObservation] = []

    @staticmethod
    def _score(value: int, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"{label} must be an integer from 0 to 100")
        return value

    def observe(
        self,
        *,
        agent_id: str,
        readiness: int,
        health: int,
        evidence_refs: tuple[str, ...],
    ) -> CentralCapabilityObservation:
        identity = self.registry.get(agent_id)
        readiness = self._score(readiness, "readiness")
        health = self._score(health, "health")
        evidence = tuple(str(x).strip() for x in evidence_refs if str(x).strip())
        if not evidence:
            raise ValueError("capability observation requires evidence refs")
        sequence = len(self._observations) + 1
        row = CentralCapabilityObservation(
            observation_id=f"capobs-{sequence:08d}",
            sequence=sequence,
            agent_id=identity.agent_id,
            readiness=readiness,
            health=health,
            evidence_refs=evidence,
        )
        self._observations.append(row)
        return row

    def observations(self) -> tuple[CentralCapabilityObservation, ...]:
        return tuple(self._observations)

    def latest_for(self, agent_id: str) -> CentralCapabilityObservation | None:
        self.registry.get(agent_id)
        for row in reversed(self._observations):
            if row.agent_id == str(agent_id):
                return row
        return None

    def capability_view(self, agent_id: str) -> dict[str, Any]:
        identity = self.registry.get(agent_id)
        latest = self.latest_for(agent_id)
        return {
            "agent_id": identity.agent_id,
            "region": identity.region,
            "role": identity.role,
            "rank": identity.rank.value if hasattr(identity.rank, "value") else str(identity.rank),
            "cognitive_capabilities": list(identity.cognitive_capabilities),
            "tool_permissions": list(identity.tool_permissions),
            "external_core_bindings": list(identity.external_core_bindings),
            "status": identity.status.value if hasattr(identity.status, "value") else str(identity.status),
            "current_task": identity.current_task,
            "latest_observation": None if latest is None else latest.to_state(),
        }

    def to_state(self) -> dict[str, Any]:
        return {"observations": [row.to_state() for row in self._observations]}

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> "CentralCapabilityMap":
        mapping = cls(registry)
        rows = [CentralCapabilityObservation.from_state(x) for x in state.get("observations", ())]
        for expected, row in enumerate(rows, start=1):
            registry.get(row.agent_id)
            if row.sequence != expected or row.observation_id != f"capobs-{expected:08d}":
                raise ValueError("capability observation sequence is not canonical")
            mapping._score(row.readiness, "readiness")
            mapping._score(row.health, "health")
            if not row.evidence_refs:
                raise ValueError("restored capability observation lacks evidence")
        mapping._observations = rows
        return mapping


@dataclass(frozen=True, slots=True)
class CentralWorldState:
    payload_json: str
    digest: str

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError("Central world-state payload must be an object")
        return value


def build_world_state(
    runtime: Any,
    capabilities: CentralCapabilityMap,
    *,
    central_extra: Mapping[str, Any] | None = None,
) -> CentralWorldState:
    payload = {
        "registry": runtime.registry.to_state(),
        "tasks": runtime.tasks.to_state(),
        "authority": runtime.authority.to_state(),
        "ledger": runtime.ledger.to_state(),
        "verification": runtime.verification.to_state(),
        "capabilities": capabilities.to_state(),
        "central_extra": dict(central_extra or {}),
    }
    payload_json = canonical_json(payload)
    return CentralWorldState(payload_json=payload_json, digest=canonical_digest(payload))


__all__ = (
    "CentralCapabilityMap",
    "CentralCapabilityObservation",
    "CentralWorldState",
    "build_world_state",
    "MIGRATED_FROM",
)
