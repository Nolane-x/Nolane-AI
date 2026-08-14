from __future__ import annotations

from . import r25_n as base
from .arc_candidate_region import program_set


def run(directory,max_attempts=2,max_programs=64):
    previous=base.program_set
    base.program_set=program_set
    try:
        return base.run(directory,max_attempts,max_programs)
    finally:
        base.program_set=previous
