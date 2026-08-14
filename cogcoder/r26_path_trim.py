from __future__ import annotations

from .arc_grid import Grid, components
from .arc_ops_view import Program, Step

Pair = tuple[Grid, Grid]
_NEIGHBORS = ((-1,0),(1,0),(0,-1),(0,1))


def _background(grid: Grid) -> int:
    hist = grid.histogram()
    top = max(hist.values())
    colors = [int(color) for color, count in hist.items() if count == top]
    if len(colors) != 1:
        raise ValueError('background role is ambiguous')
    return colors[0]


def _inside(grid: Grid, r: int, c: int) -> bool:
    return 0 <= r < grid.h and 0 <= c < grid.w


def _adjacent_cells(cells: set[tuple[int,int]], cell: tuple[int,int]) -> list[tuple[int,int]]:
    r, c = cell
    return [(r+dr, c+dc) for dr, dc in _NEIGHBORS if (r+dr, c+dc) in cells]


def _simple_path(cells: set[tuple[int,int]]):
    if len(cells) < 2:
        return None
    degrees = {cell: len(_adjacent_cells(cells, cell)) for cell in cells}
    endpoints = [cell for cell, degree in degrees.items() if degree == 1]
    if len(endpoints) != 2 or any(degree not in {1,2} for degree in degrees.values()):
        return None
    return tuple(sorted(endpoints))


def _gate(grid: Grid, start: tuple[int,int], neighbor: tuple[int,int], path_color: int, background: int):
    sr, sc = start
    nr, nc = neighbor
    dr, dc = nr - sr, nc - sc
    if (dr, dc) not in _NEIGHBORS:
        return None
    if dr:
        positions = ((sr, sc-1), (sr, sc+1))
    else:
        positions = ((sr-1, sc), (sr+1, sc))
    if not all(_inside(grid, r, c) for r, c in positions):
        return None
    values = [grid.cell(r, c) for r, c in positions]
    if values[0] != values[1] or values[0] in {background, path_color}:
        return None
    return int(values[0])


def _far_marker(
    grid: Grid,
    endpoint: tuple[int,int],
    path_cells: set[tuple[int,int]],
    path_color: int,
    gate_color: int,
    background: int,
):
    r, c = endpoint
    candidates = []
    for dr, dc in _NEIGHBORS:
        pos = (r+dr, c+dc)
        if not _inside(grid, *pos) or pos in path_cells:
            continue
        value = grid.cell(*pos)
        if value not in {background, path_color, gate_color}:
            candidates.append((pos, int(value)))
    if len(candidates) != 1:
        return None
    return candidates[0]


def gate_path_trim(grid: Grid) -> Grid:
    background = _background(grid)
    edits: dict[tuple[int,int], int] = {}
    found = 0

    for path_color in sorted(grid.colors - {background}):
        for comp in components(grid, color=path_color, connectivity=4):
            cells = set(comp)
            endpoints = _simple_path(cells)
            if endpoints is None:
                continue
            matched = None
            for start in endpoints:
                neighbors = _adjacent_cells(cells, start)
                if len(neighbors) != 1:
                    continue
                next_cell = neighbors[0]
                gate_color = _gate(grid, start, next_cell, int(path_color), background)
                if gate_color is None:
                    continue
                far = endpoints[1] if start == endpoints[0] else endpoints[0]
                marker = _far_marker(
                    grid,
                    far,
                    cells,
                    int(path_color),
                    gate_color,
                    background,
                )
                if marker is None:
                    continue
                matched = (start, next_cell, marker)
                break
            if matched is None:
                continue

            start, next_cell, (marker_pos, marker_color) = matched
            edits[next_cell] = marker_color
            for cell in cells:
                if cell not in {start, next_cell}:
                    edits[cell] = background
            edits[marker_pos] = background
            found += 1

    if found == 0:
        raise ValueError('no gate-to-marker path found')
    rows = [list(row) for row in grid.rows]
    for (r, c), value in edits.items():
        rows[r][c] = value
    return Grid.from_rows(rows)


def programs(pairs) -> tuple[Program, ...]:
    pairs = tuple(pairs)
    if not pairs:
        return ()
    try:
        if all(gate_path_trim(inp) == target for inp, target in pairs):
            return (Program((Step('gate_path_trim', ()),), 3),)
    except (ValueError, ArithmeticError, OverflowError, StopIteration, TypeError):
        pass
    return ()
