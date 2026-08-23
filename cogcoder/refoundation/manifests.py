from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from cogcoder.organization.blueprint import build_first_generation_blueprint

from ._component_specs import COMPONENT_SPECS
from .versioning import ComponentVersion


FIRST_GENERATION_SNAPSHOT = "1a8f333f72dd02abacf1a1bd6e2288c1025521de"
REFUNDATION_EPOCH = "REFOUNDATION-0"


@dataclass(frozen=True, slots=True)
class AgentManifest:
    """Zero-loss bootstrap view of one permanent first-generation identity.

    Epoch 0 derives these manifests from the accepted blueprint and proves
    field-for-field parity before a later wave flips source-of-truth authority
    from ``blueprint.py`` to persisted per-agent manifests.
    """

    agent_id: str
    name: str
    region: str
    role: str
    rank: str
    neural_version: str
    parameter_accounting: Mapping[str, int]
    direct_work_capable: bool
    learning_capable: bool
    cognitive_capabilities: tuple[str, ...]
    memory_namespace: str
    skill_namespace: str
    external_core_bindings: tuple[str, ...]
    tool_permissions: tuple[str, ...]
    agent_definition_version: str = "0.0.0"
    permanent: bool = True

    def __post_init__(self) -> None:
        if not self.agent_id.strip() or not self.name.strip() or not self.region.strip() or not self.role.strip():
            raise ValueError("agent manifest identity/name/region/role must be explicit")
        ComponentVersion.parse(self.agent_definition_version)
        if not self.permanent:
            raise ValueError("AgentManifest is reserved for the permanent 67-identity organization")
        total = int(self.parameter_accounting["total_physical_parameters"])
        if total >= 100_000_000:
            raise ValueError("first-generation permanent identity must remain below 100M physical parameters")
        if not self.memory_namespace or not self.skill_namespace:
            raise ValueError("permanent identity requires memory and skill namespaces")

    def to_state(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "region": self.region,
            "role": self.role,
            "rank": self.rank,
            "neural_version": self.neural_version,
            "parameter_accounting": dict(self.parameter_accounting),
            "direct_work_capable": self.direct_work_capable,
            "learning_capable": self.learning_capable,
            "cognitive_capabilities": list(self.cognitive_capabilities),
            "memory_namespace": self.memory_namespace,
            "skill_namespace": self.skill_namespace,
            "external_core_bindings": list(self.external_core_bindings),
            "tool_permissions": list(self.tool_permissions),
            "agent_definition_version": self.agent_definition_version,
            "permanent": self.permanent,
        }


@dataclass(frozen=True, slots=True)
class ComponentManifest:
    component_id: str
    version: ComponentVersion
    layer: str
    responsibility: str
    state_schema: str
    dependencies: tuple[str, ...] = ()
    version_identity: str = "component_version"

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.component_id, self.layer, self.responsibility, self.state_schema)):
            raise ValueError("component id/layer/responsibility/state schema must be explicit")
        if self.version_identity != "component_version":
            raise ValueError("component software revision must not be conflated with other version identities")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("component dependencies must be unique")
        if self.component_id in self.dependencies:
            raise ValueError("component cannot depend on itself")

    def to_state(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "version": str(self.version),
            "layer": self.layer,
            "responsibility": self.responsibility,
            "state_schema": self.state_schema,
            "dependencies": list(self.dependencies),
            "version_identity": self.version_identity,
        }


def build_bootstrap_agent_manifests() -> tuple[AgentManifest, ...]:
    rows: list[AgentManifest] = []
    for identity in build_first_generation_blueprint():
        rows.append(
            AgentManifest(
                agent_id=identity.agent_id,
                name=identity.name,
                region=identity.region,
                role=identity.role,
                rank=identity.rank.value,
                neural_version=identity.neural_version,
                parameter_accounting=identity.parameter_accounting.to_state(),
                direct_work_capable=identity.direct_work_capable,
                learning_capable=identity.learning_capable,
                cognitive_capabilities=identity.cognitive_capabilities,
                memory_namespace=identity.memory_namespace,
                skill_namespace=identity.skill_namespace,
                external_core_bindings=identity.external_core_bindings,
                tool_permissions=identity.tool_permissions,
            )
        )
    return tuple(rows)


def build_component_manifests() -> tuple[ComponentManifest, ...]:
    version = ComponentVersion(0, 0, 0)
    rows = tuple(
        ComponentManifest(
            component_id=component_id,
            version=version,
            layer=layer,
            responsibility=responsibility,
            state_schema=state_schema,
            dependencies=dependencies,
        )
        for component_id, layer, responsibility, state_schema, dependencies in COMPONENT_SPECS
    )
    if len({row.component_id for row in rows}) != len(rows):
        raise ValueError("canonical component registry contains duplicate component ids")
    return rows
