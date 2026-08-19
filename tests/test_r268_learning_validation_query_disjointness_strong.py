from __future__ import annotations

import pytest

from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import synthesize_adaptive_causal_basis

FIELDS=('a','b')

def _contexts(rows):
    return tuple(dict(zip(FIELDS,row,strict=True)) for row in rows)

def _need():
    return OperatorInventionNeed('R2.68 strong cross-phase oracle-query disjointness',FIELDS,'out',constants=(0.0,2.0),max_depth=5,max_candidates=120_000)

def _reject(discovery_rows,validation_rows):
    calls=[]
    def oracle(row):
        calls.append((row['a'],row['b']))
        return float(row['a'])+float(row['b'])
    with pytest.raises(ValueError,match='discovery|validation|overlap|disjoint'):
        synthesize_adaptive_causal_basis(
            oracle,FIELDS,_need(),_contexts(discovery_rows),_contexts(validation_rows),
            terminal_contexts=_contexts(((101,103),(-109,113),(127,-131))),
            intervention_anchor_values=(0.0,),intervention_arity=1,max_basis_size=2,
            composition_constants=(0.0,2.0),composition_max_depth=5,
            composition_max_candidates_per_basis=30_000,max_composition_candidates_total=160_000,
            composition_beam_width=192,probe_constants=(0.0,2.0),probe_max_depth=5,
            probe_max_candidates=50_000,probe_beam_width=192)
    assert calls==[]

def test_validation_base_reuses_discovery_base():
    _reject(((1,2),(2,3),(-2,5),(4,-3),(5,7),(-1,-2)),((1,2),(7,8),(9,-4)))

def test_validation_base_reuses_discovery_intervention():
    _reject(((1,2),(2,3),(-2,5),(4,-3),(5,7),(-1,-2)),((0,2),(7,8),(9,-4)))

def test_validation_intervention_reuses_discovery_base():
    _reject(((0,2),(2,3),(-2,5),(4,-3),(5,7),(-1,-2)),((1,2),(7,8),(9,-4)))

def test_validation_intervention_reuses_discovery_intervention():
    _reject(((1,2),(2,3),(-2,5),(4,-3),(5,7),(-1,-2)),((7,2),(8,9),(9,10)))
