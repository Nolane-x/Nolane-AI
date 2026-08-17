import pytest

from cogcoder.r251_interprocedural_query import (
    build_module_fact_graph,
    learn_interprocedural_query_macro,
    apply_interprocedural_query_macros,
    module_candidate_nodes,
)
from benchmarks.kfigg.r251_interprocedural_query_transfer import training_demo


def test_module_graph_contains_call_return_flow_between_functions():
    before, _ = training_demo('binop_add', 0, call_depth=1)
    graph = build_module_fact_graph(before)
    relations = {edge.relation for edge in graph.edges}
    assert {'CALL_TARGET', 'ARG_BIND', 'FLOW', 'FLOW*'} <= relations
    assert len(graph.functions) >= 3


def test_learns_query_when_r250_single_function_scope_is_insufficient():
    demos = (
        training_demo('binop_add', 0, call_depth=1),
        training_demo('binop_add', 1, call_depth=2),
    )
    macro = learn_interprocedural_query_macro(demos, max_depth=7)
    assert macro.support == 2
    assert macro.query.patterns
    assert all('train_' not in pattern.signature for pattern in macro.query.patterns)


def test_applies_edit_only_to_interprocedurally_relevant_site():
    before, after = training_demo('binop_add', 1, call_depth=2)
    macro = learn_interprocedural_query_macro((
        training_demo('binop_add', 0, call_depth=1),
        training_demo('binop_add', 1, call_depth=2),
    ))
    patched = apply_interprocedural_query_macros(before, (macro,))
    assert patched == after
