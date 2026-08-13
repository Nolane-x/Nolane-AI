from __future__ import annotations

from collections import Counter
from .arc_grid import Grid

KINDS=('orth_set','neighbor_set','orth_counts','neighbor_counts','orth_tuple','neighbor_tuple')


def _neighbors(grid: Grid,r:int,c:int,diagonal:bool):
    offsets=(tuple((dr,dc) for dr in (-1,0,1) for dc in (-1,0,1) if (dr,dc)!=(0,0)) if diagonal else ((-1,0),(0,1),(1,0),(0,-1)))
    return tuple(grid.cell(r+dr,c+dc) if 0<=r+dr<grid.h and 0<=c+dc<grid.w else -1 for dr,dc in offsets)


def feature(grid: Grid,r:int,c:int,kind:str):
    center=grid.cell(r,c)
    orth=_neighbors(grid,r,c,False); neigh=_neighbors(grid,r,c,True)
    if kind=='orth_set': return (center,tuple(sorted(set(orth))))
    if kind=='neighbor_set': return (center,tuple(sorted(set(neigh))))
    if kind=='orth_counts': return (center,tuple(sorted(Counter(orth).items())))
    if kind=='neighbor_counts': return (center,tuple(sorted(Counter(neigh).items())))
    if kind=='orth_tuple': return (center,orth)
    if kind=='neighbor_tuple': return (center,neigh)
    raise ValueError('unknown local feature kind')


def rewrite_sparse(grid:Grid,kind:str,rules):
    table=dict(rules); rows=[]
    for r in range(grid.h):
        rows.append(tuple(int(table.get(feature(grid,r,c,kind),grid.cell(r,c))) for c in range(grid.w)))
    return Grid.from_rows(rows)
