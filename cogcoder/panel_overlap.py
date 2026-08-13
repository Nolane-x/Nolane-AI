from __future__ import annotations

from .arc_grid import Grid, infer_background


def common_filled(grid: Grid, axis: str, marker: int) -> Grid:
    marker=int(marker)
    if axis=='h':
        if grid.w%2!=1: raise ValueError('odd width required')
        mid=grid.w//2; values={grid.cell(r,mid) for r in range(grid.h)}
        if len(values)!=1 or next(iter(values))==0: raise ValueError('center divider required')
        a=Grid.from_rows(row[:mid] for row in grid.rows); b=Grid.from_rows(row[mid+1:] for row in grid.rows)
    elif axis=='v':
        if grid.h%2!=1: raise ValueError('odd height required')
        mid=grid.h//2; values=set(grid.rows[mid])
        if len(values)!=1 or next(iter(values))==0: raise ValueError('center divider required')
        a=Grid.from_rows(grid.rows[:mid]); b=Grid.from_rows(grid.rows[mid+1:])
    else:
        raise ValueError('axis must be h or v')
    ba,bb=infer_background(a),infer_background(b)
    return Grid.from_rows(tuple(marker if a.cell(r,c)!=ba and b.cell(r,c)!=bb else 0 for c in range(a.w)) for r in range(a.h))
