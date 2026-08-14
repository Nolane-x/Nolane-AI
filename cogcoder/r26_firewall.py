from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .arc_grid import Grid
from .arc_ops_view import Program
from .r26_canonical import canonical_color_roles, color_role_signatures
from .r26_meta import permute_colors, transform_pair
from .r26_ops import apply_program

Pair = tuple[Grid, Grid]
Infer = Callable[[tuple[Pair, ...]], tuple[Program, ...]]


@dataclass(frozen=True)
class Evidence:
    loeo_passed: int
    loeo_total: int
    meta_passed: int
    meta_total: int

    @property
    def loeo_ratio(self) -> float:
        return self.loeo_passed / self.loeo_total if self.loeo_total else 0.0

    @property
    def meta_ratio(self) -> float:
        return self.meta_passed / self.meta_total if self.meta_total else 0.0


def _safe_infer(infer: Infer, pairs: tuple[Pair, ...]) -> tuple[Program, ...]:
    try:
        return tuple(infer(pairs))
    except (ValueError, ArithmeticError, OverflowError, StopIteration, TypeError):
        return ()


def _predicts(program: Program, pair: Pair) -> bool:
    inp, target = pair
    try:
        return apply_program(program, inp) == target
    except (ValueError, ArithmeticError, OverflowError, StopIteration, TypeError):
        return False


def _fits_all(program: Program, pairs: tuple[Pair, ...]) -> bool:
    return all(_predicts(program, pair) for pair in pairs)


def _loeo(infer: Infer, pairs: tuple[Pair, ...]) -> tuple[int, int]:
    if len(pairs) < 3:
        return 0, 0
    passed = 0
    for index, heldout in enumerate(pairs):
        fit = pairs[:index] + pairs[index + 1 :]
        programs = _safe_infer(infer, fit)
        passed += int(any(_predicts(program, heldout) for program in programs))
    return passed, len(pairs)


def _color_permutation(pairs: tuple[Pair, ...]) -> tuple[tuple[Pair, ...], ...]:
    role_pairs, ambiguous = canonical_color_roles(pairs)
    if ambiguous:
        return ()
    signatures = color_role_signatures(pairs)
    if not signatures:
        return ()
    max_background = max(signature[0] for signature in signatures.values())
    background_candidates = [color for color, signature in signatures.items() if signature[0] == max_background]
    if len(background_candidates) != 1:
        return ()
    background = background_candidates[0]
    role_order = [color for color, _ in sorted(role_pairs, key=lambda row: row[1]) if color != background]
    if len(role_order) < 2:
        return ()
    rotated = role_order[1:] + role_order[:1]
    mapping = tuple(zip(role_order, rotated))
    transformed = tuple((permute_colors(inp, mapping), permute_colors(out, mapping)) for inp, out in pairs)
    return (transformed,)


def _geometric_meta(pairs: tuple[Pair, ...], kind: str) -> tuple[tuple[Pair, ...], ...]:
    if kind == 'rot90' and any(inp.h != inp.w or out.h != out.w for inp, out in pairs):
        return ()
    try:
        transformed = tuple(transform_pair(pair, kind) for pair in pairs)
    except ValueError:
        return ()
    return (transformed,)


def _metamorphic_sets(pairs: tuple[Pair, ...], kind: str) -> tuple[tuple[Pair, ...], ...]:
    if kind == 'color':
        return _color_permutation(pairs)
    if kind in {'flip_h', 'rot90'}:
        return _geometric_meta(pairs, kind)
    raise ValueError(f'unsupported R2.6 metamorphism {kind}')


def validate_family(
    infer: Infer,
    pairs: Iterable[Pair],
    *,
    meta_kinds: tuple[str, ...] = ('color', 'flip_h', 'rot90'),
) -> Evidence:
    pairs = tuple(pairs)
    if not pairs:
        return Evidence(0, 0, 0, 0)

    loeo_passed, loeo_total = _loeo(infer, pairs)
    meta_passed = 0
    meta_total = 0
    for kind in meta_kinds:
        for transformed in _metamorphic_sets(pairs, kind):
            meta_total += 1
            programs = _safe_infer(infer, transformed)
            meta_passed += int(any(_fits_all(program, transformed) for program in programs))

    return Evidence(loeo_passed, loeo_total, meta_passed, meta_total)
