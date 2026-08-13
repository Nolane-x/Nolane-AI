from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .arc_grid import Grid, bbox, components, crop, infer_background, scale_nearest, transform
from .block_matrix import expand_masked
from .d4_predicate import invariant_under
from .edge_relation import anchored_complement_mirror, repeat_edge_frame
from .grid_repeat import alternating_reflect, extend_period
from .local_grid import rewrite_sparse
from .panel_combine import first_visible, mark_shared_empty
from .panel_grid import overlay_from_separated
from .panel_overlap import common_filled
from .periodic_grid import recover_missing_patch
from .shape_place import bottom_anchor_shift, corner_chain


@dataclass(frozen=True)
class Step:
    op: str
    args: tuple


@dataclass(frozen=True)
class Program:
    steps: tuple[Step, ...]
    cost: int

    @property
    def signature(self) -> tuple:
        return tuple((s.op, s.args) for s in self.steps)


def infer_color_map(src: Grid, dst: Grid) -> tuple[tuple[int,int], ...] | None:
    if src.shape != dst.shape:
        return None
    mapping: dict[int,int] = {}
    for r in range(src.h):
        for c in range(src.w):
            a,b = src.cell(r,c), dst.cell(r,c)
            if a in mapping and mapping[a] != b:
                return None
            mapping[a] = b
    return tuple(sorted(mapping.items()))


def apply_color_map(grid: Grid, mapping: Iterable[tuple[int,int]]) -> Grid:
    m = dict((int(a),int(b)) for a,b in mapping)
    return Grid.from_rows(tuple(m.get(v,v) for v in row) for row in grid.rows)


def _component_metadata(grid: Grid):
    bg = infer_background(grid)
    out=[]
    for conn in (4,8):
        for comp in components(grid, background=bg, connectivity=conn):
            b=bbox(comp)
            colors={grid.cell(r,c) for r,c in comp}
            out.append({'cells':comp,'bbox':b,'area':len(comp),'colors':colors,'conn':conn})
    unique={m['cells']:m for m in out}
    return list(unique.values())


def select_component_crop(grid: Grid, criterion: str) -> Grid:
    meta=_component_metadata(grid)
    if not meta:
        raise ValueError('no foreground component')
    if criterion == 'largest': chosen=min(meta,key=lambda m:(-m['area'],m['bbox']))
    elif criterion == 'smallest': chosen=min(meta,key=lambda m:(m['area'],m['bbox']))
    elif criterion == 'topmost': chosen=min(meta,key=lambda m:(m['bbox'][0],m['bbox'][1],-m['area']))
    elif criterion == 'bottommost': chosen=min(meta,key=lambda m:(-m['bbox'][2],m['bbox'][1],-m['area']))
    elif criterion == 'leftmost': chosen=min(meta,key=lambda m:(m['bbox'][1],m['bbox'][0],-m['area']))
    elif criterion == 'rightmost': chosen=min(meta,key=lambda m:(-m['bbox'][3],m['bbox'][0],-m['area']))
    else: raise ValueError(f'unknown component criterion {criterion}')
    return crop(grid,chosen['bbox'])


def crop_nonbackground(grid: Grid) -> Grid:
    bg=infer_background(grid)
    cells={(r,c) for r in range(grid.h) for c in range(grid.w) if grid.cell(r,c)!=bg}
    if not cells: return grid
    return crop(grid,bbox(cells))


def crop_color(grid: Grid, color: int) -> Grid:
    cells={(r,c) for r in range(grid.h) for c in range(grid.w) if grid.cell(r,c)==int(color)}
    if not cells: raise ValueError('color absent')
    return crop(grid,bbox(cells))


def concat(grid: Grid, axis: str, copies: int) -> Grid:
    n=int(copies)
    if n < 1: raise ValueError('copies must be positive')
    if axis == 'h':
        if grid.w*n > 30: raise ValueError('concat too wide')
        return Grid.from_rows(tuple(v for _ in range(n) for v in row) for row in grid.rows)
    if axis == 'v':
        if grid.h*n > 30: raise ValueError('concat too tall')
        return Grid.from_rows(grid.rows * n)
    raise ValueError('axis must be h or v')


def tile(grid: Grid, rows: int, cols: int) -> Grid:
    rr=int(rows); cc=int(cols)
    if rr<1 or cc<1 or grid.h*rr>30 or grid.w*cc>30: raise ValueError('invalid tile')
    return concat(concat(grid,'h',cc),'v',rr)


def apply_step(step: Step, grid: Grid) -> Grid:
    if step.op == 'transform': return transform(grid,str(step.args[0]))
    if step.op == 'scale': return scale_nearest(grid,int(step.args[0]),int(step.args[1]))
    if step.op == 'color_map': return apply_color_map(grid,step.args[0])
    if step.op == 'crop_nonbg': return crop_nonbackground(grid)
    if step.op == 'crop_component': return select_component_crop(grid,str(step.args[0]))
    if step.op == 'crop_color': return crop_color(grid,int(step.args[0]))
    if step.op == 'concat': return concat(grid,str(step.args[0]),int(step.args[1]))
    if step.op == 'tile': return tile(grid,int(step.args[0]),int(step.args[1]))
    if step.op == 'block_expand': return expand_masked(grid,infer_background(grid))
    if step.op == 'periodic_patch': return recover_missing_patch(grid)
    if step.op == 'panel_overlay': return overlay_from_separated(grid)
    if step.op == 'edge_frame': return repeat_edge_frame(grid)
    if step.op == 'complement_mirror': return anchored_complement_mirror(grid,int(step.args[0]))
    if step.op == 'joint_background': return mark_shared_empty(grid,str(step.args[0]),int(step.args[1]))
    if step.op == 'joint_foreground': return common_filled(grid,str(step.args[0]),int(step.args[1]))
    if step.op == 'priority_merge': return first_visible(grid,tuple(int(x) for x in step.args[0]))
    if step.op == 'alt_reflect_repeat': return alternating_reflect(grid,int(step.args[0]),int(step.args[1]))
    if step.op == 'periodic_extend': return extend_period(grid,str(step.args[0]),int(step.args[1]),int(step.args[2]))
    if step.op == 'deshear_bottom': return bottom_anchor_shift(grid)
    if step.op == 'chain_pack': return corner_chain(grid)
    if step.op == 'local_rewrite': return rewrite_sparse(grid,str(step.args[0]),step.args[1])
    if step.op == 'binary_feature':
        kind,yes,no=step.args
        return Grid.from_rows([[int(yes) if invariant_under(grid,str(kind)) else int(no)]])
    raise ValueError(f'unknown step {step.op}')


def apply_program(program: Program, grid: Grid) -> Grid:
    out=grid
    for step in program.steps:
        out=apply_step(step,out)
    return out
