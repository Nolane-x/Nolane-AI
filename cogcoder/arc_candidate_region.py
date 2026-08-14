from __future__ import annotations

from .arc_candidate_next import program_set as previous_program_set
from .arc_ops_view import Program, Step, apply_program


def program_set(pairs,limit=64):
    pairs=tuple(pairs)
    if not pairs or limit<1: return ()
    pool={p.signature:p for p in previous_program_set(pairs,limit=limit)}
    colors=sorted({color for _,target in pairs for color in target.colors})
    for color in colors:
        p=Program((Step('region_project',(int(color),)),),3)
        try: exact=all(apply_program(p,a)==b for a,b in pairs)
        except (ValueError,ArithmeticError,OverflowError,StopIteration): exact=False
        if exact: pool[p.signature]=p
    return tuple(sorted(pool.values(),key=lambda p:(p.cost,len(p.steps),repr(p.signature)))[:limit])
