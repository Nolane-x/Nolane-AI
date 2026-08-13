from __future__ import annotations

from .arc_grid import Grid, infer_background, transform


def combine_with_view(grid: Grid, kind: str) -> Grid:
    other=transform(grid,str(kind))
    if other.shape!=grid.shape:
        raise ValueError('shape-preserving view required')
    bg=infer_background(grid)
    rows=[]
    for r in range(grid.h):
        row=[]
        for c in range(grid.w):
            a=grid.cell(r,c); b=other.cell(r,c)
            row.append(a if a!=bg else b)
        rows.append(tuple(row))
    return Grid.from_rows(rows)
