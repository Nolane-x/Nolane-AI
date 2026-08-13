from __future__ import annotations

from .arc_ops_view import Program, Step, apply_program


D4_VIEWS=('flip_h','flip_v','transpose','anti_transpose','rot180','rot90','rot270')


def fit_pair_programs(pairs):
    pairs=tuple(pairs)
    if not pairs or any(x.shape!=y.shape for x,y in pairs):
        return ()
    accepted=[]
    for kind in D4_VIEWS:
        program=Program((Step('view_combine',(kind,)),),3)
        try:
            exact=all(apply_program(program,x)==y for x,y in pairs)
        except (ValueError,ArithmeticError,OverflowError,StopIteration):
            exact=False
        if exact:
            accepted.append(program)
    return tuple(sorted(accepted,key=lambda p:(p.cost,len(p.steps),repr(p.signature))))
