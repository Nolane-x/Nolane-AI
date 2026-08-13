from __future__ import annotations

from .arc_grid import Grid, infer_background, transform


def repeat_edge_frame(grid: Grid, corner_color: int = 0) -> Grid:
    corner=int(corner_color)
    if not 0 <= corner <= 9:
        raise ValueError('corner color must be an ARC color')
    if grid.h+2>30 or grid.w+2>30:
        raise ValueError('framed grid exceeds ARC bounds')
    rows=[(corner,)+tuple(grid.rows[0])+(corner,)]
    for row in grid.rows:
        rows.append((row[0],)+tuple(row)+(row[-1],))
    rows.append((corner,)+tuple(grid.rows[-1])+(corner,))
    return Grid.from_rows(rows)


def anchored_complement_mirror(grid: Grid, marker_color: int) -> Grid:
    bg=infer_background(grid); marker=int(marker_color)
    if marker==bg or not 0<=marker<=9:
        raise ValueError('marker must be a non-background ARC color')
    if grid.w*2>30:
        raise ValueError('mirrored grid exceeds ARC bounds')
    left_blank=all(grid.cell(r,0)==bg for r in range(grid.h))
    right_blank=all(grid.cell(r,grid.w-1)==bg for r in range(grid.h))
    if left_blank==right_blank:
        raise ValueError('exactly one vertical edge must be background')
    mirrored=transform(grid,'flip_h')
    complement=Grid.from_rows(tuple(marker if value==bg else bg for value in row) for row in mirrored.rows)
    if left_blank:
        return Grid.from_rows(tuple(a)+tuple(b) for a,b in zip(grid.rows,complement.rows))
    return Grid.from_rows(tuple(a)+tuple(b) for a,b in zip(complement.rows,grid.rows))
