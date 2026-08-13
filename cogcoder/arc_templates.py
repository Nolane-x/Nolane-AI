from __future__ import annotations

from typing import Iterable
from .arc_grid import Grid
from .arc_ops import Program, Step, apply_program, infer_color_map

D4=('identity','rot90','rot180','rot270','flip_h','flip_v','transpose','anti_transpose')
CRITERIA=('largest','smallest','topmost','bottommost','leftmost','rightmost')


def _p(steps,cost): return Program(tuple(steps),int(cost))

def _apply(p,g):
    try: return apply_program(p,g)
    except (ValueError,ArithmeticError,OverflowError,StopIteration): return None


def _bases(inp: Grid):
    rows=[_p((),0)]
    rows += [_p((Step('transform',(k,)),),1) for k in D4 if k!='identity']
    crops=[(Step('crop_nonbg',()),1)]
    crops += [(Step('crop_component',(c,)),2) for c in CRITERIA]
    crops += [(Step('crop_color',(c,)),2) for c in sorted(inp.colors)]
    for step,cost in crops:
        b=_p((step,),cost)
        if _apply(b,inp) is None: continue
        rows.append(b)
        rows += [_p((step,Step('transform',(k,))),cost+1) for k in D4 if k!='identity']
    unique={x.signature:x for x in rows}
    return sorted(unique.values(),key=lambda x:(x.cost,len(x.steps),repr(x.signature)))


def _resize_variants(base: Program, inp: Grid, target: Grid):
    out=_apply(base,inp)
    if out is None: return ()
    rows=[base]
    if target.h%out.h==0 and target.w%out.w==0:
        rh,cw=target.h//out.h,target.w//out.w
        if (rh,cw)!=(1,1):
            rows.append(_p(base.steps+(Step('scale',(rh,cw)),),base.cost+2))
            rows.append(_p(base.steps+(Step('tile',(rh,cw)),),base.cost+3))
    if target.h==out.h and target.w%out.w==0 and target.w//out.w>1:
        n=target.w//out.w; rows.append(_p(base.steps+(Step('concat',('h',n)),),base.cost+2))
    if target.w==out.w and target.h%out.h==0 and target.h//out.h>1:
        n=target.h//out.h; rows.append(_p(base.steps+(Step('concat',('v',n)),),base.cost+2))
    return rows


def templates_from_pair(inp: Grid, target: Grid):
    rows={}
    for base in _bases(inp):
        for item in _resize_variants(base,inp,target):
            out=_apply(item,inp)
            if out is None or out.shape!=target.shape: continue
            if out==target: rows[item.signature]=item
            mapping=infer_color_map(out,target)
            if mapping is not None and any(a!=b for a,b in mapping):
                mapped=_p(item.steps+(Step('color_map',(mapping,)),),item.cost+1+len(mapping)//4)
                if _apply(mapped,inp)==target: rows[mapped.signature]=mapped
    return tuple(sorted(rows.values(),key=lambda x:(x.cost,len(x.steps),repr(x.signature))))


def fit_templates(pairs: Iterable[tuple[Grid,Grid]], *, limit: int=64):
    pairs=tuple(pairs)
    if not pairs or limit<1: return ()
    out=[]
    for item in templates_from_pair(*pairs[0]):
        if all(_apply(item,x)==y for x,y in pairs):
            out.append(item)
            if len(out)>=limit: break
    return tuple(out)
