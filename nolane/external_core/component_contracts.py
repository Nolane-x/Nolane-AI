from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


class ExternalCoreFamily(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


@dataclass(frozen=True, slots=True)
class ExternalComponentManifest:
    component_id: str
    component_version: str
    family: ExternalCoreFamily
    protocol_versions: tuple[tuple[str, str], ...]
    consumes_contracts: tuple[str, ...]
    produces_contracts: tuple[str, ...]
    authority_capabilities: tuple[str, ...]
    forbidden_authorities: tuple[str, ...]
    mutable_resources: tuple[str, ...]
    evidence_inputs: tuple[str, ...]
    evidence_outputs: tuple[str, ...]
    restore_protocol: str
    compatibility_floor: str
    compatibility_ceiling: str
    manifest_digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_version": self.component_version,
            "family": self.family.value,
            "protocol_versions": {key: value for key, value in self.protocol_versions},
            "consumes_contracts": list(self.consumes_contracts),
            "produces_contracts": list(self.produces_contracts),
            "authority_capabilities": list(self.authority_capabilities),
            "forbidden_authorities": list(self.forbidden_authorities),
            "mutable_resources": list(self.mutable_resources),
            "evidence_inputs": list(self.evidence_inputs),
            "evidence_outputs": list(self.evidence_outputs),
            "restore_protocol": self.restore_protocol,
            "compatibility_floor": self.compatibility_floor,
            "compatibility_ceiling": self.compatibility_ceiling,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "manifest_digest": self.manifest_digest}

    @classmethod
    def create(
        cls,
        *,
        component_id: str,
        component_version: str,
        family: ExternalCoreFamily | str,
        protocol_versions: Mapping[str, str],
        consumes_contracts: tuple[str, ...],
        produces_contracts: tuple[str, ...],
        authority_capabilities: tuple[str, ...],
        forbidden_authorities: tuple[str, ...],
        mutable_resources: tuple[str, ...],
        evidence_inputs: tuple[str, ...],
        evidence_outputs: tuple[str, ...],
        restore_protocol: str,
        compatibility_floor: str,
        compatibility_ceiling: str,
    ) -> "ExternalComponentManifest":
        version = _explicit(component_version, "component version")
        floor = _explicit(compatibility_floor, "compatibility floor")
        ceiling = _explicit(compatibility_ceiling, "compatibility ceiling")
        parsed_version = _version_tuple(version)
        parsed_floor = _version_tuple(floor)
        parsed_ceiling = _version_tuple(ceiling)
        if parsed_floor > parsed_ceiling:
            raise ValueError("component compatibility floor exceeds ceiling")
        if not (parsed_floor <= parsed_version <= parsed_ceiling):
            raise ValueError("component version is outside its declared compatibility range")
        protocols = _normalize_mapping(protocol_versions, "protocol version")
        consumes = _unique_explicit(consumes_contracts, "consumed contract")
        produces = _unique_explicit(produces_contracts, "produced contract")
        authorities = _unique_explicit(authority_capabilities, "authority capability")
        forbidden = _unique_explicit(forbidden_authorities, "forbidden authority")
        overlap = set(authorities) & set(forbidden)
        if overlap:
            raise ValueError(
                "component authority capability cannot also be forbidden: "
                + ",".join(sorted(overlap))
            )
        resources = _unique_explicit(mutable_resources, "mutable resource")
        inputs = _unique_explicit(evidence_inputs, "evidence input")
        outputs = _unique_explicit(evidence_outputs, "evidence output")
        payload = {
            "component_id": _explicit(component_id, "component id"),
            "component_version": version,
            "family": ExternalCoreFamily(family).value,
            "protocol_versions": {key: value for key, value in protocols},
            "consumes_contracts": list(consumes),
            "produces_contracts": list(produces),
            "authority_capabilities": list(authorities),
            "forbidden_authorities": list(forbidden),
            "mutable_resources": list(resources),
            "evidence_inputs": list(inputs),
            "evidence_outputs": list(outputs),
            "restore_protocol": _explicit(restore_protocol, "restore protocol"),
            "compatibility_floor": floor,
            "compatibility_ceiling": ceiling,
        }
        digest = canonical_digest(payload)
        return cls(
            component_id=payload["component_id"],
            component_version=version,
            family=ExternalCoreFamily(payload["family"]),
            protocol_versions=protocols,
            consumes_contracts=consumes,
            produces_contracts=produces,
            authority_capabilities=authorities,
            forbidden_authorities=forbidden,
            mutable_resources=resources,
            evidence_inputs=inputs,
            evidence_outputs=outputs,
            restore_protocol=payload["restore_protocol"],
            compatibility_floor=floor,
            compatibility_ceiling=ceiling,
            manifest_digest=digest,
        )

    @classmethod
    def minimal(
        cls,
        component_id: str,
        family: ExternalCoreFamily | str,
        *,
        mutable_resources: tuple[str, ...] = (),
        authority_capabilities: tuple[str, ...] = (),
        forbidden_authorities: tuple[str, ...] = (),
    ) -> "ExternalComponentManifest":
        return cls.create(
            component_id=component_id,
            component_version="1.0.0",
            family=family,
            protocol_versions={"core": "1"},
            consumes_contracts=(),
            produces_contracts=(),
            authority_capabilities=authority_capabilities,
            forbidden_authorities=forbidden_authorities,
            mutable_resources=mutable_resources,
            evidence_inputs=(),
            evidence_outputs=(),
            restore_protocol="exact-revalidation",
            compatibility_floor="1.0.0",
            compatibility_ceiling="1.0.0",
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExternalComponentManifest":
        protocols = state.get("protocol_versions", {})
        if not isinstance(protocols, Mapping):
            raise ValueError("component manifest protocol_versions must be an object")
        expected = cls.create(
            component_id=str(state["component_id"]),
            component_version=str(state["component_version"]),
            family=str(state["family"]),
            protocol_versions={str(k): str(v) for k, v in protocols.items()},
            consumes_contracts=tuple(str(x) for x in state.get("consumes_contracts", ())),
            produces_contracts=tuple(str(x) for x in state.get("produces_contracts", ())),
            authority_capabilities=tuple(str(x) for x in state.get("authority_capabilities", ())),
            forbidden_authorities=tuple(str(x) for x in state.get("forbidden_authorities", ())),
            mutable_resources=tuple(str(x) for x in state.get("mutable_resources", ())),
            evidence_inputs=tuple(str(x) for x in state.get("evidence_inputs", ())),
            evidence_outputs=tuple(str(x) for x in state.get("evidence_outputs", ())),
            restore_protocol=str(state["restore_protocol"]),
            compatibility_floor=str(state["compatibility_floor"]),
            compatibility_ceiling=str(state["compatibility_ceiling"]),
        )
        if str(state.get("manifest_digest", "")) != expected.manifest_digest:
            raise ValueError("component manifest digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("component manifest state is non-canonical or semantically drifted")
        return expected

    def accepts_component_version(self, version: str) -> bool:
        value = _version_tuple(version)
        return _version_tuple(self.compatibility_floor) <= value <= _version_tuple(self.compatibility_ceiling)


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = str(value).split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f"version must be numeric semantic MAJOR.MINOR.PATCH: {value}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


def _unique_explicit(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    rows = tuple(str(value) for value in values)
    if any(not value.strip() for value in rows):
        raise ValueError(f"{label} must be explicit")
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(rows))


def _normalize_mapping(values: Mapping[str, str], label: str) -> tuple[tuple[str, str], ...]:
    rows = tuple(sorted((str(key), str(value)) for key, value in values.items()))
    if any(not key.strip() or not value.strip() for key, value in rows):
        raise ValueError(f"{label} keys and values must be explicit")
    return rows


__all__ = ("ExternalComponentManifest", "ExternalCoreFamily")
