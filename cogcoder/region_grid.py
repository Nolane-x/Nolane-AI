from __future__ import annotations

from collections import deque
from .arc_grid import Grid, infer_background


def internal_cells(grid:Grid):
    bg=infer_background(grid)
    remaining={(r,c) for r in range(grid.h) for c in range(grid.w) if grid.cell(r,c)==bg}
    internal=set()
    while remaining:
        start=min(remaining); remaining.remove(start)
        q=deque([start]); comp={start}; touches=False
        while q:
            r,c=q.popleft()
            if r in (0,grid.h-1) or c in (0,grid.w-1): touches=True
            for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
                p=(r+dr,c+dc)
                if p in remaining:
                    remaining.remove(p); comp.add(p); q.append(p)
        if not touches: internal.update(comp)
    return frozenset(internal)


def project_internal(grid:Grid,color:int):
    cells=internal_cells(grid)
    rows=[list(row) for row in grid.rows]
    for r,c in cells: rows[r][c]=int(color)
    return Grid.from_rows(rows)
