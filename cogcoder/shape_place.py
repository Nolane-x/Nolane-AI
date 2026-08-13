from __future__ import annotations

from .arc_grid import Grid, bbox, components, infer_background


def _objects(grid: Grid):
    bg=infer_background(grid); rows=[]
    for color in sorted(grid.colors-{bg}):
        for cells in components(grid,color=color,background=bg,connectivity=8):
            rows.append((color,cells,bbox(cells)))
    rows.sort(key=lambda item:(item[2][1],item[2][0],item[0]))
    return bg,rows


def bottom_anchor_shift(grid: Grid) -> Grid:
    bg,objects=_objects(grid); canvas=[[bg]*grid.w for _ in range(grid.h)]
    for color,cells,_ in objects:
        bottom=max(r for r,_ in cells)
        cols=sorted(c for r,c in cells if r==bottom)
        if not cols or cols!=list(range(cols[0],cols[-1]+1)): raise ValueError('bottom anchor must be contiguous')
        right=cols[-1]; mapped=[]
        for r,c in cells: mapped.append((r,c if r==bottom else min(c+1,right)))
        if len(set(mapped))!=len(cells): raise ValueError('cell collapse')
        for r,c in mapped:
            if canvas[r][c] not in (bg,color): raise ValueError('collision')
            canvas[r][c]=color
    return Grid.from_rows(canvas)


def corner_chain(grid: Grid) -> Grid:
    bg,objects=_objects(grid)
    if not objects: raise ValueError('no objects')
    canvas=[[bg]*grid.w for _ in range(grid.h)]; top=left=0
    for color,cells,box in objects:
        r0,c0,r1,c1=box; height=r1-r0+1; width=c1-c0+1
        for r,c in cells:
            rr=top+(r-r0); cc=left+(c-c0)
            if 0<=rr<grid.h and 0<=cc<grid.w: canvas[rr][cc]=color
        top+=height-1; left+=width-1
    return Grid.from_rows(canvas)
