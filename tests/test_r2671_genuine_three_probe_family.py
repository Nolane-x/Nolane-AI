from __future__ import annotations

import itertools
from collections.abc import Mapping

from cogcoder.r256_operator_dsl import Binary, Field, evaluate_expr
from cogcoder.r267_three_probe_causal_composition import discover_three_probe_structure

FIELDS = ('a','b','c')
ROWS = (
    (1.0,2.0,0.0),(2.0,3.0,0.0),(1.0,0.0,2.0),(2.0,0.0,3.0),(0.0,1.0,2.0),(0.0,2.0,3.0),
    (1.0,2.0,3.0),(4.0,2.0,3.0),(2.0,1.0,3.0),(2.0,4.0,3.0),(2.0,3.0,1.0),(2.0,3.0,4.0),
    (-2.0,5.0,3.0),(4.0,-3.0,2.0),(5.0,2.0,-4.0),(-3.0,-2.0,6.0),(7.0,-1.0,-5.0),(-4.0,6.0,-2.0),
)


def _contexts() -> tuple[dict[str,float], ...]:
    return tuple(dict(zip(FIELDS,row,strict=True)) for row in ROWS)


def _oracle(row: Mapping[str, object]) -> float:
    a,b,c = float(row['a']),float(row['b']),float(row['c'])
    return a*b+b*c+c*a


def _probe(field: str, row: Mapping[str, object]) -> float:
    changed=dict(row); changed[field]=0.0
    return _oracle(changed)


def test_cyclic_family_has_information_theoretic_three_probe_witness() -> None:
    rows=_contexts()
    full=Binary('add',Binary('add',Field('__p0'),Field('__p1')),Field('__p2'))
    for row in rows:
        env={'__p0':_probe('a',row),'__p1':_probe('b',row),'__p2':_probe('c',row)}
        assert float(evaluate_expr(full,env)) == float(_oracle(row))
    for left,right in itertools.combinations(FIELDS,2):
        free=({*FIELDS}-{left,right}).pop()
        buckets={}
        for row in rows:
            key=(float(_probe(left,row)),float(_probe(right,row)),float(row[free]))
            buckets.setdefault(key,set()).add(float(_oracle(row)))
        assert any(len(targets)>1 for targets in buckets.values()), (left,right,free)
    for intervention in FIELDS:
        free=tuple(field for field in FIELDS if field!=intervention)
        buckets={}
        for row in rows:
            key=(float(_probe(intervention,row)),*(float(row[field]) for field in free))
            buckets.setdefault(key,set()).add(float(_oracle(row)))
        assert any(len(targets)>1 for targets in buckets.values()), intervention


def test_engine_discovers_cyclic_family_without_host_selected_triplet() -> None:
    rows=_contexts()
    receipt=discover_three_probe_structure(
        _oracle,FIELDS,(0.0,),rows[:12],rows[12:18],
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=20_000,
        max_composition_candidates_total=20_000,
        ablation_max_candidates=12_000,
        composition_beam_width=128,
    )
    assert receipt.passed is True
    assert receipt.selected is not None
    assert {spec.bindings[0][0] for spec in receipt.selected.interventions} == {0,1,2}
    assert set(receipt.selected.used_fields) >= {'__p0','__p1','__p2'}
    assert receipt.false_accepts == 0
