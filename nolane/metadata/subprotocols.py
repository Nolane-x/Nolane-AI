from __future__ import annotations

from dataclasses import dataclass
import importlib
import re
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest

from .implementation_status import ImplementationStatus, build_component_implementation_ledger


REGISTRY_ID = "metadata.subprotocol_bindings"
REGISTRY_VERSION = "0.0.1"
_VERSION_RE = re.compile(r"^0\.0\.(0|[1-9][0-9]*)$")
_EXPECTED_PARENT_IDS = frozenset({
    "external.evidence",
    "external.knowledge",
    "external.epistemic",
    "external.verification",
    "external.assurance",
})


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


@dataclass(frozen=True, slots=True)
class SubprotocolBinding:
    parent_component_id: str
    parent_canonical_module: str
    protocol_id: str
    protocol_module: str
    digest: str

    @classmethod
    def create(
        cls,
        *,
        parent_component_id: str,
        parent_canonical_module: str,
        protocol_id: str,
        protocol_module: str,
    ) -> "SubprotocolBinding":
        payload = {
            "parent_component_id": _explicit(parent_component_id, "parent_component_id"),
            "parent_canonical_module": _explicit(parent_canonical_module, "parent_canonical_module"),
            "protocol_id": _explicit(protocol_id, "protocol_id"),
            "protocol_module": _explicit(protocol_module, "protocol_module"),
        }
        return cls(
            payload["parent_component_id"],
            payload["parent_canonical_module"],
            payload["protocol_id"],
            payload["protocol_module"],
            canonical_digest(payload),
        )

    def payload(self) -> dict[str, str]:
        return {
            "parent_component_id": self.parent_component_id,
            "parent_canonical_module": self.parent_canonical_module,
            "protocol_id": self.protocol_id,
            "protocol_module": self.protocol_module,
        }

    def to_state(self) -> dict[str, str]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SubprotocolBinding":
        row = cls.create(
            parent_component_id=str(state["parent_component_id"]),
            parent_canonical_module=str(state["parent_canonical_module"]),
            protocol_id=str(state["protocol_id"]),
            protocol_module=str(state["protocol_module"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("subprotocol binding digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class SubprotocolRegistry:
    registry_id: str
    registry_version: str
    bindings: tuple[SubprotocolBinding, ...]
    digest: str

    @staticmethod
    def _payload(
        registry_id: str,
        registry_version: str,
        bindings: tuple[SubprotocolBinding, ...],
    ) -> dict[str, Any]:
        return {
            "registry_id": registry_id,
            "registry_version": registry_version,
            "bindings": [row.to_state() for row in bindings],
        }

    @classmethod
    def create(
        cls,
        *,
        registry_id: str,
        registry_version: str,
        bindings: tuple[SubprotocolBinding, ...],
    ) -> "SubprotocolRegistry":
        registry_id = _explicit(registry_id, "registry_id")
        registry_version = _explicit(registry_version, "registry_version")
        if registry_id != REGISTRY_ID:
            raise ValueError("unsupported subprotocol registry id")
        if registry_version != REGISTRY_VERSION or _VERSION_RE.fullmatch(registry_version) is None:
            raise ValueError("unsupported subprotocol registry version")

        bindings = tuple(sorted(bindings, key=lambda row: row.parent_component_id))
        if len(bindings) != 5 or {row.parent_component_id for row in bindings} != _EXPECTED_PARENT_IDS:
            raise ValueError("truth subprotocol registry must cover exactly the five family-A parents")
        for field, values in (
            ("parent component", [row.parent_component_id for row in bindings]),
            ("parent canonical module", [row.parent_canonical_module for row in bindings]),
            ("protocol id", [row.protocol_id for row in bindings]),
            ("protocol module", [row.protocol_module for row in bindings]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"subprotocol registry {field} bindings must be unique")

        payload = cls._payload(registry_id, registry_version, bindings)
        return cls(registry_id, registry_version, bindings, canonical_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {**self._payload(self.registry_id, self.registry_version, self.bindings), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SubprotocolRegistry":
        row = cls.create(
            registry_id=str(state["registry_id"]),
            registry_version=str(state["registry_version"]),
            bindings=tuple(SubprotocolBinding.from_state(value) for value in state.get("bindings", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("subprotocol registry digest mismatch")
        return row

    def validate_live(self) -> bool:
        implementation = build_component_implementation_ledger()
        for binding in self.bindings:
            try:
                parent_record = implementation[binding.parent_component_id]
            except KeyError as exc:
                raise ValueError("subprotocol parent is absent from canonical implementation ledger") from exc
            if parent_record.status is not ImplementationStatus.CANONICAL_NATIVE:
                raise ValueError("subprotocol parent must be canonical-native")
            if not parent_record.canonical_write_authority:
                raise ValueError("subprotocol parent must retain canonical write authority")
            if parent_record.canonical_module != binding.parent_canonical_module:
                raise ValueError("subprotocol parent canonical module drift")

            parent_module = importlib.import_module(binding.parent_canonical_module)
            if getattr(parent_module, "COMPONENT_ID", None) != binding.parent_component_id:
                raise ValueError("subprotocol parent module component identity drift")

            helper = importlib.import_module(binding.protocol_module)
            if hasattr(helper, "COMPONENT_ID"):
                raise ValueError("subprotocol helper must not declare canonical component identity")
            if getattr(helper, "PARENT_COMPONENT_ID", None) != binding.parent_component_id:
                raise ValueError("subprotocol helper parent binding drift")
            if getattr(helper, "TRUTH_PROTOCOL", None) != binding.protocol_id:
                raise ValueError("subprotocol helper protocol identity drift")
        return True


def build_truth_knowledge_subprotocol_registry() -> SubprotocolRegistry:
    rows = (
        SubprotocolBinding.create(
            parent_component_id="external.evidence",
            parent_canonical_module="nolane.external_core.evidence",
            protocol_id="truth-evidence-v1",
            protocol_module="nolane.external_core.evidence_truth",
        ),
        SubprotocolBinding.create(
            parent_component_id="external.knowledge",
            parent_canonical_module="nolane.memory.knowledge",
            protocol_id="truth-knowledge-v1",
            protocol_module="nolane.external_core.knowledge_truth",
        ),
        SubprotocolBinding.create(
            parent_component_id="external.epistemic",
            parent_canonical_module="nolane.external_core.epistemic",
            protocol_id="truth-epistemic-snapshot-v1",
            protocol_module="nolane.external_core.epistemic_truth",
        ),
        SubprotocolBinding.create(
            parent_component_id="external.verification",
            parent_canonical_module="nolane.external_core.verification",
            protocol_id="truth-verification-ledger-v1",
            protocol_module="nolane.external_core.verification_truth",
        ),
        SubprotocolBinding.create(
            parent_component_id="external.assurance",
            parent_canonical_module="nolane.external_core.assurance",
            protocol_id="truth-assurance-v1",
            protocol_module="nolane.external_core.assurance_truth",
        ),
    )
    registry = SubprotocolRegistry.create(
        registry_id=REGISTRY_ID,
        registry_version=REGISTRY_VERSION,
        bindings=rows,
    )
    registry.validate_live()
    return registry


__all__ = (
    "REGISTRY_ID",
    "REGISTRY_VERSION",
    "SubprotocolBinding",
    "SubprotocolRegistry",
    "build_truth_knowledge_subprotocol_registry",
)
