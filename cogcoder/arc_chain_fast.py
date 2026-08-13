from __future__ import annotations

from .arc_ops import Program, Step, apply_color_map, apply_program, apply_step, infer_color_map
from .arc_templates import CRITERIA, D4, _bases
from .arc_family_set import family_programs


def _apply(program, grid):
    try: return apply_program(program, grid)
    except (ValueError, ArithmeticError, OverflowError, StopIteration): return None


def _step(step, grid):
    try: return apply_step(step, grid)
    except (ValueError, ArithmeticError, OverflowError, StopIteration): return None


def _merge(tables):
    merged={}
    for table in tables:
        if table is None: return None
        for source,target in table:
            if source in merged and merged[source]!=target: return None
            merged[source]=target
    return tuple(sorted(merged.items()))


def _prefixes(pairs, max_prefixes):
    first_input,first_output=pairs[0]
    seeds=list(family_programs(first_input,first_output))+list(_bases(first_input))
    best={}
    for program in seeds:
        rendered=tuple(_apply(program,x) for x,_ in pairs)
        if any(r is None for r in rendered): continue
        signature=tuple(r.rows for r in rendered)
        gap=sum(abs(r.h-y.h)+abs(r.w-y.w) for r,(_,y) in zip(rendered,pairs))
        key=(gap,program.cost,len(program.steps),repr(program.signature))
        old=best.get(signature)
        if old is None or key<old[0]: best[signature]=(key,program,rendered)
    rows=sorted(best.values(),key=lambda item:item[0])
    return tuple((p,r) for _,p,r in rows[:max_prefixes])


def _suffixes(grid,target):
    rows=[(Step('transform',(kind,)),1) for kind in D4 if kind!='identity']
    rows.append((Step('crop_nonbg',()),1))
    rows.extend((Step('crop_component',(criterion,)),2) for criterion in CRITERIA)
    rows.extend((Step('crop_color',(color,)),2) for color in sorted(grid.colors))
    if target.h%grid.h==0 and target.w%grid.w==0:
        rf,cf=target.h//grid.h,target.w//grid.w
        if (rf,cf)!=(1,1):
            rows.append((Step('scale',(rf,cf)),2)); rows.append((Step('tile',(rf,cf)),3))
    if target.h==grid.h and target.w%grid.w==0 and target.w//grid.w>1:
        rows.append((Step('concat',('h',target.w//grid.w)),2))
    if target.w==grid.w and target.h%grid.h==0 and target.h//grid.h>1:
        rows.append((Step('concat',('v',target.h//grid.h)),2))
    return tuple(rows)


def chain_programs(pairs, *, max_prefixes=24, limit=32):
    pairs=tuple(pairs)
    if not pairs or max_prefixes<1 or limit<1: return ()
    accepted={}
    for prefix,rendered in _prefixes(pairs,max_prefixes):
        for suffix,suffix_cost in _suffixes(rendered[0],pairs[0][1]):
            program=Program(prefix.steps+(suffix,),prefix.cost+suffix_cost)
            outputs=tuple(_step(suffix,g) for g in rendered)
            if any(out is None or out.shape!=y.shape for out,(_,y) in zip(outputs,pairs)): continue
            if all(out==y for out,(_,y) in zip(outputs,pairs)):
                accepted[program.signature]=program; continue
            table=_merge([infer_color_map(out,y) for out,(_,y) in zip(outputs,pairs)])
            if table is None or not any(a!=b for a,b in table): continue
            mapped=Program(program.steps+(Step('color_map',(table,)),),program.cost+1+len(table)//4)
            if all(apply_color_map(out,table)==y for out,(_,y) in zip(outputs,pairs)):
                accepted[mapped.signature]=mapped
    return tuple(sorted(accepted.values(),key=lambda p:(p.cost,len(p.steps),repr(p.signature)))[:limit])
