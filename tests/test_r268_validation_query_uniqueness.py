from __future__ import annotations

import pytest

import cogcoder._r268_runtime as runtime
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r268_adaptive_causal_basis import synthesize_adaptive_causal_basis

FIELDS=('a','b')
DISCOVERY=((11,13),(17,19),(23,29),(31,37),(41,43),(47,53))
TERMINAL=((101,103),(-109,113),(127,-131))

def _contexts(rows):
    return tuple(dict(zip(FIELDS,row,strict=True)) for row in rows)

def _need():
    return OperatorInventionNeed('R2.68 validation oracle-query uniqueness challenger',FIELDS,'out',constants=(0.0,2.0),max_depth=5,max_candidates=120_000)

def _reject(validation_rows):
    calls=[]
    def oracle(row):
        calls.append((row['a'],row['b']))
        return float(row['a'])+float(row['b'])
    with pytest.raises(ValueError,match='validation|duplicate|unique|overlap'):
        synthesize_adaptive_causal_basis(
            oracle,FIELDS,_need(),_contexts(DISCOVERY),_contexts(validation_rows),
            terminal_contexts=_contexts(TERMINAL),intervention_anchor_values=(0.0,),
            intervention_arity=1,max_basis_size=2,composition_constants=(0.0,2.0),
            composition_max_depth=5,composition_max_candidates_per_basis=30_000,
            max_composition_candidates_total=160_000,composition_beam_width=192,
            probe_constants=(0.0,2.0),probe_max_depth=5,probe_max_candidates=50_000,
            probe_beam_width=192)
    assert calls==[]

def test_rejects_duplicate_validation_base_query() -> None:
    _reject(((2,3),(2,3),(5,7)))

def test_rejects_duplicate_validation_query_after_same_intervention() -> None:
    _reject(((2,3),(7,3),(5,11)))

def test_rejects_duplicate_validation_query_across_intervention_profiles() -> None:
    _reject(((2,0),(0,7),(5,11)))

def test_private_runtime_cannot_bypass_validation_query_uniqueness() -> None:
    calls=[]
    def oracle(row):
        calls.append((row['a'],row['b']))
        return float(row['a'])+float(row['b'])
    with pytest.raises(ValueError,match='validation|duplicate|unique|overlap'):
        runtime.discover_adaptive_causal_basis(
            oracle,FIELDS,(0.0,),_contexts(DISCOVERY),_contexts(((2,3),(7,3),(5,11))),
            intervention_arity=1,max_basis_size=2)
    assert calls==[]
