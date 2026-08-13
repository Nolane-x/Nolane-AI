from __future__ import annotations

from itertools import permutations

from .arc_grid import Grid, infer_background
from .panel_grid import split_panels


def split_pair(grid: Grid, axis: str):
    if axis=='v':
        if grid.h%2: raise ValueError('even height required')
        half=grid.h//2
        return Grid.from_rows(grid.rows[:half]),Grid.from_rows(grid.rows[half:])
    if axis=='h':
        if grid.w%2: raise ValueError('even width required')
        half=grid.w//2
        return Grid.from_rows(row[:half] for row in grid.rows),Grid.from_rows(row[half:] for row in grid.rows)
    raise ValueError('axis must be v or h')


def mark_shared_empty(grid: Grid, axis: str, marker: int) -> Grid:
    a,b=split_pair(grid,axis)
    ba,bb=infer_background(a),infer_background(b)
    marker=int(marker)
    return Grid.from_rows(tuple(marker if a.cell(r,c)==ba and b.cell(r,c)==bb else 0 for c in range(a.w)) for r in range(a.h))


def first_visible(grid: Grid, order: tuple[int,...]) -> Grid:
    panels=split_panels(grid)
    if len(order)!=len(panels) or tuple(sorted(order))!=tuple(range(len(panels))): raise ValueError('invalid order')
    shape=panels[0].shape
    if any(p.shape!=shape for p in panels): raise ValueError('panel shapes differ')
    backgrounds=[infer_background(p) for p in panels]
    rows=[]
    for r in range(shape[0]):
        row=[]
        for c in range(shape[1]):
            value=0
            for i in order:
                v=panels[i].cell(r,c)
                if v!=backgrounds[i]: value=v; break
            row.append(value)
        rows.append(tuple(row))
    return Grid.from_rows(rows)


def orders(grid: Grid):
    panels=split_panels(grid)
    return tuple(permutations(range(len(panels)))) if 2<=len(panels)<=4 else ()
