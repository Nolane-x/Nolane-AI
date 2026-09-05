from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.component_contracts import ExternalComponentManifest


EVOLUTION_DELTA_PROTOCOL = "integration-evolution-delta-v1"
EVOLUTION_QUALIFICATION_PROTOCOL = "integration-evolution-qualification-v1"


class EvolutionCompatibilityDisposition(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


_MANIFEST_FIELDS = (
    "component_version",
    "protocol_versions",
    "consumes_contracts",
    "produces_contracts",
    "authority_capabilities",
    "forbidden_authorities",
    "mutable_resources",
    "evidence_inputs",
    "evidence_outputs",
    "restore_protocol",
    "compatibility_floor",
    "compatibility_ceiling",
)


@dataclass(frozen=True, slots=True)
class ComponentEvolutionDelta:
    component_id: str
    old_manifest: ExternalComponentManifest
    new_manifest: ExternalComponentManifest
    changed_fields: tuple[str, ...]
    delta_id: str

    @classmethod
    def create(
        cls,
        old_manifest: ExternalComponentManifest,
        new_manifest: ExternalComponentManifest,
    ) -> "ComponentEvolutionDelta":
        if not isinstance(old_manifest, ExternalComponentManifest) or not isinstance(new_manifest, ExternalComponentManifest):
            raise ValueError("evolution delta requires canonical component manifests")
        if old_manifest.component_id != new_manifest.component_id:
            raise ValueError("evolution delta cannot rebind component identity")
        component_id = _explicit(old_manifest.component_id, "component identity")
        old_state = old_manifest.to_state()
        new_state = new_manifest.to_state()
        changed = tuple(
            field
            for field in _MANIFEST_FIELDS
            if old_state.get(field) != new_state.get(field)
        )
        payload = {
            "protocol": EVOLUTION_DELTA_PROTOCOL,
            "component_id": component_id,
            "old_manifest": old_state,
            "new_manifest": new_state,
            "changed_fields": list(changed),
        }
        return cls(
            component_id=component_id,
            old_manifest=old_manifest,
            new_manifest=new_manifest,
            changed_fields=changed,
            delta_id="integration-evolution-delta-v1-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": EVOLUTION_DELTA_PROTOCOL,
            "component_id": self.component_id,
            "old_manifest": self.old_manifest.to_state(),
            "new_manifest": self.new_manifest.to_state(),
            "changed_fields": list(self.changed_fields),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "delta_id": self.delta_id}

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("component evolution delta integrity validation failed") from exc
        if restored != self:
            raise ValueError("component evolution delta integrity validation failed")

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ComponentEvolutionDelta":
        if state.get("protocol") != EVOLUTION_DELTA_PROTOCOL:
            raise ValueError("component evolution delta protocol mismatch")
        old_state = state.get("old_manifest")
        new_state = state.get("new_manifest")
        if not isinstance(old_state, Mapping) or not isinstance(new_state, Mapping):
            raise ValueError("component evolution delta manifests must be objects")
        expected = cls.create(
            ExternalComponentManifest.from_state(old_state),
            ExternalComponentManifest.from_state(new_state),
        )
        if state.get("component_id") != expected.component_id:
            raise ValueError("component evolution delta identity mismatch")
        if state.get("changed_fields") != list(expected.changed_fields):
            raise ValueError("component evolution delta changed-field drift")
        if state.get("delta_id") != expected.delta_id:
            raise ValueError("component evolution delta digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("component evolution delta state is non-canonical")
        return expected


@dataclass(frozen=True, slots=True)
class EvolutionCompatibilityQualification:
    delta_id: str
    disposition: EvolutionCompatibilityDisposition
    reason_codes: tuple[str, ...]
    digest: str

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": EVOLUTION_QUALIFICATION_PROTOCOL,
            "delta_id": self.delta_id,
            "disposition": self.disposition.value,
            "reason_codes": list(self.reason_codes),
            "digest": self.digest,
        }


def qualify_component_evolution(delta: ComponentEvolutionDelta) -> EvolutionCompatibilityQualification:
    try:
        delta.validate_integrity()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("component evolution delta integrity invalid for qualification") from exc

    old = delta.old_manifest
    new = delta.new_manifest
    incompatible: list[str] = []
    revalidate: list[str] = []

    if not delta.changed_fields:
        disposition = EvolutionCompatibilityDisposition.COMPATIBLE
        reasons: tuple[str, ...] = ()
    else:
        if set(old.produces_contracts) - set(new.produces_contracts):
            incompatible.append("PRODUCED_CONTRACT_REMOVED")
        if set(old.consumes_contracts) - set(new.consumes_contracts):
            incompatible.append("CONSUMED_CONTRACT_REMOVED")
        if old.mutable_resources != new.mutable_resources:
            incompatible.append("MUTABLE_RESOURCE_AUTHORITY_CHANGED")
        if old.authority_capabilities != new.authority_capabilities:
            incompatible.append("AUTHORITY_CAPABILITY_CHANGED")
        if old.forbidden_authorities != new.forbidden_authorities:
            incompatible.append("FORBIDDEN_AUTHORITY_CHANGED")

        if incompatible:
            disposition = EvolutionCompatibilityDisposition.INCOMPATIBLE
            reasons = tuple(sorted(set(incompatible)))
        else:
            if old.component_version != new.component_version:
                revalidate.append("COMPONENT_VERSION_CHANGED")
            if old.protocol_versions != new.protocol_versions:
                revalidate.append("PROTOCOL_VERSION_CHANGED")
            if old.produces_contracts != new.produces_contracts:
                revalidate.append("PRODUCED_CONTRACT_SET_CHANGED")
            if old.consumes_contracts != new.consumes_contracts:
                revalidate.append("CONSUMED_CONTRACT_SET_CHANGED")
            if old.evidence_inputs != new.evidence_inputs or old.evidence_outputs != new.evidence_outputs:
                revalidate.append("EVIDENCE_CONTRACT_CHANGED")
            if old.restore_protocol != new.restore_protocol:
                revalidate.append("RESTORE_PROTOCOL_CHANGED")
            if old.compatibility_floor != new.compatibility_floor or old.compatibility_ceiling != new.compatibility_ceiling:
                revalidate.append("COMPATIBILITY_RANGE_CHANGED")
            if not revalidate:
                revalidate.append("MANIFEST_SEMANTICS_CHANGED")
            disposition = EvolutionCompatibilityDisposition.REVALIDATION_REQUIRED
            reasons = tuple(sorted(set(revalidate)))

    payload = {
        "protocol": EVOLUTION_QUALIFICATION_PROTOCOL,
        "delta_id": delta.delta_id,
        "disposition": disposition.value,
        "reason_codes": list(reasons),
    }
    return EvolutionCompatibilityQualification(
        delta_id=delta.delta_id,
        disposition=disposition,
        reason_codes=reasons,
        digest="integration-evolution-qualification-v1-" + canonical_digest(payload),
    )


def _explicit(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an explicit string")
    return value


__all__ = (
    "ComponentEvolutionDelta",
    "EvolutionCompatibilityDisposition",
    "EvolutionCompatibilityQualification",
    "qualify_component_evolution",
)
