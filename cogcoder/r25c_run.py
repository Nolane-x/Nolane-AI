from __future__ import annotations

from pathlib import Path
from .arc_eval import load_task
from .r25_c import score


def run(directory,max_attempts=2,max_programs=64):
    paths=sorted(Path(directory).glob('*.json')); solved=errors=candidates=attempts=0
    for path in paths:
        try: result=score(load_task(path),max_attempts,max_programs)
        except Exception: errors+=1; continue
        solved+=int(result.solved); candidates+=result.candidate_programs; attempts+=result.attempts_emitted
    cases=len(paths); scored=max(0,cases-errors)
    return {'cases':cases,'scored':scored,'solved':solved,'solve_rate':solved/max(1,cases),'errors':errors,'mean_candidate_programs':candidates/max(1,scored),'mean_attempts_emitted':attempts/max(1,scored),'max_attempts':max_attempts,'max_programs':max_programs}
