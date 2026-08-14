from __future__ import annotations

from typing import Iterable

from .arc_grid import Grid, transform

Pair = tuple[Grid, Grid]


def permute_colors(grid: Grid, mapping: Iterable[tuple[int, int]]) -> Grid:
    pairs = tuple((int(a), int(b)) for a, b in mapping)
    sources = [a for a, _ in pairs]
    targets = [b for _, b in pairs]
    if len(set(sources)) != len(sources):
        raise ValueError('color permutation has duplicate sources')
    if len(set(targets)) != len(targets):
        raise ValueError('color permutation must be injective')
    table = dict(pairs)
    return Grid.from_rows(tuple(table.get(v, v) for v in row) for row in grid.rows)


def transform_pair(pair: Pair, kind: str) -> Pair:
    inp, out = pair
    if kind == 'rot90' and (inp.h != inp.w or out.h != out.w):
        raise ValueError('rot90 metamorphism is restricted to square input/output grids')
    return transform(inp, kind), transform(out, kind)


def inverse_kind(kind: str) -> str:
    inverse = {
        'identity': 'identity',
        'flip_h': 'flip_h',
        'flip_v': 'flip_v',
        'rot90': 'rot270',
        'rot180': 'rot180',
        'rot270': 'rot90',
        'transpose': 'transpose',
        'anti_transpose': 'anti_transpose',
    }
    try:
        return inverse[kind]
    except KeyError as exc:
        raise ValueError(f'unknown transform {kind}') from exc
