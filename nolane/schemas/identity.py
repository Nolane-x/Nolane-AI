from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


COMPONENT_ID = "schemas.identity"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.types"

PHYSICAL_PARAMETER_CEILING = 100_000_000


class AgentRank(str, Enum):
    CENTRAL = "central"
    CHIEF = "chief"
    SENIOR_SPECIALIST = "senior_specialist"
    SPECIALIST = "specialist"


class AgentStatus(str, Enum):
    SLEEPING = "sleeping"
    WAKING = "waking"
    ACTIVE = "active"
    WAITING = "waiting"
    BLOCKED = "blocked"
    CHECKPOINTING = "checkpointing"
    PAUSED = "paused"
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True)
class ParameterAccounting:
    shared_physical_parameters: int
    local_physical_parameters: int

    def __post_init__(self) -> None:
        if isinstance(self.shared_physical_parameters, bool) or isinstance(self.local_physical_parameters, bool):
            raise TypeError("parameter counts must be integers")
        if self.shared_physical_parameters < 0 or self.local_physical_parameters < 0:
            raise ValueError("parameter counts must be non-negative")
        if self.total_physical_parameters >= PHYSICAL_PARAMETER_CEILING:
            raise ValueError("first-generation physical parameters must remain below 100,000,000")

    @property
    def total_physical_parameters(self) -> int:
        return self.shared_physical_parameters + self.local_physical_parameters

    def to_state(self) -> dict[str, int]:
        return {
            "shared_physical_parameters": self.shared_physical_parameters,
            "local_physical_parameters": self.local_physical_parameters,
            "total_physical_parameters": self.total_physical_parameters,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ParameterAccounting":
        return cls(
            shared_physical_parameters=int(state["shared_physical_parameters"]),
            local_physical_parameters=int(state["local_physical_parameters"]),
        )


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    agent_id: str
    name: str
    region: str
    role: str
    rank: AgentRank
    neural_version: str
    parameter_accounting: ParameterAccounting
    region_chief_id: str | None
    direct_work_capable: bool
    learning_capable: bool
    cognitive_capabilities: tuple[str, ...]
    memory_namespace: str
    skill_namespace: str
    external_core_bindings: tuple[str, ...] = ()
    tool_permissions: tuple[str, ...] = ()
    status: AgentStatus = AgentStatus.SLEEPING
    current_task: str | None = None
    specialization_version: str = "specialization-0.1"
    authority_scope: tuple[str, ...] = ("task",)
    subscriptions: tuple[str, ...] = ()
    checkpoint_id: str | None = None
    self_model_version: str = "self-model-0.1"

    def __post_init__(self) -> None:
        for value, label in (
            (self.agent_id, "agent_id"),
            (self.name, "name"),
            (self.region, "region"),
            (self.role, "role"),
            (self.neural_version, "neural_version"),
            (self.memory_namespace, "memory_namespace"),
            (self.skill_namespace, "skill_namespace"),
            (self.specialization_version, "specialization_version"),
            (self.self_model_version, "self_model_version"),
        ):
            if not str(value).strip():
                raise ValueError(f"{label} must be non-empty")
        if not self.cognitive_capabilities:
            raise ValueError("every permanent identity needs a cognitive capability floor")
        if not self.authority_scope:
            raise ValueError("every permanent identity needs an authority scope")
        if not self.learning_capable:
            raise ValueError("permanent identities must be learning capable")
        if self.rank in (AgentRank.CENTRAL, AgentRank.CHIEF) and not self.direct_work_capable:
            raise ValueError("Central and Regional Chiefs must be direct workers")
        if self.rank is AgentRank.CENTRAL and self.region_chief_id is not None:
            raise ValueError("Central cannot have a regional chief")
        if self.rank is AgentRank.CHIEF and self.region_chief_id != self.agent_id:
            raise ValueError("Regional Chief must identify itself as region chief")

    def to_state(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "region": self.region,
            "role": self.role,
            "rank": self.rank.value,
            "neural_version": self.neural_version,
            "parameter_accounting": self.parameter_accounting.to_state(),
            "region_chief_id": self.region_chief_id,
            "direct_work_capable": self.direct_work_capable,
            "learning_capable": self.learning_capable,
            "cognitive_capabilities": list(self.cognitive_capabilities),
            "memory_namespace": self.memory_namespace,
            "skill_namespace": self.skill_namespace,
            "external_core_bindings": list(self.external_core_bindings),
            "tool_permissions": list(self.tool_permissions),
            "status": self.status.value,
            "current_task": self.current_task,
            "specialization_version": self.specialization_version,
            "authority_scope": list(self.authority_scope),
            "subscriptions": list(self.subscriptions),
            "checkpoint_id": self.checkpoint_id,
            "self_model_version": self.self_model_version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AgentIdentity":
        return cls(
            agent_id=str(state["agent_id"]),
            name=str(state["name"]),
            region=str(state["region"]),
            role=str(state["role"]),
            rank=AgentRank(str(state["rank"])),
            neural_version=str(state["neural_version"]),
            parameter_accounting=ParameterAccounting.from_state(state["parameter_accounting"]),
            region_chief_id=None if state.get("region_chief_id") is None else str(state["region_chief_id"]),
            direct_work_capable=bool(state["direct_work_capable"]),
            learning_capable=bool(state["learning_capable"]),
            cognitive_capabilities=tuple(str(row) for row in state["cognitive_capabilities"]),
            memory_namespace=str(state["memory_namespace"]),
            skill_namespace=str(state["skill_namespace"]),
            external_core_bindings=tuple(str(row) for row in state.get("external_core_bindings", ())),
            tool_permissions=tuple(str(row) for row in state.get("tool_permissions", ())),
            status=AgentStatus(str(state.get("status", AgentStatus.SLEEPING.value))),
            current_task=None if state.get("current_task") is None else str(state["current_task"]),
            specialization_version=str(state.get("specialization_version", "specialization-0.1")),
            authority_scope=tuple(str(row) for row in state.get("authority_scope", ("task",))),
            subscriptions=tuple(str(row) for row in state.get("subscriptions", ())),
            checkpoint_id=None if state.get("checkpoint_id") is None else str(state["checkpoint_id"]),
            self_model_version=str(state.get("self_model_version", "self-model-0.1")),
        )


__all__ = (
    "PHYSICAL_PARAMETER_CEILING",
    "AgentRank",
    "AgentStatus",
    "ParameterAccounting",
    "AgentIdentity",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
