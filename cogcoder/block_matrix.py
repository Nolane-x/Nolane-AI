from __future__ import annotations

from .arc_grid import Grid


def expand_masked(source: Grid, background: int) -> Grid:
    if source.h*source.h>30 or source.w*source.w>30:
        raise ValueError('expanded grid exceeds bounds')
    rows=[]
    blank=(int(background),)*source.w
    for mask_row in source.rows:
        for r in range(source.h):
            row=[]
            for value in mask_row:
                row.extend(source.rows[r] if value!=background else blank)
            rows.append(tuple(row))
    return Grid.from_rows(rows)
