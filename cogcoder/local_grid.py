from __future__ import annotations

from collections import Counter

from .arc_grid import Grid


KINDS=('orth_set','neighbor_set','orth_counts','neighbor_counts')


def _neighbors(grid: Grid, r: int, c: int, *, diagonal: bool):
    if diagonal:
        offsets=((dr,dc) for dr in (-1,0,1) for dc in (-1,0,1) if (dr,dc)!=(0,0))
    else:
        offsets=(( -1,0),(0,1),(1,0),(0,-1))
    values=[]
    for dr,dc in offsets:
        rr,cc=r+dr,c+dc
        values.append(grid.cell(rr,cc) if 0<=rr<grid.h and 0<=cc<grid.w else -1)
    return tuple(values)


def feature(grid: Grid, r: int, c: int, kind: str):
    center=grid.cell(r,c)
    if kind=='orth_set':
        return (center,tuple(sorted(set(_neighbors(grid,r,c,diagonal=False)))))
    if kind=='neighbor_set':
        return (center,tuple(sorted(set(_neighbors(grid,r,c,diagonal=True)))))
    if kind=='orth_counts':
        return (center,tuple(sorted(Counter(_neighbors(grid,r,c,diagonal=False)).items())))
    if kind=='neighbor_counts':
        return (center,tuple(sorted(Counter(_neighbors(grid,r,c,diagonal=True)).items())))
    raise ValueError('unknown local feature kind')


def rewrite_sparse(grid: Grid, kind: str, rules) -> Grid:
    table=dict(rules)
    rows=[]
    for r in range(grid.h):
        row=[]
        for c in range(grid.w):
            key=feature(grid,r,c,kind)
            row.append(int(table.get(key,grid.cell(r,c))))
        rows.append(tuple(row))
    return Grid.from_rows(rows)
