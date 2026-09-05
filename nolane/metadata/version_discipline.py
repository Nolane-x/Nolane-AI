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
    MISSING_CANONICAL_COMPONENT_ROOT = "MISSING_CANONICAL_COMPONENT_ROOT"
    REMOVED_COMPONENT = "REMOVED_COMPONENT"
    UNKNOWN_COMPONENT_REVISION = "UNKNOWN_COMPONENT_REVISION"
    OWNERSHIP_DISCOVERY_ERROR = "OWNERSHIP_DISCOVERY_ERROR"


@dataclass(frozen=True, slots=True)
class VersionDisciplineFinding:
    code: VersionDisciplineCode
    component_id: str
    detail: str

    def to_state(self) -> dict[str, str]:
        return {"code": self.code.value, "component_id": self.component_id, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class VersionDisciplineReport:
    findings: tuple[VersionDisciplineFinding, ...]

    @property
    def clean(self) -> bool:
        return not self.findings

    def to_state(self) -> dict[str, object]:
        return {"clean": self.clean, "findings": [finding.to_state() for finding in self.findings]}


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


def _is_private_module(module: str) -> bool:
    """Return whether a module is implementation-private rather than a root.

    Private modules remain full members of the internal import DAG. This only
    prevents compatibility/helper modules such as
    ``_software_engineering_control_v07`` from laundering an inherited
    ``COMPONENT_ID`` alias into a canonical component root.
    """

    return module.rsplit(".", 1)[-1].startswith("_")


def _canonical_root_locator(component_id: str) -> str | None:
    """Project a canonical component id to its conventional public module.

    This is a locator, never identity authority.  The projected module must
    actually exist among statically proven same-component surfaces before it
    can anchor them.  Unknown namespaces deliberately return ``None`` so root
    selection falls back to import-topology proof rather than guessing.
    """

    namespace_roots = {
        "core": "nolane.core",
        "schemas": "nolane.schemas",
        "organization": "nolane.organization",
        "external": "nolane.external_core",
        "evaluation": "nolane.evaluation",
        "neural": "nolane.neural",
    }
    parts = component_id.split(".")
    if len(parts) < 2 or any(not part for part in parts):
        return None
    package = namespace_roots.get(parts[0])
    if package is None:
        return None
    module_leaf = "_".join(parts[1:])
    return f"{package}.{module_leaf}"


def evaluate_revision_delta(
    base_revisions: Mapping[str, int],
    head_revisions: Mapping[str, int],
    affected_components: Collection[str],
    *,
    new_component_roots: Collection[str] = (),
) -> VersionDisciplineReport:
    """Compare exact component-local revision state with semantic ownership."""

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
    for component_id in sorted(set(base) | set(head) | affected | new_roots):
        in_base = component_id in base
        in_head = component_id in head
        if in_base and not in_head:
            findings.append(VersionDisciplineFinding(VersionDisciplineCode.REMOVED_COMPONENT, component_id, "canonical component revision slot was removed without a retirement protocol"))
            continue
        if not in_base and in_head:
            if head[component_id] != 0:
                findings.append(VersionDisciplineFinding(VersionDisciplineCode.NEW_COMPONENT_NOT_BOOTSTRAP, component_id, f"new component must begin at revision 0; got {head[component_id]}"))
            elif component_id not in new_roots:
                findings.append(VersionDisciplineFinding(VersionDisciplineCode.MISSING_COMPONENT_REVISION_SLOT, component_id, "new revision slot has no newly discovered canonical component root"))
            continue
        if not in_base and not in_head:
            findings.append(VersionDisciplineFinding(VersionDisciplineCode.UNKNOWN_COMPONENT_REVISION, component_id, "semantic ownership references a component with no canonical revision slot"))
            continue

        delta = head[component_id] - base[component_id]
        is_affected = component_id in affected
        if delta < 0:
            findings.append(VersionDisciplineFinding(VersionDisciplineCode.REVISION_DOWNGRADE, component_id, f"component revision moved backward {base[component_id]}->{head[component_id]}"))
        elif delta > 1:
            findings.append(VersionDisciplineFinding(VersionDisciplineCode.REVISION_JUMP, component_id, f"component revision must advance exactly once; got {base[component_id]}->{head[component_id]}"))
        elif delta == 1 and not is_affected:
            findings.append(VersionDisciplineFinding(VersionDisciplineCode.REVISION_WITHOUT_SEMANTIC_CHANGE, component_id, "component revision advanced without an owned semantic source change"))
        elif delta == 0 and is_affected:
            findings.append(VersionDisciplineFinding(VersionDisciplineCode.SEMANTIC_CHANGE_WITHOUT_REVISION, component_id, "owned semantic source changed without advancing the component revision"))

    return VersionDisciplineReport(tuple(sorted(findings, key=lambda row: (row.code.value, row.component_id, row.detail))))


def _component_id_assignments(tree: ast.AST) -> tuple[ast.expr, ...]:
    values: list[ast.expr] = []
    for node in getattr(tree, "body", ()):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "COMPONENT_ID" for target in node.targets):
            values.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "COMPONENT_ID" and node.value is not None:
            values.append(node.value)
    return tuple(values)


def _import_from_base(module: str, node: ast.ImportFrom) -> str:
    if node.level:
        package_parts = module.split(".")[:-1]
        ascend = max(node.level - 1, 0)
        if ascend:
            package_parts = package_parts[:-ascend]
        return ".".join(package_parts + ([node.module] if node.module else []))
    return node.module or ""


def _import_bindings(
    module: str,
    tree: ast.AST,
    known_modules: set[str],
) -> dict[str, tuple[str, str]]:
    """Map local imported names to exact source module/symbol pairs.

    Only ``from module import symbol [as local]`` participates in component
    identity proof. Star imports, module attributes and runtime expressions are
    intentionally not identity authority.
    """

    bindings: dict[str, tuple[str, str]] = {}
    for node in getattr(tree, "body", ()):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = _import_from_base(module, node)
        if base not in known_modules:
            continue
        for alias in node.names:
            if alias.name == "*":
                continue
            local = alias.asname or alias.name
            pair = (base, alias.name)
            previous = bindings.get(local)
            if previous is not None and previous != pair:
                raise ValueError(f"ambiguous imported identity symbol in {module}: {local}")
            bindings[local] = pair
    return bindings


def _resolve_component_id(
    module: str,
    trees: Mapping[str, ast.AST],
    bindings_by_module: Mapping[str, Mapping[str, tuple[str, str]]],
    *,
    stack: tuple[str, ...] = (),
    allow_import_passthrough: bool = False,
) -> str | None:
    """Resolve COMPONENT_ID without executing source.

    Accepted authority forms are deliberately narrow:
    1. a literal non-empty string assignment; or
    2. an assignment from a local name imported *exactly* from another known
       module's ``COMPONENT_ID``; private frozen chains may also re-export
       ``COMPONENT_ID`` directly with no assignment.

    Arbitrary expressions, calls, attributes, computed strings and cycles fail
    closed.
    """

    if module in stack:
        raise ValueError("component identity import alias cycle: " + " -> ".join(stack + (module,)))
    tree = trees[module]
    bindings = bindings_by_module.get(module, {})
    assignments = _component_id_assignments(tree)

    def resolve_expression(expression: ast.expr) -> str:
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str) and expression.value.strip():
            return expression.value
        if isinstance(expression, ast.Name):
            binding = bindings.get(expression.id)
            if binding is None:
                raise ValueError("canonical COMPONENT_ID must be a literal non-empty string or exact imported alias")
            source_module, imported_name = binding
            if imported_name != "COMPONENT_ID":
                raise ValueError("canonical COMPONENT_ID alias must import the exact COMPONENT_ID symbol")
            resolved = _resolve_component_id(
                source_module,
                trees,
                bindings_by_module,
                stack=stack + (module,),
                allow_import_passthrough=True,
            )
            if resolved is None:
                raise ValueError(f"imported COMPONENT_ID source has no statically resolvable identity: {source_module}")
            return resolved
        raise ValueError("canonical COMPONENT_ID must be a literal non-empty string or exact imported alias")

    if assignments:
        resolved_values = tuple(resolve_expression(expression) for expression in assignments)
        if len(set(resolved_values)) != 1:
            raise ValueError("module declares multiple canonical component identities")
        return resolved_values[0]

    if allow_import_passthrough:
        binding = bindings.get("COMPONENT_ID")
        if binding is not None:
            source_module, imported_name = binding
            if imported_name != "COMPONENT_ID":
                raise ValueError("COMPONENT_ID passthrough must import the exact COMPONENT_ID symbol")
            return _resolve_component_id(
                source_module,
                trees,
                bindings_by_module,
                stack=stack + (module,),
                allow_import_passthrough=True,
            )
    return None


def _internal_imports(module: str, tree: ast.AST, known_modules: set[str]) -> tuple[str, ...]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known_modules:
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _import_from_base(module, node)
            if base in known_modules:
                imports.add(base)
            for alias in node.names:
                candidate = f"{base}.{alias.name}" if base else alias.name
                if candidate in known_modules:
                    imports.add(candidate)
    return tuple(sorted(imports))


def _reachable_modules(start: str, graph: Mapping[str, tuple[str, ...]]) -> set[str]:
    reachable: set[str] = set()
    stack = [start]
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(reversed(graph.get(current, ())))
    return reachable


def _parse_topology_sources(source_by_module: Mapping[str, str]) -> tuple[dict[str, ast.AST], dict[str, tuple[str, ...]], dict[str, dict[str, tuple[str, str]]]]:
    trees: dict[str, ast.AST] = {}
    for module, source in source_by_module.items():
        if not isinstance(module, str) or not module.strip() or not isinstance(source, str):
            raise ValueError("ownership source map must contain explicit module names and source text")
        try:
            trees[module] = ast.parse(source, filename=module)
        except SyntaxError as exc:
            raise ValueError(f"ownership discovery cannot parse canonical module: {module}") from exc
    known_modules = set(trees)
    graph = {module: _internal_imports(module, trees[module], known_modules) for module in sorted(trees)}
    bindings = {module: _import_bindings(module, trees[module], known_modules) for module in sorted(trees)}
    return trees, graph, bindings


def _component_surfaces_and_roots(
    trees: Mapping[str, ast.AST],
    graph: Mapping[str, tuple[str, ...]],
    bindings_by_module: Mapping[str, Mapping[str, tuple[str, str]]],
    canonical_ids: set[str],
) -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    """Resolve public component surfaces to one canonical root each.

    A canonical-locator module, when it actually exists among statically proven
    same-component surfaces, anchors all of those surfaces even when they are
    independent semantic modules.  If no locator exists, import topology must
    prove exactly one dependency-root.  Thus legitimate multi-surface
    components are supported without accepting ambiguous duplicate roots.
    """

    declared: dict[str, list[str]] = {}
    for module in sorted(trees):
        if _is_private_module(module) or not _component_id_assignments(trees[module]):
            continue
        try:
            component_id = _resolve_component_id(module, trees, bindings_by_module)
        except ValueError as exc:
            raise ValueError(f"ownership discovery failed for {module}: {exc}") from exc
        if component_id is None or component_id not in canonical_ids:
            continue
        declared.setdefault(component_id, []).append(module)

    surfaces: dict[str, tuple[str, ...]] = {}
    roots: dict[str, str] = {}
    for component_id, rows in sorted(declared.items()):
        ordered = tuple(sorted(rows))
        locator = _canonical_root_locator(component_id)
        if locator is not None and locator in ordered:
            root = locator
        else:
            candidates: list[str] = []
            for module in ordered:
                reachable = _reachable_modules(module, graph)
                if not any(peer != module and peer in reachable for peer in ordered):
                    candidates.append(module)
            if len(candidates) != 1:
                raise ValueError(f"duplicate canonical component root for {component_id}: " + ", ".join(ordered))
            root = candidates[0]
        surfaces[component_id] = ordered
        roots[component_id] = root
    return surfaces, roots


def _discover_component_root_ids(source_by_module: Mapping[str, str], component_ids: Collection[str]) -> set[str]:
    canonical_ids = _component_ids(tuple(component_ids), "canonical component id")
    trees, graph, bindings = _parse_topology_sources(source_by_module)
    _surfaces, roots = _component_surfaces_and_roots(trees, graph, bindings, canonical_ids)
    return set(roots)


def discover_component_ownership(
    source_by_module: Mapping[str, str],
    changed_modules: Collection[str],
    component_ids: Collection[str],
) -> dict[str, tuple[str, ...]]:
    """Derive semantic ownership from public surfaces and the internal DAG.

    A statically proven canonical component surface is an ownership boundary:
    changing that surface advances the component that declares it, not every
    downstream component that merely imports it. Modules without a canonical
    surface identity remain implementation helpers and propagate to every
    component surface that can reach them.
    """

    canonical_ids = _component_ids(tuple(component_ids), "canonical component id")
    trees, graph, bindings = _parse_topology_sources(source_by_module)
    surfaces, _roots = _component_surfaces_and_roots(trees, graph, bindings, canonical_ids)

    surface_owner_by_module: dict[str, str] = {}
    for component_id, component_surfaces in sorted(surfaces.items()):
        for surface in component_surfaces:
            previous = surface_owner_by_module.get(surface)
            if previous is not None and previous != component_id:
                raise ValueError(f"canonical surface has ambiguous component ownership: {surface}")
            surface_owner_by_module[surface] = component_id

    reachable_by_component: dict[str, set[str]] = {}
    for component_id, component_surfaces in sorted(surfaces.items()):
        reachable: set[str] = set()
        for surface in component_surfaces:
            reachable.update(_reachable_modules(surface, graph))
        reachable_by_component[component_id] = reachable

    result: dict[str, tuple[str, ...]] = {}
    for module in sorted(_component_ids(tuple(changed_modules), "changed module")):
        direct_owner = surface_owner_by_module.get(module)
        if direct_owner is not None:
            result[module] = (direct_owner,)
            continue
        result[module] = tuple(
            component_id
            for component_id in sorted(reachable_by_component)
            if module in reachable_by_component[component_id]
        )
    return result


# Imported after the pure definitions so the Git reader can reuse these types
# without a circular initialization dependency.
from nolane.metadata.version_discipline_git import check_git_revision_discipline  # noqa: E402


__all__ = (
    "VersionDisciplineCode",
    "VersionDisciplineFinding",
    "VersionDisciplineReport",
    "check_git_revision_discipline",
    "discover_component_ownership",
    "evaluate_revision_delta",
)
