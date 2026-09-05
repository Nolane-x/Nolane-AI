from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.authority_graph import ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest


EVOLUTION_DELTA_PROTOCOL = "integration-evolution-delta-v1"
EVOLUTION_QUALIFICATION_PROTOCOL = "integration-evolution-qualification-v1"
INTEGRATION_IMPACT_PROTOCOL = "integration-impact-closure-v1"


class EvolutionCompatibilityDisposition(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


_MANIFEST_FIELDS = (
    "component_version", "protocol_versions", "consumes_contracts", "produces_contracts",
    "authority_capabilities", "forbidden_authorities", "mutable_resources",
    "evidence_inputs", "evidence_outputs", "restore_protocol", "compatibility_floor",
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
    def create(cls, old_manifest: ExternalComponentManifest, new_manifest: ExternalComponentManifest) -> "ComponentEvolutionDelta":
        if not isinstance(old_manifest, ExternalComponentManifest) or not isinstance(new_manifest, ExternalComponentManifest):
            raise ValueError("evolution delta requires canonical component manifests")
        if old_manifest.component_id != new_manifest.component_id:
            raise ValueError("evolution delta cannot rebind component identity")
        component_id = _explicit(old_manifest.component_id, "component identity")
        old_state, new_state = old_manifest.to_state(), new_manifest.to_state()
        changed = tuple(field for field in _MANIFEST_FIELDS if old_state.get(field) != new_state.get(field))
        payload = {"protocol": EVOLUTION_DELTA_PROTOCOL, "component_id": component_id, "old_manifest": old_state, "new_manifest": new_state, "changed_fields": list(changed)}
        return cls(component_id, old_manifest, new_manifest, changed, "integration-evolution-delta-v1-" + canonical_digest(payload))

    def payload(self) -> dict[str, Any]:
        return {"protocol": EVOLUTION_DELTA_PROTOCOL, "component_id": self.component_id, "old_manifest": self.old_manifest.to_state(), "new_manifest": self.new_manifest.to_state(), "changed_fields": list(self.changed_fields)}

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
        old_state, new_state = state.get("old_manifest"), state.get("new_manifest")
        if not isinstance(old_state, Mapping) or not isinstance(new_state, Mapping):
            raise ValueError("component evolution delta manifests must be objects")
        expected = cls.create(ExternalComponentManifest.from_state(old_state), ExternalComponentManifest.from_state(new_state))
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
        return {"protocol": EVOLUTION_QUALIFICATION_PROTOCOL, "delta_id": self.delta_id, "disposition": self.disposition.value, "reason_codes": list(self.reason_codes), "digest": self.digest}


def qualify_component_evolution(delta: ComponentEvolutionDelta) -> EvolutionCompatibilityQualification:
    try:
        delta.validate_integrity()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("component evolution delta integrity invalid for qualification") from exc
    old, new = delta.old_manifest, delta.new_manifest
    incompatible: list[str] = []
    revalidate: list[str] = []
    if not delta.changed_fields:
        disposition, reasons = EvolutionCompatibilityDisposition.COMPATIBLE, ()
    else:
        if set(old.produces_contracts) - set(new.produces_contracts): incompatible.append("PRODUCED_CONTRACT_REMOVED")
        if set(old.consumes_contracts) - set(new.consumes_contracts): incompatible.append("CONSUMED_CONTRACT_REMOVED")
        if old.mutable_resources != new.mutable_resources: incompatible.append("MUTABLE_RESOURCE_AUTHORITY_CHANGED")
        if old.authority_capabilities != new.authority_capabilities: incompatible.append("AUTHORITY_CAPABILITY_CHANGED")
        if old.forbidden_authorities != new.forbidden_authorities: incompatible.append("FORBIDDEN_AUTHORITY_CHANGED")
        if incompatible:
            disposition, reasons = EvolutionCompatibilityDisposition.INCOMPATIBLE, tuple(sorted(set(incompatible)))
        else:
            if old.component_version != new.component_version: revalidate.append("COMPONENT_VERSION_CHANGED")
            if old.protocol_versions != new.protocol_versions: revalidate.append("PROTOCOL_VERSION_CHANGED")
            if old.produces_contracts != new.produces_contracts: revalidate.append("PRODUCED_CONTRACT_SET_CHANGED")
            if old.consumes_contracts != new.consumes_contracts: revalidate.append("CONSUMED_CONTRACT_SET_CHANGED")
            if old.evidence_inputs != new.evidence_inputs or old.evidence_outputs != new.evidence_outputs: revalidate.append("EVIDENCE_CONTRACT_CHANGED")
            if old.restore_protocol != new.restore_protocol: revalidate.append("RESTORE_PROTOCOL_CHANGED")
            if old.compatibility_floor != new.compatibility_floor or old.compatibility_ceiling != new.compatibility_ceiling: revalidate.append("COMPATIBILITY_RANGE_CHANGED")
            if not revalidate: revalidate.append("MANIFEST_SEMANTICS_CHANGED")
            disposition, reasons = EvolutionCompatibilityDisposition.REVALIDATION_REQUIRED, tuple(sorted(set(revalidate)))
    payload = {"protocol": EVOLUTION_QUALIFICATION_PROTOCOL, "delta_id": delta.delta_id, "disposition": disposition.value, "reason_codes": list(reasons)}
    return EvolutionCompatibilityQualification(delta.delta_id, disposition, reasons, "integration-evolution-qualification-v1-" + canonical_digest(payload))


@dataclass(frozen=True, slots=True)
class IntegrationImpactReason:
    source_id: str
    target_id: str
    relation: str
    contract_kind: str
    digest: str

    @classmethod
    def create(cls, source_id: str, target_id: str, relation: str, contract_kind: str) -> "IntegrationImpactReason":
        payload = {"source_id": _explicit(source_id, "impact source"), "target_id": _explicit(target_id, "impact target"), "relation": _explicit(relation, "impact relation"), "contract_kind": _explicit(contract_kind, "impact contract")}
        return cls(payload["source_id"], payload["target_id"], payload["relation"], payload["contract_kind"], canonical_digest(payload))

    def to_state(self) -> dict[str, str]:
        return {"source_id": self.source_id, "target_id": self.target_id, "relation": self.relation, "contract_kind": self.contract_kind, "digest": self.digest}


@dataclass(frozen=True, slots=True)
class IntegrationImpactClosure:
    changed_component_ids: tuple[str, ...]
    impacted_component_ids: tuple[str, ...]
    reasons: tuple[IntegrationImpactReason, ...]
    authority_graph_digest: str
    closure_id: str

    def to_state(self) -> dict[str, Any]:
        return {"protocol": INTEGRATION_IMPACT_PROTOCOL, "changed_component_ids": list(self.changed_component_ids), "impacted_component_ids": list(self.impacted_component_ids), "reasons": [row.to_state() for row in self.reasons], "authority_graph_digest": self.authority_graph_digest, "closure_id": self.closure_id}


def build_integration_impact_closure(changed_component_ids: tuple[str, ...], authority_graph: ExternalAuthorityGraph) -> IntegrationImpactClosure:
    if not isinstance(authority_graph, ExternalAuthorityGraph):
        raise ValueError("integration impact requires an ExternalAuthorityGraph")
    changed = tuple(sorted({_explicit(value, "changed component identity") for value in changed_component_ids}))
    if not changed:
        raise ValueError("integration impact requires at least one changed component")
    graph_ids = {manifest.component_id for manifest in authority_graph.manifests}
    unknown = sorted(set(changed) - graph_ids)
    if unknown:
        raise ValueError("unknown changed component: " + ",".join(unknown))

    impacted = set(changed)
    reasons: dict[str, IntegrationImpactReason] = {}
    progressed = True
    while progressed:
        progressed = False
        for edge in authority_graph.edges:
            if edge.source_component_id not in impacted or edge.target_component_id in impacted:
                continue
            impacted.add(edge.target_component_id)
            reason = IntegrationImpactReason.create(edge.source_component_id, edge.target_component_id, edge.relation.value, edge.contract_kind)
            reasons[reason.digest] = reason
            progressed = True
    ordered_reasons = tuple(sorted(reasons.values(), key=lambda row: (row.source_id, row.target_id, row.relation, row.contract_kind)))
    payload = {"protocol": INTEGRATION_IMPACT_PROTOCOL, "changed_component_ids": list(changed), "impacted_component_ids": sorted(impacted), "reasons": [row.to_state() for row in ordered_reasons], "authority_graph_digest": authority_graph.digest}
    return IntegrationImpactClosure(changed, tuple(sorted(impacted)), ordered_reasons, authority_graph.digest, "integration-impact-v1-" + canonical_digest(payload))


def _explicit(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an explicit string")
    return value


__all__ = (
    "ComponentEvolutionDelta", "EvolutionCompatibilityDisposition", "EvolutionCompatibilityQualification",
    "IntegrationImpactClosure", "IntegrationImpactReason", "build_integration_impact_closure",
    "qualify_component_evolution",
)
