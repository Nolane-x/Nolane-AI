from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .architecture import ArchitectureGraph, EdgeKind
from .types import canonical_digest


@dataclass(frozen=True, slots=True)
class ImpactPacket:
    changed_components: tuple[str, ...]
    changed_interfaces: tuple[str, ...]
    transitive_dependents: tuple[str, ...]
    requirement_refs: tuple[str, ...]
    plan_refs: tuple[str, ...]
    required_verification_classes: tuple[str, ...]
    severity: int
    digest: str


class ChangeImpactEngine:
    def __init__(self, graph: ArchitectureGraph) -> None:
        self.graph = graph

    def compute(self, *, changed_components: tuple[str, ...] = (), changed_interfaces: tuple[str, ...] = ()) -> ImpactPacket:
        components = set(str(x) for x in changed_components)
        interfaces = set(str(x) for x in changed_interfaces)
        for interface_id in interfaces:
            interface = self.graph.get_interface(interface_id)
            components.add(interface.producer_component_id)
        for component_id in components:
            self.graph.get_component(component_id)

        reverse: dict[str, set[str]] = {x.component_id: set() for x in self.graph.components()}
        for edge in self.graph.edges():
            if edge.kind is EdgeKind.DEPENDS_ON:
                reverse[edge.target_component_id].add(edge.source_component_id)
        frontier = list(sorted(components))
        dependents: set[str] = set()
        while frontier:
            current = frontier.pop(0)
            for nxt in sorted(reverse.get(current, ())):
                if nxt not in components and nxt not in dependents:
                    dependents.add(nxt); frontier.append(nxt)

        affected = components | dependents
        reqs: set[str] = set()
        plans: set[str] = set()
        for component_id in affected:
            row = self.graph.get_component(component_id)
            reqs.update(row.requirement_refs)
            plans.update(row.plan_refs)
        verification = {'integration'}
        if interfaces:
            verification.update({'contract', 'compatibility'})
        if any(self.graph.get_interface(i).stability.value == 'public' for i in interfaces):
            verification.add('public-api')
        severity = min(100, 20 + 15 * len(dependents) + 20 * len(interfaces))
        payload: dict[str, Any] = {
            'changed_components': sorted(components), 'changed_interfaces': sorted(interfaces),
            'transitive_dependents': sorted(dependents), 'requirement_refs': sorted(reqs),
            'plan_refs': sorted(plans), 'required_verification_classes': sorted(verification),
            'severity': severity,
        }
        return ImpactPacket(
            tuple(payload['changed_components']), tuple(payload['changed_interfaces']),
            tuple(payload['transitive_dependents']), tuple(payload['requirement_refs']),
            tuple(payload['plan_refs']), tuple(payload['required_verification_classes']),
            severity, canonical_digest(payload),
        )
