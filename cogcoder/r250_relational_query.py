from __future__ import annotations

import ast
import hashlib
import itertools
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r247_executable_patch_cegis import PatchMacro, _parse_function


@dataclass(frozen=True, order=True)
class FactNode:
    node_id: str
    kind: str
    attrs: tuple[tuple[str, str], ...] = ()

    def attr(self, key: str) -> str | None:
        for k, v in self.attrs:
            if k == key:
                return v
        return None


@dataclass(frozen=True, order=True)
class FactEdge:
    src: str
    relation: str
    dst: str


@dataclass
class ProgramFactGraph:
    function: ast.FunctionDef
    nodes: dict[str, FactNode]
    edges: tuple[FactEdge, ...]
    ast_node_ids: dict[int, str]
    symbol_ids: dict[str, str]


@dataclass(frozen=True, order=True)
class TracePattern:
    steps: tuple[tuple[str, str], ...]

    @property
    def signature(self) -> str:
        return '|'.join(f'{relation}:{kind}' for relation, kind in self.steps)


def _kind(node: ast.AST) -> str:
    return type(node).__name__.lower()


def _node_attrs(node: ast.AST) -> tuple[tuple[str, str], ...]:
    attrs: list[tuple[str, str]] = []
    if isinstance(node, ast.BinOp):
        attrs.append(('op', type(node.op).__name__))
        attrs.append(('left_kind', _kind(node.left)))
        attrs.append(('right_kind', _kind(node.right)))
    elif isinstance(node, ast.Compare) and len(node.ops) == 1:
        attrs.append(('op', type(node.ops[0]).__name__))
    return tuple(sorted(attrs))


def _build_program_fact_graph_from_function(fn: ast.FunctionDef) -> ProgramFactGraph:
    nodes: dict[str, FactNode] = {}
    edges: list[FactEdge] = []
    ast_node_ids: dict[int, str] = {}
    symbol_ids: dict[str, str] = {}

    ast_nodes = list(ast.walk(fn))
    for index, node in enumerate(ast_nodes):
        node_id = f'a{index:04d}'
        ast_node_ids[id(node)] = node_id
        nodes[node_id] = FactNode(node_id, _kind(node), _node_attrs(node))

    def symbol_id(name: str) -> str:
        if name not in symbol_ids:
            node_id = f's{len(symbol_ids):04d}'
            symbol_ids[name] = node_id
            nodes[node_id] = FactNode(node_id, 'symbol')
        return symbol_ids[name]

    def add(src: str, relation: str, dst: str) -> None:
        edges.append(FactEdge(src, relation, dst))

    def value_node(value: ast.AST) -> str:
        if isinstance(value, ast.Name):
            return symbol_id(value.id)
        return ast_node_ids[id(value)]

    # Generic syntax graph. Raw identifiers are never serialized into node kinds or relations.
    for parent in ast_nodes:
        parent_id = ast_node_ids[id(parent)]
        for child in ast.iter_child_nodes(parent):
            child_id = ast_node_ids[id(child)]
            add(parent_id, 'AST_CHILD', child_id)
            add(child_id, 'AST_PARENT', parent_id)

    # Parameter-origin markers provide a low-level binding fact without exposing names.
    for index, arg in enumerate(fn.args.args):
        sid = symbol_id(arg.arg)
        pid = f'p{index:04d}'
        nodes[pid] = FactNode(pid, 'parameter')
        add(sid, 'IS_PARAMETER', pid)

    for node in ast_nodes:
        node_id = ast_node_ids[id(node)]
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            sid = symbol_id(node.targets[0].id)
            add(node_id, 'ASSIGNS', sid)
            add(sid, 'DEFINED_BY', value_node(node.value))
            if isinstance(node.value, ast.Name):
                add(sid, 'ALIAS_OF', symbol_id(node.value.id))
        elif isinstance(node, ast.BinOp):
            add(node_id, 'LEFT_OPERAND', value_node(node.left))
            add(node_id, 'RIGHT_OPERAND', value_node(node.right))
        elif isinstance(node, ast.Call):
            for arg in node.args:
                add(node_id, 'CALL_ARG', value_node(arg))
        elif isinstance(node, ast.Compare):
            add(node_id, 'COMPARE_LEFT', value_node(node.left))
            for comparator in node.comparators:
                add(node_id, 'COMPARE_RIGHT', value_node(comparator))
        elif isinstance(node, ast.If):
            add(node_id, 'IF_TEST', ast_node_ids[id(node.test)])
            for child in node.body:
                add(node_id, 'IF_TRUE_CHILD', ast_node_ids[id(child)])
            for child in node.orelse:
                add(node_id, 'IF_FALSE_CHILD', ast_node_ids[id(child)])
        elif isinstance(node, ast.Return) and node.value is not None:
            add(node_id, 'RETURN_VALUE', value_node(node.value))

    # Direct use facts for expression nodes. These are syntactic/binding facts, not semantic labels.
    for node in ast_nodes:
        if not isinstance(node, ast.expr):
            continue
        node_id = ast_node_ids[id(node)]
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                add(node_id, 'USES', symbol_id(child.id))

    return ProgramFactGraph(fn, nodes, tuple(sorted(set(edges))), ast_node_ids, symbol_ids)


def build_program_fact_graph(source: str) -> ProgramFactGraph:
    return _build_program_fact_graph_from_function(_parse_function(source))


def candidate_site_ids(graph: ProgramFactGraph, base: PatchMacro) -> tuple[str, ...]:
    out: list[str] = []
    for node_id, node in sorted(graph.nodes.items()):
        if base.slot == 'binop' and node.kind == 'binop' and node.attr('op') == base.src:
            out.append(node_id)
        elif base.slot == 'operand_wrapper' and node.kind == 'binop':
            if node.attr('left_kind') == 'name' and node.attr('right_kind') == 'name':
                out.append(node_id)
        elif base.slot == 'compare' and node.kind == 'compare' and node.attr('op') == base.src:
            out.append(node_id)
        elif base.slot == 'return_wrapper' and node.kind == 'return':
            out.append(node_id)
    return tuple(out)


def _adjacency(graph: ProgramFactGraph) -> dict[str, tuple[FactEdge, ...]]:
    grouped: dict[str, list[FactEdge]] = {}
    for edge in graph.edges:
        if edge.relation in {'ALIAS_OF', 'AST_CHILD'}:
            continue
        grouped.setdefault(edge.src, []).append(edge)
    return {src: tuple(sorted(items)) for src, items in grouped.items()}


def _alias_closure(graph: ProgramFactGraph) -> dict[str, tuple[str, ...]]:
    direct: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.relation == 'ALIAS_OF':
            direct.setdefault(edge.src, []).append(edge.dst)
    out: dict[str, tuple[str, ...]] = {}
    for node_id, node in graph.nodes.items():
        if node.kind != 'symbol':
            continue
        seen = {node_id}
        stack = [node_id]
        while stack:
            cur = stack.pop()
            for nxt in direct.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        out[node_id] = tuple(sorted(seen))
    return out


def trace_patterns_for_site(graph: ProgramFactGraph, site_node_id: str, max_depth: int = 6) -> frozenset[TracePattern]:
    if site_node_id not in graph.nodes:
        raise ValueError('unknown site node')
    if max_depth <= 0:
        raise ValueError('max_depth must be positive')

    adjacency = _adjacency(graph)
    alias_closure = _alias_closure(graph)
    patterns: set[TracePattern] = set()
    # state: node, steps, visited node ids, whether the reflexive/transitive alias token was used
    queue: list[tuple[str, tuple[tuple[str, str], ...], frozenset[str], bool]] = [
        (site_node_id, (), frozenset({site_node_id}), False)
    ]
    cursor = 0
    while cursor < len(queue):
        current, steps, visited, used_alias_star = queue[cursor]
        cursor += 1
        if len(steps) >= max_depth:
            continue

        next_edges = list(adjacency.get(current, ()))
        if graph.nodes[current].kind == 'symbol' and not used_alias_star:
            for dst in alias_closure.get(current, (current,)):
                next_edges.append(FactEdge(current, 'ALIAS_OF*', dst))

        for edge in sorted(next_edges):
            dst_kind = graph.nodes[edge.dst].kind
            new_steps = (*steps, (edge.relation, dst_kind))
            patterns.add(TracePattern(new_steps))
            is_alias_star = edge.relation == 'ALIAS_OF*'
            if edge.dst in visited and not (is_alias_star and edge.dst == current):
                continue
            new_visited = visited if edge.dst == current else frozenset((*visited, edge.dst))
            queue.append((edge.dst, new_steps, new_visited, used_alias_star or is_alias_star))

    return frozenset(patterns)


@dataclass(frozen=True, order=True)
class InducedRelationalQuery:
    query_id: str
    patterns: tuple[TracePattern, ...]
    support: int
    positive_sites: int
    negative_sites: int

    def __post_init__(self) -> None:
        if not self.patterns:
            raise ValueError('query must contain at least one trace pattern')
        canonical = tuple(sorted(set(self.patterns), key=lambda p: p.signature))
        object.__setattr__(self, 'patterns', canonical)
        object.__setattr__(self, 'support', int(self.support))
        object.__setattr__(self, 'positive_sites', int(self.positive_sites))
        object.__setattr__(self, 'negative_sites', int(self.negative_sites))
        if self.support <= 0 or self.positive_sites <= 0:
            raise ValueError('query support/positives must be positive')


def query_matches(query: InducedRelationalQuery, trace_set: frozenset[TracePattern] | set[TracePattern]) -> bool:
    available = set(trace_set)
    return all(pattern in available for pattern in query.patterns)


def _query_id(patterns: Sequence[TracePattern]) -> str:
    payload = '\n'.join(sorted(pattern.signature for pattern in patterns))
    return 'irq:' + hashlib.sha256(payload.encode()).hexdigest()[:20]


def learn_induced_query(
    positive_trace_sets: Sequence[frozenset[TracePattern] | set[TracePattern]],
    negative_trace_sets: Sequence[frozenset[TracePattern] | set[TracePattern]],
    *,
    max_conjunction: int = 4,
) -> InducedRelationalQuery:
    positives = tuple(frozenset(items) for items in positive_trace_sets)
    negatives = tuple(frozenset(items) for items in negative_trace_sets)
    if not positives:
        raise ValueError('at least one positive site is required')
    if max_conjunction <= 0:
        raise ValueError('max_conjunction must be positive')

    common = set(positives[0])
    for positive in positives[1:]:
        common.intersection_update(positive)
    ordered = tuple(sorted(common, key=lambda p: (len(p.steps), p.signature)))
    if not ordered:
        raise ValueError('trace grammar cannot separate positive and negative sites')

    upper = min(max_conjunction, len(ordered))
    for width in range(1, upper + 1):
        candidates: list[tuple[tuple[int, int, tuple[str, ...]], tuple[TracePattern, ...]]] = []
        for combo in itertools.combinations(ordered, width):
            if any(all(pattern in negative for pattern in combo) for negative in negatives):
                continue
            signatures = tuple(pattern.signature for pattern in combo)
            description_length = sum(len(pattern.steps) for pattern in combo)
            key = (description_length, width, signatures)
            candidates.append((key, combo))
        if candidates:
            _key, chosen = min(candidates, key=lambda item: item[0])
            return InducedRelationalQuery(
                _query_id(chosen),
                tuple(chosen),
                support=len(positives),
                positive_sites=len(positives),
                negative_sites=len(negatives),
            )

    raise ValueError('trace grammar cannot separate positive and negative sites')

from .r247_executable_patch_cegis import PatchCandidate, _BINOPS, _CMPOPS, _digest, _wrap, infer_patch_macro
from .r249_relational_context import _candidate_nodes, _changed_labels


@dataclass(frozen=True, order=True)
class QueryPatchMacro:
    macro_id: str
    base: PatchMacro
    query: InducedRelationalQuery
    support: int
    positive_sites: int
    negative_sites: int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'support', int(self.support))
        object.__setattr__(self, 'positive_sites', int(self.positive_sites))
        object.__setattr__(self, 'negative_sites', int(self.negative_sites))
        if self.support <= 0 or self.positive_sites <= 0:
            raise ValueError('macro support/positives must be positive')

    @property
    def slot(self) -> str:
        return self.base.slot


def _query_patch_macro_id(base: PatchMacro, query: InducedRelationalQuery) -> str:
    payload = '|'.join((*('' if v is None else str(v) for v in base.signature), query.query_id))
    return 'qpm:' + hashlib.sha256(payload.encode()).hexdigest()[:20]


def learn_query_patch_macro(demos: Sequence[tuple[str, str]], *, max_depth: int = 7) -> QueryPatchMacro:
    if len(demos) < 2:
        raise ValueError('at least two demonstrations are required')
    bases: list[PatchMacro] = []
    positives: list[frozenset[TracePattern]] = []
    negatives: list[frozenset[TracePattern]] = []

    for before_source, after_source in demos:
        base = infer_patch_macro(before_source, after_source)
        bases.append(base)
        before_fn = _parse_function(before_source)
        after_fn = _parse_function(after_source)
        candidate_nodes = _candidate_nodes(before_fn, base)
        labels = _changed_labels(before_fn, after_fn, base)
        if len(candidate_nodes) != len(labels) or sum(labels) != 1:
            raise ValueError('each demonstration must contain exactly one changed candidate site')
        graph = _build_program_fact_graph_from_function(before_fn)
        for node, changed in zip(candidate_nodes, labels):
            site_id = graph.ast_node_ids[id(node)]
            traces = trace_patterns_for_site(graph, site_id, max_depth=max_depth)
            (positives if changed else negatives).append(traces)

    signature = bases[0].signature
    if any(base.signature != signature for base in bases):
        raise ValueError('demonstrations disagree on base patch macro')
    query = learn_induced_query(tuple(positives), tuple(negatives))
    base0 = bases[0]
    supported_base = PatchMacro(base0.macro_id, *base0.signature, support=len(demos))
    return QueryPatchMacro(
        _query_patch_macro_id(supported_base, query),
        supported_base,
        query,
        support=len(demos),
        positive_sites=len(positives),
        negative_sites=len(negatives),
    )


def learn_query_patch_library(
    grouped_demos: Mapping[str, Sequence[tuple[str, str]]], *, max_depth: int = 7
) -> tuple[QueryPatchMacro, ...]:
    macros = [learn_query_patch_macro(demos, max_depth=max_depth) for _name, demos in sorted(grouped_demos.items())]
    return tuple(sorted(macros, key=lambda macro: macro.macro_id))


def _apply_base_edit(node: ast.AST, base: PatchMacro) -> None:
    if isinstance(node, ast.BinOp):
        if base.slot == 'binop' and base.kind == 'replace':
            if type(node.op).__name__ == base.src and base.dst in _BINOPS:
                node.op = _BINOPS[str(base.dst)]()
        elif base.slot == 'operand_wrapper' and base.kind == 'wrap':
            if isinstance(node.left, ast.Name) and isinstance(node.right, ast.Name):
                node.left = _wrap(node.left, str(base.dst))
                node.right = _wrap(node.right, str(base.dst))
    elif isinstance(node, ast.Compare) and base.slot == 'compare' and base.kind == 'replace':
        if len(node.ops) == 1 and type(node.ops[0]).__name__ == base.src and base.dst in _CMPOPS:
            node.ops[0] = _CMPOPS[str(base.dst)]()
    elif isinstance(node, ast.Return) and base.slot == 'return_wrapper' and base.kind == 'wrap':
        if node.value is not None:
            node.value = _wrap(node.value, str(base.dst))


def apply_query_patch_macros(source: str, macros: Sequence[QueryPatchMacro], *, max_depth: int = 7) -> str:
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1:
        raise ValueError('source must contain exactly one synchronous function')
    fn = functions[0]
    order = {'binop': 0, 'operand_wrapper': 1, 'compare': 2, 'return_wrapper': 3}
    ordered = tuple(sorted(macros, key=lambda item: (order[item.slot], item.macro_id)))

    # Causal localization is evaluated against the immutable pre-edit program graph.
    # Otherwise an earlier edit (for example wrapping operands) can erase the very
    # evidence a later edit needs in order to identify its original causal site.
    graph = _build_program_fact_graph_from_function(fn)
    selections: list[tuple[QueryPatchMacro, tuple[ast.AST, ...]]] = []
    for macro in ordered:
        selected: list[ast.AST] = []
        for node in _candidate_nodes(fn, macro.base):
            site_id = graph.ast_node_ids[id(node)]
            traces = trace_patterns_for_site(graph, site_id, max_depth=max_depth)
            if query_matches(macro.query, traces):
                selected.append(node)
        selections.append((macro, tuple(selected)))

    for macro, selected in selections:
        for node in selected:
            _apply_base_edit(node, macro.base)
        ast.fix_missing_locations(tree)
    return ast.unparse(tree) + '\n'


def enumerate_query_patch_candidates(
    source: str, macros: Sequence[QueryPatchMacro], *, max_depth: int = 7
) -> tuple[PatchCandidate, ...]:
    by_slot: dict[str, list[QueryPatchMacro]] = {slot: [] for slot in ('binop', 'operand_wrapper', 'compare', 'return_wrapper')}
    for macro in macros:
        by_slot[macro.slot].append(macro)
    choices = [(None, *sorted(by_slot[slot], key=lambda item: item.macro_id)) for slot in ('binop', 'operand_wrapper', 'compare', 'return_wrapper')]
    dedup: dict[str, PatchCandidate] = {}
    for selection in itertools.product(*choices):
        selected = tuple(item for item in selection if item is not None)
        patched = apply_query_patch_macros(source, selected, max_depth=max_depth)
        ids = tuple(sorted(item.macro_id for item in selected))
        candidate_id = 'qpc:' + _digest('|'.join(ids) + '|' + patched)
        candidate = PatchCandidate(candidate_id, ids, patched, sum(item.support for item in selected), len(selected))
        prior = dedup.get(patched)
        if prior is None or (candidate.edit_count, -candidate.support_score, candidate.macro_ids) < (
            prior.edit_count,
            -prior.support_score,
            prior.macro_ids,
        ):
            dedup[patched] = candidate
    return tuple(sorted(dedup.values(), key=lambda item: (item.edit_count, -item.support_score, item.macro_ids, item.candidate_id)))
