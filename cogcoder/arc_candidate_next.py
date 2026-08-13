from __future__ import annotations

from .arc_current_local import program_set as previous_program_set
from .component_fit import programs as component_programs


MAX_COMPONENT_ITEMS=4


def program_set(pairs,limit=64):
    pairs=tuple(pairs)
    if not pairs or limit<1: return ()
    pool={p.signature:p for p in previous_program_set(pairs,limit=limit)}
    for p in component_programs(pairs,max_items=MAX_COMPONENT_ITEMS):
        pool[p.signature]=p
    return tuple(sorted(pool.values(),key=lambda p:(p.cost,len(p.steps),repr(p.signature)))[:limit])
