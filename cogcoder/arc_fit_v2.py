from __future__ import annotations

from .arc_grid import Grid
from .arc_ops import Program, Step, apply_program, infer_color_map
from .arc_templates import _bases


def _program(steps, cost):
    return Program(tuple(steps), int(cost))


def _apply(program, grid):
    try:
        return apply_program(program, grid)
    except (ValueError, ArithmeticError, OverflowError, StopIteration):
        return None


def _variants(base, inp, target):
    out=_apply(base, inp)
    if out is None:
        return ()
    rows=[base]
    if target.shape==(out.h*out.h,out.w*out.w) and target.h<=30 and target.w<=30:
        rows.append(_program(base.steps+(Step('block_expand',()),), base.cost+3))
    if target.h%out.h==0 and target.w%out.w==0:
        rh,cw=target.h//out.h,target.w//out.w
        if (rh,cw)!=(1,1):
            rows.append(_program(base.steps+(Step('scale',(rh,cw)),),base.cost+2))
            rows.append(_program(base.steps+(Step('tile',(rh,cw)),),base.cost+3))
    if target.h==out.h and target.w%out.w==0 and target.w//out.w>1:
        n=target.w//out.w
        rows.append(_program(base.steps+(Step('concat',('h',n)),),base.cost+2))
    if target.w==out.w and target.h%out.h==0 and target.h//out.h>1:
        n=target.h//out.h
        rows.append(_program(base.steps+(Step('concat',('v',n)),),base.cost+2))
    return rows


def _unify(tables):
    result={}
    for table in tables:
        if table is None:
            return None
        for source,target in table:
            if source in result and result[source]!=target:
                return None
            result[source]=target
    return tuple(sorted(result.items()))


def fit_across_pairs(pairs, limit=64):
    pairs=tuple(pairs)
    if not pairs or limit<1:
        return ()
    first_input,first_output=pairs[0]
    candidates={}
    for base in _bases(first_input):
        for item in _variants(base,first_input,first_output):
            candidates[item.signature]=item
    accepted=[]
    for item in sorted(candidates.values(), key=lambda x:(x.cost,len(x.steps),repr(x.signature))):
        rendered=[_apply(item,x) for x,_ in pairs]
        if any(r is None or r.shape!=y.shape for r,(_,y) in zip(rendered,pairs)):
            continue
        if all(r==y for r,(_,y) in zip(rendered,pairs)):
            accepted.append(item)
        else:
            table=_unify([infer_color_map(r,y) for r,(_,y) in zip(rendered,pairs)])
            if table is not None and any(a!=b for a,b in table):
                mapped=_program(item.steps+(Step('color_map',(table,)),),item.cost+1+len(table)//4)
                if all(_apply(mapped,x)==y for x,y in pairs):
                    accepted.append(mapped)
        if len(accepted)>=limit:
            break
    return tuple(accepted)
