from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r250_relational_query import (
    build_program_fact_graph,
    candidate_site_ids,
    trace_patterns_for_site,
)


def _base():
    return PatchMacro('pm:test', 'binop', 'replace', 'Sub', 'Add')


def _source(alias_depth: int = 1) -> str:
    aliases = []
    cur = 'a'
    for i in range(alias_depth):
        nxt = f'a{i}'
        aliases.append(f'    {nxt} = {cur}')
        cur = nxt
    body = [
        'def f(a, b):',
        *aliases,
        '    local = abs(a)',
        f'    good = {cur} - b',
        '    bad = local - b',
        '    return good + bad',
    ]
    return '\n'.join(body) + '\n'


def _sigs(graph, site_id):
    return {p.signature for p in trace_patterns_for_site(graph, site_id, max_depth=7)}


def test_low_level_trace_distinguishes_parameter_alias_origin_from_call_origin_without_names():
    graph = build_program_fact_graph(_source(alias_depth=1))
    sites = candidate_site_ids(graph, _base())
    assert len(sites) == 2
    sig_sets = [_sigs(graph, site_id) for site_id in sites]

    direct_param_pattern = 'LEFT_OPERAND:symbol|ALIAS_OF*:symbol|IS_PARAMETER:parameter'
    call_pattern_fragment = 'DEFINED_BY:call'
    assert sum(direct_param_pattern in sigs for sigs in sig_sets) == 1
    assert sum(any(call_pattern_fragment in sig for sig in sigs) for sigs in sig_sets) == 1

    serialized = '\n'.join(sorted(sig for sigs in sig_sets for sig in sigs))
    for raw_name in ('a0', 'local', 'good', 'bad'):
        assert raw_name not in serialized


def test_alias_closure_normalizes_unseen_alias_depth_to_same_parameter_origin_trace():
    shallow = build_program_fact_graph(_source(alias_depth=1))
    deep = build_program_fact_graph(_source(alias_depth=3))
    pattern = 'LEFT_OPERAND:symbol|ALIAS_OF*:symbol|IS_PARAMETER:parameter'

    assert any(pattern in _sigs(shallow, site) for site in candidate_site_ids(shallow, _base()))
    assert any(pattern in _sigs(deep, site) for site in candidate_site_ids(deep, _base()))


def _pattern(label: str):
    from cogcoder.r250_relational_query import TracePattern
    return TracePattern(((label, 'symbol'),))


def test_induced_query_chooses_shortest_discriminative_conjunction_deterministically():
    import cogcoder.r250_relational_query as r250
    assert hasattr(r250, 'learn_induced_query'), 'R2.50 query induction API missing'
    a, b, c = (_pattern(x) for x in ('A', 'B', 'C'))
    positives = (frozenset({a, b, c}), frozenset({a, b, c}))
    negatives = (frozenset({a, c}), frozenset({b, c}))

    query = r250.learn_induced_query(positives, negatives)
    assert tuple(p.signature for p in query.patterns) == (a.signature, b.signature)
    assert query.support == 2
    assert query.positive_sites == 2
    assert query.negative_sites == 2
    assert r250.query_matches(query, positives[0]) is True
    assert all(r250.query_matches(query, n) is False for n in negatives)

    reversed_query = r250.learn_induced_query(tuple(reversed(positives)), tuple(reversed(negatives)))
    assert reversed_query.query_id == query.query_id
    assert reversed_query.patterns == query.patterns


def test_induced_query_fails_closed_when_trace_grammar_cannot_separate_sites():
    import pytest
    import cogcoder.r250_relational_query as r250
    assert hasattr(r250, 'learn_induced_query'), 'R2.50 query induction API missing'
    a = _pattern('A')
    positives = (frozenset({a}), frozenset({a}))
    negatives = (frozenset({a}),)
    with pytest.raises(ValueError, match='cannot separate'):
        r250.learn_induced_query(positives, negatives)


def _adversarial_source(*, call_side: str, target_alias_depth: int, after: bool) -> str:
    if call_side not in {'left', 'right'}:
        raise ValueError(call_side)
    lines = ['def f(a, b, cap, alt):']
    if call_side == 'left':
        lines += ['    d0 = abs(a)']
        decoy_left, decoy_right = 'd0', 'b'
    else:
        lines += ['    d0 = abs(b)']
        decoy_left, decoy_right = 'a', 'd0'
    lines += [
        f'    shadow = {decoy_left} - {decoy_right}',
        '    if shadow < alt:',
        '        return shadow + 100',
    ]
    left_current = 'a'
    right_current = 'b'
    for i in range(target_alias_depth):
        lines.append(f'    ta{i} = {left_current}')
        lines.append(f'    tb{i} = {right_current}')
        left_current = f'ta{i}'
        right_current = f'tb{i}'
    op = '+' if after else '-'
    lines += [
        f'    core = {left_current} {op} {right_current}',
        '    if core < cap:',
        '        return core + 10',
        '    return cap + alt + shadow + core',
    ]
    return '\n'.join(lines) + '\n'


def _assert_r249_sites_are_indistinguishable(source: str):
    from cogcoder.r247_executable_patch_cegis import _parse_function, PatchMacro
    from cogcoder.r249_relational_context import _candidate_nodes, relational_features_for_site
    base = PatchMacro('pm:test', 'binop', 'replace', 'Sub', 'Add')
    fn = _parse_function(source)
    sites = _candidate_nodes(fn, base)
    assert len(sites) == 2
    feature_sets = [relational_features_for_site(fn, site) for site in sites]
    assert feature_sets[0] == feature_sets[1]
    return feature_sets


def test_query_patch_macro_learns_where_to_edit_when_complete_r249_features_are_identical():
    import ast
    import cogcoder.r250_relational_query as r250
    assert hasattr(r250, 'learn_query_patch_macro'), 'query-conditioned patch macro API missing'

    demos = (
        (_adversarial_source(call_side='left', target_alias_depth=0, after=False), _adversarial_source(call_side='left', target_alias_depth=0, after=True)),
        (_adversarial_source(call_side='right', target_alias_depth=2, after=False), _adversarial_source(call_side='right', target_alias_depth=2, after=True)),
    )
    for before, _after in demos:
        _assert_r249_sites_are_indistinguishable(before)

    macro = r250.learn_query_patch_macro(demos)
    assert macro.base.signature == ('binop', 'replace', 'Sub', 'Add')
    assert len(macro.query.patterns) == 2
    signatures = tuple(p.signature for p in macro.query.patterns)
    assert 'LEFT_OPERAND:symbol|ALIAS_OF*:symbol|IS_PARAMETER:parameter' in signatures
    assert 'RIGHT_OPERAND:symbol|ALIAS_OF*:symbol|IS_PARAMETER:parameter' in signatures

    heldout_before = _adversarial_source(call_side='left', target_alias_depth=4, after=False)
    heldout_after = _adversarial_source(call_side='left', target_alias_depth=4, after=True)
    _assert_r249_sites_are_indistinguishable(heldout_before)
    patched = r250.apply_query_patch_macros(heldout_before, (macro,))
    assert ast.dump(ast.parse(patched), include_attributes=False) == ast.dump(ast.parse(heldout_after), include_attributes=False)

    import re
    serialized = macro.query.query_id + '\n' + '\n'.join(signatures)
    for raw_name in ('a', 'b', 'cap', 'alt', 'shadow', 'core', 'd0', 'ta0', 'tb0'):
        assert re.search(rf'\b{re.escape(raw_name)}\b', serialized) is None


def test_query_patch_composition_localizes_all_edits_on_pre_edit_graph():
    import ast
    import cogcoder.r250_relational_query as r250

    def demo(kind: str, call_side: str, depth: int):
        if kind == 'binop_add':
            before = _adversarial_source(call_side=call_side, target_alias_depth=depth, after=False)
            after = before.replace('core = ' + ('ta%d' % (depth - 1) if depth else 'a') + ' - ', 'core = ' + ('ta%d' % (depth - 1) if depth else 'a') + ' + ', 1)
            return before, after
        raise AssertionError(kind)

    # Use explicit sources so each learned macro sees the same causal target but a different base edit.
    binop_demos = (
        (_adversarial_source(call_side='left', target_alias_depth=0, after=False), _adversarial_source(call_side='left', target_alias_depth=0, after=True)),
        (_adversarial_source(call_side='right', target_alias_depth=2, after=False), _adversarial_source(call_side='right', target_alias_depth=2, after=True)),
    )

    def wrapper_pair(call_side: str, depth: int):
        before = _adversarial_source(call_side=call_side, target_alias_depth=depth, after=True)
        left = 'a' if depth == 0 else f'ta{depth - 1}'
        right = 'b' if depth == 0 else f'tb{depth - 1}'
        after = before.replace(f'core = {left} + {right}', f'core = abs({left}) + abs({right})', 1)
        return before, after

    def compare_pair(call_side: str, depth: int):
        before = _adversarial_source(call_side=call_side, target_alias_depth=depth, after=False)
        after = before.replace('if core < cap:', 'if core <= cap:', 1)
        return before, after

    macros = (
        r250.learn_query_patch_macro(binop_demos),
        r250.learn_query_patch_macro((wrapper_pair('left', 0), wrapper_pair('right', 2))),
        r250.learn_query_patch_macro((compare_pair('left', 0), compare_pair('right', 2))),
    )

    before = _adversarial_source(call_side='left', target_alias_depth=4, after=False)
    left, right = 'ta3', 'tb3'
    expected = _adversarial_source(call_side='left', target_alias_depth=4, after=True)
    expected = expected.replace(f'core = {left} + {right}', f'core = abs({left}) + abs({right})', 1)
    expected = expected.replace('if core < cap:', 'if core <= cap:', 1)
    patched = r250.apply_query_patch_macros(before, macros)
    assert ast.dump(ast.parse(patched), include_attributes=False) == ast.dump(ast.parse(expected), include_attributes=False)
