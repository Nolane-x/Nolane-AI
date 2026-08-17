import math

from cogcoder.r239_predicate_macros import ProbeMacro
from cogcoder.r239_typed_probe_dsl import ProbeType, and_probe, bool_atom, or_probe
from cogcoder.r241_macro_competition import MacroCompetitionState
from cogcoder.r243_macro_composition import discover_composed_macro_probe


def _macro(mid: str, left_param: int, right_param: int) -> ProbeMacro:
    op = and_probe if mid == 'left-family' else or_probe
    template = op(bool_atom(f'$p{left_param}'), bool_atom(f'$p{right_param}'))
    return ProbeMacro(mid, template, (ProbeType.BOOL, ProbeType.BOOL), support=4, compression_gain=3.0, raw_mdl_cost=3)


def _fixture():
    # Cross-family target uses renamed atoms. Each learned macro gives a coarse
    # partition (0.70/0.30 posterior mass); their composition isolates h0 at
    # 0.55/0.45 and therefore carries strictly more verifier information.
    values = {
        'h0': {'a': True, 'b': True, 'c': True, 'd': False},
        'h1': {'a': True, 'b': True, 'c': False, 'd': False},
        'h2': {'a': True, 'b': False, 'c': False, 'd': True},
        'h3': {'a': False, 'b': False, 'c': False, 'd': False},
    }
    posterior = {'h0': .55, 'h1': .15, 'h2': .15, 'h3': .15}
    macros = (_macro('left-family', 0, 1), _macro('right-family', 0, 1))
    return values, posterior, macros


def test_cross_family_composition_has_positive_information_synergy():
    values, posterior, macros = _fixture()
    result = discover_composed_macro_probe(
        macros,
        {ProbeType.BOOL: ('a', 'b', 'c', 'd')},
        posterior,
        values,
        max_applications_per_macro=12,
        argument_pools_by_macro={
            'left-family': {ProbeType.BOOL: ('a', 'b')},
            'right-family': {ProbeType.BOOL: ('c', 'd')},
        },
        min_synergy=0.02,
        counterexample_check=lambda program: True,
    )
    assert result.status == 'accept'
    assert result.program is not None
    assert len(result.selected_macro_ids) == 2
    assert result.selected_macro_ids[0] != result.selected_macro_ids[1]
    assert result.synergy > 0.02
    assert result.information_gain > result.best_parent_information_gain


def test_counterexample_guidance_rejects_bad_top_composition_and_falls_back():
    values, posterior, macros = _fixture()
    seen = []
    def check(program):
        seen.append(program.probe_id)
        return len(seen) >= 2
    result = discover_composed_macro_probe(
        macros,
        {ProbeType.BOOL: ('a', 'b', 'c', 'd')},
        posterior,
        values,
        max_applications_per_macro=12,
        argument_pools_by_macro={
            'left-family': {ProbeType.BOOL: ('a', 'b')},
            'right-family': {ProbeType.BOOL: ('c', 'd')},
        },
        min_synergy=0.0,
        counterexample_check=check,
    )
    assert result.status == 'accept'
    assert len(result.rejected_composition_ids) == 1
    assert result.composition_id not in result.rejected_composition_ids
    assert result.counterexamples_checked >= 2


def test_quarantined_macro_cannot_participate_in_composition():
    values, posterior, macros = _fixture()
    states = {
        'left-family': MacroCompetitionState('left-family', quarantined=True),
        'right-family': MacroCompetitionState('right-family'),
    }
    result = discover_composed_macro_probe(
        macros,
        {ProbeType.BOOL: ('a', 'b', 'c', 'd')},
        posterior,
        values,
        macro_states=states,
        argument_pools_by_macro={
            'left-family': {ProbeType.BOOL: ('a', 'b')},
            'right-family': {ProbeType.BOOL: ('c', 'd')},
        },
        counterexample_check=lambda program: True,
    )
    assert result.status == 'abstain'
    assert result.reason == 'need_two_trusted_macros'


def test_composition_is_deterministic_under_macro_and_atom_order_changes():
    values, posterior, macros = _fixture()
    scopes = {'left-family': {ProbeType.BOOL: ('a','b')}, 'right-family': {ProbeType.BOOL: ('c','d')}}
    reversed_scopes = {'right-family': {ProbeType.BOOL: ('d','c')}, 'left-family': {ProbeType.BOOL: ('b','a')}}
    a = discover_composed_macro_probe(macros, {ProbeType.BOOL: ('a','b','c','d')}, posterior, values, argument_pools_by_macro=scopes, counterexample_check=lambda p: True)
    b = discover_composed_macro_probe(tuple(reversed(macros)), {ProbeType.BOOL: ('d','c','b','a')}, posterior, values, argument_pools_by_macro=reversed_scopes, counterexample_check=lambda p: True)
    assert a.status == b.status == 'accept'
    assert a.composition_id == b.composition_id
    assert a.program.probe_id == b.program.probe_id
    assert math.isclose(a.synergy, b.synergy, rel_tol=0, abs_tol=1e-12)


def test_duplicate_macro_ids_are_rejected():
    values, posterior, macros = _fixture()
    duplicate = ProbeMacro('left-family', macros[1].template, macros[1].parameter_types, 4, 3.0, 3)
    import pytest
    with pytest.raises(ValueError, match='macro ids must be unique'):
        discover_composed_macro_probe((macros[0], duplicate), {ProbeType.BOOL: ('a','b','c','d')}, posterior, values)


def test_candidate_budget_is_hard_bounded():
    values, posterior, macros = _fixture()
    result = discover_composed_macro_probe(
        macros, {ProbeType.BOOL: ('a','b','c','d')}, posterior, values,
        argument_pools_by_macro={'left-family': {ProbeType.BOOL: ('a','b')}, 'right-family': {ProbeType.BOOL: ('c','d')}},
        max_composition_candidates=2, min_synergy=0.0, counterexample_check=lambda p: True,
    )
    assert result.candidates_evaluated <= 2


def test_all_falsified_compositions_abstain_instead_of_forcing_answer():
    values, posterior, macros = _fixture()
    result = discover_composed_macro_probe(
        macros, {ProbeType.BOOL: ('a','b','c','d')}, posterior, values,
        argument_pools_by_macro={'left-family': {ProbeType.BOOL: ('a','b')}, 'right-family': {ProbeType.BOOL: ('c','d')}},
        min_synergy=0.0, counterexample_check=lambda p: False,
    )
    assert result.status == 'abstain'
    assert result.reason == 'all_compositions_falsified'
    assert result.counterexamples_checked == len(result.rejected_composition_ids)
