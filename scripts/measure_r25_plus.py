from __future__ import annotations

import argparse
import json
from pathlib import Path

from cogcoder.arc_eval import load_task
from cogcoder.arc_score_plus import score_plus


def measure(directory, max_attempts=2, max_programs=64):
    paths=sorted(Path(directory).glob('*.json'))
    solved=errors=candidates=attempts=0
    for path in paths:
        try:
            score=score_plus(load_task(path),max_attempts=max_attempts,max_programs=max_programs)
        except Exception:
            errors+=1
            continue
        solved+=int(score.solved)
        candidates+=score.candidate_programs
        attempts+=score.attempts_emitted
    cases=len(paths); scored=max(0,cases-errors)
    return {'cases':cases,'scored':scored,'solved':solved,'solve_rate':solved/max(1,cases),'errors':errors,'mean_candidate_programs':candidates/max(1,scored),'mean_attempts_emitted':attempts/max(1,scored),'max_attempts':int(max_attempts),'max_programs':int(max_programs)}


def main():
    p=argparse.ArgumentParser(); p.add_argument('directory'); p.add_argument('--max-attempts',type=int,default=2); p.add_argument('--max-programs',type=int,default=64); a=p.parse_args()
    print(json.dumps(measure(a.directory,a.max_attempts,a.max_programs),indent=2,sort_keys=True))


if __name__=='__main__': main()
