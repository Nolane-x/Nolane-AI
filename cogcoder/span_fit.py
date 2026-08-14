from __future__ import annotations

from .arc_ops_view import Program, Step, apply_program


def programs(pairs):
    pairs=tuple(pairs)
    if not pairs or any(a.shape!=b.shape for a,b in pairs): return ()
    colors=sorted({color for _,b in pairs for color in b.colors})
    out=[]
    for color in colors:
        p=Program((Step('span',(int(color),)),),3)
        try: exact=all(apply_program(p,a)==b for a,b in pairs)
        except (ValueError,ArithmeticError,OverflowError,StopIteration): exact=False
        if exact: out.append(p)
    return tuple(out)
