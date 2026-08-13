from __future__ import annotations

from math import gcd

from .arc_ops import Program, Step
from .panel_combine import orders


def family_programs(first_input, first_output):
    rows=[
        Program((Step('periodic_patch',()),),3),
        Program((Step('panel_overlay',()),),3),
        Program((Step('edge_frame',()),),2),
        Program((Step('deshear_bottom',()),),4),
        Program((Step('chain_pack',()),),4),
    ]
    rows += [Program((Step('complement_mirror',(color,)),),3) for color in range(1,10)]
    rows += [Program((Step('joint_background',(axis,color)),),3) for axis in ('v','h') for color in range(1,10)]
    rows += [Program((Step('joint_foreground',(axis,color,sep)),),3) for axis in ('v','h') for color in range(1,10) for sep in (False,True)]
    if first_output.h%first_input.h==0 and first_output.w%first_input.w==0:
        rb,cb=first_output.h//first_input.h,first_output.w//first_input.w
        if (rb,cb)!=(1,1): rows.append(Program((Step('alt_reflect_repeat',(rb,cb)),),3))
    if first_output.w==first_input.w and first_output.h!=first_input.h:
        g=gcd(first_output.h,first_input.h)
        rows.append(Program((Step('periodic_extend',('v',first_output.h//g,first_input.h//g)),),3))
    if first_output.h==first_input.h and first_output.w!=first_input.w:
        g=gcd(first_output.w,first_input.w)
        rows.append(Program((Step('periodic_extend',('h',first_output.w//g,first_input.w//g)),),3))
    try:
        rows += [Program((Step('priority_merge',(order,)),),4) for order in orders(first_input)]
    except ValueError:
        pass
    return tuple(rows)
