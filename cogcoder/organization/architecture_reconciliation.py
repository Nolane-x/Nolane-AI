from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .architecture import ArchitectureGraph, EdgeKind
from .types import canonical_digest


class ArchitectureDriftClass(str, Enum):
    UNDECLARED_COMPONENT = 'undeclared_component'
    MISSING_COMPONENT = 'missing_component'
    UNDECLARED_DEPENDENCY = 'undeclared_dependency'
    FORBIDDEN_DEPENDENCY = 'forbidden_dependency'
    INTERFACE_SIGNATURE_DRIFT = 'interface_signature_drift'
    TRUST_BOUNDARY_DRIFT = 'trust_boundary_drift'
    STALE_ARCHITECTURE_REF = 'stale_architecture_ref'


@dataclass(frozen=True, slots=True)
class ArchitectureObservation:
    observed_component_ids: tuple[str, ...]
    observed_dependency_pairs: tuple[tuple[str, str], ...]
    interface_signature_digests: tuple[tuple[str, str], ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArchitectureFinding:
    finding_id: str
    drift_class: ArchitectureDriftClass
    object_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    summary: str
    digest: str


class ArchitectureReconciler:
    def __init__(self, graph: ArchitectureGraph) -> None:
        self.graph = graph

    def scan(self, observation: ArchitectureObservation) -> tuple[ArchitectureFinding, ...]:
        declared_components = {x.component_id for x in self.graph.components()}
        observed_components = set(observation.observed_component_ids)
        rows: list[tuple[ArchitectureDriftClass, tuple[str, ...], str]] = []

        for component_id in sorted(observed_components - declared_components):
            rows.append((ArchitectureDriftClass.UNDECLARED_COMPONENT, (component_id,), 'observed component is not declared'))
        for component_id in sorted(declared_components - observed_components):
            rows.append((ArchitectureDriftClass.MISSING_COMPONENT, (component_id,), 'declared component was not observed'))

        declared_dependencies = {
            (edge.source_component_id, edge.target_component_id)
            for edge in self.graph.edges() if edge.kind is EdgeKind.DEPENDS_ON
        }
        for pair in sorted(set(observation.observed_dependency_pairs) - declared_dependencies):
            rows.append((ArchitectureDriftClass.UNDECLARED_DEPENDENCY, tuple(pair), 'observed dependency is not declared'))

        observed_signatures = dict(observation.interface_signature_digests)
        for interface in self.graph.interfaces():
            if interface.interface_id in observed_signatures and observed_signatures[interface.interface_id] != interface.signature_digest:
                rows.append((ArchitectureDriftClass.INTERFACE_SIGNATURE_DRIFT, (interface.interface_id,), 'observed interface signature differs from authority'))

        findings: list[ArchitectureFinding] = []
        for index, (drift_class, refs, summary) in enumerate(sorted(rows, key=lambda x: (x[0].value, x[1])), 1):
            payload = {
                'drift_class': drift_class.value, 'object_refs': list(refs),
                'source_refs': list(observation.source_refs), 'summary': summary,
            }
            findings.append(ArchitectureFinding(
                f'arch-drift-{index:08d}', drift_class, refs,
                tuple(observation.source_refs), summary, canonical_digest(payload),
            ))
        return tuple(findings)
