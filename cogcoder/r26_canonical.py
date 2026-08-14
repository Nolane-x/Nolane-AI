from __future__ import annotations

from collections import Counter

from .arc_grid import Grid, components, infer_background

Pair = tuple[Grid, Grid]


def _border_count(grid: Grid, color: int) -> int:
    return sum(
        1
        for r in range(grid.h)
        for c in range(grid.w)
        if grid.cell(r, c) == color and (r in (0, grid.h - 1) or c in (0, grid.w - 1))
    )


def _corner_count(grid: Grid, color: int) -> int:
    corners = {(0, 0), (0, grid.w - 1), (grid.h - 1, 0), (grid.h - 1, grid.w - 1)}
    return sum(1 for r, c in corners if grid.cell(r, c) == color)


def color_role_signatures(pairs: tuple[Pair, ...] | list[Pair]) -> dict[int, tuple[int, ...]]:
    pairs = tuple(pairs)
    colors = sorted({v for a, b in pairs for grid in (a, b) for v in grid.colors})
    signatures: dict[int, tuple[int, ...]] = {}
    for color in colors:
        background_votes = 0
        input_presence = 0
        output_presence = 0
        total_count = 0
        component_count = 0
        component_area_total = 0
        max_component_area = 0
        border_cells = 0
        corner_cells = 0
        changed_source = 0
        changed_target = 0
        for inp, out in pairs:
            for is_input, grid in ((True, inp), (False, out)):
                hist = grid.histogram()
                count = int(hist.get(color, 0))
                total_count += count
                if count:
                    if is_input:
                        input_presence += 1
                    else:
                        output_presence += 1
                    comps = components(grid, color=color)
                    component_count += len(comps)
                    areas = [len(comp) for comp in comps]
                    component_area_total += sum(areas)
                    max_component_area = max(max_component_area, max(areas, default=0))
                    border_cells += _border_count(grid, color)
                    corner_cells += _corner_count(grid, color)
                background_votes += int(infer_background(grid) == color)
            if inp.shape == out.shape:
                for r in range(inp.h):
                    for c in range(inp.w):
                        before, after = inp.cell(r, c), out.cell(r, c)
                        if before != after:
                            changed_source += int(before == color)
                            changed_target += int(after == color)
        signatures[color] = (
            background_votes,
            input_presence,
            output_presence,
            total_count,
            component_count,
            component_area_total,
            max_component_area,
            border_cells,
            corner_cells,
            changed_source,
            changed_target,
        )
    return signatures


def canonical_color_roles(pairs: tuple[Pair, ...] | list[Pair]) -> tuple[tuple[tuple[int, int], ...], bool]:
    signatures = color_role_signatures(pairs)
    counts = Counter(signatures.values())
    ambiguous = any(count > 1 for count in counts.values())
    ordered = sorted(signatures, key=lambda color: (signatures[color], color))
    return tuple((color, role) for role, color in enumerate(ordered)), ambiguous


def _apply_role_map(grid: Grid, mapping: dict[int, int]) -> Grid:
    return Grid.from_rows(tuple(mapping[v] for v in row) for row in grid.rows)


def canonicalize_pairs(pairs: tuple[Pair, ...] | list[Pair]) -> tuple[tuple[Pair, ...], bool]:
    pairs = tuple(pairs)
    role_pairs, ambiguous = canonical_color_roles(pairs)
    mapping = dict(role_pairs)
    normalized = tuple((_apply_role_map(inp, mapping), _apply_role_map(out, mapping)) for inp, out in pairs)
    return normalized, ambiguous
