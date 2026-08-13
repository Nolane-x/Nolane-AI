from __future__ import annotations

from .arc_ops import Program, Step, apply_program as apply_base_program, apply_step as apply_base_step
from .grid_fold import combine_with_view


def apply_step(step: Step, grid):
    if step.op=='view_combine':
        return combine_with_view(grid,str(step.args[0]))
    return apply_base_step(step,grid)


def apply_program(program: Program, grid):
    out=grid
    for step in program.steps:
        out=apply_step(step,out)
    return out


__all__=['Program','Step','apply_step','apply_program','apply_base_program']
