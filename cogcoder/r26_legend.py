from __future__ import annotations

from .arc_grid import Grid, infer_background
from .arc_ops_view import Program, Step

Pair = tuple[Grid, Grid]


def _corner_key(grid: Grid) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], tuple[int, int]]]:
    if grid.h < 2 or grid.w < 2:
        raise ValueError('grid too small for legend key')
    bg = infer_background(grid)
    candidates = []
    origins = ((0, 0), (0, grid.w - 2), (grid.h - 2, 0), (grid.h - 2, grid.w - 2))
    for r0, c0 in origins:
        coords = ((r0, c0), (r0, c0 + 1), (r0 + 1, c0), (r0 + 1, c0 + 1))
        values = tuple(grid.cell(r, c) for r, c in coords)
        if bg in values or len(set(values)) != 4:
            continue
        matrix = ((values[0], values[1]), (values[2], values[3]))
        candidates.append((coords, matrix))
    if len(candidates) != 1:
        raise ValueError('2x2 corner legend is absent or ambiguous')
    return candidates[0]


def legend_swap(grid: Grid, axis: str) -> Grid:
    coords, matrix = _corner_key(grid)
    a, b = matrix[0]
    c, d = matrix[1]
    if axis == 'rows':
        pairs = ((a, b), (c, d))
    elif axis == 'cols':
        pairs = ((a, c), (b, d))
    else:
        raise ValueError('legend axis must be rows or cols')
    mapping = {}
    for left, right in pairs:
        mapping[int(left)] = int(right)
        mapping[int(right)] = int(left)
    protected = set(coords)
    return Grid.from_rows(
        tuple(
            grid.cell(r, col) if (r, col) in protected else mapping.get(grid.cell(r, col), grid.cell(r, col))
            for col in range(grid.w)
        )
        for r in range(grid.h)
    )


def programs(pairs) -> tuple[Program, ...]:
    pairs = tuple(pairs)
    if not pairs:
        return ()
    out = []
    for axis in ('rows', 'cols'):
        try:
            if all(legend_swap(inp, axis) == target for inp, target in pairs):
                out.append(Program((Step('legend_swap', (axis,)),), 2))
        except (ValueError, ArithmeticError, OverflowError, StopIteration, TypeError):
            continue
    return tuple(out)
