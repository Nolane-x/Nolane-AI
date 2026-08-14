from __future__ import annotations

from .arc_grid import Grid, infer_background


def span_aligned(grid:Grid,paint:int):
    bg=infer_background(grid); rows=[list(row) for row in grid.rows]
    for marker in sorted(grid.colors-{bg}):
        cells=[(r,c) for r in range(grid.h) for c in range(grid.w) if grid.cell(r,c)==marker]
        for i,(r1,c1) in enumerate(cells):
            for r2,c2 in cells[i+1:]:
                if r1==r2:
                    lo,hi=sorted((c1,c2))
                    if hi-lo>1 and all(grid.cell(r1,c)==bg for c in range(lo+1,hi)):
                        for c in range(lo+1,hi): rows[r1][c]=int(paint)
                elif c1==c2:
                    lo,hi=sorted((r1,r2))
                    if hi-lo>1 and all(grid.cell(r,c1)==bg for r in range(lo+1,hi)):
                        for r in range(lo+1,hi): rows[r][c1]=int(paint)
    return Grid.from_rows(rows)
