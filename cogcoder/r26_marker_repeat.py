from __future__ import annotations

from .arc_grid import Grid, infer_background
from .arc_ops_view import Program, Step

Pair = tuple[Grid, Grid]


def _consecutive(values: list[int]) -> bool:
    return bool(values) and values == list(range(values[0], values[-1] + 1))


def _marker(grid: Grid, axis: str) -> tuple[int, str, int]:
    """Return (marker_color, end, length) for a unique border control bar.

    `axis='rows'` means a vertical bar whose length defines row slices.
    `axis='cols'` means a horizontal bar whose length defines column slices.
    `end` is `start` when the bar touches row/column zero, otherwise `end`.
    """
    background = infer_background(grid)
    candidates: list[tuple[int, str, int]] = []
    for color in sorted(grid.colors - {background}):
        coords = [(r, c) for r in range(grid.h) for c in range(grid.w) if grid.cell(r, c) == color]
        if not coords:
            continue
        if axis == 'rows':
            cols = {c for _, c in coords}
            rows = sorted(r for r, _ in coords)
            if len(cols) != 1 or next(iter(cols)) not in {0, grid.w - 1} or not _consecutive(rows):
                continue
            if rows[0] == 0 and rows[-1] != grid.h - 1:
                candidates.append((int(color), 'start', len(rows)))
            elif rows[-1] == grid.h - 1 and rows[0] != 0:
                candidates.append((int(color), 'end', len(rows)))
        elif axis == 'cols':
            rows = {r for r, _ in coords}
            cols = sorted(c for _, c in coords)
            if len(rows) != 1 or next(iter(rows)) not in {0, grid.h - 1} or not _consecutive(cols):
                continue
            if cols[0] == 0 and cols[-1] != grid.w - 1:
                candidates.append((int(color), 'start', len(cols)))
            elif cols[-1] == grid.w - 1 and cols[0] != 0:
                candidates.append((int(color), 'end', len(cols)))
        else:
            raise ValueError('axis must be rows or cols')
    if len(candidates) != 1:
        raise ValueError('border marker is absent or ambiguous')
    return candidates[0]


def _without_marker(values, marker: int, background: int):
    return tuple(background if int(v) == marker else int(v) for v in values)


def border_marker_repeat(grid: Grid, axis: str) -> Grid:
    background = infer_background(grid)
    marker, end, length = _marker(grid, axis)
    if length < 1:
        raise ValueError('empty marker')

    nonmarker = [
        (r, c)
        for r in range(grid.h)
        for c in range(grid.w)
        if grid.cell(r, c) not in {background, marker}
    ]
    if not nonmarker:
        raise ValueError('marker has no motif content')

    rows = [list(row) for row in grid.rows]
    changed = False

    if axis == 'rows':
        if end == 'start':
            content_edge = max(r for r, _ in nonmarker)
            if content_edge >= grid.h - 1:
                raise ValueError('no blank row extension')
            template = [
                _without_marker(grid.rows[r], marker, background)
                for r in range(length)
            ]
            for offset, r in enumerate(range(content_edge + 1, grid.h)):
                if any(v != background for v in grid.rows[r]):
                    raise ValueError('tail is not blank')
                rows[r] = list(template[offset % length])
                changed = True
        else:
            content_edge = min(r for r, _ in nonmarker)
            if content_edge <= 0:
                raise ValueError('no blank row extension')
            traversal = [
                _without_marker(grid.rows[grid.h - 1 - i], marker, background)
                for i in range(length)
            ]
            for offset, r in enumerate(range(content_edge - 1, -1, -1)):
                if any(v != background for v in grid.rows[r]):
                    raise ValueError('head is not blank')
                rows[r] = list(traversal[offset % length])
                changed = True
    elif axis == 'cols':
        if end == 'start':
            content_edge = max(c for _, c in nonmarker)
            if content_edge >= grid.w - 1:
                raise ValueError('no blank column extension')
            template = [
                tuple(background if grid.cell(r, c) == marker else grid.cell(r, c) for r in range(grid.h))
                for c in range(length)
            ]
            for offset, c in enumerate(range(content_edge + 1, grid.w)):
                if any(grid.cell(r, c) != background for r in range(grid.h)):
                    raise ValueError('tail is not blank')
                source = template[offset % length]
                for r, value in enumerate(source):
                    rows[r][c] = value
                changed = True
        else:
            content_edge = min(c for _, c in nonmarker)
            if content_edge <= 0:
                raise ValueError('no blank column extension')
            traversal = [
                tuple(
                    background if grid.cell(r, grid.w - 1 - i) == marker else grid.cell(r, grid.w - 1 - i)
                    for r in range(grid.h)
                )
                for i in range(length)
            ]
            for offset, c in enumerate(range(content_edge - 1, -1, -1)):
                if any(grid.cell(r, c) != background for r in range(grid.h)):
                    raise ValueError('head is not blank')
                source = traversal[offset % length]
                for r, value in enumerate(source):
                    rows[r][c] = value
                changed = True
    else:
        raise ValueError('axis must be rows or cols')

    if not changed:
        raise ValueError('marker repeat made no change')
    return Grid.from_rows(rows)


def programs(pairs) -> tuple[Program, ...]:
    pairs = tuple(pairs)
    if not pairs:
        return ()
    out = []
    for axis in ('rows', 'cols'):
        try:
            if all(border_marker_repeat(inp, axis) == target for inp, target in pairs):
                out.append(Program((Step('border_marker_repeat', (axis,)),), 3))
        except (ValueError, ArithmeticError, OverflowError, StopIteration, TypeError):
            continue
    return tuple(out)
