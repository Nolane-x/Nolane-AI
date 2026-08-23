from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class SharedNeuralManifest:
    core_id: str
    version: str
    physical_parameters: int
    cognitive_capabilities: tuple[str, ...]
    scope: str = "global"

    def __post_init__(self) -> None:
        if not self.core_id or not self.version or self.scope != "global":
            raise ValueError("shared Neural manifest must be explicit and global")
        if self.physical_parameters != 56_000_000:
            raise ValueError("Epoch-0 shared Neural parameters must remain exactly 56M")
        if not self.cognitive_capabilities:
            raise ValueError("shared Neural capability floor cannot be empty")


@dataclass(frozen=True, slots=True)
class SharedExternalManifest:
    core_id: str
    version: str
    capabilities: tuple[str, ...]
    capability_kinds: Mapping[str, str]
    scope: str = "global"

    def __post_init__(self) -> None:
        if not self.core_id or not self.version or self.scope != "global":
            raise ValueError("shared External manifest must be explicit and global")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("shared External capabilities must be unique")
        if set(self.capabilities) != set(self.capability_kinds):
            raise ValueError("every shared External capability requires a type")


@dataclass(frozen=True, slots=True)
class RegionManifest:
    order: int
    region_id: str
    chief_id: str
    neural_overlay_version: str
    neural_overlay_physical_parameters: int
    external_version: str
    external_core_bindings: tuple[str, ...]
    members: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.order < 0 or not self.region_id or not self.chief_id:
            raise ValueError("region order/id/chief must be explicit")
        if self.neural_overlay_physical_parameters != 0:
            raise ValueError("Epoch-0 regional Neural overlays must not invent physical parameters")
        if not self.members or self.members[0] != self.chief_id:
            raise ValueError("region membership must begin with its Chief")
        if len(self.members) != len(set(self.members)):
            raise ValueError("region members must be unique")


@dataclass(frozen=True, slots=True)
class AIProfile:
    order: int
    agent_id: str
    name: str
    region: str
    role: str
    rank: str
    region_chief_id: str | None
    local_physical_parameters: int
    direct_work_capable: bool
    learning_capable: bool
    accepted_neural_version: str
    private_neural_version: str
    specialization_version: str
    private_external_version: str
    private_external_core_bindings: tuple[str, ...]
    private_tool_permissions: tuple[str, ...]
    memory_namespace: str
    skill_namespace: str
    authority_scope: tuple[str, ...]
    subscriptions: tuple[str, ...]
    status: str
    current_task: str | None
    checkpoint_id: str | None
    self_model_version: str

    def __post_init__(self) -> None:
        if self.order < 0 or not all((self.agent_id, self.name, self.region, self.role, self.rank)):
            raise ValueError("AI profile identity fields must be explicit")
        expected_local = {
            "central": 40_000_000,
            "chief": 34_000_000,
            "senior_specialist": 20_000_000,
            "specialist": 8_000_000,
        }
        if self.rank not in expected_local or self.local_physical_parameters != expected_local[self.rank]:
            raise ValueError("AI profile local parameter band mismatch")
        if 56_000_000 + self.local_physical_parameters >= 100_000_000:
            raise ValueError("first-generation AI must remain below 100M physical parameters")
        if not self.direct_work_capable or not self.learning_capable:
            raise ValueError("all permanent first-generation AIs must work and learn directly")
        if self.rank == "central" and self.region_chief_id is not None:
            raise ValueError("Central cannot have a Regional Chief")
        if self.rank == "chief" and self.region_chief_id != self.agent_id:
            raise ValueError("Regional Chief must identify itself as Chief")


@dataclass(frozen=True, slots=True)
class ResolvedAI:
    agent_id: str
    name: str
    role: str
    rank: str
    region: str
    region_chief_id: str | None
    accepted_neural_version: str
    shared_neural_version: str
    regional_neural_version: str | None
    private_neural_version: str
    resolved_neural_version: str
    shared_external_version: str
    regional_external_version: str | None
    private_external_version: str
    shared_external_capabilities: tuple[str, ...]
    regional_external_core_bindings: tuple[str, ...]
    private_external_core_bindings: tuple[str, ...]
    effective_external_core_bindings: tuple[str, ...]
    effective_tool_permissions: tuple[str, ...]
    parameter_accounting: Mapping[str, int]
    memory_namespace: str
    skill_namespace: str
    authority_scope: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "rank": self.rank,
            "region": self.region,
            "region_chief_id": self.region_chief_id,
            "accepted_neural_version": self.accepted_neural_version,
            "neural_core": {
                "shared_version": self.shared_neural_version,
                "regional_version": self.regional_neural_version,
                "private_version": self.private_neural_version,
                "resolved_version": self.resolved_neural_version,
            },
            "external_core": {
                "shared_version": self.shared_external_version,
                "regional_version": self.regional_external_version,
                "private_version": self.private_external_version,
                "shared_capabilities": list(self.shared_external_capabilities),
                "regional_bindings": list(self.regional_external_core_bindings),
                "private_bindings": list(self.private_external_core_bindings),
                "effective_bindings": list(self.effective_external_core_bindings),
                "effective_tool_permissions": list(self.effective_tool_permissions),
            },
            "parameter_accounting": dict(self.parameter_accounting),
            "memory_namespace": self.memory_namespace,
            "skill_namespace": self.skill_namespace,
            "authority_scope": list(self.authority_scope),
        }
