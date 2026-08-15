from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class RepoNode:
    node_id: str
    kind: str
    path: str = ''

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError('node_id must be non-empty')
        if not self.kind:
            raise ValueError('kind must be non-empty')


@dataclass(frozen=True, slots=True)
class RepoEdge:
    source: str
    target: str
    kind: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.source or not self.target:
            raise ValueError('edge endpoints must be non-empty')
        if not self.kind:
            raise ValueError('edge kind must be non-empty')
        if self.weight <= 0.0:
            raise ValueError('edge weight must be positive')


class RepoWorldGraph:
    """Language-agnostic repository topology used by the R2.8 cognition layer.

    Edges point from a dependent/observer toward the dependency it consumes.
    For example ``api -> service`` with kind ``depends_on`` means editing
    ``service`` can impact ``api``. ``test -> api`` means the test observes api.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, RepoNode] = {}
        self._outgoing: dict[str, list[RepoEdge]] = defaultdict(list)
        self._incoming: dict[str, list[RepoEdge]] = defaultdict(list)

    @property
    def nodes(self) -> tuple[RepoNode, ...]:
        return tuple(self._nodes.values())

    def add_node(self, node: RepoNode) -> None:
        existing = self._nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise ValueError(f'node id already bound to different record: {node.node_id}')
        self._nodes[node.node_id] = node

    def add_edge(self, edge: RepoEdge) -> None:
        if edge.source not in self._nodes or edge.target not in self._nodes:
            raise KeyError('both edge endpoints must exist before add_edge')
        if edge not in self._outgoing[edge.source]:
            self._outgoing[edge.source].append(edge)
            self._incoming[edge.target].append(edge)

    def get_node(self, node_id: str) -> RepoNode:
        return self._nodes[node_id]

    def neighbors(
        self,
        node_id: str,
        *,
        direction: str = 'outgoing',
        kinds: Iterable[str] | None = None,
    ) -> set[str]:
        if node_id not in self._nodes:
            raise KeyError(node_id)
        allowed = None if kinds is None else set(kinds)
        if direction == 'outgoing':
            edges = self._outgoing.get(node_id, ())
            return {edge.target for edge in edges if allowed is None or edge.kind in allowed}
        if direction == 'incoming':
            edges = self._incoming.get(node_id, ())
            return {edge.source for edge in edges if allowed is None or edge.kind in allowed}
        raise ValueError("direction must be 'outgoing' or 'incoming'")

    def impact_closure(
        self,
        edited_nodes: Iterable[str],
        *,
        edge_kinds: Iterable[str] = ('depends_on', 'imports', 'calls', 'tests', 'contains'),
        max_depth: int = 64,
    ) -> set[str]:
        seeds = set(edited_nodes)
        missing = seeds.difference(self._nodes)
        if missing:
            raise KeyError(f'unknown edited nodes: {sorted(missing)}')
        if max_depth < 0:
            raise ValueError('max_depth must be non-negative')
        allowed = set(edge_kinds)
        impacted = set(seeds)
        queue = deque((node_id, 0) for node_id in seeds)
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in self._incoming.get(current, ()):
                if edge.kind not in allowed or edge.source in impacted:
                    continue
                impacted.add(edge.source)
                queue.append((edge.source, depth + 1))
        return impacted

    def edit_risk(self, edited_nodes: Iterable[str]) -> float:
        if not self._nodes:
            return 0.0
        return len(self.impact_closure(edited_nodes)) / len(self._nodes)
