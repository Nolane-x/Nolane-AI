from __future__ import annotations

from .arc_ops import Program, Step, apply_program as apply_base_program, apply_step as apply_base_step
from .grid_fold import combine_with_view
from .local_grid_v2 import rewrite_sparse as rewrite_sparse_v2
from .object_grid import rewrite_objects


_V2_LOCAL_KINDS=('orth_tuple','neighbor_tuple','axis_set','axis_counts')


def apply_step(step: Step, grid):
    if step.op=='view_combine':
        return combine_with_view(grid,str(step.args[0]))
    if step.op=='local_rewrite' and str(step.args[0]) in _V2_LOCAL_KINDS:
        return rewrite_sparse_v2(grid,str(step.args[0]),step.args[1])
    if step.op=='object_rewrite':
        return rewrite_objects(grid,str(step.args[0]),step.args[1])
    return apply_base_step(step,grid)


def apply_program(program: Program, grid):
    out=grid
    for step in program.steps:
        out=apply_step(step,out)
    return out


__all__=['Program','Step','apply_step','apply_program','apply_base_program']
