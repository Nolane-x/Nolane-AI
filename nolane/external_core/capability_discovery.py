from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.authority_graph import ExternalAuthorityGraph
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily


DISCOVERY_PROTOCOL = "external-capability-discovery-v1"


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    component_id: str
    component_version: str
    family: ExternalCoreFamily
    consumes_contracts: tuple[str, ...]
    produces_contracts: tuple[str, ...]
    authority_capabilities: tuple[str, ...]
    forbidden_authorities: tuple[str, ...]
    evidence_inputs: tuple[str, ...]
    evidence_outputs: tuple[str, ...]
    restore_protocol: str
    manifest_digest: str

    @classmethod
    def from_manifest(cls, manifest: ExternalComponentManifest) -> "CapabilityDescriptor":
        return cls(
            component_id=manifest.component_id,
            component_version=manifest.component_version,
            family=manifest.family,
            consumes_contracts=manifest.consumes_contracts,
            produces_contracts=manifest.produces_contracts,
            authority_capabilities=manifest.authority_capabilities,
            forbidden_authorities=manifest.forbidden_authorities,
            evidence_inputs=manifest.evidence_inputs,
            evidence_outputs=manifest.evidence_outputs,
            restore_protocol=manifest.restore_protocol,
            manifest_digest=manifest.manifest_digest,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_version": self.component_version,
            "family": self.family.value,
            "consumes_contracts": list(self.consumes_contracts),
            "produces_contracts": list(self.produces_contracts),
            "authority_capabilities": list(self.authority_capabilities),
            "forbidden_authorities": list(self.forbidden_authorities),
            "evidence_inputs": list(self.evidence_inputs),
            "evidence_outputs": list(self.evidence_outputs),
            "restore_protocol": self.restore_protocol,
            "manifest_digest": self.manifest_digest,
        }


@dataclass(frozen=True, slots=True)
class ContractDiscoveryResult:
    contract_kind: str
    producers: tuple[CapabilityDescriptor, ...]
    consumers: tuple[CapabilityDescriptor, ...]
    authority_graph_digest: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "contract_kind": self.contract_kind,
            "producers": [row.to_state() for row in self.producers],
            "consumers": [row.to_state() for row in self.consumers],
            "authority_graph_digest": self.authority_graph_digest,
        }


class CapabilityDiscoveryIndex:
    """Read-only semantic discovery over declared External Core capabilities.

    Discovery can describe which component declares a contract and what
    evidence/authority/restore semantics it exposes. It deliberately has no
    invocation, execution, authorization, promotion, or mutation surface.
    """

    def __init__(
        self,
        manifests: tuple[ExternalComponentManifest, ...],
        authority_graph: ExternalAuthorityGraph,
    ) -> None:
        ordered = tuple(sorted(manifests, key=lambda row: row.component_id))
        if len({row.component_id for row in ordered}) != len(ordered):
            raise ValueError("duplicate component manifest in capability discovery")
        graph_ids = tuple(row.component_id for row in authority_graph.manifests)
        manifest_ids = tuple(row.component_id for row in ordered)
        if graph_ids != manifest_ids:
            raise ValueError("capability discovery manifests do not match authority graph manifests")
        graph_manifest_digests = tuple(row.manifest_digest for row in authority_graph.manifests)
        manifest_digests = tuple(row.manifest_digest for row in ordered)
        if graph_manifest_digests != manifest_digests:
            raise ValueError("capability discovery manifest digest drift from authority graph")
        self._manifests = ordered
        self._by_id = {row.component_id: row for row in ordered}
        self._graph = authority_graph

    @property
    def authority_graph_digest(self) -> str:
        return self._graph.digest

    @property
    def digest(self) -> str:
        return canonical_digest(self._payload())

    def describe(self, component_id: str) -> CapabilityDescriptor:
        try:
            manifest = self._by_id[str(component_id)]
        except KeyError as exc:
            raise KeyError(f"unknown External Core component: {component_id}") from exc
        return CapabilityDescriptor.from_manifest(manifest)

    def components(self) -> tuple[CapabilityDescriptor, ...]:
        return tuple(CapabilityDescriptor.from_manifest(row) for row in self._manifests)

    def by_contract(self, contract_kind: str) -> ContractDiscoveryResult:
        contract = _explicit(contract_kind, "discovery contract kind")
        producers = tuple(
            CapabilityDescriptor.from_manifest(row)
            for row in self._manifests
            if contract in row.produces_contracts
        )
        consumers = tuple(
            CapabilityDescriptor.from_manifest(row)
            for row in self._manifests
            if contract in row.consumes_contracts
        )
        payload = {
            "contract_kind": contract,
            "producers": [row.to_state() for row in producers],
            "consumers": [row.to_state() for row in consumers],
            "authority_graph_digest": self._graph.digest,
        }
        return ContractDiscoveryResult(
            contract_kind=contract,
            producers=producers,
            consumers=consumers,
            authority_graph_digest=self._graph.digest,
            digest=canonical_digest(payload),
        )

    def by_authority(self, authority: str) -> tuple[CapabilityDescriptor, ...]:
        value = _explicit(authority, "discovery authority")
        return tuple(
            CapabilityDescriptor.from_manifest(row)
            for row in self._manifests
            if value in row.authority_capabilities and value not in row.forbidden_authorities
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "protocol": DISCOVERY_PROTOCOL,
            "manifests": [row.to_state() for row in self._manifests],
            "authority_graph": self._graph.to_state(),
            "authority_graph_digest": self._graph.digest,
        }

    def to_state(self) -> dict[str, Any]:
        payload = self._payload()
        return {**payload, "digest": canonical_digest(payload)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CapabilityDiscoveryIndex":
        if str(state.get("protocol", "")) != DISCOVERY_PROTOCOL:
            raise ValueError("unsupported capability discovery protocol")
        manifests = tuple(
            ExternalComponentManifest.from_state(raw) for raw in state.get("manifests", ())
        )
        graph_state = state.get("authority_graph")
        if not isinstance(graph_state, Mapping):
            raise ValueError("capability discovery state is missing authority graph")
        graph = ExternalAuthorityGraph.from_state(graph_state)
        expected_graph_digest = str(state.get("authority_graph_digest", ""))
        if expected_graph_digest != graph.digest:
            raise ValueError("capability discovery authority graph digest mismatch")
        index = cls(manifests, graph)
        if str(state.get("digest", "")) != index.digest:
            raise ValueError("capability discovery digest mismatch")
        if dict(state) != index.to_state():
            raise ValueError("capability discovery state is non-canonical")
        return index


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


__all__ = (
    "DISCOVERY_PROTOCOL",
    "CapabilityDescriptor",
    "CapabilityDiscoveryIndex",
    "ContractDiscoveryResult",
)
