from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest

from .manifests import FIRST_GENERATION_SNAPSHOT, build_component_manifests
from .migration import WAVE1_PRESERVED_LEGACY_PATHS


@dataclass(frozen=True, slots=True)
class CompositionLock:
    source_snapshot_sha: str
    components: Mapping[str, str]
    dependencies: Mapping[str, tuple[str, ...]]
    preserved_legacy_paths: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "source_snapshot_sha": self.source_snapshot_sha,
            "components": dict(sorted((str(k), str(v)) for k, v in self.components.items())),
            "dependencies": {
                key: list(self.dependencies[key])
                for key in sorted(self.dependencies)
            },
            "preserved_legacy_paths": list(self.preserved_legacy_paths),
        }

    def __post_init__(self) -> None:
        if len(self.source_snapshot_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in self.source_snapshot_sha):
            raise ValueError("composition lock requires a full immutable source commit SHA")
        if not self.components:
            raise ValueError("composition lock requires components")
        if set(self.dependencies) != set(self.components):
            raise ValueError("composition dependency graph must have exactly one node per component")
        if canonical_digest(self.payload()) != self.digest:
            raise ValueError("composition lock digest mismatch")
        self.topological_order()

    def unresolved_dependencies(self) -> tuple[str, ...]:
        known = set(self.components)
        missing = {
            dependency
            for values in self.dependencies.values()
            for dependency in values
            if dependency not in known
        }
        return tuple(sorted(missing))

    def topological_order(self) -> tuple[str, ...]:
        missing = self.unresolved_dependencies()
        if missing:
            raise ValueError(f"composition contains unresolved dependencies: {missing}")

        remaining = {key: set(values) for key, values in self.dependencies.items()}
        ready = sorted(key for key, deps in remaining.items() if not deps)
        ordered: list[str] = []

        while ready:
            node = ready.pop(0)
            if node in ordered:
                continue
            ordered.append(node)
            for other in sorted(remaining):
                if node in remaining[other]:
                    remaining[other].remove(node)
                    if not remaining[other] and other not in ordered and other not in ready:
                        ready.append(other)
                        ready.sort()

        if len(ordered) != len(remaining):
            cycle_nodes = tuple(sorted(set(remaining) - set(ordered)))
            raise ValueError(f"composition dependency cycle detected: {cycle_nodes}")
        return tuple(ordered)

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}


def build_wave1_composition_lock() -> CompositionLock:
    manifests = build_component_manifests()
    components = {row.component_id: str(row.version) for row in manifests}
    dependencies = {row.component_id: row.dependencies for row in manifests}
    preserved = tuple(row.path for row in WAVE1_PRESERVED_LEGACY_PATHS)
    payload = {
        "source_snapshot_sha": FIRST_GENERATION_SNAPSHOT,
        "components": dict(sorted(components.items())),
        "dependencies": {key: list(dependencies[key]) for key in sorted(dependencies)},
        "preserved_legacy_paths": list(preserved),
    }
    return CompositionLock(
        source_snapshot_sha=FIRST_GENERATION_SNAPSHOT,
        components=components,
        dependencies=dependencies,
        preserved_legacy_paths=preserved,
        digest=canonical_digest(payload),
    )
