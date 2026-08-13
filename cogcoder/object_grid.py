from __future__ import annotations

from .arc_grid import Grid, bbox, components, infer_background


KINDS=(
    'area','area_color','bbox','bbox_color',
    'area_bbox','area_bbox_color','touch','touch_color',
)


def objects(grid: Grid):
    bg=infer_background(grid)
    rows=[]
    for color in sorted(grid.colors-{bg}):
        for cells in components(grid,color=color,background=bg,connectivity=4):
            box=bbox(cells)
            rows.append((int(color),cells,box))
    rows.sort(key=lambda item:(item[2],item[0],len(item[1])))
    return tuple(rows)


def feature(grid:Grid,color:int,cells,box,kind:str):
    r0,c0,r1,c1=box
    area=len(cells); h=r1-r0+1; w=c1-c0+1
    touch=(r0==0 or c0==0 or r1==grid.h-1 or c1==grid.w-1)
    if kind=='area': return (area,)
    if kind=='area_color': return (int(color),area)
    if kind=='bbox': return (h,w)
    if kind=='bbox_color': return (int(color),h,w)
    if kind=='area_bbox': return (area,h,w)
    if kind=='area_bbox_color': return (int(color),area,h,w)
    if kind=='touch': return (bool(touch),)
    if kind=='touch_color': return (int(color),bool(touch))
    raise ValueError('unknown object feature kind')


def rewrite_objects(grid:Grid,kind:str,rules):
    table=dict(rules)
    rows=[list(row) for row in grid.rows]
    for color,cells,box in objects(grid):
        key=feature(grid,color,cells,box,kind)
        if key not in table: continue
        target=int(table[key])
        for r,c in cells: rows[r][c]=target
    return Grid.from_rows(rows)
