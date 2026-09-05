from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
from typing import Collection, Mapping


class VersionDisciplineCode(str, Enum):
    SEMANTIC_CHANGE_WITHOUT_REVISION = "SEMANTIC_CHANGE_WITHOUT_REVISION"
    REVISION_WITHOUT_SEMANTIC_CHANGE = "REVISION_WITHOUT_SEMANTIC_CHANGE"
    REVISION_JUMP = "REVISION_JUMP"
    REVISION_DOWNGRADE = "REVISION_DOWNGRADE"
    NEW_COMPONENT_NOT_BOOTSTRAP = "NEW_COMPONENT_NOT_BOOTSTRAP"
    MISSING_COMPONENT_REVISION_SLOT = "MISSING_COMPONENT_REVISION_SLOT"
    REMOVED_COMPONENT = "REMOVED_COMPONENT"
    UNKNOWN_COMPONENT_REVISION = "UNKNOWN_COMPONENT_REVISION"
    OWNERSHIP_DISCOVERY_ERROR = "OWNERSHIP_DISCOVERY_ERROR"


@dataclass(frozen=True, slots=True)
class VersionDisciplineFinding:
    code: VersionDisciplineCode
    component_id: str
    detail: str

    def to_state(self) -> dict[str, str]:
        return {
            "code": self.code.value,
            "component_id": self.component_id,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class VersionDisciplineReport:
    findings: tuple[VersionDisciplineFinding, ...]

    @property
    def clean(self) -> bool:
        return not self.findings

    def to_state(self) -> dict[str, object]:
        return {
            "clean": self.clean,
            "findings": [finding.to_state() for finding in self.findings],
        }


def _revision(value: object, component_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"component revision must be a non-negative integer: {component_id}")
    return value


def _component_ids(values: Collection[str], label: str) -> set[str]:
    result: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must contain explicit component ids")
        if value in result:
            raise ValueError(f"duplicate {label}: {value}")
        result.add(value)
    return result


def evaluate_revision_delta(
    base_revisions: Mapping[str, int],
    head_revisions: Mapping[str, int],
    affected_components: Collection[str],
    *,
    new_component_roots: Collection[str] = (),
) -> VersionDisciplineReport:
    """Compare exact component-local revision state with semantic ownership.

    This function is read-only. It never repairs or advances a revision. A
    semantic change is admitted only when the owning existing component moves
    exactly one local 0.0.N revision; unrelated, skipped or reversed movement
    is a categorical finding.
    """

    base: dict[str, int] = {}
    head: dict[str, int] = {}
    for component_id, value in base_revisions.items():
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("base revision map contains an invalid component id")
        base[component_id] = _revision(value, component_id)
    for component_id, value in head_revisions.items():
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("head revision map contains an invalid component id")
        head[component_id] = _revision(value, component_id)

    affected = _component_ids(tuple(affected_components), "affected component")
    new_roots = _component_ids(tuple(new_component_roots), "new component root")
    findings: list[VersionDisciplineFinding] = []

    all_ids = sorted(set(base) | set(head) | affected | new_roots)
    for component_id in all_ids:
        in_base = component_id in base
        in_head = component_id in head

        if in_base and not in_head:
            findings.append(
                VersionDisciplineFinding(
                    VersionDisciplineCode.REMOVED_COMPONENT,
                    component_id,
                    "canonical component revision slot was removed without a retirement protocol",
                )
            )
            continue

        if not in_base and in_head:
            if head[component_id] != 0:
                findings.append(
                    VersionDisciplineFinding(
                        VersionDisciplineCode.NEW_COMPONENT_NOT_BOOTSTRAP,
                        component_id,
                        f"new component must begin at revision 0; got {head[component_id]}",
                    )
                )
            elif component_id not in new_roots:
                findings.append(
                    VersionDisciplineFinding(
                        VersionDisciplineCode.MISSING_COMPONENT_REVISION_SLOT,
                        component_id,
                        "new revision slot has no newly discovered canonical component root",
                    )
                )
            continue

        if not in_base and not in_head:
            findings.append(
                VersionDisciplineFinding(
                    VersionDisciplineCode.UNKNOWN_COMPONENT_REVISION,
                    component_id,
                    "semantic ownership references a component with no canonical revision slot",
                )
            )
            continue

        delta = head[component_id] - base[component_id]
        is_affected = component_id in affected
        if delta < 0:
            findings.append(
                VersionDisciplineFinding(
                    VersionDisciplineCode.REVISION_DOWNGRADE,
                    component_id,
                    f"component revision moved backward {base[component_id]}->{head[component_id]}",
                )
            )
        elif delta > 1:
            findings.append(
                VersionDisciplineFinding(
                    VersionDisciplineCode.REVISION_JUMP,
                    component_id,
                    f"component revision must advance exactly once; got {base[component_id]}->{head[component_id]}",
                )
            )
        elif delta == 1 and not is_affected:
            findings.append(
                VersionDisciplineFinding(
                    VersionDisciplineCode.REVISION_WITHOUT_SEMANTIC_CHANGE,
                    component_id,
                    "component revision advanced without an owned semantic source change",
                )
            )
        elif delta == 0 and is_affected:
            findings.append(
                VersionDisciplineFinding(
                    VersionDisciplineCode.SEMANTIC_CHANGE_WITHOUT_REVISION,
                    component_id,
                    "owned semantic source changed without advancing the component revision",
                )
            )

    ordered = tuple(sorted(findings, key=lambda row: (row.code.value, row.component_id, row.detail)))
    return VersionDisciplineReport(ordered)


def _literal_component_id(tree: ast.AST) -> str | None:
    value: str | None = None
    for node in getattr(tree, "body", ()):
        candidate: ast.expr | None = None
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "COMPONENT_ID" for target in node.targets):
            candidate = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "COMPONENT_ID":
            candidate = node.value
        if candidate is None:
            continue
        if not isinstance(candidate, ast.Constant) or not isinstance(candidate.value, str) or not candidate.value.strip():
            raise ValueError("canonical COMPONENT_ID must be a literal non-empty string")
        if value is not None and value != candidate.value:
            raise ValueError("module declares multiple canonical component identities")
        value = candidate.value
    return value


def _internal_imports(module: str, tree: ast.AST, known_modules: set[str]) -> tuple[str, ...]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known_modules:
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Canonical production modules use absolute nolane imports for
                # cross-module authority wiring. Relative imports are resolved
                # conservatively when their package target is available.
                package_parts = module.split(".")[:-1]
                ascend = max(node.level - 1, 0)
                if ascend:
                    package_parts = package_parts[:-ascend]
                base = ".".join(package_parts + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            if base in known_modules:
                imports.add(base)
            for alias in node.names:
                candidate = f"{base}.{alias.name}" if base else alias.name
                if candidate in known_modules:
                    imports.add(candidate)
    return tuple(sorted(imports))


def discover_component_ownership(
    source_by_module: Mapping[str, str],
    changed_modules: Collection[str],
    component_ids: Collection[str],
) -> dict[str, tuple[str, ...]]:
    """Derive semantic ownership from literal roots and the internal import DAG.

    A helper belongs to every canonical component root that can reach it. No
    second hand-maintained path->component table is introduced.
    """

    canonical_ids = _component_ids(tuple(component_ids), "canonical component id")
    modules: dict[str, str] = {}
    trees: dict[str, ast.AST] = {}
    for module, source in source_by_module.items():
        if not isinstance(module, str) or not module.strip() or not isinstance(source, str):
            raise ValueError("ownership source map must contain explicit module names and source text")
        modules[module] = source
        try:
            trees[module] = ast.parse(source, filename=module)
        except SyntaxError as exc:
            raise ValueError(f"ownership discovery cannot parse canonical module: {module}") from exc

    roots: dict[str, str] = {}
    for module in sorted(trees):
        component_id = _literal_component_id(trees[module])
        if component_id is None or component_id not in canonical_ids:
            continue
        previous = roots.get(component_id)
        if previous is not None and previous != module:
            raise ValueError(
                f"duplicate canonical component root for {component_id}: {previous}, {module}"
            )
        roots[component_id] = module

    known_modules = set(modules)
    graph = {
        module: _internal_imports(module, trees[module], known_modules)
        for module in sorted(trees)
    }

    reachable_by_component: dict[str, set[str]] = {}
    for component_id, root in sorted(roots.items()):
        reachable: set[str] = set()
        stack = [root]
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stack.extend(reversed(graph.get(current, ())))
        reachable_by_component[component_id] = reachable

    result: dict[str, tuple[str, ...]] = {}
    for module in sorted(_component_ids(tuple(changed_modules), "changed module")):
        owners = tuple(
            component_id
            for component_id in sorted(reachable_by_component)
            if module in reachable_by_component[component_id]
        )
        result[module] = owners
    return result


__all__ = (
    "VersionDisciplineCode",
    "VersionDisciplineFinding",
    "VersionDisciplineReport",
    "discover_component_ownership",
    "evaluate_revision_delta",
)
