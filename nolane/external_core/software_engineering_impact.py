from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.software_engineering.impact"
COMPONENT_VERSION = "0.5.0"
CANONICAL_WRITE_AUTHORITY = False


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


def _node(value: Any) -> str:
    return _text(value, field="dependency node")


def _edge(value: Sequence[Any]) -> tuple[str, str]:
    if len(value) != 2:
        raise ValueError("dependency edge must contain exactly two nodes")
    return (_node(value[0]), _node(value[1]))


def _membership_pairs(value: Mapping[Any, Any] | Sequence[Sequence[Any]]) -> tuple[tuple[str, str], ...]:
    items = value.items() if isinstance(value, Mapping) else value
    normalized = {(_node(node), _text(component, field="component ref")) for node, component in items}
    return tuple(sorted(normalized))


def _coverage_pairs(value: Mapping[Any, Sequence[Any]] | Sequence[Mapping[str, Any]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if isinstance(value, Mapping):
        items = value.items()
    else:
        items = ((entry["test_ref"], entry.get("nodes", ())) for entry in value)
    normalized: dict[str, tuple[str, ...]] = {}
    for test_ref, nodes in items:
        test = _text(test_ref, field="test ref")
        covered = _refs(tuple(nodes))
        if not covered:
            raise ValueError(f"test coverage must name nodes: {test}")
        old = normalized.get(test)
        if old is not None and old != covered:
            raise ValueError(f"test coverage cannot rebind test ref: {test}")
        normalized[test] = covered
    if not normalized:
        raise ValueError("engineering test coverage cannot be empty")
    return tuple((test, normalized[test]) for test in sorted(normalized))


@dataclass(frozen=True, slots=True)
class EngineeringDependencyGraph:
    graph_id: str
    source_revision: str
    nodes: tuple[str, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    component_membership: tuple[tuple[str, str], ...]
    provenance_refs: tuple[str, ...]
    digest: str

    def __post_init__(self) -> None:
        _text(self.graph_id, field="dependency graph id")
        _text(self.source_revision, field="source revision")
        _text(self.digest, field="dependency graph digest")
        if not self.nodes:
            raise ValueError("engineering dependency graph requires nodes")
        if not self.provenance_refs:
            raise ValueError("engineering dependency graph requires provenance refs")
        node_set = set(self.nodes)
        for source, dependent in self.dependency_edges:
            if source not in node_set or dependent not in node_set:
                raise ValueError("dependency edge endpoint is not represented in graph")
        for node, _ in self.component_membership:
            if node not in node_set:
                raise ValueError("component membership node is not represented in graph")

    def payload(self) -> dict[str, Any]:
        return {
            "source_revision": self.source_revision,
            "nodes": list(self.nodes),
            "dependency_edges": [list(edge) for edge in self.dependency_edges],
            "component_membership": [
                {"node": node, "component_ref": component}
                for node, component in self.component_membership
            ],
            "provenance_refs": list(self.provenance_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {"graph_id": self.graph_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringDependencyGraph":
        row = cls(
            graph_id=_text(state["graph_id"], field="dependency graph id"),
            source_revision=_text(state["source_revision"], field="source revision"),
            nodes=_refs(tuple(state.get("nodes", ()))),
            dependency_edges=tuple(sorted({_edge(tuple(value)) for value in state.get("dependency_edges", ())})),
            component_membership=_membership_pairs(tuple(
                (entry["node"], entry["component_ref"])
                for entry in state.get("component_membership", ())
            )),
            provenance_refs=_refs(tuple(state.get("provenance_refs", ()))),
            digest=_text(state["digest"], field="dependency graph digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.graph_id != f"eng-depgraph-{expected[:20]}":
            raise ValueError("engineering dependency graph digest/id mismatch")
        return row

    def component_for(self, node: str) -> str | None:
        for candidate, component in self.component_membership:
            if candidate == node:
                return component
        return None


class EngineeringDependencyGraphLedger:
    def __init__(self) -> None:
        self._graphs: dict[str, EngineeringDependencyGraph] = {}

    def graphs(self) -> tuple[EngineeringDependencyGraph, ...]:
        return tuple(self._graphs[key] for key in sorted(self._graphs))

    def get(self, graph_id: str) -> EngineeringDependencyGraph:
        try:
            return self._graphs[str(graph_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering dependency graph: {graph_id}") from exc

    def register(
        self,
        *,
        source_revision: str,
        nodes: tuple[str, ...],
        dependency_edges: tuple[tuple[str, str], ...],
        component_membership: Mapping[str, str] | Sequence[Sequence[str]],
        provenance_refs: tuple[str, ...],
    ) -> EngineeringDependencyGraph:
        normalized_nodes = _refs(nodes)
        normalized_edges = tuple(sorted({_edge(edge) for edge in dependency_edges}))
        membership = _membership_pairs(component_membership)
        provenance = _refs(provenance_refs)
        payload = {
            "source_revision": _text(source_revision, field="source revision"),
            "nodes": list(normalized_nodes),
            "dependency_edges": [list(edge) for edge in normalized_edges],
            "component_membership": [
                {"node": node, "component_ref": component}
                for node, component in membership
            ],
            "provenance_refs": list(provenance),
        }
        digest = canonical_digest(payload)
        row = EngineeringDependencyGraph(
            graph_id=f"eng-depgraph-{digest[:20]}",
            source_revision=payload["source_revision"],
            nodes=normalized_nodes,
            dependency_edges=normalized_edges,
            component_membership=membership,
            provenance_refs=provenance,
            digest=digest,
        )
        existing = self._graphs.get(row.graph_id)
        if existing is not None and existing != row:
            raise ValueError("engineering dependency graph id cannot be rebound")
        self._graphs[row.graph_id] = row
        return existing or row

    def to_state(self) -> dict[str, Any]:
        return {"graphs": [row.to_state() for row in self.graphs()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringDependencyGraphLedger":
        ledger = cls()
        for value in state.get("graphs", ()):
            row = EngineeringDependencyGraph.from_state(value)
            existing = ledger._graphs.get(row.graph_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound engineering dependency graph")
            ledger._graphs[row.graph_id] = row
        return ledger


@dataclass(frozen=True, slots=True)
class EngineeringImpactReceipt:
    impact_id: str
    patch_ref: str
    patch_digest: str
    source_revision: str
    graph_id: str
    graph_digest: str
    direct_nodes: tuple[str, ...]
    impacted_nodes: tuple[str, ...]
    impacted_component_refs: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        if self.authority != "evidence_only":
            raise ValueError("engineering impact receipt cannot hold mutation/promotion authority")
        if not self.direct_nodes:
            raise ValueError("engineering impact receipt requires direct nodes")
        if not set(self.direct_nodes).issubset(set(self.impacted_nodes)):
            raise ValueError("engineering impact direct nodes must be impacted")

    def payload(self) -> dict[str, Any]:
        return {
            "patch_ref": self.patch_ref,
            "patch_digest": self.patch_digest,
            "source_revision": self.source_revision,
            "graph_id": self.graph_id,
            "graph_digest": self.graph_digest,
            "direct_nodes": list(self.direct_nodes),
            "impacted_nodes": list(self.impacted_nodes),
            "impacted_component_refs": list(self.impacted_component_refs),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"impact_id": self.impact_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringImpactReceipt":
        row = cls(
            impact_id=_text(state["impact_id"], field="impact id"),
            patch_ref=_text(state["patch_ref"], field="patch ref"),
            patch_digest=_text(state["patch_digest"], field="patch digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            graph_id=_text(state["graph_id"], field="dependency graph id"),
            graph_digest=_text(state["graph_digest"], field="dependency graph digest"),
            direct_nodes=_refs(tuple(state.get("direct_nodes", ()))),
            impacted_nodes=_refs(tuple(state.get("impacted_nodes", ()))),
            impacted_component_refs=_refs(tuple(state.get("impacted_component_refs", ()))),
            authority=_text(state["authority"], field="impact authority"),
            digest=_text(state["digest"], field="impact digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.impact_id != f"eng-impact-{expected[:20]}":
            raise ValueError("engineering impact receipt digest/id mismatch")
        return row


class EngineeringImpactAnalyzer:
    @staticmethod
    def _seed_nodes(patch: Any, graph: EngineeringDependencyGraph) -> tuple[str, ...]:
        symbols = tuple(str(value).strip() for value in getattr(patch, "touched_symbols", ()) if str(value).strip())
        files = tuple(str(value).replace("\\", "/").strip() for value in getattr(patch, "touched_files", ()) if str(value).strip())
        requested = tuple(f"symbol:{value}" for value in symbols) if symbols else tuple(f"file:{value}" for value in files)
        if not requested:
            raise ValueError("impact analysis requires touched patch scope")
        missing = tuple(sorted(node for node in requested if node not in set(graph.nodes)))
        if missing:
            raise ValueError("patch scope is not represented in dependency graph: " + ", ".join(missing))
        return tuple(sorted(set(requested)))

    def analyze(self, *, patch: Any, graph: EngineeringDependencyGraph) -> EngineeringImpactReceipt:
        if not hasattr(patch, "to_state"):
            raise TypeError("impact analysis requires canonical patch state")
        patch_ref = _text(getattr(patch, "patch_id"), field="patch id")
        patch_digest = canonical_digest(patch.to_state())
        direct = self._seed_nodes(patch, graph)

        adjacency: dict[str, set[str]] = {node: set() for node in graph.nodes}
        for source, dependent in graph.dependency_edges:
            adjacency[source].add(dependent)
        impacted: set[str] = set()
        frontier = list(reversed(direct))
        while frontier:
            node = frontier.pop()
            if node in impacted:
                continue
            impacted.add(node)
            for dependent in sorted(adjacency.get(node, ())):
                if dependent not in impacted:
                    frontier.append(dependent)

        components = {
            component
            for node, component in graph.component_membership
            if node in impacted
        }
        payload = {
            "patch_ref": patch_ref,
            "patch_digest": patch_digest,
            "source_revision": graph.source_revision,
            "graph_id": graph.graph_id,
            "graph_digest": graph.digest,
            "direct_nodes": list(direct),
            "impacted_nodes": list(sorted(impacted)),
            "impacted_component_refs": list(sorted(components)),
            "authority": "evidence_only",
        }
        digest = canonical_digest(payload)
        return EngineeringImpactReceipt(
            impact_id=f"eng-impact-{digest[:20]}",
            patch_ref=patch_ref,
            patch_digest=patch_digest,
            source_revision=graph.source_revision,
            graph_id=graph.graph_id,
            graph_digest=graph.digest,
            direct_nodes=direct,
            impacted_nodes=tuple(payload["impacted_nodes"]),
            impacted_component_refs=tuple(payload["impacted_component_refs"]),
            authority="evidence_only",
            digest=digest,
        )


@dataclass(frozen=True, slots=True)
class EngineeringTestCoverage:
    coverage_id: str
    source_revision: str
    graph_id: str
    graph_digest: str
    test_to_nodes: tuple[tuple[str, tuple[str, ...]], ...]
    provenance_refs: tuple[str, ...]
    digest: str

    def __post_init__(self) -> None:
        if not self.test_to_nodes:
            raise ValueError("engineering test coverage cannot be empty")
        if not self.provenance_refs:
            raise ValueError("engineering test coverage requires provenance refs")

    def payload(self) -> dict[str, Any]:
        return {
            "source_revision": self.source_revision,
            "graph_id": self.graph_id,
            "graph_digest": self.graph_digest,
            "test_to_nodes": [
                {"test_ref": test_ref, "nodes": list(nodes)}
                for test_ref, nodes in self.test_to_nodes
            ],
            "provenance_refs": list(self.provenance_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {"coverage_id": self.coverage_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringTestCoverage":
        row = cls(
            coverage_id=_text(state["coverage_id"], field="test coverage id"),
            source_revision=_text(state["source_revision"], field="source revision"),
            graph_id=_text(state["graph_id"], field="dependency graph id"),
            graph_digest=_text(state["graph_digest"], field="dependency graph digest"),
            test_to_nodes=_coverage_pairs(tuple(state.get("test_to_nodes", ()))),
            provenance_refs=_refs(tuple(state.get("provenance_refs", ()))),
            digest=_text(state["digest"], field="test coverage digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.coverage_id != f"eng-coverage-{expected[:20]}":
            raise ValueError("engineering test coverage digest/id mismatch")
        return row

    def mapping(self) -> dict[str, tuple[str, ...]]:
        return dict(self.test_to_nodes)


class EngineeringTestCoverageLedger:
    def __init__(self) -> None:
        self._rows: dict[str, EngineeringTestCoverage] = {}

    def rows(self) -> tuple[EngineeringTestCoverage, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def get(self, coverage_id: str) -> EngineeringTestCoverage:
        try:
            return self._rows[str(coverage_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering test coverage: {coverage_id}") from exc

    def register(
        self,
        *,
        source_revision: str,
        graph_id: str,
        graph_digest: str,
        test_to_nodes: Mapping[str, Sequence[str]] | Sequence[Mapping[str, Any]],
        provenance_refs: tuple[str, ...],
    ) -> EngineeringTestCoverage:
        mapping = _coverage_pairs(test_to_nodes)
        provenance = _refs(provenance_refs)
        payload = {
            "source_revision": _text(source_revision, field="source revision"),
            "graph_id": _text(graph_id, field="dependency graph id"),
            "graph_digest": _text(graph_digest, field="dependency graph digest"),
            "test_to_nodes": [
                {"test_ref": test_ref, "nodes": list(nodes)}
                for test_ref, nodes in mapping
            ],
            "provenance_refs": list(provenance),
        }
        digest = canonical_digest(payload)
        row = EngineeringTestCoverage(
            coverage_id=f"eng-coverage-{digest[:20]}",
            source_revision=payload["source_revision"],
            graph_id=payload["graph_id"],
            graph_digest=payload["graph_digest"],
            test_to_nodes=mapping,
            provenance_refs=provenance,
            digest=digest,
        )
        existing = self._rows.get(row.coverage_id)
        if existing is not None and existing != row:
            raise ValueError("engineering test coverage id cannot be rebound")
        self._rows[row.coverage_id] = row
        return existing or row

    def to_state(self) -> dict[str, Any]:
        return {"coverage": [row.to_state() for row in self.rows()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringTestCoverageLedger":
        ledger = cls()
        for value in state.get("coverage", ()):
            row = EngineeringTestCoverage.from_state(value)
            existing = ledger._rows.get(row.coverage_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound engineering test coverage")
            ledger._rows[row.coverage_id] = row
        return ledger


@dataclass(frozen=True, slots=True)
class EngineeringTestSelectionProof:
    selection_id: str
    impact_id: str
    impact_digest: str
    coverage_id: str
    coverage_digest: str
    source_revision: str
    selected_tests: tuple[str, ...]
    covered_nodes: tuple[str, ...]
    uncovered_nodes: tuple[str, ...]
    coverage_ppm: int
    complete: bool
    authority: str
    digest: str

    def __post_init__(self) -> None:
        if self.authority != "evidence_only":
            raise ValueError("test selection proof cannot hold mutation/promotion authority")
        if not 0 <= self.coverage_ppm <= 1_000_000:
            raise ValueError("test selection coverage_ppm outside range")
        if set(self.covered_nodes) & set(self.uncovered_nodes):
            raise ValueError("test selection covered/uncovered nodes overlap")
        if self.complete != (not self.uncovered_nodes):
            raise ValueError("test selection completeness contradicts uncovered nodes")

    def payload(self) -> dict[str, Any]:
        return {
            "impact_id": self.impact_id,
            "impact_digest": self.impact_digest,
            "coverage_id": self.coverage_id,
            "coverage_digest": self.coverage_digest,
            "source_revision": self.source_revision,
            "selected_tests": list(self.selected_tests),
            "covered_nodes": list(self.covered_nodes),
            "uncovered_nodes": list(self.uncovered_nodes),
            "coverage_ppm": self.coverage_ppm,
            "complete": self.complete,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"selection_id": self.selection_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringTestSelectionProof":
        selected = tuple(_text(value, field="selected test") for value in state.get("selected_tests", ()))
        if len(selected) != len(set(selected)):
            raise ValueError("test selection contains duplicate tests")
        row = cls(
            selection_id=_text(state["selection_id"], field="test selection id"),
            impact_id=_text(state["impact_id"], field="impact id"),
            impact_digest=_text(state["impact_digest"], field="impact digest"),
            coverage_id=_text(state["coverage_id"], field="coverage id"),
            coverage_digest=_text(state["coverage_digest"], field="coverage digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            selected_tests=selected,
            covered_nodes=_refs(tuple(state.get("covered_nodes", ()))),
            uncovered_nodes=_refs(tuple(state.get("uncovered_nodes", ()))),
            coverage_ppm=int(state["coverage_ppm"]),
            complete=bool(state["complete"]),
            authority=_text(state["authority"], field="test selection authority"),
            digest=_text(state["digest"], field="test selection digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.selection_id != f"eng-test-selection-{expected[:20]}":
            raise ValueError("engineering test selection digest/id mismatch")
        return row


class EngineeringTestSelectionEngine:
    def select(
        self,
        *,
        impact: EngineeringImpactReceipt,
        coverage: EngineeringTestCoverage,
    ) -> EngineeringTestSelectionProof:
        if coverage.source_revision != impact.source_revision:
            raise ValueError("test coverage source revision does not match impact source revision")
        if coverage.graph_id != impact.graph_id or coverage.graph_digest != impact.graph_digest:
            raise ValueError("test coverage dependency graph lineage mismatch")

        impacted = set(impact.impacted_nodes)
        mapping = {
            test_ref: set(nodes) & impacted
            for test_ref, nodes in coverage.test_to_nodes
        }
        mapping = {test_ref: nodes for test_ref, nodes in mapping.items() if nodes}
        uncovered = set(impacted)
        selected: list[str] = []
        covered: set[str] = set()

        while uncovered:
            ranked = sorted(
                (
                    (-len(nodes & uncovered), test_ref, nodes & uncovered)
                    for test_ref, nodes in mapping.items()
                    if nodes & uncovered and test_ref not in selected
                ),
                key=lambda row: (row[0], row[1]),
            )
            if not ranked:
                break
            _, test_ref, newly_covered = ranked[0]
            selected.append(test_ref)
            covered.update(newly_covered)
            uncovered.difference_update(newly_covered)

        denominator = len(impacted)
        coverage_ppm = 1_000_000 if denominator == 0 else (len(covered) * 1_000_000) // denominator
        payload = {
            "impact_id": impact.impact_id,
            "impact_digest": impact.digest,
            "coverage_id": coverage.coverage_id,
            "coverage_digest": coverage.digest,
            "source_revision": impact.source_revision,
            "selected_tests": list(selected),
            "covered_nodes": list(sorted(covered)),
            "uncovered_nodes": list(sorted(uncovered)),
            "coverage_ppm": coverage_ppm,
            "complete": not uncovered,
            "authority": "evidence_only",
        }
        digest = canonical_digest(payload)
        return EngineeringTestSelectionProof(
            selection_id=f"eng-test-selection-{digest[:20]}",
            impact_id=impact.impact_id,
            impact_digest=impact.digest,
            coverage_id=coverage.coverage_id,
            coverage_digest=coverage.digest,
            source_revision=impact.source_revision,
            selected_tests=tuple(selected),
            covered_nodes=tuple(payload["covered_nodes"]),
            uncovered_nodes=tuple(payload["uncovered_nodes"]),
            coverage_ppm=coverage_ppm,
            complete=not uncovered,
            authority="evidence_only",
            digest=digest,
        )


__all__ = (
    "EngineeringDependencyGraph",
    "EngineeringDependencyGraphLedger",
    "EngineeringImpactReceipt",
    "EngineeringImpactAnalyzer",
    "EngineeringTestCoverage",
    "EngineeringTestCoverageLedger",
    "EngineeringTestSelectionProof",
    "EngineeringTestSelectionEngine",
)
