from __future__ import annotations

from . import r25_n as base
from .arc_candidate_region import program_set as region_program_set
from .span_fit import programs as extra_programs


def _program_set(pairs,limit=64):
    pool={p.signature:p for p in region_program_set(pairs,limit=limit)}
    for p in extra_programs(pairs): pool[p.signature]=p
    return tuple(sorted(pool.values(),key=lambda p:(p.cost,len(p.steps),repr(p.signature)))[:limit])


def run(directory,max_attempts=2,max_programs=64):
    previous=base.program_set
    base.program_set=_program_set
    try: return base.run(directory,max_attempts,max_programs)
    finally: base.program_set=previous
