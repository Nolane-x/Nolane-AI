import itertools

import pytest

from cogcoder.r239_predicate_macros import ProbeMacro, instantiate_macro
from cogcoder.r239_typed_probe_dsl import (
    ProbeType,
    and_probe,
    bool_atom,
    evaluate_typed_probe,
    or_probe,
    typed_prediction_row,
    xor_probe,
)
from cogcoder.r243_macro_composition import CompositionDiscoveryDecision
from cogcoder.r244_recursive_abstraction import (
    RecursiveAbstractionRecord,
    RecursiveCompositionDecision,
    build_recursive_application_frontier,
    conditional_composition_novelty,
    flat_unique_binding_count,
    promote_composition_batch,
    propagate_quarantine,
)


def macro(mid, op):
    t = op(bool_atom('$p0'), bool_atom('$p1'))
    return ProbeMacro(mid, t, (ProbeType.BOOL, ProbeType.BOOL), 6, 5.0, t.mdl_cost, 2)


def decision_for(seed, left, right):
    names = [f'x{seed}_{i}' for i in range(4)]
    a, b, c, d = names
    left_program = instantiate_macro(left, (bool_atom(a), bool_atom(b)))
    right_program = instantiate_macro(right, (bool_atom(c), bool_atom(d)))
    program = and_probe(left_program, right_program)
    return CompositionDiscoveryDecision(
        status='accept', composition_id=f'cm:{seed}',
        selected_macro_ids=tuple(sorted((left.macro_id, right.macro_id))),
        connective='and', program=program, information_gain=0.9,
        best_parent_information_gain=0.8, synergy=0.1,
        candidates_evaluated=4, counterexamples_checked=1,
        rejected_composition_ids=(), reason='counterexample_surviving_composition',
    )


def test_batch_promotion_requires_repeated_cross_episode_structure_and_abstracts_names():
    left, right = macro('left', and_probe), macro('right', or_probe)
    decisions = {f'e{i}': decision_for(100 + i, left, right) for i in range(3)}
    promoted = promote_composition_batch(decisions, base_macros=(left, right), min_support=3)
    assert len(promoted) == 1
    rec = promoted[0]
    assert isinstance(rec, RecursiveAbstractionRecord)
    assert rec.generation == 1
    assert rec.connective == 'and'
    assert rec.support_episode_ids == ('e0', 'e1', 'e2')
    assert rec.parent_macro_ids == ('left', 'right')
    assert rec.macro.arity == 4
    atoms = []
    stack = [rec.macro.template]
    while stack:
        n = stack.pop()
        if n.op == 'atom':
            atoms.append(n.atom_id)
        stack.extend(n.children)
    assert atoms and all(str(a).startswith('$p') for a in atoms)
    assert not any('x100_' in str(a) or 'x101_' in str(a) or 'x102_' in str(a) for a in atoms)


def test_single_episode_cannot_self_promote():
    left, right = macro('left', and_probe), macro('right', or_probe)
    assert promote_composition_batch(
        {'solo': decision_for(1, left, right)}, base_macros=(left, right), min_support=2
    ) == ()


def test_promotion_is_deterministic_under_episode_order():
    left, right = macro('left', and_probe), macro('right', or_probe)
    items = [(f'e{i}', decision_for(200 + i, left, right)) for i in range(3)]
    a = promote_composition_batch(dict(items), base_macros=(left, right), min_support=3)
    b = promote_composition_batch(dict(reversed(items)), base_macros=(left, right), min_support=3)
    assert a == b


def test_descendant_is_blocked_when_any_ancestor_is_quarantined():
    left, right = macro('left', and_probe), macro('right', or_probe)
    rec = promote_composition_batch(
        {f'e{i}': decision_for(300 + i, left, right) for i in range(3)},
        base_macros=(left, right), min_support=3,
    )[0]
    blocked = propagate_quarantine((rec,), {'left'})
    assert 'left' in blocked
    assert rec.macro.macro_id in blocked
    assert 'right' not in blocked


def _uniform_world(atom_ids):
    assignments = tuple(itertools.product((False, True), repeat=len(atom_ids)))
    values = {
        f'h{i:03d}': {atom: bit for atom, bit in zip(atom_ids, bits)}
        for i, bits in enumerate(assignments)
    }
    posterior = {hid: 1.0 / len(values) for hid in values}
    return posterior, values


def test_conditional_novelty_does_not_saturate_at_one_bit_and_rejects_copy():
    posterior, values = _uniform_world(('a', 'b'))
    left = {h: bool(v['a']) for h, v in values.items()}
    right = {h: bool(v['b']) for h, v in values.items()}
    child = {h: bool(v['a']) ^ bool(v['b']) for h, v in values.items()}
    copy = dict(left)
    assert conditional_composition_novelty(child, left, right, posterior) == pytest.approx(1.0)
    assert conditional_composition_novelty(copy, left, right, posterior) == pytest.approx(0.0)


def _recursive_decision(episode, left_macro, right_macro, connective, program, novelty=0.25):
    return RecursiveCompositionDecision(
        status='accept', composition_id=f'rcm:{episode}',
        selected_macro_ids=tuple(sorted((left_macro.macro_id, right_macro.macro_id))),
        connective=connective, program=program,
        information_gain=0.9, best_parent_information_gain=0.9,
        conditional_novelty=novelty, candidates_evaluated=8,
        counterexamples_checked=1, rejected_composition_ids=(),
        reason='counterexample_surviving_recursive_composition',
    )


def test_recursive_frontier_reuses_lineage_instead_of_flat_factorial_binding():
    m_and, m_or = macro('and-base', and_probe), macro('or-base', or_probe)
    decisions = {}
    for i in range(3):
        names = [f't{i}_{j}' for j in range(4)]
        p = xor_probe(
            instantiate_macro(m_and, (bool_atom(names[0]), bool_atom(names[1]))),
            instantiate_macro(m_or, (bool_atom(names[2]), bool_atom(names[3]))),
        )
        decisions[f'e{i}'] = _recursive_decision(i, m_and, m_or, 'xor', p)
    rec = promote_composition_batch(decisions, base_macros=(m_and, m_or), min_support=3)[0]

    atom_ids = ('a', 'b', 'c', 'd')
    posterior, values = _uniform_world(atom_ids)
    receipt = build_recursive_application_frontier(
        rec.macro.macro_id,
        base_macros=(m_and, m_or), records=(rec,),
        atom_pools_by_macro={
            m_and.macro_id: {ProbeType.BOOL: ('a', 'b')},
            m_or.macro_id: {ProbeType.BOOL: ('c', 'd')},
        },
        posterior=posterior, atom_values_by_hypothesis=values,
    )
    assert receipt.reason == 'recursive_frontier_ready'
    assert receipt.max_generation == 1
    assert receipt.candidates_evaluated <= 5
    target = xor_probe(and_probe(bool_atom('a'), bool_atom('b')), or_probe(bool_atom('c'), bool_atom('d')))
    target_row = typed_prediction_row(target, values)
    assert any(typed_prediction_row(app.program, values) == target_row for app in receipt.applications)
    assert flat_unique_binding_count(rec.macro, {ProbeType.BOOL: 4}) == 24


def test_recursive_quarantine_prevents_descendant_instantiation():
    left, right = macro('left', and_probe), macro('right', or_probe)
    rec = promote_composition_batch(
        {f'e{i}': decision_for(400 + i, left, right) for i in range(3)},
        base_macros=(left, right), min_support=3,
    )[0]
    posterior, values = _uniform_world(('a', 'b', 'c', 'd'))
    receipt = build_recursive_application_frontier(
        rec.macro.macro_id, base_macros=(left, right), records=(rec,),
        atom_pools_by_macro={
            'left': {ProbeType.BOOL: ('a', 'b')},
            'right': {ProbeType.BOOL: ('c', 'd')},
        }, posterior=posterior, atom_values_by_hypothesis=values,
        blocked_macro_ids=('left',),
    )
    assert receipt.applications == ()
    assert receipt.reason == 'macro_or_ancestor_quarantined'
