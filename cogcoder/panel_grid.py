from __future__ import annotations

from .arc_grid import Grid, infer_background


def _uniform_rows(grid: Grid):
    return [r for r,row in enumerate(grid.rows) if 0<r<grid.h-1 and len(set(row))==1 and row[0]!=0]


def _uniform_cols(grid: Grid):
    cols=[]
    for c in range(1,grid.w-1):
        values={grid.cell(r,c) for r in range(grid.h)}
        if len(values)==1 and next(iter(values))!=0:
            cols.append(c)
    return cols


def _segments(length: int, separators):
    separators=set(separators); parts=[]; start=0
    for i in range(length+1):
        if i==length or i in separators:
            if start<i: parts.append((start,i))
            start=i+1
    return parts


def split_panels(grid: Grid):
    row_seps=_uniform_rows(grid); col_seps=_uniform_cols(grid)
    if not row_seps and not col_seps:
        raise ValueError('no panel separator')
    rparts=_segments(grid.h,row_seps) if row_seps else [(0,grid.h)]
    cparts=_segments(grid.w,col_seps) if col_seps else [(0,grid.w)]
    return tuple(Grid.from_rows(row[c0:c1] for row in grid.rows[r0:r1]) for r0,r1 in rparts for c0,c1 in cparts)


def overlay_panels(panels):
    panels=tuple(panels)
    if not panels: raise ValueError('no panels')
    shape=panels[0].shape
    if any(p.shape!=shape for p in panels): raise ValueError('panel shapes differ')
    backgrounds=[infer_background(p) for p in panels]
    rows=[]
    for r in range(shape[0]):
        row=[]
        for c in range(shape[1]):
            values=[p.cell(r,c) for p,bg in zip(panels,backgrounds) if p.cell(r,c)!=bg]
            if len(set(values))>1: raise ValueError('panel overlay conflict')
            row.append(values[0] if values else backgrounds[0])
        rows.append(tuple(row))
    return Grid.from_rows(rows)


def overlay_from_separated(grid: Grid) -> Grid:
    return overlay_panels(split_panels(grid))
