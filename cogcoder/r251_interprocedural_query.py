from __future__ import annotations

import ast
import hashlib
import itertools
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r247_executable_patch_cegis import (
    PatchCandidate,
    PatchCegisReceipt,
    PatchMacro,
    PatchRound,
    PatchTest,
    _BINOPS,
    _CMPOPS,
    _digest,
    _dump,
    _node_pairs,
    _operator_name,
    _wrap,
    infer_patch_macro,
)
from .r250_relational_query import (
    FactEdge,
    FactNode,
    InducedRelationalQuery,
    ProgramFactGraph,
    QueryPatchMacro,
    _apply_base_edit,
    _node_attrs,
    learn_induced_query,
    query_matches,
    TracePattern,
)


@dataclass
class ModuleFactGraph:
    nodes: dict[str, FactNode]
    edges: tuple[FactEdge, ...]
    ast_node_ids: dict[int, str]
    symbol_ids: dict[str, str]
    functions: dict[str, str]


def _parse_module(source: str) -> ast.Module:
    module = ast.parse(str(source))
    funcs = [node for node in module.body if isinstance(node, ast.FunctionDef)]
    if len(funcs) < 2 or any(isinstance(node, ast.AsyncFunctionDef) for node in module.body):
        raise ValueError('interprocedural source must contain at least two synchronous top-level functions')
    if len({fn.name for fn in funcs}) != len(funcs):
        raise ValueError('duplicate function names')
    return module


def _function_map(module: ast.Module) -> dict[str, ast.FunctionDef]:
    return {fn.name: fn for fn in module.body if isinstance(fn, ast.FunctionDef)}


def _scope_key(function_name: str, symbol: str) -> str:
    return f'{function_name}::{symbol}'


def _value_ref(graph_nodes, ast_node_ids, symbol_id, fn_name: str, value: ast.AST) -> str:
    if isinstance(value, ast.Name):
        return symbol_id(fn_name, value.id)
    return ast_node_ids[id(value)]


def _build_module_fact_graph_from_module(module: ast.Module) -> ModuleFactGraph:
    funcs = _function_map(module)
    nodes: dict[str, FactNode] = {}
    edges: list[FactEdge] = []
    ast_node_ids: dict[int, str] = {}
    symbol_ids: dict[str, str] = {}
    function_ids: dict[str, str] = {}

    def add(src: str, relation: str, dst: str) -> None:
        edges.append(FactEdge(src, relation, dst))

    for index, fn_name in enumerate(sorted(funcs)):
        fid = f'f{index:04d}'
        function_ids[fn_name] = fid
        nodes[fid] = FactNode(fid, 'function')

    all_ast: list[tuple[str, ast.AST]] = []
    for fn_name in sorted(funcs):
        for node in ast.walk(funcs[fn_name]):
            all_ast.append((fn_name, node))
    for index, (_fn_name, node) in enumerate(all_ast):
        nid = f'a{index:05d}'
        ast_node_ids[id(node)] = nid
        nodes[nid] = FactNode(nid, type(node).__name__.lower(), _node_attrs(node))

    def symbol_id(fn_name: str, name: str) -> str:
        key = _scope_key(fn_name, name)
        if key not in symbol_ids:
            sid = f's{len(symbol_ids):05d}'
            symbol_ids[key] = sid
            nodes[sid] = FactNode(sid, 'symbol')
        return symbol_ids[key]

    # Syntax + function ownership.
    for fn_name in sorted(funcs):
        fn = funcs[fn_name]
        fid = function_ids[fn_name]
        add(fid, 'FUNCTION_BODY', ast_node_ids[id(fn)])
        for parent in ast.walk(fn):
            pid = ast_node_ids[id(parent)]
            for child in ast.iter_child_nodes(parent):
                cid = ast_node_ids[id(child)]
                add(pid, 'AST_CHILD', cid)
                add(cid, 'AST_PARENT', pid)

        for index, arg in enumerate(fn.args.args):
            sid = symbol_id(fn_name, arg.arg)
            pid = f'p{fn_name}:{index}'
            nodes[pid] = FactNode(pid, 'parameter')
            add(sid, 'IS_PARAMETER', pid)

    # Intraprocedural flow and direct-use facts.
    for fn_name in sorted(funcs):
        fn = funcs[fn_name]
        fid = function_ids[fn_name]
        for node in ast.walk(fn):
            nid = ast_node_ids[id(node)]
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target = symbol_id(fn_name, node.targets[0].id)
                value = _value_ref(nodes, ast_node_ids, symbol_id, fn_name, node.value)
                add(nid, 'ASSIGNS', target)
                add(value, 'FLOW', target)
                if isinstance(node.value, ast.Name):
                    add(target, 'ALIAS_OF', symbol_id(fn_name, node.value.id))
            elif isinstance(node, ast.BinOp):
                add(nid, 'LEFT_OPERAND', _value_ref(nodes, ast_node_ids, symbol_id, fn_name, node.left))
                add(nid, 'RIGHT_OPERAND', _value_ref(nodes, ast_node_ids, symbol_id, fn_name, node.right))
            elif isinstance(node, ast.Compare):
                add(nid, 'COMPARE_LEFT', _value_ref(nodes, ast_node_ids, symbol_id, fn_name, node.left))
                for comp in node.comparators:
                    add(nid, 'COMPARE_RIGHT', _value_ref(nodes, ast_node_ids, symbol_id, fn_name, comp))
            elif isinstance(node, ast.Return) and node.value is not None:
                value = _value_ref(nodes, ast_node_ids, symbol_id, fn_name, node.value)
                add(nid, 'RETURN_VALUE', value)
                add(value, 'FLOW', nid)
                add(nid, 'FLOW', fid)

            if isinstance(node, ast.expr):
                for child in ast.walk(node):
                    if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                        sid = symbol_id(fn_name, child.id)
                        add(nid, 'USES', sid)
                        add(sid, 'FLOW', nid)

    # Static direct-call binding and return-to-call flow.
    for caller_name in sorted(funcs):
        caller = funcs[caller_name]
        for call in (n for n in ast.walk(caller) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)):
            callee = funcs.get(call.func.id)
            if callee is None:
                continue
            call_id = ast_node_ids[id(call)]
            callee_id = function_ids[callee.name]
            add(call_id, 'CALL_TARGET', callee_id)
            add(callee_id, 'FLOW', call_id)
            for index, arg in enumerate(call.args):
                if index >= len(callee.args.args):
                    break
                actual = _value_ref(nodes, ast_node_ids, symbol_id, caller_name, arg)
                formal = symbol_id(callee.name, callee.args.args[index].arg)
                add(actual, 'ARG_BIND', formal)
                add(actual, 'FLOW', formal)

    # Materialize generic transitive flow closure. This is intentionally low-level
    # and becomes a visible audit boundary for later relation-vocabulary induction.
    flow_adj: dict[str, set[str]] = {}
    for edge in edges:
        if edge.relation == 'FLOW':
            flow_adj.setdefault(edge.src, set()).add(edge.dst)
    closure_edges: list[FactEdge] = []
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
            closure_edges.append(FactEdge(src, 'FLOW*', dst))

    return ModuleFactGraph(nodes, tuple(sorted(set((*edges, *closure_edges)))), ast_node_ids, symbol_ids, function_ids)


def build_module_fact_graph(source: str) -> ModuleFactGraph:
    return _build_module_fact_graph_from_module(_parse_module(source))




def _interprocedural_trace_patterns(
    graph: ProgramFactGraph, site_node_id: str, *, max_depth: int = 7
) -> frozenset[TracePattern]:
    """Enumerate bounded relation/kind traces without path-instance explosion.

    Module graphs contain materialized FLOW* closure edges.  Once a trace takes a
    FLOW* edge there is no value in expanding through another concrete path: the
    closure edge already represents arbitrary call/return depth.  States are also
    deduplicated by (node, abstract trace), so graph aliases that produce the same
    observable relational hypothesis do not multiply the search space.
    """
    if site_node_id not in graph.nodes:
        raise ValueError('unknown site node')
    if int(max_depth) <= 0:
        raise ValueError('max_depth must be positive')
    adjacency: dict[str, list[FactEdge]] = {}
    for edge in graph.edges:
        if edge.relation in {'ALIAS_OF', 'AST_CHILD'}:
            continue
        adjacency.setdefault(edge.src, []).append(edge)
    for rows in adjacency.values():
        rows.sort()

    patterns: set[TracePattern] = set()
    queue: list[tuple[str, tuple[tuple[str, str], ...]]] = [(site_node_id, ())]
    seen = {(site_node_id, ())}
    cursor = 0
    while cursor < len(queue):
        current, steps = queue[cursor]
        cursor += 1
        if len(steps) >= int(max_depth):
            continue
        for edge in adjacency.get(current, ()):
            new_steps = (*steps, (edge.relation, graph.nodes[edge.dst].kind))
            pattern = TracePattern(new_steps)
            patterns.add(pattern)
            if edge.relation == 'FLOW*':
                continue
            state = (edge.dst, new_steps)
            if state not in seen:
                seen.add(state)
                queue.append(state)
    return frozenset(patterns)


def module_candidate_nodes(module: ast.Module, base: PatchMacro) -> tuple[ast.AST, ...]:
    nodes = list(ast.walk(module))
    if base.slot in {'binop', 'operand_wrapper'}:
        rows = [n for n in nodes if isinstance(n, ast.BinOp)]
        if base.slot == 'binop':
            rows = [n for n in rows if type(n.op).__name__ == base.src]
        else:
            rows = [n for n in rows if isinstance(n.left, ast.Name) and isinstance(n.right, ast.Name)]
        return tuple(rows)
    if base.slot == 'compare':
        return tuple(n for n in nodes if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]).__name__ == base.src)
    if base.slot == 'return_wrapper':
        return tuple(n for n in nodes if isinstance(n, ast.Return) and n.value is not None)
    raise ValueError('unsupported slot')


def infer_module_patch_macro(before_source: str, after_source: str) -> PatchMacro:
    before = _parse_module(before_source)
    after = _parse_module(after_source)
    before_funcs = _function_map(before); after_funcs = _function_map(after)
    if set(before_funcs) != set(after_funcs):
        raise ValueError('function set changed')
    changed = [name for name in sorted(before_funcs) if _dump(before_funcs[name]) != _dump(after_funcs[name])]
    if len(changed) != 1:
        raise ValueError(f'demonstration must change exactly one function, got {changed!r}')
    name = changed[0]
    return infer_patch_macro(ast.unparse(before_funcs[name]) + '\n', ast.unparse(after_funcs[name]) + '\n')


def _module_changed_labels(before: ast.Module, after: ast.Module, base: PatchMacro) -> tuple[bool, ...]:
    candidates = module_candidate_nodes(before, base)
    typ: type[ast.AST]
    if base.slot in {'binop', 'operand_wrapper'}:
        typ = ast.BinOp
    elif base.slot == 'compare':
        typ = ast.Compare
    else:
        typ = ast.Return
    before_raw = [n for n in ast.walk(before) if isinstance(n, typ)]
    after_raw = [n for n in ast.walk(after) if isinstance(n, typ)]
    if len(before_raw) != len(after_raw):
        raise ValueError('candidate count changed')
    changed_by_id = {id(a): _dump(a) != _dump(b) for a, b in zip(before_raw, after_raw)}
    return tuple(bool(changed_by_id[id(node)]) for node in candidates)


def _as_program_graph(graph: ModuleFactGraph, module: ast.Module) -> ProgramFactGraph:
    first = next(fn for fn in module.body if isinstance(fn, ast.FunctionDef))
    return ProgramFactGraph(first, graph.nodes, graph.edges, graph.ast_node_ids, graph.symbol_ids)


@dataclass(frozen=True, order=True)
class InterproceduralQueryMacro:
    macro_id: str
    base: PatchMacro
    query: InducedRelationalQuery
    support: int
    positive_sites: int
    negative_sites: int

    @property
    def slot(self) -> str:
        return self.base.slot


def _macro_id(base: PatchMacro, query: InducedRelationalQuery) -> str:
    payload = '|'.join([*(str(v) for v in base.signature), query.query_id])
    return 'ipq:' + hashlib.sha256(payload.encode()).hexdigest()[:20]


def learn_interprocedural_query_macro(
    demos: Sequence[tuple[str, str]], *, max_depth: int = 7
) -> InterproceduralQueryMacro:
    if len(demos) < 2:
        raise ValueError('at least two demonstrations required')
    bases: list[PatchMacro] = []
    positives = []
    negatives = []
    for before_source, after_source in demos:
        base = infer_module_patch_macro(before_source, after_source)
        bases.append(base)
        before = _parse_module(before_source); after = _parse_module(after_source)
        candidates = module_candidate_nodes(before, base)
        labels = _module_changed_labels(before, after, base)
        if len(candidates) != len(labels) or sum(labels) != 1:
            raise ValueError('each demo must contain exactly one positive candidate site')
        module_graph = _build_module_fact_graph_from_module(before)
        graph = _as_program_graph(module_graph, before)
        for node, label in zip(candidates, labels):
            traces = _interprocedural_trace_patterns(graph, module_graph.ast_node_ids[id(node)], max_depth=max_depth)
            (positives if label else negatives).append(traces)
    sig = bases[0].signature
    if any(base.signature != sig for base in bases):
        raise ValueError('demonstrations disagree on base patch')
    query = learn_induced_query(positives, negatives, max_conjunction=4)
    base0 = bases[0]
    supported = PatchMacro(base0.macro_id, *base0.signature, support=len(demos))
    return InterproceduralQueryMacro(_macro_id(supported, query), supported, query, len(demos), len(positives), len(negatives))


def learn_interprocedural_query_library(
    grouped_demos: Mapping[str, Sequence[tuple[str, str]]], *, max_depth: int = 7
) -> tuple[InterproceduralQueryMacro, ...]:
    return tuple(sorted((learn_interprocedural_query_macro(demos, max_depth=max_depth) for _, demos in sorted(grouped_demos.items())), key=lambda m: m.macro_id))


def _localize_interprocedural_macros(
    source: str, macros: Sequence[InterproceduralQueryMacro], *, max_depth: int = 7
) -> dict[str, tuple[int, ...]]:
    module = _parse_module(source)
    module_graph = _build_module_fact_graph_from_module(module)
    graph = _as_program_graph(module_graph, module)
    localized: dict[str, tuple[int, ...]] = {}
    for macro in macros:
        candidates = module_candidate_nodes(module, macro.base)
        selected: list[int] = []
        for index, node in enumerate(candidates):
            traces = _interprocedural_trace_patterns(
                graph, module_graph.ast_node_ids[id(node)], max_depth=max_depth
            )
            if query_matches(macro.query, traces):
                selected.append(index)
        localized[macro.macro_id] = tuple(selected)
    return localized


def _apply_localized_interprocedural_macros(
    source: str, macros: Sequence[InterproceduralQueryMacro], localized: Mapping[str, Sequence[int]]
) -> str:
    module = _parse_module(source)
    order = {'binop': 0, 'operand_wrapper': 1, 'compare': 2, 'return_wrapper': 3}
    planned: list[tuple[InterproceduralQueryMacro, tuple[ast.AST, ...]]] = []
    # Resolve every AST node against the immutable pre-edit module first.
    for macro in sorted(macros, key=lambda m: (order[m.slot], m.macro_id)):
        candidates = module_candidate_nodes(module, macro.base)
        indices = tuple(int(i) for i in localized.get(macro.macro_id, ()))
        if any(i < 0 or i >= len(candidates) for i in indices):
            raise ValueError('localized candidate index is out of range')
        planned.append((macro, tuple(candidates[i] for i in indices)))
    for macro, nodes in planned:
        for node in nodes:
            _apply_base_edit(node, macro.base)
    ast.fix_missing_locations(module)
    return ast.unparse(module) + '\n'


def apply_interprocedural_query_macros(
    source: str, macros: Sequence[InterproceduralQueryMacro], *, max_depth: int = 7
) -> str:
    localized = _localize_interprocedural_macros(source, macros, max_depth=max_depth)
    return _apply_localized_interprocedural_macros(source, macros, localized)


def enumerate_interprocedural_candidates(
    source: str, macros: Sequence[InterproceduralQueryMacro], *, max_depth: int = 7
) -> tuple[PatchCandidate, ...]:
    by_slot = {slot: [] for slot in ('binop', 'operand_wrapper', 'compare', 'return_wrapper')}
    for macro in macros:
        by_slot[macro.slot].append(macro)
    choices = [(None, *sorted(by_slot[slot], key=lambda m: m.macro_id)) for slot in ('binop', 'operand_wrapper', 'compare', 'return_wrapper')]
    # Query localization is invariant across a patch transaction.  Compute it once
    # per learned macro, not once per Cartesian candidate.
    localized = _localize_interprocedural_macros(source, macros, max_depth=max_depth)
    dedup: dict[str, PatchCandidate] = {}
    for selection in itertools.product(*choices):
        selected = tuple(m for m in selection if m is not None)
        patched = _apply_localized_interprocedural_macros(source, selected, localized)
        ids = tuple(sorted(m.macro_id for m in selected))
        candidate = PatchCandidate('ipc:' + _digest('|'.join(ids) + '|' + patched), ids, patched, sum(m.support for m in selected), len(selected))
        prior = dedup.get(patched)
        if prior is None or (candidate.edit_count, -candidate.support_score, candidate.macro_ids) < (prior.edit_count, -prior.support_score, prior.macro_ids):
            dedup[patched] = candidate
    return tuple(sorted(dedup.values(), key=lambda c: (c.edit_count, -c.support_score, c.macro_ids, c.candidate_id)))


def _root_function_name(module: ast.Module) -> str:
    funcs = _function_map(module)
    called = set()
    for fn in funcs.values():
        for call in (n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)):
            if call.func.id in funcs:
                called.add(call.func.id)
    roots = sorted(set(funcs) - called)
    if len(roots) != 1:
        raise ValueError(f'module must have one call-graph root, got {roots!r}')
    return roots[0]


def compile_interprocedural_candidate(candidate: PatchCandidate):
    module = _parse_module(candidate.source)
    root = _root_function_name(module)
    namespace = {'__builtins__': {'abs': abs, 'max': max}}
    exec(compile(candidate.source, f'<{candidate.candidate_id}>', 'exec'), namespace, namespace)
    return root, namespace[root]


def _passes(candidate: PatchCandidate, tests: Sequence[PatchTest]) -> tuple[bool, int]:
    try:
        _name, fn = compile_interprocedural_candidate(candidate)
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


def solve_interprocedural_patch_with_sparse_tests(
    candidates: Sequence[PatchCandidate], tests: Sequence[PatchTest], *, initial_test_ids: Sequence[str], hidden_order: Sequence[str], max_counterexamples: int = 32
) -> PatchCegisReceipt:
    by_id = {t.test_id: t for t in tests}
    if len(by_id) != len(tuple(tests)):
        raise ValueError('duplicate test ids')
    initial = tuple(map(str, initial_test_ids)); order = tuple(map(str, hidden_order))
    if not initial or len(set(initial)) != len(initial) or any(t not in by_id for t in initial):
        raise ValueError('invalid initial tests')
    if set(order) != set(by_id) or len(order) != len(by_id):
        raise ValueError('hidden_order must permute tests')
    observed = list(initial); observed_set = set(initial); survivors = list(candidates)
    rounds = []; total_evals = 0; counterexamples = 0
    for round_index in range(int(max_counterexamples) + 1):
        visible = [by_id[tid] for tid in observed]
        next_survivors = []
        for candidate in survivors:
            ok, evals = _passes(candidate, visible); total_evals += evals
            if ok: next_survivors.append(candidate)
        survivors = sorted(next_survivors, key=lambda c: (c.edit_count, -c.support_score, c.macro_ids, c.candidate_id))
        if not survivors:
            rounds.append(PatchRound(round_index, tuple(observed), 0, None, None))
            return PatchCegisReceipt('abstain', None, False, len(initial), counterexamples, tuple(observed), len(observed)/len(tests), tuple(rounds), len(candidates), 0, total_evals, 0, 'version_space_empty')
        selected = survivors[0]
        _name, fn = compile_interprocedural_candidate(selected)
        hidden_failure = None
        for tid in order:
            if tid in observed_set: continue
            test = by_id[tid]; total_evals += 1
            try: value = fn(*test.args)
            except Exception:
                hidden_failure = tid; break
            if value != test.expected:
                hidden_failure = tid; break
        rounds.append(PatchRound(round_index, tuple(observed), len(survivors), selected.candidate_id, hidden_failure))
        if hidden_failure is None:
            exact_count = 0
            for test in tests:
                total_evals += 1
                try:
                    if fn(*test.args) == test.expected: exact_count += 1
                except Exception: pass
            exact = exact_count == len(tests)
            return PatchCegisReceipt('accept' if exact else 'abstain', selected, exact, len(initial), counterexamples, tuple(observed), len(observed)/len(tests), tuple(rounds), len(candidates), len(survivors), total_evals, exact_count, 'sparse_interprocedural_patch_converged' if exact else 'final_verification_failed')
        if counterexamples >= int(max_counterexamples): break
        observed.append(hidden_failure); observed_set.add(hidden_failure); counterexamples += 1
    return PatchCegisReceipt('abstain', survivors[0] if survivors else None, False, len(initial), counterexamples, tuple(observed), len(observed)/len(tests), tuple(rounds), len(candidates), len(survivors), total_evals, 0, 'counterexample_budget_exhausted')
