from __future__ import annotations

from .arc_grid import Grid, bbox, infer_background


def _period_template(grid: Grid, ph: int, pw: int, background: int):
    values={}
    for r in range(grid.h):
        for c in range(grid.w):
            value=grid.cell(r,c)
            if value==background:
                continue
            key=(r%ph,c%pw)
            previous=values.get(key)
            if previous is not None and previous!=value:
                return None
            values[key]=value
    if len(values)!=ph*pw:
        return None
    return values


def recover_missing_patch(grid: Grid) -> Grid:
    bg=infer_background(grid)
    candidates=[]
    for ph in range(1,grid.h+1):
        for pw in range(1,grid.w+1):
            if ph==grid.h and pw==grid.w:
                continue
            template=_period_template(grid,ph,pw,bg)
            if template is None:
                continue
            missing=[]
            for r in range(grid.h):
                for c in range(grid.w):
                    expected=template[(r%ph,c%pw)]
                    if grid.cell(r,c)==bg and expected!=bg:
                        missing.append((r,c))
            if not missing:
                continue
            missing_set=set(missing)
            r0,c0,r1,c1=bbox(missing)
            if any((r,c) not in missing_set for r in range(r0,r1+1) for c in range(c0,c1+1)):
                continue
            patch=Grid.from_rows(tuple(template[(r%ph,c%pw)] for c in range(c0,c1+1)) for r in range(r0,r1+1))
            candidates.append((ph*pw,ph,pw,patch))
    if not candidates:
        raise ValueError('no recoverable periodic patch')
    candidates.sort(key=lambda row:(row[0],row[1],row[2],row[3].rows))
    return candidates[0][3]
