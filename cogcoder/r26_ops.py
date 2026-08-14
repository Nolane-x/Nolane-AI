from __future__ import annotations

from .arc_ops_view import Program, Step, apply_step as apply_legacy_step
from .r26_structural import frame_inner, separator_map, separator_repack, unique_foreground_panel


def apply_step(step: Step, grid):
    if step.op == 'separator_map':
        return separator_map(grid)
    if step.op == 'separator_repack':
        return separator_repack(grid)
    if step.op == 'frame_inner':
        return frame_inner(grid)
    if step.op == 'unique_foreground_panel':
        return unique_foreground_panel(grid)
    return apply_legacy_step(step, grid)


def apply_program(program: Program, grid):
    out = grid
    for step in program.steps:
        out = apply_step(step, out)
    return out


__all__ = ['Program', 'Step', 'apply_step', 'apply_program']
