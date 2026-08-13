from __future__ import annotations

from .arc_current import program_set as base_program_set
from .arc_local import fit_local_programs
from .arc_pair_v2 import fit_pair_programs


def program_set(pairs, limit=64):
    pairs=tuple(pairs)
    if not pairs or limit<1:
        return ()
    pool={p.signature:p for p in base_program_set(pairs,limit=limit)}
    for p in fit_local_programs(pairs,max_rules=8):
        pool[p.signature]=p
    for p in fit_pair_programs(pairs):
        pool[p.signature]=p
    return tuple(sorted(pool.values(),key=lambda p:(p.cost,len(p.steps),repr(p.signature)))[:limit])
