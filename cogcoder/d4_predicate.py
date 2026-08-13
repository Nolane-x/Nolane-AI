from __future__ import annotations

from .arc_grid import Grid, transform


def invariant_under(grid: Grid, kind: str) -> bool:
    return transform(grid,str(kind))==grid
