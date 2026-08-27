from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.organization.events import EventKind
from nolane.core.canonical_digest import canonical_digest

COMPONENT_ID = "external.architecture"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.architecture"


class ComponentKind(str, Enum):
    SERVICE = "service"
    MODULE = "module"
    LIBRARY = "library"
    UI = "ui"
    DATA_STORE = "data_store"
    RUNTIME = "runtime"
    EXTERNAL = "external"
    BUILD = "build"


class ComponentStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    REMOVED = "removed"


class EdgeKind(str, Enum):
    DEPENDS_ON = "depends_on"
    CALLS = "calls"
    READS = "reads"
    WRITES = "writes"
    EMITS = "emits"
    CONSUMES = "consumes"
    IMPLEMENTS = "implements"
    HOSTS = "hosts"
    TRUSTS = "trusts"


class InterfaceClass(str, Enum):
    API = "api"
    EVENT = "event"
    SCHEMA = "schema"
    FILE = "file"
    CLI = "cli"
    LIBRARY = "library"
    UI_CONTRACT = "ui_contract"


class InterfaceStability(str, Enum):
    PRIVATE = "private"
    INTERNAL = "internal"
    PUBLIC = "public"


@dataclass(frozen=True, slots=True)
class ArchitectureComponent:
    component_id: str
    title: str
    kind: ComponentKind
    owner_region: str
    trust_zone: str
    requirement_refs: tuple[str, ...] = ()
    plan_refs: tuple[str, ...] = ()
    status: ComponentStatus = ComponentStatus.ACTIVE

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.component_id, self.title, self.owner_region, self.trust_zone)):
            raise ValueError("component identity/title/owner/trust-zone must be non-empty")

    def to_state(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "title": self.title,
            "kind": self.kind.value,
            "owner_region": self.owner_region,
            "trust_zone": self.trust_zone,
            "requirement_refs": list(self.requirement_refs),
            "plan_refs": list(self.plan_refs),
            "status": self.status.value,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArchitectureComponent":
        return cls(
            str(state["component_id"]),
            str(state["title"]),
            ComponentKind(str(state["kind"])),
            str(state["owner_region"]),
            str(state["trust_zone"]),
            tuple(str(x) for x in state.get("requirement_refs", ())),
            tuple(str(x) for x in state.get("plan_refs", ())),
            ComponentStatus(str(state.get("status", ComponentStatus.ACTIVE.value))),
        )


@dataclass(frozen=True, slots=True)
class InterfaceContract:
    interface_id: str
    producer_component_id: str
    interface_class: InterfaceClass
    semantic_version: str
    signature_digest: str
    stability: InterfaceStability
    consumer_scope: tuple[str, ...] = ()
    compatibility_policy: str = "backward"
    trust_classification: str = "internal"

    def __post_init__(self) -> None:
        if not all(
            str(x).strip()
            for x in (
                self.interface_id,
                self.producer_component_id,
                self.semantic_version,
                self.signature_digest,
            )
        ):
            raise ValueError("interface identity/producer/version/signature must be non-empty")

    def to_state(self) -> dict[str, Any]:
        return {
            "interface_id": self.interface_id,
            "producer_component_id": self.producer_component_id,
            "interface_class": self.interface_class.value,
            "semantic_version": self.semantic_version,
            "signature_digest": self.signature_digest,
            "stability": self.stability.value,
            "consumer_scope": list(self.consumer_scope),
            "compatibility_policy": self.compatibility_policy,
            "trust_classification": self.trust_classification,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "InterfaceContract":
        return cls(
            str(state["interface_id"]),
            str(state["producer_component_id"]),
            InterfaceClass(str(state["interface_class"])),
            str(state["semantic_version"]),
            str(state["signature_digest"]),
            InterfaceStability(str(state["stability"])),
            tuple(str(x) for x in state.get("consumer_scope", ())),
            str(state.get("compatibility_policy", "backward")),
            str(state.get("trust_classification", "internal")),
        )


@dataclass(frozen=True, slots=True)
class ArchitectureEdge:
    edge_id: str
    source_component_id: str
    target_component_id: str
    kind: EdgeKind

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.edge_id, self.source_component_id, self.target_component_id)):
            raise ValueError("architecture edge identity/endpoints must be non-empty")

    def to_state(self) -> dict[str, str]:
        return {
            "edge_id": self.edge_id,
            "source_component_id": self.source_component_id,
            "target_component_id": self.target_component_id,
            "kind": self.kind.value,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArchitectureEdge":
        return cls(
            str(state["edge_id"]),
            str(state["source_component_id"]),
            str(state["target_component_id"]),
            EdgeKind(str(state["kind"])),
        )


@dataclass(frozen=True, slots=True)
class ArchitectureRevision:
    version: int
    parent_version: int | None
    actor_agent_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    changed_refs: tuple[str, ...]
    graph_digest: str

    def to_state(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "parent_version": self.parent_version,
            "actor_agent_id": self.actor_agent_id,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "changed_refs": list(self.changed_refs),
            "graph_digest": self.graph_digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArchitectureRevision":
        return cls(
            int(state["version"]),
            None if state.get("parent_version") is None else int(state["parent_version"]),
            str(state["actor_agent_id"]),
            str(state["reason"]),
            tuple(str(x) for x in state.get("evidence_refs", ())),
            tuple(str(x) for x in state.get("changed_refs", ())),
            str(state["graph_digest"]),
        )


class ArchitectureGraph:
    def __init__(self) -> None:
        self._components: dict[str, ArchitectureComponent] = {}
        self._interfaces: dict[str, InterfaceContract] = {}
        self._edges: dict[str, ArchitectureEdge] = {}
        self._revisions: list[ArchitectureRevision] = []

    @property
    def version(self) -> int:
        return len(self._revisions)

    def components(self) -> tuple[ArchitectureComponent, ...]:
        return tuple(self._components[k] for k in sorted(self._components))

    def interfaces(self) -> tuple[InterfaceContract, ...]:
        return tuple(self._interfaces[k] for k in sorted(self._interfaces))

    def edges(self) -> tuple[ArchitectureEdge, ...]:
        return tuple(self._edges[k] for k in sorted(self._edges))

    def get_component(self, component_id: str) -> ArchitectureComponent:
        try:
            return self._components[str(component_id)]
        except KeyError as exc:
            raise KeyError(f"unknown architecture component: {component_id}") from exc

    def get_interface(self, interface_id: str) -> InterfaceContract:
        try:
            return self._interfaces[str(interface_id)]
        except KeyError as exc:
            raise KeyError(f"unknown interface: {interface_id}") from exc

    def contains_ref(self, ref: str) -> bool:
        return str(ref) in self._components or str(ref) in self._interfaces

    def _payload(self, components=None, interfaces=None, edges=None) -> dict[str, Any]:
        components = self._components if components is None else components
        interfaces = self._interfaces if interfaces is None else interfaces
        edges = self._edges if edges is None else edges
        return {
            "components": [components[k].to_state() for k in sorted(components)],
            "interfaces": [interfaces[k].to_state() for k in sorted(interfaces)],
            "edges": [edges[k].to_state() for k in sorted(edges)],
        }

    @property
    def digest(self) -> str:
        return canonical_digest({"version": self.version, **self._payload()})

    @staticmethod
    def _validate(
        components: Mapping[str, ArchitectureComponent],
        interfaces: Mapping[str, InterfaceContract],
        edges: Mapping[str, ArchitectureEdge],
    ) -> None:
        for interface in interfaces.values():
            if interface.producer_component_id not in components:
                raise ValueError(f"interface producer is unknown: {interface.producer_component_id}")
        for edge in edges.values():
            if edge.source_component_id not in components or edge.target_component_id not in components:
                raise ValueError("architecture edge references unknown component")
        adjacency: dict[str, list[str]] = {key: [] for key in components}
        for edge in edges.values():
            if edge.kind is EdgeKind.DEPENDS_ON:
                adjacency[edge.source_component_id].append(edge.target_component_id)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("architecture dependency cycle detected")
            if node in visited:
                return
            visiting.add(node)
            for nxt in adjacency[node]:
                visit(nxt)
            visiting.remove(node)
            visited.add(node)

        for key in sorted(adjacency):
            visit(key)

    def apply(
        self,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        upsert_components: tuple[ArchitectureComponent, ...] = (),
        upsert_interfaces: tuple[InterfaceContract, ...] = (),
        upsert_edges: tuple[ArchitectureEdge, ...] = (),
    ) -> ArchitectureRevision:
        reason = str(reason).strip()
        evidence = tuple(str(x).strip() for x in evidence_refs if str(x).strip())
        if not reason or not evidence or (not upsert_components and not upsert_interfaces and not upsert_edges):
            raise ValueError("architecture revision requires reason, evidence and mutation")
        components, interfaces, edges = dict(self._components), dict(self._interfaces), dict(self._edges)
        changed: list[str] = []
        for row in upsert_components:
            components[row.component_id] = row
            changed.append(row.component_id)
        for row in upsert_interfaces:
            interfaces[row.interface_id] = row
            changed.append(row.interface_id)
        for row in upsert_edges:
            edges[row.edge_id] = row
            changed.append(row.edge_id)
        self._validate(components, interfaces, edges)
        next_version = self.version + 1
        digest = canonical_digest({"version": next_version, **self._payload(components, interfaces, edges)})
        revision = ArchitectureRevision(
            next_version,
            self.version or None,
            str(actor_agent_id),
            reason,
            evidence,
            tuple(sorted(set(changed))),
            digest,
        )
        self._components, self._interfaces, self._edges = components, interfaces, edges
        self._revisions.append(revision)
        return revision

    def to_state(self) -> dict[str, Any]:
        return {**self._payload(), "revisions": [x.to_state() for x in self._revisions]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArchitectureGraph":
        graph = cls()
        graph._components = {
            x.component_id: x for x in (ArchitectureComponent.from_state(v) for v in state.get("components", ()))
        }
        graph._interfaces = {
            x.interface_id: x for x in (InterfaceContract.from_state(v) for v in state.get("interfaces", ()))
        }
        graph._edges = {
            x.edge_id: x for x in (ArchitectureEdge.from_state(v) for v in state.get("edges", ()))
        }
        graph._validate(graph._components, graph._interfaces, graph._edges)
        graph._revisions = [ArchitectureRevision.from_state(v) for v in state.get("revisions", ())]
        for index, revision in enumerate(graph._revisions, 1):
            if revision.version != index:
                raise ValueError("non-canonical architecture revision sequence")
        if graph._revisions and graph._revisions[-1].graph_digest != graph.digest:
            raise ValueError("architecture graph digest mismatch")
        return graph


class ArchitectureControlPlane:
    def __init__(self, *, registry: Any, authority: Any, ledger: Any, graph: ArchitectureGraph | None = None) -> None:
        self.registry, self.authority, self.ledger = registry, authority, ledger
        self.graph = graph or ArchitectureGraph()

    def apply_revision(
        self,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        upsert_components: tuple[ArchitectureComponent, ...] = (),
        upsert_interfaces: tuple[InterfaceContract, ...] = (),
        upsert_edges: tuple[ArchitectureEdge, ...] = (),
    ) -> ArchitectureRevision:
        self.registry.get(actor_agent_id)
        self.authority.require_write(actor_agent_id, "architecture-graph")
        revision = self.graph.apply(
            actor_agent_id=actor_agent_id,
            reason=reason,
            evidence_refs=evidence_refs,
            upsert_components=upsert_components,
            upsert_interfaces=upsert_interfaces,
            upsert_edges=upsert_edges,
        )
        self.ledger.append(
            EventKind.ARCHITECTURE_CONCERN,
            source_agent_id=actor_agent_id,
            target_agent_id="architecture.chief",
            region="architecture-system",
            object_refs=revision.changed_refs,
            evidence_refs=revision.evidence_refs,
            payload={"architecture_action": "changed", "version": revision.version, "reason": revision.reason},
        )
        return revision

    def propose_concern(
        self,
        *,
        source_agent_id: str,
        component_refs: tuple[str, ...],
        observation: str,
        alternatives: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        severity: int,
    ):
        self.registry.get(source_agent_id)
        for ref in component_refs:
            self.graph.get_component(ref)
        if not observation.strip() or not alternatives or not evidence_refs or not 0 <= int(severity) <= 100:
            raise ValueError("architecture concern requires observation, alternatives, evidence and bounded severity")
        return self.ledger.append(
            EventKind.ARCHITECTURE_CONCERN,
            source_agent_id=source_agent_id,
            target_agent_id="architecture.chief",
            region="architecture-system",
            object_refs=component_refs,
            evidence_refs=tuple(str(x) for x in evidence_refs),
            payload={
                "architecture_action": "concern",
                "observation": observation,
                "alternatives": list(alternatives),
                "severity": int(severity),
            },
        )

    def to_state(self) -> dict[str, Any]:
        return {"graph": self.graph.to_state()}

    @classmethod
    def from_state(
        cls,
        *,
        registry: Any,
        authority: Any,
        ledger: Any,
        state: Mapping[str, Any],
    ) -> "ArchitectureControlPlane":
        return cls(
            registry=registry,
            authority=authority,
            ledger=ledger,
            graph=ArchitectureGraph.from_state(state.get("graph", {})),
        )


__all__ = (
    "ComponentKind",
    "ComponentStatus",
    "EdgeKind",
    "InterfaceClass",
    "InterfaceStability",
    "ArchitectureComponent",
    "InterfaceContract",
    "ArchitectureEdge",
    "ArchitectureRevision",
    "ArchitectureGraph",
    "ArchitectureControlPlane",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
