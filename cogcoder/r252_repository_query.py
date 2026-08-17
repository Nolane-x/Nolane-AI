from __future__ import annotations

import ast
import hashlib
import itertools
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Mapping, Sequence

from .r247_executable_patch_cegis import (
    PatchCegisReceipt,
    PatchMacro,
    PatchRound,
    PatchTest,
    _digest,
    _dump,
    infer_patch_macro,
)
from .r250_relational_query import (
    FactEdge,
    FactNode,
    InducedRelationalQuery,
    ProgramFactGraph,
    TracePattern,
    _apply_base_edit,
    _node_attrs,
    learn_induced_query,
    query_matches,
)
from .r251_interprocedural_query import _interprocedural_trace_patterns


@dataclass(frozen=True)
class RepositorySnapshot:
    files: tuple[tuple[str, str], ...]

    @classmethod
    def from_mapping(cls, files: Mapping[str, str]) -> 'RepositorySnapshot':
        if not files:
            raise ValueError('repository must contain at least one Python file')
        normalized: list[tuple[str, str]] = []
        modules: dict[str, str] = {}
        for raw_path, raw_source in files.items():
            path = _normalize_path(raw_path)
            module = _module_name_from_path(path)
            prior = modules.get(module)
            if prior is not None and prior != path:
                raise ValueError(f'ambiguous module name {module!r}: {prior!r}, {path!r}')
            modules[module] = path
            normalized.append((path, str(raw_source)))
        return cls(tuple(sorted(normalized)))

    def as_dict(self) -> dict[str, str]:
        return dict(self.files)

    def source(self, path: str) -> str:
        key = _normalize_path(path)
        try:
            return dict(self.files)[key]
        except KeyError as exc:
            raise KeyError(key) from exc


@dataclass
class RepositoryFactGraph:
    nodes: dict[str, FactNode]
    edges: tuple[FactEdge, ...]
    ast_node_ids: dict[int, str]
    symbol_ids: dict[str, str]
    modules: dict[str, str]
    functions: dict[str, str]
    node_modules: dict[str, str]
    path_modules: dict[str, str]


def _normalize_path(path: str) -> str:
    raw = str(path).replace('\\', '/').strip()
    p = PurePosixPath(raw)
    if not raw or p.is_absolute() or '..' in p.parts or p.suffix != '.py':
        raise ValueError(f'invalid repository Python path: {path!r}')
    normalized = p.as_posix()
    if normalized.startswith('./'):
        normalized = normalized[2:]
    return normalized


def _module_name_from_path(path: str) -> str:
    p = PurePosixPath(_normalize_path(path))
    parts = list(p.with_suffix('').parts)
    if parts[-1] == '__init__':
        parts = parts[:-1]
    if not parts:
        raise ValueError('root __init__.py is not a supported standalone module')
    if any(not part.isidentifier() for part in parts):
        raise ValueError(f'path does not map to a valid Python module: {path!r}')
    return '.'.join(parts)


def _parse_repository(snapshot: RepositorySnapshot) -> tuple[dict[str, ast.Module], dict[str, str]]:
    modules: dict[str, ast.Module] = {}
    paths: dict[str, str] = {}
    for path, source in snapshot.files:
        module_name = _module_name_from_path(path)
        module = ast.parse(source, filename=path)
        for node in module.body:
            if isinstance(node, ast.Import):
                raise ValueError('plain import statements are unsupported in R2.52')
            if isinstance(node, ast.ImportFrom):
                if node.level != 0 or not node.module or any(alias.name == '*' for alias in node.names):
                    raise ValueError('only absolute direct from-imports are supported in R2.52')
            elif isinstance(node, ast.AsyncFunctionDef):
                raise ValueError('async functions are unsupported in R2.52')
        modules[module_name] = module
        paths[module_name] = path
    return modules, paths


def _function_map(module: ast.Module) -> dict[str, ast.FunctionDef]:
    funcs = {node.name: node for node in module.body if isinstance(node, ast.FunctionDef)}
    if not funcs:
        raise ValueError('every R2.52 module must define at least one top-level synchronous function')
    return funcs


def _function_key(module_name: str, function_name: str) -> str:
    return f'{module_name}::{function_name}'


def _scope_key(module_name: str, function_name: str, symbol: str) -> str:
    return f'{module_name}::{function_name}::{symbol}'


def _collect_import_bindings(
    modules: Mapping[str, ast.Module], functions: Mapping[str, Mapping[str, ast.FunctionDef]]
) -> dict[str, dict[str, str]]:
    bindings: dict[str, dict[str, str]] = {}
    for module_name in sorted(modules):
        rows: dict[str, str] = {}
        for node in modules[module_name].body:
            if not isinstance(node, ast.ImportFrom):
                continue
            assert node.module is not None
            if node.module not in modules:
                raise ValueError(f'missing repository import module {node.module!r}')
            for alias in node.names:
                if alias.name not in functions[node.module]:
                    raise ValueError(f'imported symbol is not a repository function: {node.module}.{alias.name}')
                local_name = alias.asname or alias.name
                target = _function_key(node.module, alias.name)
                if local_name in rows and rows[local_name] != target:
                    raise ValueError(f'ambiguous import binding {module_name}.{local_name}')
                rows[local_name] = target
        bindings[module_name] = rows
    return bindings


def _build_repository_fact_graph_from_modules(
    snapshot: RepositorySnapshot,
    modules: Mapping[str, ast.Module],
    paths: Mapping[str, str],
) -> RepositoryFactGraph:
    functions_by_module = {name: _function_map(module) for name, module in modules.items()}
    imports = _collect_import_bindings(modules, functions_by_module)

    nodes: dict[str, FactNode] = {}
    edges: list[FactEdge] = []
    ast_node_ids: dict[int, str] = {}
    symbol_ids: dict[str, str] = {}
    module_ids: dict[str, str] = {}
    function_ids: dict[str, str] = {}
    node_modules: dict[str, str] = {}

    def add(src: str, relation: str, dst: str) -> None:
        edges.append(FactEdge(src, relation, dst))

    for index, module_name in enumerate(sorted(modules)):
        mid = f'm{index:04d}'
        module_ids[module_name] = mid
        nodes[mid] = FactNode(mid, 'module')
        node_modules[mid] = module_name

    for index, key in enumerate(sorted(
        _function_key(module_name, fn_name)
        for module_name, funcs in functions_by_module.items()
        for fn_name in funcs
    )):
        module_name, _fn_name = key.rsplit('::', 1)
        fid = f'f{index:05d}'
        function_ids[key] = fid
        nodes[fid] = FactNode(fid, 'function')
        node_modules[fid] = module_name
        add(module_ids[module_name], 'MODULE_CONTAINS', fid)

    all_ast: list[tuple[str, str, ast.AST]] = []
    for module_name in sorted(functions_by_module):
        for fn_name in sorted(functions_by_module[module_name]):
            fn = functions_by_module[module_name][fn_name]
            for node in ast.walk(fn):
                all_ast.append((module_name, fn_name, node))
    for index, (module_name, _fn_name, node) in enumerate(all_ast):
        nid = f'a{index:06d}'
        ast_node_ids[id(node)] = nid
        nodes[nid] = FactNode(nid, type(node).__name__.lower(), _node_attrs(node))
        node_modules[nid] = module_name

    def symbol_id(module_name: str, fn_name: str, name: str) -> str:
        key = _scope_key(module_name, fn_name, name)
        if key not in symbol_ids:
            sid = f's{len(symbol_ids):06d}'
            symbol_ids[key] = sid
            nodes[sid] = FactNode(sid, 'symbol')
            node_modules[sid] = module_name
        return symbol_ids[key]

    def value_ref(module_name: str, fn_name: str, value: ast.AST) -> str:
        if isinstance(value, ast.Name):
            return symbol_id(module_name, fn_name, value.id)
        return ast_node_ids[id(value)]

    # Syntax, ownership, parameter, and intraprocedural flow facts.
    for module_name in sorted(functions_by_module):
        for fn_name in sorted(functions_by_module[module_name]):
            fn = functions_by_module[module_name][fn_name]
            fid = function_ids[_function_key(module_name, fn_name)]
            add(fid, 'FUNCTION_BODY', ast_node_ids[id(fn)])
            for parent in ast.walk(fn):
                pid = ast_node_ids[id(parent)]
                for child in ast.iter_child_nodes(parent):
                    cid = ast_node_ids[id(child)]
                    add(pid, 'AST_CHILD', cid)
                    add(cid, 'AST_PARENT', pid)

            for arg_index, arg in enumerate(fn.args.args):
                sid = symbol_id(module_name, fn_name, arg.arg)
                pid = f'p{module_name}:{fn_name}:{arg_index}'
                nodes[pid] = FactNode(pid, 'parameter')
                node_modules[pid] = module_name
                add(sid, 'IS_PARAMETER', pid)

            for node in ast.walk(fn):
                nid = ast_node_ids[id(node)]
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    target = symbol_id(module_name, fn_name, node.targets[0].id)
                    value = value_ref(module_name, fn_name, node.value)
                    add(nid, 'ASSIGNS', target)
                    add(value, 'FLOW', target)
                    if isinstance(node.value, ast.Name):
                        add(target, 'ALIAS_OF', symbol_id(module_name, fn_name, node.value.id))
                elif isinstance(node, ast.BinOp):
                    add(nid, 'LEFT_OPERAND', value_ref(module_name, fn_name, node.left))
                    add(nid, 'RIGHT_OPERAND', value_ref(module_name, fn_name, node.right))
                elif isinstance(node, ast.Compare):
                    add(nid, 'COMPARE_LEFT', value_ref(module_name, fn_name, node.left))
                    for comp in node.comparators:
                        add(nid, 'COMPARE_RIGHT', value_ref(module_name, fn_name, comp))
                elif isinstance(node, ast.Return) and node.value is not None:
                    value = value_ref(module_name, fn_name, node.value)
                    add(nid, 'RETURN_VALUE', value)
                    add(value, 'FLOW', nid)
                    add(nid, 'FLOW', fid)

                if isinstance(node, ast.expr):
                    for child in ast.walk(node):
                        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                            sid = symbol_id(module_name, fn_name, child.id)
                            add(nid, 'USES', sid)
                            add(sid, 'FLOW', nid)

    # Import bindings are structural and identifier-free.
    import_binding_ids: dict[tuple[str, str], str] = {}
    for module_name in sorted(imports):
        for local_name, target_key in sorted(imports[module_name].items()):
            iid = f'i{len(import_binding_ids):05d}'
            import_binding_ids[(module_name, local_name)] = iid
            nodes[iid] = FactNode(iid, 'import_binding')
            node_modules[iid] = module_name
            add(module_ids[module_name], 'HAS_IMPORT', iid)
            add(iid, 'IMPORTS_SYMBOL', function_ids[target_key])

    # Direct same-module/imported call binding and argument/return flow.
    for module_name in sorted(functions_by_module):
        local_funcs = functions_by_module[module_name]
        for fn_name in sorted(local_funcs):
            fn = local_funcs[fn_name]
            for call in (n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)):
                target_key: str | None = None
                if call.func.id in local_funcs:
                    target_key = _function_key(module_name, call.func.id)
                elif call.func.id in imports[module_name]:
                    target_key = imports[module_name][call.func.id]
                if target_key is None:
                    continue
                target_module, target_fn_name = target_key.rsplit('::', 1)
                callee = functions_by_module[target_module][target_fn_name]
                call_id = ast_node_ids[id(call)]
                callee_id = function_ids[target_key]
                add(call_id, 'CALL_TARGET', callee_id)
                add(callee_id, 'FLOW', call_id)
                for arg_index, arg in enumerate(call.args):
                    if arg_index >= len(callee.args.args):
                        break
                    actual = value_ref(module_name, fn_name, arg)
                    formal = symbol_id(target_module, target_fn_name, callee.args.args[arg_index].arg)
                    add(actual, 'ARG_BIND', formal)
                    add(actual, 'FLOW', formal)

    # Materialized generic flow closure, matching R2.51 semantics.
    flow_adj: dict[str, set[str]] = {}
    for edge in edges:
        if edge.relation == 'FLOW':
            flow_adj.setdefault(edge.src, set()).add(edge.dst)
    closure: list[FactEdge] = []
    for src in sorted(nodes):
        seen: set[str] = set()
        stack = list(sorted(flow_adj.get(src, ()), reverse=True))
        while stack:
            cur = stack.pop()
            if cur in seen or cur == src:
                continue
            seen.add(cur)
            stack.extend(sorted(flow_adj.get(cur, ()), reverse=True))
        for dst in sorted(seen):
            closure.append(FactEdge(src, 'FLOW*', dst))

    path_modules = {path: module_name for module_name, path in paths.items()}
    return RepositoryFactGraph(
        nodes,
        tuple(sorted(set((*edges, *closure)))),
        ast_node_ids,
        symbol_ids,
        module_ids,
        function_ids,
        node_modules,
        path_modules,
    )


def build_repository_fact_graph(snapshot: RepositorySnapshot | Mapping[str, str]) -> RepositoryFactGraph:
    if not isinstance(snapshot, RepositorySnapshot):
        snapshot = RepositorySnapshot.from_mapping(snapshot)
    modules, paths = _parse_repository(snapshot)
    return _build_repository_fact_graph_from_modules(snapshot, modules, paths)


def _repository_candidate_nodes(
    modules: Mapping[str, ast.Module], base: PatchMacro
) -> tuple[tuple[str, ast.AST], ...]:
    rows: list[tuple[str, ast.AST]] = []
    for module_name in sorted(modules):
        nodes = list(ast.walk(modules[module_name]))
        if base.slot in {'binop', 'operand_wrapper'}:
            candidates = [node for node in nodes if isinstance(node, ast.BinOp)]
            if base.slot == 'binop':
                candidates = [node for node in candidates if type(node.op).__name__ == base.src]
            else:
                candidates = [
                    node for node in candidates
                    if isinstance(node.left, ast.Name) and isinstance(node.right, ast.Name)
                ]
        elif base.slot == 'compare':
            candidates = [
                node for node in nodes
                if isinstance(node, ast.Compare)
                and len(node.ops) == 1
                and type(node.ops[0]).__name__ == base.src
            ]
        elif base.slot == 'return_wrapper':
            candidates = [node for node in nodes if isinstance(node, ast.Return) and node.value is not None]
        else:
            raise ValueError('unsupported slot')
        rows.extend((module_name, node) for node in candidates)
    return tuple(rows)


def infer_repository_patch_macro(
    before_snapshot: RepositorySnapshot | Mapping[str, str],
    after_snapshot: RepositorySnapshot | Mapping[str, str],
) -> PatchMacro:
    if not isinstance(before_snapshot, RepositorySnapshot):
        before_snapshot = RepositorySnapshot.from_mapping(before_snapshot)
    if not isinstance(after_snapshot, RepositorySnapshot):
        after_snapshot = RepositorySnapshot.from_mapping(after_snapshot)
    if tuple(path for path, _ in before_snapshot.files) != tuple(path for path, _ in after_snapshot.files):
        raise ValueError('demonstration file set changed')
    before_modules, _ = _parse_repository(before_snapshot)
    after_modules, _ = _parse_repository(after_snapshot)
    changed: list[tuple[str, str]] = []
    for module_name in sorted(before_modules):
        before_funcs = _function_map(before_modules[module_name])
        after_funcs = _function_map(after_modules[module_name])
        if set(before_funcs) != set(after_funcs):
            raise ValueError('demonstration function set changed')
        for fn_name in sorted(before_funcs):
            if _dump(before_funcs[fn_name]) != _dump(after_funcs[fn_name]):
                changed.append((module_name, fn_name))
    if len(changed) != 1:
        raise ValueError(f'demonstration must change exactly one function, got {changed!r}')
    module_name, fn_name = changed[0]
    before_fn = _function_map(before_modules[module_name])[fn_name]
    after_fn = _function_map(after_modules[module_name])[fn_name]
    return infer_patch_macro(ast.unparse(before_fn) + '\n', ast.unparse(after_fn) + '\n')


def _repository_changed_labels(
    before_modules: Mapping[str, ast.Module],
    after_modules: Mapping[str, ast.Module],
    base: PatchMacro,
) -> tuple[bool, ...]:
    if base.slot in {'binop', 'operand_wrapper'}:
        typ: type[ast.AST] = ast.BinOp
    elif base.slot == 'compare':
        typ = ast.Compare
    else:
        typ = ast.Return
    changed_by_id: dict[int, bool] = {}
    for module_name in sorted(before_modules):
        before_raw = [node for node in ast.walk(before_modules[module_name]) if isinstance(node, typ)]
        after_raw = [node for node in ast.walk(after_modules[module_name]) if isinstance(node, typ)]
        if len(before_raw) != len(after_raw):
            raise ValueError('candidate count changed')
        for left, right in zip(before_raw, after_raw):
            changed_by_id[id(left)] = _dump(left) != _dump(right)
    candidates = _repository_candidate_nodes(before_modules, base)
    return tuple(bool(changed_by_id[id(node)]) for _module_name, node in candidates)


def _repository_as_program_graph(
    graph: RepositoryFactGraph, modules: Mapping[str, ast.Module]
) -> ProgramFactGraph:
    first_module = modules[sorted(modules)[0]]
    first = next(node for node in first_module.body if isinstance(node, ast.FunctionDef))
    return ProgramFactGraph(first, graph.nodes, graph.edges, graph.ast_node_ids, graph.symbol_ids)


@dataclass(frozen=True, order=True)
class RepositoryQueryMacro:
    macro_id: str
    base: PatchMacro
    query: InducedRelationalQuery
    support: int
    positive_sites: int
    negative_sites: int

    @property
    def slot(self) -> str:
        return self.base.slot


def _repository_macro_id(base: PatchMacro, query: InducedRelationalQuery) -> str:
    payload = '|'.join([*(str(value) for value in base.signature), query.query_id])
    return 'rpq:' + hashlib.sha256(payload.encode()).hexdigest()[:20]


def learn_repository_query_macro(
    demos: Sequence[
        tuple[
            RepositorySnapshot | Mapping[str, str],
            RepositorySnapshot | Mapping[str, str],
        ]
    ],
    *,
    max_depth: int = 6,
) -> RepositoryQueryMacro:
    if len(demos) < 2:
        raise ValueError('at least two demonstrations required')
    bases: list[PatchMacro] = []
    positives: list[frozenset[TracePattern]] = []
    negatives: list[frozenset[TracePattern]] = []
    for before_raw, after_raw in demos:
        before = before_raw if isinstance(before_raw, RepositorySnapshot) else RepositorySnapshot.from_mapping(before_raw)
        after = after_raw if isinstance(after_raw, RepositorySnapshot) else RepositorySnapshot.from_mapping(after_raw)
        base = infer_repository_patch_macro(before, after)
        bases.append(base)
        before_modules, before_paths = _parse_repository(before)
        after_modules, _ = _parse_repository(after)
        candidates = _repository_candidate_nodes(before_modules, base)
        labels = _repository_changed_labels(before_modules, after_modules, base)
        if len(candidates) != len(labels) or sum(labels) != 1:
            raise ValueError('each demo must contain exactly one positive candidate site')
        repo_graph = _build_repository_fact_graph_from_modules(before, before_modules, before_paths)
        graph = _repository_as_program_graph(repo_graph, before_modules)
        for (_module_name, node), label in zip(candidates, labels):
            traces = _interprocedural_trace_patterns(
                graph,
                repo_graph.ast_node_ids[id(node)],
                max_depth=max_depth,
            )
            (positives if label else negatives).append(traces)
    signature = bases[0].signature
    if any(base.signature != signature for base in bases):
        raise ValueError('demonstrations disagree on base patch')
    query = learn_induced_query(positives, negatives, max_conjunction=4)
    base0 = bases[0]
    supported = PatchMacro(base0.macro_id, *base0.signature, support=len(demos))
    return RepositoryQueryMacro(
        _repository_macro_id(supported, query),
        supported,
        query,
        len(demos),
        len(positives),
        len(negatives),
    )


def learn_repository_query_library(
    grouped_demos: Mapping[
        str,
        Sequence[
            tuple[
                RepositorySnapshot | Mapping[str, str],
                RepositorySnapshot | Mapping[str, str],
            ]
        ],
    ],
    *,
    max_depth: int = 6,
) -> tuple[RepositoryQueryMacro, ...]:
    return tuple(sorted(
        (
            learn_repository_query_macro(demos, max_depth=max_depth)
            for _kind, demos in sorted(grouped_demos.items())
        ),
        key=lambda macro: macro.macro_id,
    ))


def _localize_repository_macros(
    snapshot: RepositorySnapshot,
    macros: Sequence[RepositoryQueryMacro],
    *,
    max_depth: int = 6,
) -> dict[str, tuple[int, ...]]:
    modules, paths = _parse_repository(snapshot)
    repo_graph = _build_repository_fact_graph_from_modules(snapshot, modules, paths)
    graph = _repository_as_program_graph(repo_graph, modules)
    localized: dict[str, tuple[int, ...]] = {}
    trace_cache: dict[str, frozenset[TracePattern]] = {}
    for macro in macros:
        candidates = _repository_candidate_nodes(modules, macro.base)
        selected: list[int] = []
        for index, (_module_name, node) in enumerate(candidates):
            node_id = repo_graph.ast_node_ids[id(node)]
            traces = trace_cache.get(node_id)
            if traces is None:
                traces = _interprocedural_trace_patterns(
                    graph,
                    node_id,
                    max_depth=max_depth,
                )
                trace_cache[node_id] = traces
            if query_matches(macro.query, traces):
                selected.append(index)
        localized[macro.macro_id] = tuple(selected)
    return localized


def _apply_localized_repository_macros(
    snapshot: RepositorySnapshot,
    macros: Sequence[RepositoryQueryMacro],
    localized: Mapping[str, Sequence[int]],
) -> RepositorySnapshot:
    modules, paths = _parse_repository(snapshot)
    order = {'binop': 0, 'operand_wrapper': 1, 'compare': 2, 'return_wrapper': 3}
    planned: list[tuple[RepositoryQueryMacro, tuple[tuple[str, ast.AST], ...]]] = []
    for macro in sorted(macros, key=lambda item: (order[item.slot], item.macro_id)):
        candidates = _repository_candidate_nodes(modules, macro.base)
        indices = tuple(int(index) for index in localized.get(macro.macro_id, ()))
        if any(index < 0 or index >= len(candidates) for index in indices):
            raise ValueError('localized repository candidate index is out of range')
        planned.append((macro, tuple(candidates[index] for index in indices)))
    for macro, targets in planned:
        for _module_name, node in targets:
            _apply_base_edit(node, macro.base)
    for module in modules.values():
        ast.fix_missing_locations(module)
    updated = {
        paths[module_name]: ast.unparse(modules[module_name]) + '\n'
        for module_name in sorted(modules)
    }
    return RepositorySnapshot.from_mapping(updated)


def apply_repository_query_macros(
    snapshot: RepositorySnapshot | Mapping[str, str],
    macros: Sequence[RepositoryQueryMacro],
    *,
    max_depth: int = 6,
) -> RepositorySnapshot:
    if not isinstance(snapshot, RepositorySnapshot):
        snapshot = RepositorySnapshot.from_mapping(snapshot)
    localized = _localize_repository_macros(snapshot, macros, max_depth=max_depth)
    return _apply_localized_repository_macros(snapshot, macros, localized)


@dataclass(frozen=True)
class RepositoryPatchCandidate:
    candidate_id: str
    macro_ids: tuple[str, ...]
    files: tuple[tuple[str, str], ...]
    support_score: int
    edit_count: int

    @property
    def snapshot(self) -> RepositorySnapshot:
        return RepositorySnapshot(self.files)


def _repository_payload(snapshot: RepositorySnapshot) -> str:
    return '\n'.join(f'@@{path}\n{source}' for path, source in snapshot.files)


def enumerate_repository_candidates(
    snapshot: RepositorySnapshot | Mapping[str, str],
    macros: Sequence[RepositoryQueryMacro],
    *,
    max_depth: int = 6,
) -> tuple[RepositoryPatchCandidate, ...]:
    if not isinstance(snapshot, RepositorySnapshot):
        snapshot = RepositorySnapshot.from_mapping(snapshot)
    by_slot = {slot: [] for slot in ('binop', 'operand_wrapper', 'compare', 'return_wrapper')}
    for macro in macros:
        by_slot[macro.slot].append(macro)
    choices = [
        (None, *sorted(by_slot[slot], key=lambda macro: macro.macro_id))
        for slot in ('binop', 'operand_wrapper', 'compare', 'return_wrapper')
    ]
    localized = _localize_repository_macros(snapshot, macros, max_depth=max_depth)
    dedup: dict[tuple[tuple[str, str], ...], RepositoryPatchCandidate] = {}
    for selection in itertools.product(*choices):
        selected = tuple(macro for macro in selection if macro is not None)
        patched = _apply_localized_repository_macros(snapshot, selected, localized)
        ids = tuple(sorted(macro.macro_id for macro in selected))
        candidate = RepositoryPatchCandidate(
            'rpc:' + _digest('|'.join(ids) + '|' + _repository_payload(patched)),
            ids,
            patched.files,
            sum(macro.support for macro in selected),
            len(selected),
        )
        prior = dedup.get(patched.files)
        if prior is None or (
            candidate.edit_count,
            -candidate.support_score,
            candidate.macro_ids,
        ) < (
            prior.edit_count,
            -prior.support_score,
            prior.macro_ids,
        ):
            dedup[patched.files] = candidate
    return tuple(sorted(
        dedup.values(),
        key=lambda candidate: (
            candidate.edit_count,
            -candidate.support_score,
            candidate.macro_ids,
            candidate.candidate_id,
        ),
    ))


def _repository_static_context(snapshot: RepositorySnapshot):
    modules, paths = _parse_repository(snapshot)
    functions_by_module = {name: _function_map(module) for name, module in modules.items()}
    imports = _collect_import_bindings(modules, functions_by_module)
    return modules, paths, functions_by_module, imports


def _module_dependency_order(
    modules: Mapping[str, ast.Module],
    imports: Mapping[str, Mapping[str, str]],
) -> tuple[str, ...]:
    dependencies: dict[str, set[str]] = {name: set() for name in modules}
    for module_name, bindings in imports.items():
        for target_key in bindings.values():
            target_module, _target_fn = target_key.rsplit('::', 1)
            if target_module != module_name:
                dependencies[module_name].add(target_module)
    state: dict[str, int] = {}
    order: list[str] = []

    def visit(module_name: str) -> None:
        mark = state.get(module_name, 0)
        if mark == 1:
            raise ValueError('repository import cycle detected')
        if mark == 2:
            return
        state[module_name] = 1
        for dependency in sorted(dependencies[module_name]):
            visit(dependency)
        state[module_name] = 2
        order.append(module_name)

    for module_name in sorted(modules):
        visit(module_name)
    return tuple(order)


def _repository_root_key(
    functions_by_module: Mapping[str, Mapping[str, ast.FunctionDef]],
    imports: Mapping[str, Mapping[str, str]],
) -> str:
    all_keys = {
        _function_key(module_name, fn_name)
        for module_name, funcs in functions_by_module.items()
        for fn_name in funcs
    }
    called: set[str] = set()
    for module_name in sorted(functions_by_module):
        local_funcs = functions_by_module[module_name]
        for fn_name in sorted(local_funcs):
            fn = local_funcs[fn_name]
            for call in (node for node in ast.walk(fn) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                if call.func.id in local_funcs:
                    called.add(_function_key(module_name, call.func.id))
                elif call.func.id in imports[module_name]:
                    called.add(imports[module_name][call.func.id])
    roots = sorted(all_keys - called)
    if len(roots) != 1:
        raise ValueError(f'repository must have one call-graph root, got {roots!r}')
    return roots[0]


def compile_repository_candidate(candidate: RepositoryPatchCandidate):
    snapshot = candidate.snapshot
    modules, _paths, functions_by_module, imports = _repository_static_context(snapshot)
    order = _module_dependency_order(modules, imports)
    root_key = _repository_root_key(functions_by_module, imports)
    namespaces: dict[str, dict[str, object]] = {}
    for module_name in order:
        namespace: dict[str, object] = {'__builtins__': {'abs': abs, 'max': max}}
        for local_name, target_key in imports[module_name].items():
            target_module, target_fn = target_key.rsplit('::', 1)
            if target_module not in namespaces or target_fn not in namespaces[target_module]:
                raise ValueError(f'import dependency not compiled: {target_key}')
            namespace[local_name] = namespaces[target_module][target_fn]
        stripped = ast.Module(
            body=[node for node in modules[module_name].body if not isinstance(node, ast.ImportFrom)],
            type_ignores=list(modules[module_name].type_ignores),
        )
        ast.fix_missing_locations(stripped)
        exec(compile(stripped, f'<repo:{module_name}:{candidate.candidate_id}>', 'exec'), namespace, namespace)
        namespaces[module_name] = namespace
    root_module, root_fn = root_key.rsplit('::', 1)
    return root_key, namespaces[root_module][root_fn]


def _repository_passes(
    candidate: RepositoryPatchCandidate,
    tests: Sequence[PatchTest],
) -> tuple[bool, int]:
    try:
        _root, fn = compile_repository_candidate(candidate)
    except Exception:
        return False, 0
    evaluations = 0
    for test in tests:
        evaluations += 1
        try:
            value = fn(*test.args)
        except Exception:
            return False, evaluations
        if value != test.expected:
            return False, evaluations
    return True, evaluations


def solve_repository_patch_with_sparse_tests(
    candidates: Sequence[RepositoryPatchCandidate],
    tests: Sequence[PatchTest],
    *,
    initial_test_ids: Sequence[str],
    hidden_order: Sequence[str],
    max_counterexamples: int = 32,
) -> PatchCegisReceipt:
    by_id = {test.test_id: test for test in tests}
    if len(by_id) != len(tuple(tests)):
        raise ValueError('duplicate test ids')
    initial = tuple(map(str, initial_test_ids))
    order = tuple(map(str, hidden_order))
    if not initial or len(set(initial)) != len(initial) or any(test_id not in by_id for test_id in initial):
        raise ValueError('invalid initial tests')
    if set(order) != set(by_id) or len(order) != len(by_id):
        raise ValueError('hidden_order must permute tests')
    observed = list(initial)
    observed_set = set(initial)
    survivors = list(candidates)
    rounds: list[PatchRound] = []
    total_evals = 0
    counterexamples = 0
    for round_index in range(int(max_counterexamples) + 1):
        visible = [by_id[test_id] for test_id in observed]
        next_survivors: list[RepositoryPatchCandidate] = []
        for candidate in survivors:
            ok, evaluations = _repository_passes(candidate, visible)
            total_evals += evaluations
            if ok:
                next_survivors.append(candidate)
        survivors = sorted(
            next_survivors,
            key=lambda candidate: (
                candidate.edit_count,
                -candidate.support_score,
                candidate.macro_ids,
                candidate.candidate_id,
            ),
        )
        if not survivors:
            rounds.append(PatchRound(round_index, tuple(observed), 0, None, None))
            return PatchCegisReceipt(
                'abstain', None, False, len(initial), counterexamples,
                tuple(observed), len(observed) / len(tests), tuple(rounds),
                len(candidates), 0, total_evals, 0, 'repository_version_space_empty',
            )
        selected = survivors[0]
        _root, fn = compile_repository_candidate(selected)
        hidden_failure: str | None = None
        for test_id in order:
            if test_id in observed_set:
                continue
            test = by_id[test_id]
            total_evals += 1
            try:
                value = fn(*test.args)
            except Exception:
                hidden_failure = test_id
                break
            if value != test.expected:
                hidden_failure = test_id
                break
        rounds.append(PatchRound(
            round_index,
            tuple(observed),
            len(survivors),
            selected.candidate_id,
            hidden_failure,
        ))
        if hidden_failure is None:
            exact_count = 0
            for test in tests:
                total_evals += 1
                try:
                    if fn(*test.args) == test.expected:
                        exact_count += 1
                except Exception:
                    pass
            exact = exact_count == len(tests)
            return PatchCegisReceipt(
                'accept' if exact else 'abstain', selected, exact, len(initial),
                counterexamples, tuple(observed), len(observed) / len(tests),
                tuple(rounds), len(candidates), len(survivors), total_evals,
                exact_count,
                'sparse_repository_patch_converged' if exact else 'final_repository_verification_failed',
            )
        if counterexamples >= int(max_counterexamples):
            break
        observed.append(hidden_failure)
        observed_set.add(hidden_failure)
        counterexamples += 1
    return PatchCegisReceipt(
        'abstain', survivors[0] if survivors else None, False, len(initial),
        counterexamples, tuple(observed), len(observed) / len(tests), tuple(rounds),
        len(candidates), len(survivors), total_evals, 0, 'repository_counterexample_budget_exhausted',
    )
