from __future__ import annotations

from .arc_family_set import family_programs
from .arc_fit_v2 import fit_across_pairs
from .arc_ops import Program, Step, apply_program, infer_color_map


def _apply(program,grid):
    try: return apply_program(program,grid)
    except (ValueError,ArithmeticError,OverflowError,StopIteration): return None


def _merge(tables):
    merged={}
    for table in tables:
        if table is None: return None
        for source,target in table:
            if source in merged and merged[source]!=target: return None
            merged[source]=target
    return tuple(sorted(merged.items()))


def program_set(pairs,limit=64):
    pairs=tuple(pairs)
    if not pairs or limit<1: return ()
    pool={p.signature:p for p in fit_across_pairs(pairs,limit=64)}
    for p in family_programs(pairs[0][0],pairs[0][1]): pool[p.signature]=p
    accepted=[]
    for p in pool.values():
        rendered=[_apply(p,x) for x,_ in pairs]
        if any(r is None or r.shape!=y.shape for r,(_,y) in zip(rendered,pairs)): continue
        if all(r==y for r,(_,y) in zip(rendered,pairs)):
            accepted.append(p); continue
        table=_merge([infer_color_map(r,y) for r,(_,y) in zip(rendered,pairs)])
        if table is not None and any(a!=b for a,b in table):
            mapped=Program(p.steps+(Step('color_map',(table,)),),p.cost+1+len(table)//4)
            if all(_apply(mapped,x)==y for x,y in pairs): accepted.append(mapped)
    unique={p.signature:p for p in accepted}
    return tuple(sorted(unique.values(),key=lambda p:(p.cost,len(p.steps),repr(p.signature)))[:limit])
