from __future__ import annotations

from .arc_ops_view import Program, Step, apply_program
from .object_grid import KINDS, feature, objects

_COST={'area':0,'area_color':1,'bbox':1,'bbox_color':2,'area_bbox':2,'area_bbox_color':3,'touch':1,'touch_color':2}


def programs(pairs,max_items=4):
    pairs=tuple(pairs)
    if not pairs or max_items<1 or any(a.shape!=b.shape for a,b in pairs): return ()
    out=[]
    for kind in KINDS:
        table={}; unchanged=set(); bad=False
        for a,b in pairs:
            for color,cells,box in objects(a):
                key=feature(a,color,cells,box,kind)
                targets={b.cell(r,c) for r,c in cells}
                if len(targets)!=1: bad=True; break
                target=next(iter(targets))
                if target==color: unchanged.add(key); continue
                if key in table and table[key]!=target: bad=True; break
                table[key]=int(target)
            if bad: break
        if bad or not table or len(table)>max_items or any(k in unchanged for k in table): continue
        items=tuple(sorted(table.items(),key=lambda item:repr(item[0])))
        p=Program((Step('object_rewrite',(kind,items)),),5+_COST[kind]+2*len(items))
        if all(apply_program(p,a)==b for a,b in pairs): out.append(p)
    return tuple(sorted(out,key=lambda p:(p.cost,len(p.steps),repr(p.signature))))
