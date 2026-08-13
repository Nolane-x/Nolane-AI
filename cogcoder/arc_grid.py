from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Iterable

from .grid_prior import preferred_background


@dataclass(frozen=True)
class Grid:
    rows: tuple[tuple[int, ...], ...]

    @classmethod
    def from_rows(cls, rows: Iterable[Iterable[int]]) -> 'Grid':
        data = tuple(tuple(int(v) for v in row) for row in rows)
        if not data or not data[0]:
            raise ValueError('grid must be non-empty')
        w = len(data[0])
        if any(len(r) != w for r in data):
            raise ValueError('grid must be rectangular')
        if len(data) > 30 or w > 30:
            raise ValueError('ARC grid exceeds 30x30')
        if any(v < 0 or v > 9 for r in data for v in r):
            raise ValueError('ARC colors must be in 0..9')
        return cls(data)

    @property
    def h(self) -> int:
        return len(self.rows)

    @property
    def w(self) -> int:
        return len(self.rows[0])

    @property
    def shape(self) -> tuple[int, int]:
        return self.h, self.w

    @property
    def colors(self) -> set[int]:
        return {v for r in self.rows for v in r}

    def histogram(self) -> Counter:
        return Counter(v for r in self.rows for v in r)

    def cell(self, r: int, c: int) -> int:
        return self.rows[r][c]

    def to_lists(self) -> list[list[int]]:
        return [list(r) for r in self.rows]


def infer_background(grid: Grid) -> int:
    return preferred_background(grid.histogram())


def components(grid: Grid, *, color: int | None = None, background: int | None = None, connectivity: int = 4) -> tuple[frozenset[tuple[int,int]], ...]:
    if connectivity not in (4, 8):
        raise ValueError('connectivity must be 4 or 8')
    bg = infer_background(grid) if background is None else int(background)
    eligible = {(r,c) for r in range(grid.h) for c in range(grid.w) if (grid.cell(r,c) == color if color is not None else grid.cell(r,c) != bg)}
    dirs = ((1,0),(-1,0),(0,1),(0,-1)) if connectivity == 4 else tuple((dr,dc) for dr in (-1,0,1) for dc in (-1,0,1) if (dr,dc)!=(0,0))
    out = []
    while eligible:
        start = min(eligible)
        eligible.remove(start)
        q = deque([start]); comp = {start}
        while q:
            r,c = q.popleft()
            for dr,dc in dirs:
                p = (r+dr,c+dc)
                if p in eligible:
                    eligible.remove(p); comp.add(p); q.append(p)
        out.append(frozenset(comp))
    out.sort(key=lambda s:(min(s), len(s)))
    return tuple(out)


def bbox(cells: Iterable[tuple[int,int]]) -> tuple[int,int,int,int]:
    cells = tuple(cells)
    if not cells:
        raise ValueError('empty cell set')
    rs = [p[0] for p in cells]; cs = [p[1] for p in cells]
    return min(rs), min(cs), max(rs), max(cs)


def crop(grid: Grid, box: tuple[int,int,int,int]) -> Grid:
    r0,c0,r1,c1 = box
    if not (0 <= r0 <= r1 < grid.h and 0 <= c0 <= c1 < grid.w):
        raise ValueError('invalid crop box')
    return Grid.from_rows(row[c0:c1+1] for row in grid.rows[r0:r1+1])


def transform(grid: Grid, kind: str) -> Grid:
    a = grid.rows
    if kind == 'identity': return grid
    if kind == 'rot90': return Grid.from_rows(zip(*a[::-1]))
    if kind == 'rot180': return Grid.from_rows(row[::-1] for row in a[::-1])
    if kind == 'rot270': return Grid.from_rows(tuple(zip(*a))[::-1])
    if kind == 'flip_h': return Grid.from_rows(row[::-1] for row in a)
    if kind == 'flip_v': return Grid.from_rows(a[::-1])
    if kind == 'transpose': return Grid.from_rows(zip(*a))
    if kind == 'anti_transpose': return transform(transform(grid,'transpose'),'rot180')
    raise ValueError(f'unknown transform {kind}')


def scale_nearest(grid: Grid, row_factor: int, col_factor: int | None = None) -> Grid:
    rf = int(row_factor); cf = rf if col_factor is None else int(col_factor)
    if rf < 1 or cf < 1 or grid.h*rf > 30 or grid.w*cf > 30:
        raise ValueError('invalid scale')
    rows=[]
    for row in grid.rows:
        expanded = tuple(v for v in row for _ in range(cf))
        rows.extend([expanded]*rf)
    return Grid.from_rows(rows)
