from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.organization.identity import AgentRegistry

COMPONENT_ID = "external.invokable_cores"
COMPONENT_VERSION = "0.1.0"
MIGRATED_FROM = "cogcoder.organization.external_core"


@dataclass(frozen=True, slots=True)
class ExternalCoreSpec:
    core_id: str
    owner_agent_or_region: str
    capabilities: tuple[str, ...]
    input_schema: str
    output_schema: str
    side_effects: tuple[str, ...]
    required_permissions: tuple[str, ...]
    cost_model: str
    failure_modes: tuple[str, ...]
    verification_hooks: tuple[str, ...]
    version: str
    effect_classes: tuple[str, ...] = ("owner_declares_per_call",)
    idempotency_mode: str = "caller_keyed"
    retry_mode: str = "bounded"
    compensation_mode: str = "owner_declared"
    max_attempts: int = 1

    def __post_init__(self) -> None:
        for value, label in (
            (self.core_id, "external core id"),
            (self.owner_agent_or_region, "external core owner"),
            (self.input_schema, "input schema"),
            (self.output_schema, "output schema"),
            (self.version, "external core version"),
            (self.idempotency_mode, "idempotency mode"),
            (self.retry_mode, "retry mode"),
            (self.compensation_mode, "compensation mode"),
        ):
            if not str(value).strip():
                raise ValueError(f"{label} must be explicit")
        for values, label in (
            (self.capabilities, "capabilities"),
            (self.side_effects, "side effects"),
            (self.required_permissions, "required permissions"),
            (self.failure_modes, "failure modes"),
            (self.verification_hooks, "verification hooks"),
            (self.effect_classes, "effect classes"),
        ):
            if not values or any(not str(x).strip() for x in values):
                raise ValueError(f"external core {label} must be explicit")
            if len(set(values)) != len(values):
                raise ValueError(f"external core {label} must be unique")
        if isinstance(self.max_attempts, bool) or int(self.max_attempts) <= 0:
            raise ValueError("external core max_attempts must be positive")

    @property
    def contract_digest(self) -> str:
        return canonical_digest(self.to_state())

    def to_state(self) -> dict[str, Any]:
        return {
            "core_id": self.core_id,
            "owner_agent_or_region": self.owner_agent_or_region,
            "capabilities": list(self.capabilities),
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "side_effects": list(self.side_effects),
            "required_permissions": list(self.required_permissions),
            "cost_model": self.cost_model,
            "failure_modes": list(self.failure_modes),
            "verification_hooks": list(self.verification_hooks),
            "version": self.version,
            "effect_classes": list(self.effect_classes),
            "idempotency_mode": self.idempotency_mode,
            "retry_mode": self.retry_mode,
            "compensation_mode": self.compensation_mode,
            "max_attempts": self.max_attempts,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExternalCoreSpec":
        return cls(
            core_id=str(state["core_id"]),
            owner_agent_or_region=str(state["owner_agent_or_region"]),
            capabilities=tuple(str(x) for x in state.get("capabilities", ())),
            input_schema=str(state.get("input_schema", "mapping")),
            output_schema=str(state.get("output_schema", "mapping")),
            side_effects=tuple(str(x) for x in state.get("side_effects", ())),
            required_permissions=tuple(str(x) for x in state.get("required_permissions", ())),
            cost_model=str(state.get("cost_model", "bounded")),
            failure_modes=tuple(str(x) for x in state.get("failure_modes", ())),
            verification_hooks=tuple(str(x) for x in state.get("verification_hooks", ())),
            version=str(state.get("version", "0.1")),
            effect_classes=tuple(str(x) for x in state.get("effect_classes", ("owner_declares_per_call",))),
            idempotency_mode=str(state.get("idempotency_mode", "caller_keyed")),
            retry_mode=str(state.get("retry_mode", "bounded")),
            compensation_mode=str(state.get("compensation_mode", "owner_declared")),
            max_attempts=int(state.get("max_attempts", 1)),
        )


class ExternalCoreRegistry:
    def __init__(self) -> None:
        self._cores: dict[str, ExternalCoreSpec] = {}

    def register(self, spec: ExternalCoreSpec) -> None:
        existing = self._cores.get(spec.core_id)
        if existing is not None and existing != spec:
            raise ValueError(f"external core {spec.core_id} already registered differently")
        self._cores[spec.core_id] = spec

    def get(self, core_id: str) -> ExternalCoreSpec:
        try:
            return self._cores[str(core_id)]
        except KeyError as exc:
            raise KeyError(f"unknown external core: {core_id}") from exc

    def specs(self) -> tuple[ExternalCoreSpec, ...]:
        return tuple(self._cores[key] for key in sorted(self._cores))

    @property
    def contract_digest(self) -> str:
        return canonical_digest(self.to_state())

    def to_state(self) -> dict[str, Any]:
        return {"cores": [row.to_state() for row in self.specs()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExternalCoreRegistry":
        registry = cls()
        for value in state.get("cores", ()):
            registry.register(ExternalCoreSpec.from_state(value))
        return registry


def build_default_external_core_registry(registry: AgentRegistry) -> ExternalCoreRegistry:
    owners: dict[str, list[str]] = {}
    for identity in registry.identities():
        for core_id in identity.external_core_bindings:
            owners.setdefault(core_id, []).append(identity.agent_id)

    result = ExternalCoreRegistry()
    for core_id, agent_ids in sorted(owners.items()):
        identities = [registry.get(agent_id) for agent_id in agent_ids]
        regions = {row.region for row in identities}
        if len(regions) == 1:
            owner = next(iter(regions))
        elif agent_ids == ["nolane.central"]:
            owner = "nolane.central"
        else:
            owner = "shared-governed-core"
        result.register(
            ExternalCoreSpec(
                core_id=core_id,
                owner_agent_or_region=owner,
                capabilities=(core_id.replace("-", "_"),),
                input_schema="canonical_mapping_v1",
                output_schema="canonical_mapping_v1",
                side_effects=("owner_declares_side_effects_per_call",),
                required_permissions=("external_core.invoke",),
                cost_model="bounded_owner_metered",
                failure_modes=("unavailable", "invalid_input", "invalid_output", "execution_failure"),
                verification_hooks=("input_receipt", "output_receipt", "failure_receipt", "postcondition_receipt"),
                version="0.2",
                effect_classes=("read", "local_mutation", "external_mutation", "irreversible"),
                idempotency_mode="caller_keyed",
                retry_mode="bounded_declared",
                compensation_mode="owner_declared_with_evidence",
                max_attempts=1,
            )
        )
    return result


__all__ = (
    "ExternalCoreSpec",
    "ExternalCoreRegistry",
    "build_default_external_core_registry",
)
