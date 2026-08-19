from __future__ import annotations

import pytest

from cogcoder.r256_operator_invention import OperatorInventionNeed


def _module():
    try:
        import cogcoder.r268_adaptive_causal_basis as r268
    except ImportError as exc:
        pytest.fail(f'R2.68 module missing: {exc}')
    return r268


def _need(label: str, fields: tuple[str, ...]) -> OperatorInventionNeed:
    return OperatorInventionNeed(label, fields, 'out', constants=(0.0, 2.0), max_depth=5, max_candidates=120_000)


def _contexts(fields: tuple[str, ...], rows: tuple[tuple[float, ...], ...]) -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(fields, row, strict=True)) for row in rows)


def _solve(oracle, fields, discovery_rows, validation_rows, terminal_rows, *, max_basis_size):
    r268 = _module()
    return r268.synthesize_adaptive_causal_basis(
        oracle, fields, _need(f'R2.68 basis-{max_basis_size}', fields),
        _contexts(fields, discovery_rows), _contexts(fields, validation_rows), terminal_contexts=_contexts(fields, terminal_rows),
        intervention_anchor_values=(0.0,), intervention_arity=1, max_basis_size=max_basis_size,
        composition_constants=(0.0, 2.0), composition_max_depth=5, composition_max_candidates_per_basis=30_000,
        max_composition_candidates_total=160_000, composition_beam_width=192, probe_constants=(0.0, 2.0),
        probe_max_depth=5, probe_max_candidates=50_000, probe_beam_width=192,
    )


def test_rejects_target_preserving_one_probe_nuisance_as_noncausal() -> None:
    fields=('a','b','c')
    def oracle(row): return float(row['a'])*float(row['b'])
    receipt=_solve(oracle,fields,((1,2,3),(2,3,4),(-2,5,7),(4,-3,9),(5,2,11),(-3,-2,13)),((6,7,15),(-5,4,17),(8,-2,19)),((101,103,107),(-109,113,127),(131,-137,139)),max_basis_size=1)
    assert receipt.passed is False
    assert receipt.selected_basis_size==0
    assert receipt.false_accepts==0


def test_certifies_two_probe_sum_basis() -> None:
    fields=('a','b')
    def oracle(row): return float(row['a'])+float(row['b'])
    receipt=_solve(oracle,fields,((-2,-2),(-2,-1),(-1,-2),(1,3),(4,-2),(5,7)),((2,5),(-3,6),(8,-4)),((101,103),(-109,113),(127,-131)),max_basis_size=2)
    assert receipt.passed is True and receipt.selected_basis_size==2 and receipt.globally_minimal is True
    assert receipt.reason=='adaptive_basis_discovered'
    assert len(receipt.structure.necessity_certificates)>=2 and receipt.false_accepts==0
    assert receipt.final_validation_exact==receipt.final_validation_cases==3
    assert receipt.terminal_probe_validation_exact==receipt.terminal_probe_validation_cases==6


def test_certifies_three_probe_triangle_basis() -> None:
    fields=('a','b','c')
    def oracle(row):
        a,b,c=(float(row[name]) for name in fields); return a*b+b*c+c*a
    discovery=((-2,-2,-2),(-2,-2,-1),(-2,-2,0),(-2,-1,-2),(-2,-1,0),(-2,0,-2),(-2,0,-1),(-1,-2,-2),(0,-2,-2),(0,-2,-1),(1,2,3),(4,-3,2),(5,2,-4))
    receipt=_solve(oracle,fields,discovery,((3,5,7),(-5,4,6),(8,-2,9)),((101,103,107),(-109,113,127),(131,-137,139)),max_basis_size=3)
    assert receipt.passed is True and receipt.selected_basis_size==3 and receipt.globally_minimal is True
    assert receipt.false_accepts==0
    assert receipt.final_validation_exact==receipt.final_validation_cases==3
    assert receipt.terminal_probe_validation_exact==receipt.terminal_probe_validation_cases==9


def test_certifies_four_probe_complete_pairwise_basis() -> None:
    fields=('a','b','c','d')
    def oracle(row):
        a,b,c,d=(float(row[name]) for name in fields); return a*b+a*c+a*d+b*c+b*d+c*d
    discovery=((-2,-2,-2,-2),(-2,-2,-2,-1),(-2,-2,-2,2),(-2,-2,-1,-2),(-2,-2,-1,2),(-2,-2,2,-2),(-2,-2,2,-1),(-2,-2,2,2),(-2,-1,-2,-2),(-2,-1,-2,2),(-2,-1,2,2),(-2,2,-2,-2),(-2,2,-2,-1),(-1,-2,-2,-2),(1,2,3,4),(5,-3,2,7),(-4,6,-2,3))
    receipt=_solve(oracle,fields,discovery,((3,5,7,11),(-5,4,6,-3),(8,-2,9,10)),((101,103,107,109),(-113,127,131,137),(139,-149,151,157)),max_basis_size=4)
    assert receipt.passed is True and receipt.selected_basis_size==4 and receipt.globally_minimal is True
    assert receipt.false_accepts==0
    assert receipt.final_validation_exact==receipt.final_validation_cases==3
    assert receipt.terminal_probe_validation_exact==receipt.terminal_probe_validation_cases==12
    assert {1,2,3}<={cert.subset_cardinality for cert in receipt.structure.necessity_certificates}


def test_minimality_receipt_carries_complete_lower_basis_ledger() -> None:
    fields=('a','b','c')
    def oracle(row):
        a,b,c=(float(row[name]) for name in fields); return a*b+b*c+c*a
    discovery=((-2,-2,-2),(-2,-2,-1),(-2,-2,0),(-2,-1,-2),(-2,-1,0),(-2,0,-2),(-2,0,-1),(-1,-2,-2),(0,-2,-2),(0,-2,-1),(1,2,3),(4,-3,2),(5,2,-4))
    receipt=_solve(oracle,fields,discovery,((3,5,7),(-5,4,6),(8,-2,9)),((101,103,107),(-109,113,127),(131,-137,139)),max_basis_size=3)
    assert receipt.passed is True and receipt.selected_basis_size==3
    assert receipt.structure.lower_basis_count==6
    assert receipt.structure.lower_basis_certified==6
    assert receipt.structure.lower_basis_inconclusive==0
    assert receipt.structure.proof_ledger_complete is True
    assert len(receipt.structure.lower_basis_universe_digest)==64


def test_three_probe_selection_is_field_order_invariant() -> None:
    fields=('a','b','c')
    discovery_rows=((-2,-2,-2),(-2,-2,-1),(-2,-2,0),(-2,-1,-2),(-2,-1,0),(-2,0,-2),(-2,0,-1),(-1,-2,-2),(0,-2,-2),(0,-2,-1),(1,2,3),(4,-3,2),(5,2,-4))
    validation_rows=((3,5,7),(-5,4,6),(8,-2,9)); terminal_rows=((101,103,107),(-109,113,127),(131,-137,139))
    def contexts(rows): return tuple(dict(zip(fields,row,strict=True)) for row in rows)
    def oracle(row):
        a,b,c=(float(row[name]) for name in fields); return a*b+b*c+c*a
    r268=_module()
    def solve(order):
        return r268.synthesize_adaptive_causal_basis(oracle,order,_need('field order invariant',fields),contexts(discovery_rows),contexts(validation_rows),terminal_contexts=contexts(terminal_rows),intervention_anchor_values=(0.0,),intervention_arity=1,max_basis_size=3,composition_constants=(0.0,2.0),composition_max_depth=5,composition_max_candidates_per_basis=30_000,max_composition_candidates_total=160_000,composition_beam_width=192,probe_constants=(0.0,2.0),probe_max_depth=5,probe_max_candidates=50_000,probe_beam_width=192)
    base=solve(('a','b','c')); permuted=solve(('c','a','b'))
    assert base.passed is permuted.passed is True
    assert base.selected_basis_size==permuted.selected_basis_size==3
    assert base.globally_minimal is permuted.globally_minimal is True
    assert base.structure.lower_basis_count==permuted.structure.lower_basis_count==6
    assert base.structure.lower_basis_certified==permuted.structure.lower_basis_certified==6
    assert base.false_accepts==permuted.false_accepts==0


def test_structure_proposal_search_never_trains_on_validation_targets(monkeypatch) -> None:
    import cogcoder._r268_runtime as runtime
    original=runtime.synthesize_variable_expression; observed=[]
    def traced(field_names,required_probe_fields,constants,examples,**kwargs):
        if tuple(required_probe_fields): observed.append(len(tuple(examples)))
        return original(field_names,required_probe_fields,constants,examples,**kwargs)
    monkeypatch.setattr(runtime,'synthesize_variable_expression',traced)
    fields=('a','b')
    def oracle(row): return float(row['a'])+float(row['b'])
    discovery=_contexts(fields,((-2,-2),(-2,-1),(-1,-2),(1,3),(4,-2),(5,7))); validation=_contexts(fields,((2,5),(-3,6),(8,-4)))
    receipt=runtime.discover_adaptive_causal_basis(oracle,fields,(0.0,),discovery,validation,intervention_arity=1,max_basis_size=2,composition_constants=(0.0,2.0),composition_max_depth=5,composition_max_candidates_per_basis=30_000,max_composition_candidates_total=160_000,composition_beam_width=192)
    assert receipt.passed is True
    assert observed and all(count==len(discovery) for count in observed)
    assert receipt.selected is not None
    assert receipt.selected.selection_cases==len(discovery)
    assert receipt.selected.validation_cases==len(validation)
    assert receipt.selected.validation_exact==len(validation)
