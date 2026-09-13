from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.organization.events import EventKind
from nolane.core.canonical_digest import canonical_digest

COMPONENT_ID = "external.architecture"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder.organization.architecture"


def _exact_non_empty_string(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be an exact non-empty string")
    return value


def _exact_string_sequence(value: object, label: str) -> tuple[str, ...]:
    if type(value) not in (list, tuple):
        raise ValueError(f"{label} must be a sequence of exact non-empty strings")
    return tuple(_exact_non_empty_string(item, label) for item in value)


def _canonical_state_record(
    state: object,
    expected_keys: tuple[str, ...],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(state, Mapping) or set(state) != set(expected_keys):
        raise ValueError(f"{label} must use canonical serialized state")
    return state


def _canonical_state_list(value: object, label: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"{label} must use canonical serialized state")
    return value


def _canonical_string_list(value: object, label: str) -> tuple[str, ...]:
    return tuple(
        _exact_non_empty_string(item, label)
        for item in _canonical_state_list(value, label)
    )


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
        _exact_non_empty_string(self.component_id, "architecture component identity")
        _exact_non_empty_string(self.title, "architecture component title")
        _exact_non_empty_string(self.owner_region, "architecture component owner region")
        _exact_non_empty_string(self.trust_zone, "architecture component trust zone")
        _exact_string_sequence(self.requirement_refs, "architecture component requirement reference")
        _exact_string_sequence(self.plan_refs, "architecture component plan reference")

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
        state = _canonical_state_record(
            state,
            (
                "component_id",
                "title",
                "kind",
                "owner_region",
                "trust_zone",
                "requirement_refs",
                "plan_refs",
                "status",
            ),
            "architecture component",
        )
        return cls(
            _exact_non_empty_string(state["component_id"], "architecture component identity"),
            _exact_non_empty_string(state["title"], "architecture component title"),
            ComponentKind(_exact_non_empty_string(state["kind"], "architecture component kind")),
            _exact_non_empty_string(state["owner_region"], "architecture component owner region"),
            _exact_non_empty_string(state["trust_zone"], "architecture component trust zone"),
            _canonical_string_list(
                state["requirement_refs"],
                "architecture component requirement reference",
            ),
            _canonical_string_list(
                state["plan_refs"],
                "architecture component plan reference",
            ),
            ComponentStatus(
                _exact_non_empty_string(
                    state["status"],
                    "architecture component status",
                )
            ),
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
        _exact_non_empty_string(self.interface_id, "architecture interface identity")
        _exact_non_empty_string(self.producer_component_id, "architecture interface producer")
        _exact_non_empty_string(self.semantic_version, "architecture interface semantic version")
        _exact_non_empty_string(self.signature_digest, "architecture interface signature digest")
        _exact_string_sequence(self.consumer_scope, "architecture interface consumer scope")
        _exact_non_empty_string(self.compatibility_policy, "architecture interface compatibility policy")
        _exact_non_empty_string(self.trust_classification, "architecture interface trust classification")

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
        state = _canonical_state_record(
            state,
            (
                "interface_id",
                "producer_component_id",
                "interface_class",
                "semantic_version",
                "signature_digest",
                "stability",
                "consumer_scope",
                "compatibility_policy",
                "trust_classification",
            ),
            "architecture interface",
        )
        return cls(
            _exact_non_empty_string(state["interface_id"], "architecture interface identity"),
            _exact_non_empty_string(state["producer_component_id"], "architecture interface producer"),
            InterfaceClass(_exact_non_empty_string(state["interface_class"], "architecture interface class")),
            _exact_non_empty_string(state["semantic_version"], "architecture interface semantic version"),
            _exact_non_empty_string(state["signature_digest"], "architecture interface signature digest"),
            InterfaceStability(_exact_non_empty_string(state["stability"], "architecture interface stability")),
            _canonical_string_list(
                state["consumer_scope"],
                "architecture interface consumer scope",
            ),
            _exact_non_empty_string(
                state["compatibility_policy"],
                "architecture interface compatibility policy",
            ),
            _exact_non_empty_string(
                state["trust_classification"],
                "architecture interface trust classification",
            ),
        )


@dataclass(frozen=True, slots=True)
class ArchitectureEdge:
    edge_id: str
    source_component_id: str
    target_component_id: str
    kind: EdgeKind

    def __post_init__(self) -> None:
        _exact_non_empty_string(self.edge_id, "architecture edge identity")
        _exact_non_empty_string(self.source_component_id, "architecture edge source")
        _exact_non_empty_string(self.target_component_id, "architecture edge target")

    def to_state(self) -> dict[str, str]:
        return {
            "edge_id": self.edge_id,
            "source_component_id": self.source_component_id,
            "target_component_id": self.target_component_id,
            "kind": self.kind.value,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ArchitectureEdge":
        state = _canonical_state_record(
            state,
            ("edge_id", "source_component_id", "target_component_id", "kind"),
            "architecture edge",
        )
        return cls(
            _exact_non_empty_string(state["edge_id"], "architecture edge identity"),
            _exact_non_empty_string(state["source_component_id"], "architecture edge source"),
            _exact_non_empty_string(state["target_component_id"], "architecture edge target"),
            EdgeKind(_exact_non_empty_string(state["kind"], "architecture edge kind")),
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

    def __post_init__(self) -> None:
        _exact_non_empty_string(self.actor_agent_id, "architecture revision actor")
        _exact_non_empty_string(self.reason, "architecture revision reason")
        _exact_string_sequence(self.evidence_refs, "architecture revision evidence reference")
        _exact_string_sequence(self.changed_refs, "architecture revision changed reference")
        _exact_non_empty_string(self.graph_digest, "architecture revision graph digest")

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
        state = _canonical_state_record(
            state,
            (
                "version",
                "parent_version",
                "actor_agent_id",
                "reason",
                "evidence_refs",
                "changed_refs",
                "graph_digest",
            ),
            "architecture revision",
        )
        version = state["version"]
        if type(version) is not int or version <= 0:
            raise ValueError("architecture revision version must be a positive exact int")
        parent_version = state["parent_version"]
        if parent_version is not None and (type(parent_version) is not int or parent_version <= 0):
            raise ValueError("architecture parent version must be a positive exact int or None")
        return cls(
            version,
            parent_version,
            _exact_non_empty_string(state["actor_agent_id"], "architecture revision actor"),
            _exact_non_empty_string(state["reason"], "architecture revision reason"),
            _canonical_string_list(
                state["evidence_refs"],
                "architecture revision evidence reference",
            ),
            _canonical_string_list(
                state["changed_refs"],
                "architecture revision changed reference",
            ),
            _exact_non_empty_string(state["graph_digest"], "architecture revision graph digest"),
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
        actor = _exact_non_empty_string(actor_agent_id, "architecture revision actor")
        reason_value = _exact_non_empty_string(reason, "architecture revision reason").strip()
        evidence = tuple(
            value.strip()
            for value in _exact_string_sequence(evidence_refs, "architecture revision evidence reference")
        )
        if not evidence or (not upsert_components and not upsert_interfaces and not upsert_edges):
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
            actor,
            reason_value,
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
        state = _canonical_state_record(
            state,
            ("components", "interfaces", "edges", "revisions"),
            "architecture graph",
        )
        graph = cls()
        component_rows = _canonical_state_list(
            state["components"],
            "architecture graph components",
        )
        interface_rows = _canonical_state_list(
            state["interfaces"],
            "architecture graph interfaces",
        )
        edge_rows = _canonical_state_list(
            state["edges"],
            "architecture graph edges",
        )
        revision_rows = _canonical_state_list(
            state["revisions"],
            "architecture graph revisions",
        )

        components = tuple(ArchitectureComponent.from_state(v) for v in component_rows)
        component_ids: set[str] = set()
        for component in components:
            if component.component_id in component_ids:
                raise ValueError(f"duplicate architecture component: {component.component_id}")
            component_ids.add(component.component_id)
        component_order = [component.component_id for component in components]
        if component_order != sorted(component_order):
            raise ValueError("architecture components must use canonical serialized state order")

        interfaces = tuple(InterfaceContract.from_state(v) for v in interface_rows)
        interface_ids: set[str] = set()
        for interface in interfaces:
            if interface.interface_id in interface_ids:
                raise ValueError(f"duplicate architecture interface: {interface.interface_id}")
            interface_ids.add(interface.interface_id)
        interface_order = [interface.interface_id for interface in interfaces]
        if interface_order != sorted(interface_order):
            raise ValueError("architecture interfaces must use canonical serialized state order")

        edges = tuple(ArchitectureEdge.from_state(v) for v in edge_rows)
        edge_ids: set[str] = set()
        for edge in edges:
            if edge.edge_id in edge_ids:
                raise ValueError(f"duplicate architecture edge: {edge.edge_id}")
            edge_ids.add(edge.edge_id)
        edge_order = [edge.edge_id for edge in edges]
        if edge_order != sorted(edge_order):
            raise ValueError("architecture edges must use canonical serialized state order")

        graph._components = {component.component_id: component for component in components}
        graph._interfaces = {interface.interface_id: interface for interface in interfaces}
        graph._edges = {edge.edge_id: edge for edge in edges}
        graph._validate(graph._components, graph._interfaces, graph._edges)
        graph._revisions = [ArchitectureRevision.from_state(v) for v in revision_rows]
        for index, revision in enumerate(graph._revisions, 1):
            if revision.version != index:
                raise ValueError("non-canonical architecture revision sequence")
            expected_parent = None if index == 1 else index - 1
            if revision.parent_version != expected_parent:
                raise ValueError("architecture parent lineage is not canonical")
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
        state = _canonical_state_record(
            state,
            ("graph",),
            "architecture control plane",
        )
        graph = ArchitectureGraph.from_state(state["graph"])
        if hasattr(ledger, "events_since"):
            events = ledger.events_since(None)
        else:
            events = tuple(getattr(ledger, "events", ()))

        change_events: dict[int, tuple[str, object, tuple[str, ...], tuple[str, ...]]] = {}
        for event in events:
            if isinstance(event, Mapping):
                target_agent_id = event.get("target_agent_id")
                region = event.get("region")
                payload = event.get("payload", {})
                source_agent_id = event.get("source_agent_id")
                evidence_refs = tuple(event.get("evidence_refs", ()))
                object_refs = tuple(event.get("object_refs", ()))
            else:
                target_agent_id = event.target_agent_id
                region = event.region
                payload = event.payload
                source_agent_id = event.source_agent_id
                evidence_refs = tuple(event.evidence_refs)
                object_refs = tuple(event.object_refs)
            if target_agent_id != "architecture.chief" or region != "architecture-system":
                continue
            if not isinstance(payload, Mapping) or payload.get("architecture_action") != "changed":
                continue
            version = payload.get("version")
            if type(version) is not int or version <= 0 or version in change_events:
                raise ValueError("architecture change provenance mismatch")
            change_events[version] = (
                _exact_non_empty_string(source_agent_id, "architecture provenance source actor"),
                payload.get("reason"),
                evidence_refs,
                object_refs,
            )

        expected_versions: set[int] = set()
        for revision in graph._revisions:
            expected_versions.add(revision.version)
            matched = change_events.get(revision.version)
            if matched is None:
                raise ValueError("architecture change provenance mismatch")
            source_agent_id, reason, evidence_refs, object_refs = matched
            if (
                source_agent_id != revision.actor_agent_id
                or reason != revision.reason
                or evidence_refs != revision.evidence_refs
                or object_refs != revision.changed_refs
            ):
                raise ValueError("architecture change provenance mismatch")
        if set(change_events) != expected_versions:
            raise ValueError("architecture change provenance mismatch")

        return cls(
            registry=registry,
            authority=authority,
            ledger=ledger,
            graph=graph,
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
