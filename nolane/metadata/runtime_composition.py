from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest

from .manifests import build_component_manifests
from .runtime_state_map import build_runtime_state_bindings


@dataclass(frozen=True, slots=True)
class SemanticRuntimeNode:
    """One independently versioned semantic runtime component.

    Historical runtime inheritance names are deliberately absent. State
    ownership is projected from ``RuntimeStateBinding`` so this graph cannot
    silently invent a second serialization ontology.
    """

    component_id: str
    component_version: str
    domain: str
    semantic_contract: str
    dependencies: tuple[str, ...]
    state_sections: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(str(value).strip() for value in (
            self.component_id,
            self.component_version,
            self.domain,
            self.semantic_contract,
        )):
            raise ValueError("semantic runtime node requires id/version/domain/contract")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError(f"duplicate semantic dependencies for {self.component_id}")
        if len(set(self.state_sections)) != len(self.state_sections):
            raise ValueError(f"duplicate state-section ownership inside {self.component_id}")
        if self.component_id in self.dependencies:
            raise ValueError("semantic runtime node cannot depend on itself")

    def to_state(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_version": self.component_version,
            "domain": self.domain,
            "semantic_contract": self.semantic_contract,
            "dependencies": list(self.dependencies),
            "state_sections": list(self.state_sections),
        }


@dataclass(frozen=True, slots=True)
class SemanticRuntimeComposition:
    """Canonical semantic DAG replacing historical runtime-Part composition.

    The graph covers all declared components while ``section_owners`` is the
    exact reversible ownership projection of the accepted serialized runtime.
    This object describes architecture; it does not grant legacy write access.
    """

    nodes: tuple[SemanticRuntimeNode, ...]
    section_owners: Mapping[str, str]
    expected_state_sections: tuple[str, ...]
    digest: str

    def __post_init__(self) -> None:
        component_ids = [row.component_id for row in self.nodes]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("semantic runtime composition contains duplicate components")
        if not component_ids:
            raise ValueError("semantic runtime composition cannot be empty")
        if self.unresolved_dependencies():
            raise ValueError(
                f"semantic runtime composition has unresolved dependencies: {self.unresolved_dependencies()}"
            )
        if self.unowned_state_sections:
            raise ValueError(
                f"semantic runtime composition has unowned state sections: {self.unowned_state_sections}"
            )
        if self.duplicate_state_sections:
            raise ValueError(
                f"semantic runtime composition has duplicate state owners: {self.duplicate_state_sections}"
            )
        if set(self.section_owners.values()) - set(component_ids):
            raise ValueError("runtime state section references undeclared semantic component")
        self.topological_order()
        if canonical_digest(self.payload()) != self.digest:
            raise ValueError("semantic runtime composition digest mismatch")

    @property
    def lossless(self) -> bool:
        return not self.unowned_state_sections and not self.duplicate_state_sections

    @property
    def unowned_state_sections(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.expected_state_sections) - set(self.section_owners)))

    @property
    def duplicate_state_sections(self) -> tuple[str, ...]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for row in self.nodes:
            for section in row.state_sections:
                if section in seen:
                    duplicates.add(section)
                seen.add(section)
        return tuple(sorted(duplicates))

    def owned_state_sections(self) -> tuple[str, ...]:
        return tuple(sorted(self.section_owners))

    def unresolved_dependencies(self) -> tuple[str, ...]:
        known = {row.component_id for row in self.nodes}
        missing = {
            dependency
            for row in self.nodes
            for dependency in row.dependencies
            if dependency not in known
        }
        return tuple(sorted(missing))

    def topological_order(self) -> tuple[str, ...]:
        remaining = {
            row.component_id: set(row.dependencies)
            for row in self.nodes
        }
        ready = sorted(component_id for component_id, deps in remaining.items() if not deps)
        ordered: list[str] = []

        while ready:
            component_id = ready.pop(0)
            if component_id in ordered:
                continue
            ordered.append(component_id)
            for other in sorted(remaining):
                if component_id in remaining[other]:
                    remaining[other].remove(component_id)
                    if not remaining[other] and other not in ordered and other not in ready:
                        ready.append(other)
                        ready.sort()

        if len(ordered) != len(remaining):
            cycle = tuple(sorted(set(remaining) - set(ordered)))
            raise ValueError(f"semantic runtime dependency cycle detected: {cycle}")
        return tuple(ordered)

    def payload(self) -> dict[str, Any]:
        return {
            "nodes": [row.to_state() for row in self.nodes],
            "section_owners": dict(sorted(self.section_owners.items())),
            "expected_state_sections": list(self.expected_state_sections),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}


def build_semantic_runtime_composition() -> SemanticRuntimeComposition:
    manifests = build_component_manifests()
    bindings = build_runtime_state_bindings()

    section_owners: dict[str, str] = {}
    owner_sections: dict[str, list[str]] = {}
    for binding in bindings:
        if binding.legacy_section in section_owners:
            raise ValueError(f"duplicate runtime state binding: {binding.legacy_section}")
        section_owners[binding.legacy_section] = binding.canonical_owner
        owner_sections.setdefault(binding.canonical_owner, []).append(binding.legacy_section)

    declared = {row.component_id for row in manifests}
    unknown_owners = tuple(sorted(set(owner_sections) - declared))
    if unknown_owners:
        raise ValueError(f"runtime state owners are not declared components: {unknown_owners}")

    nodes = tuple(
        SemanticRuntimeNode(
            component_id=row.component_id,
            component_version=str(row.version),
            domain=row.layer,
            semantic_contract=row.responsibility,
            dependencies=row.dependencies,
            state_sections=tuple(sorted(owner_sections.get(row.component_id, ()))),
        )
        for row in manifests
    )
    expected = tuple(sorted(section_owners))
    payload = {
        "nodes": [row.to_state() for row in nodes],
        "section_owners": dict(sorted(section_owners.items())),
        "expected_state_sections": list(expected),
    }
    return SemanticRuntimeComposition(
        nodes=nodes,
        section_owners=section_owners,
        expected_state_sections=expected,
        digest=canonical_digest(payload),
    )
