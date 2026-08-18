from __future__ import annotations

from collections.abc import Mapping
import pytest

from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r266_learned_contextual_composition import synthesize_contextual_composition_program


def _oracle(row: Mapping[str,object])->float:
    x=float(row['x']);lo=float(row['lo']);hi=float(row['hi'])
    if x<lo:return float(row['left'])
    if x>hi:return float(row['right'])
    return float(row['middle'])


def _rows()->tuple[dict[str,float],...]:
    configs=((-3.0,2.0,-7.0,4.0,-5.0),(-1.0,4.0,6.0,-3.0,9.0),(-5.0,1.0,-8.0,5.0,2.0),(0.0,6.0,3.0,-6.0,-4.0),(-4.0,3.0,8.0,2.0,-9.0),(-2.0,5.0,-6.0,-1.0,7.0));out=[]
    for lo,hi,left,middle,right in configs:
        for x in (lo-3.0,lo,(lo+hi)/2.0,hi,hi+3.0):out.append({'x':x,'lo':lo,'hi':hi,'left':left,'middle':middle,'right':right})
    return tuple(out)


def test_terminal_context_cannot_alias_learning_context_by_numeric_json_type()->None:
    rows=_rows();discovery=rows[:18];validation=rows[18:24]
    terminal_alias={key:int(value) for key,value in discovery[0].items()}
    need=OperatorInventionNeed('R2.66 terminal numeric-alias disjointness',('x','lo','hi','left','middle','right'),'out',constants=(0.0,),max_depth=3,max_candidates=25000)
    with pytest.raises(ValueError,match='disjoint'):
        synthesize_contextual_composition_program(_oracle,('x','lo','hi','left','middle','right'),need,discovery,validation,terminal_contexts=(terminal_alias,),intervention_arity=1,composition_constants=(0.0,),composition_max_depth=2,composition_max_candidates_per_pair=12000,max_composition_candidates_total=120000,probe_constants=(0.0,),probe_max_depth=3,probe_max_candidates=20000)
