from __future__ import annotations

from collections import Counter

from .arc_grid import Grid, bbox, components, crop, infer_background
from .arc_ops_view import Program, Step

Pair = tuple[Grid, Grid]


def _separator_axes(grid: Grid) -> tuple[int, tuple[int, ...], tuple[int, ...]]:
    row_by_color: dict[int, list[int]] = {}
    col_by_color: dict[int, list[int]] = {}
    for r in range(1, grid.h - 1):
        values = set(grid.rows[r])
        if len(values) == 1:
            color = int(next(iter(values)))
            row_by_color.setdefault(color, []).append(r)
    for c in range(1, grid.w - 1):
        values = {grid.cell(r, c) for r in range(grid.h)}
        if len(values) == 1:
            color = int(next(iter(values)))
            col_by_color.setdefault(color, []).append(c)
    candidates = sorted(set(row_by_color) & set(col_by_color))
    if len(candidates) != 1:
        raise ValueError('separator color is absent or ambiguous')
    color = candidates[0]
    return color, tuple(row_by_color[color]), tuple(col_by_color[color])


def _segments(length: int, separators: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    blocked = set(separators)
    parts: list[tuple[int, int]] = []
    start = 0
    for i in range(length + 1):
        if i == length or i in blocked:
            if start < i:
                parts.append((start, i))
            start = i + 1
    return tuple(parts)


def _dominant_nonseparator(grid: Grid, separator: int) -> int:
    counts = Counter(v for row in grid.rows for v in row if v != separator)
    if not counts:
        raise ValueError('no nonseparator color')
    top = max(counts.values())
    colors = sorted(color for color, count in counts.items() if count == top)
    if len(colors) != 1:
        raise ValueError('dominant nonseparator color is ambiguous')
    return int(colors[0])


def separator_map(grid: Grid) -> Grid:
    separator, row_seps, col_seps = _separator_axes(grid)
    rparts = _segments(grid.h, row_seps)
    cparts = _segments(grid.w, col_seps)
    if len(rparts) < 2 or len(cparts) < 2:
        raise ValueError('separator map requires a 2D partition')
    fill = _dominant_nonseparator(grid, separator)
    return Grid.from_rows([[fill] * len(cparts) for _ in range(len(rparts))])


def _crop_nonbackground(grid: Grid) -> Grid:
    bg = infer_background(grid)
    cells = {(r, c) for r in range(grid.h) for c in range(grid.w) if grid.cell(r, c) != bg}
    if not cells:
        raise ValueError('empty panel')
    return crop(grid, bbox(cells))


def separator_repack(grid: Grid) -> Grid:
    _, row_seps, col_seps = _separator_axes(grid)
    rparts = _segments(grid.h, row_seps)
    cparts = _segments(grid.w, col_seps)
    if len(rparts) < 2 or len(cparts) < 2:
        raise ValueError('repack requires a 2D partition')
    panels: list[list[Grid]] = []
    for r0, r1 in rparts:
        row: list[Grid] = []
        for c0, c1 in cparts:
            panel = Grid.from_rows(source[c0:c1] for source in grid.rows[r0:r1])
            row.append(_crop_nonbackground(panel))
        panels.append(row)
    shapes = {panel.shape for row in panels for panel in row}
    if len(shapes) != 1:
        raise ValueError('cropped panel shapes differ')
    ph, _ = next(iter(shapes))
    rows = []
    for panel_row in panels:
        for r in range(ph):
            rows.append(tuple(v for panel in panel_row for v in panel.rows[r]))
    return Grid.from_rows(rows)


def _active_bands(grid: Grid, *, axis: str, background: int) -> tuple[tuple[int, int], ...]:
    if axis == 'rows':
        active = [any(v != background for v in grid.rows[r]) for r in range(grid.h)]
    elif axis == 'cols':
        active = [any(grid.cell(r, c) != background for r in range(grid.h)) for c in range(grid.w)]
    else:
        raise ValueError('axis must be rows or cols')
    bands: list[tuple[int, int]] = []
    start = None
    for index, is_active in enumerate(active + [False]):
        if is_active and start is None:
            start = index
        elif not is_active and start is not None:
            bands.append((start, index))
            start = None
    return tuple(bands)


def unique_foreground_panel(grid: Grid) -> Grid:
    """Select the background-separated panel whose sole foreground color is unique.

    The rule is position- and raw-color-independent. Every non-empty panel must
    contain exactly one non-background color. Exactly one panel color must occur
    once while at least one other panel color occurs multiple times.
    """
    background = infer_background(grid)
    row_bands = _active_bands(grid, axis='rows', background=background)
    col_bands = _active_bands(grid, axis='cols', background=background)
    if len(row_bands) < 2 or len(col_bands) < 2:
        raise ValueError('unique panel extraction requires a background-separated panel grid')

    panels: list[tuple[Grid, int]] = []
    for r0, r1 in row_bands:
        for c0, c1 in col_bands:
            panel = Grid.from_rows(row[c0:c1] for row in grid.rows[r0:r1])
            foreground = sorted(panel.colors - {background})
            if not foreground:
                continue
            if len(foreground) != 1:
                raise ValueError('panel has multiple foreground colors')
            panels.append((panel, int(foreground[0])))
    if len(panels) < 3:
        raise ValueError('not enough non-empty panels')

    counts = Counter(color for _, color in panels)
    unique_colors = [color for color, count in counts.items() if count == 1]
    repeated_colors = [color for color, count in counts.items() if count >= 2]
    if len(unique_colors) != 1 or not repeated_colors:
        raise ValueError('foreground-color uniqueness is absent or ambiguous')
    selected = [panel for panel, color in panels if color == unique_colors[0]]
    if len(selected) != 1:
        raise ValueError('unique panel is ambiguous')
    return selected[0]


def _perfect_frame_boxes(grid: Grid) -> tuple[tuple[int, int, int, int], ...]:
    boxes: set[tuple[int, int, int, int]] = set()
    background = infer_background(grid)
    for color in sorted(grid.colors):
        if color == background:
            continue
        for cells in components(grid, color=color, connectivity=4):
            r0, c0, r1, c1 = bbox(cells)
            if r1 - r0 < 2 or c1 - c0 < 2:
                continue
            border = (
                [(r0, c) for c in range(c0, c1 + 1)]
                + [(r1, c) for c in range(c0, c1 + 1)]
                + [(r, c0) for r in range(r0 + 1, r1)]
                + [(r, c1) for r in range(r0 + 1, r1)]
            )
            if all(grid.cell(r, c) == color for r, c in border):
                boxes.add((r0, c0, r1, c1))
    return tuple(sorted(boxes))


def frame_inner(grid: Grid) -> Grid:
    boxes = _perfect_frame_boxes(grid)
    if len(boxes) != 1:
        raise ValueError('rectangular frame absent or ambiguous')
    r0, c0, r1, c1 = boxes[0]
    return Grid.from_rows(row[c0 + 1 : c1] for row in grid.rows[r0 + 1 : r1])


_OPERATIONS = (
    ('separator_map', separator_map, 2),
    ('separator_repack', separator_repack, 3),
    ('frame_inner', frame_inner, 2),
    ('unique_foreground_panel', unique_foreground_panel, 3),
)


def programs(pairs) -> tuple[Program, ...]:
    pairs = tuple(pairs)
    if not pairs:
        return ()
    out: list[Program] = []
    for name, fn, cost in _OPERATIONS:
        try:
            if all(fn(inp) == target for inp, target in pairs):
                out.append(Program((Step(name, ()),), cost))
        except (ValueError, ArithmeticError, OverflowError, StopIteration, TypeError):
            continue
    return tuple(out)
