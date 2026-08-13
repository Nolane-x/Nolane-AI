from __future__ import annotations

from math import gcd
from .arc_grid import Grid, transform


def alternating_reflect(grid: Grid, row_blocks: int, col_blocks: int) -> Grid:
    rb=int(row_blocks); cb=int(col_blocks)
    if rb<1 or cb<1 or grid.h*rb>30 or grid.w*cb>30: raise ValueError('invalid factors')
    rows=[]; flipped=transform(grid,'flip_h')
    for block_row in range(rb):
        source=grid if block_row%2==0 else flipped
        for row in source.rows: rows.append(tuple(v for _ in range(cb) for v in row))
    return Grid.from_rows(rows)


def _period(items):
    items=tuple(items)
    for p in range(1,len(items)+1):
        if all(items[i]==items[i%p] for i in range(len(items))): return items[:p]
    return items


def extend_period(grid: Grid, axis: str, numerator: int, denominator: int) -> Grid:
    num=int(numerator); den=int(denominator)
    if num<1 or den<1: raise ValueError('positive ratio required')
    g=gcd(num,den); num//=g; den//=g
    if axis=='v':
        total=grid.h*num
        if total%den: raise ValueError('non-integer height')
        target=total//den; period=_period(grid.rows)
        if not 1<=target<=30: raise ValueError('invalid height')
        return Grid.from_rows(period[i%len(period)] for i in range(target))
    if axis=='h':
        total=grid.w*num
        if total%den: raise ValueError('non-integer width')
        target=total//den
        if not 1<=target<=30: raise ValueError('invalid width')
        cols=tuple(tuple(grid.cell(r,c) for r in range(grid.h)) for c in range(grid.w))
        period=_period(cols); out=tuple(period[i%len(period)] for i in range(target))
        return Grid.from_rows(tuple(out[c][r] for c in range(target)) for r in range(grid.h))
    raise ValueError('axis must be v or h')
