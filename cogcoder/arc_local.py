from __future__ import annotations

from .arc_ops_view import Program, Step, apply_program
from .local_grid_v2 import KINDS, feature


_KIND_COST={'orth_set':0,'neighbor_set':1,'orth_counts':1,'neighbor_counts':2,'orth_tuple':1,'neighbor_tuple':2}


def fit_local_programs(pairs, *, max_rules=8):
    pairs=tuple(pairs)
    if not pairs or max_rules<1:
        return ()
    if any(x.shape!=y.shape for x,y in pairs):
        return ()
    accepted=[]
    for kind in KINDS:
        changed={}
        unchanged=set()
        conflict=False
        for x,y in pairs:
            for r in range(x.h):
                for c in range(x.w):
                    key=feature(x,r,c,kind)
                    source=x.cell(r,c); target=y.cell(r,c)
                    if target==source:
                        unchanged.add(key)
                        continue
                    if key in changed and changed[key]!=target:
                        conflict=True; break
                    changed[key]=target
                if conflict: break
            if conflict: break
        if conflict or not changed or len(changed)>max_rules:
            continue
        if any(key in unchanged for key in changed):
            continue
        rules=tuple(sorted(changed.items(),key=lambda item:repr(item[0])))
        program=Program((Step('local_rewrite',(kind,rules)),),4+_KIND_COST[kind]+2*len(rules))
        try:
            exact=all(apply_program(program,x)==y for x,y in pairs)
        except (ValueError,ArithmeticError,OverflowError,StopIteration):
            exact=False
        if exact:
            accepted.append(program)
    return tuple(sorted(accepted,key=lambda p:(p.cost,len(p.steps),repr(p.signature))))
