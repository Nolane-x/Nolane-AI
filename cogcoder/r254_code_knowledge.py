from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Mapping

from .r254_cognitive_retrieval import InMemoryArtifactSource, RetrievalArtifact, make_artifact


def _module_name(path: str) -> str:
    value = str(path).replace('\\', '/').removesuffix('.py').strip('/')
    return value.replace('/', '.')


def _artifact_id(path: str, qualname: str) -> str:
    return f'code:{path}:{qualname}'


@dataclass(frozen=True, slots=True)
class _Definition:
    path: str
    module: str
    qualname: str
    simple_name: str
    node: ast.AST
    source: str

    @property
    def artifact_id(self) -> str:
        return _artifact_id(self.path, self.qualname)


class _DefinitionCollector(ast.NodeVisitor):
    def __init__(self, path: str, source: str) -> None:
        self.path = path
        self.source = source
        self.module = _module_name(path)
        self.stack: list[str] = []
        self.definitions: list[_Definition] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qualname = '.'.join(self.stack + [node.name])
        self.definitions.append(_Definition(self.path, self.module, qualname, node.name, node, self.source))
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)


class PythonRepositoryIndexer:
    """Build a compact symbol/call/import memory from Python source without model inference."""

    trainable_parameter_count = 0

    def build_artifacts(self, files: Mapping[str, str]) -> tuple[RetrievalArtifact, ...]:
        parsed: dict[str, ast.Module] = {}
        definitions: list[_Definition] = []
        for path, source in sorted((str(path), str(source)) for path, source in files.items()):
            tree = ast.parse(source, filename=path)
            parsed[path] = tree
            collector = _DefinitionCollector(path, source)
            collector.visit(tree)
            definitions.extend(collector.definitions)

        by_simple: dict[str, list[_Definition]] = {}
        by_qualified: dict[str, _Definition] = {}
        for definition in definitions:
            by_simple.setdefault(definition.simple_name, []).append(definition)
            by_qualified[definition.qualname] = definition
            by_qualified[f'{definition.module}.{definition.qualname}'] = definition

        artifacts: list[RetrievalArtifact] = []
        module_ids = {path: _artifact_id(path, '<module>') for path in parsed}
        module_by_name = {_module_name(path): path for path in parsed}

        for path, tree in parsed.items():
            source = str(files[path])
            relations: list[tuple[str, str, float]] = []
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        target_path = module_by_name.get(alias.name)
                        if target_path:
                            relations.append((module_ids[target_path], 'imports', 0.9))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    target_path = module_by_name.get(node.module)
                    if target_path:
                        relations.append((module_ids[target_path], 'imports', 0.9))
            artifacts.append(make_artifact(
                artifact_id=module_ids[path],
                kind='code',
                text=source,
                source_uri=f'repo://{path}',
                version='1',
                trust_score=1.0,
                tags=frozenset({'python', 'module', _module_name(path)}),
                symbols=frozenset({_module_name(path), path}),
                relations=relations,
            ))

        for definition in definitions:
            node = definition.node
            text = ast.get_source_segment(definition.source, node) or ''
            calls: list[str] = []
            references: list[str] = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    name = self._call_name(child.func)
                    if name:
                        calls.append(name)
                elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    references.append(child.id)
                elif isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
                    name = self._call_name(child)
                    if name:
                        references.append(name)
            relations: list[tuple[str, str, float]] = []
            call_targets: set[str] = set()
            for name in dict.fromkeys(calls):
                target = self._resolve_call(name, definition, by_simple, by_qualified)
                if target is not None and target.artifact_id != definition.artifact_id:
                    relations.append((target.artifact_id, 'calls', 1.0))
                    call_targets.add(target.artifact_id)
            for name in dict.fromkeys(references):
                target = self._resolve_call(name, definition, by_simple, by_qualified)
                if target is not None and target.artifact_id != definition.artifact_id and target.artifact_id not in call_targets:
                    relations.append((target.artifact_id, 'references', 0.82))
            symbols = {
                definition.simple_name,
                definition.qualname,
                f'{definition.module}.{definition.qualname}',
                f'{definition.path}:{definition.qualname}',
            }
            artifacts.append(make_artifact(
                artifact_id=definition.artifact_id,
                kind='code',
                text=text,
                source_uri=f'repo://{definition.path}',
                version='1',
                trust_score=1.0,
                tags=frozenset({'python', 'function', definition.module}),
                symbols=frozenset(symbols),
                relations=relations,
            ))
        return tuple(artifacts)

    def build_source(self, source_id: str, files: Mapping[str, str]) -> InMemoryArtifactSource:
        return InMemoryArtifactSource(source_id, self.build_artifacts(files))

    @staticmethod
    def _call_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts = []
            current: ast.AST = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            parts.reverse()
            return '.'.join(parts)
        return None

    @staticmethod
    def _resolve_call(
        name: str,
        current: _Definition,
        by_simple: Mapping[str, list[_Definition]],
        by_qualified: Mapping[str, _Definition],
    ) -> _Definition | None:
        direct = by_qualified.get(name)
        if direct is not None:
            return direct
        last = name.split('.')[-1]
        candidates = list(by_simple.get(last, ()))
        if not candidates:
            return None
        same_path = [row for row in candidates if row.path == current.path]
        if len(same_path) == 1:
            return same_path[0]
        if len(candidates) == 1:
            return candidates[0]
        same_module = [row for row in candidates if row.module == current.module]
        if len(same_module) == 1:
            return same_module[0]
        return sorted(candidates, key=lambda row: (row.path, row.qualname))[0]


__all__ = ['PythonRepositoryIndexer']
