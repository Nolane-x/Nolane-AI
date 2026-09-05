from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import Mapping

from nolane.metadata.version_discipline import (
    VersionDisciplineCode,
    VersionDisciplineFinding,
    VersionDisciplineReport,
    _is_private_module,
    discover_component_ownership,
    evaluate_revision_delta,
)


def _git(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "git command failed").strip()
        raise ValueError(f"version discipline git read failed: {detail}") from exc
    return completed.stdout


def _module_name(path: str) -> str:
    value = path[:-3].replace("/", ".")
    if value.endswith(".__init__"):
        value = value[: -len(".__init__")]
    return value


def _tree_sources(repo_root: Path, ref: str) -> dict[str, str]:
    names = _git(repo_root, "ls-tree", "-r", "--name-only", ref, "--", "nolane")
    result: dict[str, str] = {}
    for path in sorted(line.strip() for line in names.splitlines() if line.strip().endswith(".py")):
        result[_module_name(path)] = _git(repo_root, "show", f"{ref}:{path}")
    return result


def _source_at(repo_root: Path, ref: str, path: str) -> str:
    return _git(repo_root, "show", f"{ref}:{path}")


def _assignment_value(tree: ast.Module, name: str) -> ast.expr | None:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return node.value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node.value
    return None


def _is_docstring_expr(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _is_component_version_assignment(node: ast.stmt) -> bool:
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id == "COMPONENT_VERSION"
    if not isinstance(node, ast.Assign) or not node.targets:
        return False
    return all(isinstance(target, ast.Name) and target.id == "COMPONENT_VERSION" for target in node.targets)


class _SemanticAstNormalizer(ast.NodeTransformer):
    """Remove non-behavioral text/version metadata from semantic comparison.

    Component revision metadata cannot be allowed to justify its own revision.
    Comments/formatting are absent from the AST already; docstrings are removed
    so documentation-only edits also cannot create a synthetic semantic delta.
    """

    @staticmethod
    def _without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
        if body and _is_docstring_expr(body[0]):
            return body[1:]
        return body

    def visit_Module(self, node: ast.Module) -> ast.AST:
        node.body = self._without_docstring(node.body)
        node.body = [row for row in node.body if not _is_component_version_assignment(row)]
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.body = self._without_docstring(node.body)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.body = self._without_docstring(node.body)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.body = self._without_docstring(node.body)
        self.generic_visit(node)
        return node


def _semantic_ast_dump(source: str, module: str) -> str:
    try:
        tree = ast.parse(source, filename=module)
    except SyntaxError as exc:
        raise ValueError(f"cannot parse canonical source for semantic delta: {module}") from exc
    normalized = _SemanticAstNormalizer().visit(tree)
    ast.fix_missing_locations(normalized)
    return ast.dump(normalized, annotate_fields=True, include_attributes=False)


def _semantic_source_changed(
    module: str,
    base_sources: Mapping[str, str],
    head_sources: Mapping[str, str],
) -> bool:
    base = base_sources.get(module)
    head = head_sources.get(module)
    if base is None or head is None:
        return base != head
    return _semantic_ast_dump(base, module) != _semantic_ast_dump(head, module)


def _component_specs(source: str) -> dict[str, tuple[object, ...]]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError("component spec source is not valid Python") from exc
    expression = _assignment_value(tree, "COMPONENT_SPECS")
    if expression is None:
        raise ValueError("COMPONENT_SPECS literal is missing")
    try:
        rows = ast.literal_eval(expression)
    except (ValueError, TypeError) as exc:
        raise ValueError("COMPONENT_SPECS must remain literal for version discipline") from exc
    if not isinstance(rows, (tuple, list)):
        raise ValueError("COMPONENT_SPECS must be a literal sequence")

    result: dict[str, tuple[object, ...]] = {}
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 5:
            raise ValueError("COMPONENT_SPECS contains a non-canonical component row")
        component_id, layer, responsibility, state_schema, dependencies = row
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("COMPONENT_SPECS contains an invalid component identity")
        if component_id in result:
            raise ValueError("COMPONENT_SPECS contains duplicate component identities")
        if not all(isinstance(value, str) and value.strip() for value in (layer, responsibility, state_schema)):
            raise ValueError(f"COMPONENT_SPECS metadata must be explicit for {component_id}")
        if not isinstance(dependencies, (tuple, list)):
            raise ValueError(f"COMPONENT_SPECS dependencies must be a literal sequence for {component_id}")
        dependency_ids = tuple(dependencies)
        if any(not isinstance(value, str) or not value.strip() for value in dependency_ids):
            raise ValueError(f"COMPONENT_SPECS contains an invalid dependency for {component_id}")
        if len(set(dependency_ids)) != len(dependency_ids):
            raise ValueError(f"COMPONENT_SPECS contains duplicate dependencies for {component_id}")
        if component_id in dependency_ids:
            raise ValueError(f"COMPONENT_SPECS component depends on itself: {component_id}")
        result[component_id] = (
            component_id,
            layer,
            responsibility,
            state_schema,
            tuple(dependency_ids),
        )
    return result


def _component_ids_from_specs(source: str) -> tuple[str, ...]:
    return tuple(_component_specs(source))


def _revision_overrides(source: str) -> Mapping[str, int]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError("component version source is not valid Python") from exc
    overrides: dict[str, int] = {}
    direct = _assignment_value(tree, "_COMPONENT_REVISIONS")
    if isinstance(direct, ast.Dict):
        try:
            raw = ast.literal_eval(direct)
        except (ValueError, TypeError) as exc:
            raise ValueError("component revision dictionary must be literal") from exc
        if isinstance(raw, dict):
            overrides.update(raw)
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "_COMPONENT_REVISIONS"
            and call.func.attr == "update"
            and len(call.args) == 1
            and not call.keywords
        ):
            continue
        try:
            raw = ast.literal_eval(call.args[0])
        except (ValueError, TypeError) as exc:
            raise ValueError("component revision update must remain a literal mapping") from exc
        if not isinstance(raw, dict):
            raise ValueError("component revision update must be a mapping")
        overrides.update(raw)
    normalized: dict[str, int] = {}
    for component_id, revision in overrides.items():
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("component revision override has invalid component identity")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ValueError(f"component revision override must be a non-negative integer: {component_id}")
        normalized[component_id] = revision
    return normalized


def _revision_map(repo_root: Path, ref: str) -> dict[str, int]:
    specs_source = _source_at(repo_root, ref, "nolane/metadata/_component_specs.py")
    versions_source = _source_at(repo_root, ref, "nolane/metadata/component_versions.py")
    component_ids = _component_ids_from_specs(specs_source)
    revisions = {component_id: 0 for component_id in component_ids}
    overrides = _revision_overrides(versions_source)
    unknown = sorted(set(overrides) - set(revisions))
    if unknown:
        raise ValueError("component revision map references identities outside COMPONENT_SPECS: " + ",".join(unknown))
    revisions.update(overrides)
    return revisions


def _root_ids(sources: Mapping[str, str], component_ids: set[str]) -> set[str]:
    roots: set[str] = set()
    seen: dict[str, str] = {}
    for module, source in sorted(sources.items()):
        if _is_private_module(module):
            continue
        try:
            tree = ast.parse(source, filename=module)
        except SyntaxError as exc:
            raise ValueError(f"cannot parse canonical source for component-root discovery: {module}") from exc
        candidate = _assignment_value(tree, "COMPONENT_ID")
        if candidate is None:
            continue
        if not isinstance(candidate, ast.Constant) or not isinstance(candidate.value, str) or not candidate.value.strip():
            raise ValueError(f"canonical COMPONENT_ID is not a literal non-empty string: {module}")
        component_id = candidate.value
        if component_id not in component_ids:
            continue
        if component_id in seen and seen[component_id] != module:
            raise ValueError(f"duplicate canonical component root for {component_id}: {seen[component_id]}, {module}")
        seen[component_id] = module
        roots.add(component_id)
    return roots


def check_git_revision_discipline(
    repo_root: Path | str,
    base_ref: str,
    head_ref: str,
) -> VersionDisciplineReport:
    """Evaluate component-local revisions from exact Git base/head trees.

    The checker executes Git only. Python source being evaluated is parsed with
    AST and never imported or executed. Semantic ownership is based on
    normalized AST changes plus canonical component-spec row changes, so
    revision constants, docstrings and formatting cannot manufacture a
    semantic change while responsibility/schema/dependency metadata cannot
    escape revision discipline.
    """

    root = Path(repo_root)
    if not isinstance(base_ref, str) or not base_ref.strip() or not isinstance(head_ref, str) or not head_ref.strip():
        raise ValueError("base/head refs must be explicit strings")

    try:
        base_spec_source = _source_at(root, base_ref, "nolane/metadata/_component_specs.py")
        head_spec_source = _source_at(root, head_ref, "nolane/metadata/_component_specs.py")
        base_specs = _component_specs(base_spec_source)
        head_specs = _component_specs(head_spec_source)
        base_revisions = _revision_map(root, base_ref)
        head_revisions = _revision_map(root, head_ref)
        canonical_ids = set(base_revisions) | set(head_revisions)
        base_sources = _tree_sources(root, base_ref)
        head_sources = _tree_sources(root, head_ref)
        changed_paths = _git(root, "diff", "--name-only", base_ref, head_ref, "--", "nolane")
        candidate_modules = {
            _module_name(path)
            for path in (line.strip() for line in changed_paths.splitlines())
            if path.endswith(".py")
        }
        changed_modules = {
            module
            for module in candidate_modules
            if _semantic_source_changed(module, base_sources, head_sources)
        }

        affected: set[str] = {
            component_id
            for component_id in set(base_specs) & set(head_specs)
            if base_specs[component_id] != head_specs[component_id]
        }
        if changed_modules:
            for source_map in (base_sources, head_sources):
                ownership = discover_component_ownership(source_map, changed_modules, canonical_ids)
                for owners in ownership.values():
                    affected.update(owners)

        base_roots = _root_ids(base_sources, canonical_ids)
        head_roots = _root_ids(head_sources, canonical_ids)
        new_roots = head_roots - base_roots
        return evaluate_revision_delta(
            base_revisions,
            head_revisions,
            affected,
            new_component_roots=new_roots,
        )
    except ValueError as exc:
        return VersionDisciplineReport(
            (
                VersionDisciplineFinding(
                    VersionDisciplineCode.OWNERSHIP_DISCOVERY_ERROR,
                    "repository",
                    str(exc),
                ),
            )
        )


__all__ = ("check_git_revision_discipline",)
