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
    return OperatorInventionNeed('R2.68 private combined authority',FIELDS,'out',constants=(0.0,2.0),max_depth=5,max_candidates=120_000)

def _runtime_reject(validation_rows):
    calls=[]
    def oracle(row):
        calls.append((row['a'],row['b']))
        return float(row['a'])+float(row['b'])
    with pytest.raises(ValueError,match='discovery|validation|overlap|disjoint|unique|duplicate'):
        runtime.discover_adaptive_causal_basis(
            oracle,FIELDS,(0.0,),_contexts(DISCOVERY),_contexts(validation_rows),
            intervention_arity=1,max_basis_size=2)
    assert calls==[]

def test_private_runtime_rejects_cross_phase_intervention_alias_pre_oracle():
    # Validation base (0,13) equals discovery (11,13) after a=0.
    _runtime_reject(((0,13),(59,61),(67,71)))

def test_private_runtime_rejects_duplicate_validation_base_pre_oracle():
    _runtime_reject(((2,3),(2,3),(5,7)))

def test_private_runtime_rejects_same_intervention_validation_alias_pre_oracle():
    # a=0 maps both first rows to (0,3).
    _runtime_reject(((2,3),(7,3),(5,11)))

def test_private_runtime_rejects_cross_intervention_validation_alias_pre_oracle():
    # a=0 on (2,0), b=0 on (0,7) both yield (0,0).
    _runtime_reject(((2,0),(0,7),(5,11)))

def test_public_synthesis_preserves_same_authority():
    calls=[]
    def oracle(row):
        calls.append((row['a'],row['b']))
        return float(row['a'])+float(row['b'])
    with pytest.raises(ValueError,match='validation|unique|duplicate|overlap|disjoint'):
        synthesize_adaptive_causal_basis(
            oracle,FIELDS,_need(),_contexts(DISCOVERY),_contexts(((2,3),(7,3),(5,11))),
            terminal_contexts=_contexts(TERMINAL),intervention_anchor_values=(0.0,),
            intervention_arity=1,max_basis_size=2)
    assert calls==[]
