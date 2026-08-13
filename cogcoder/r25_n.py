from __future__ import annotations

from pathlib import Path

from .arc_candidate_next import program_set
from .arc_eval import TaskScore, load_task
from .arc_ops_view import apply_program


def score(task,max_attempts=2,max_programs=64):
    programs=program_set(task.train_pairs,limit=max_programs)
    correct=attempts=0
    for inp,target in zip(task.test_inputs,task.test_outputs):
        seen=set(); preds=[]
        for p in programs:
            try: out=apply_program(p,inp)
            except (ValueError,ArithmeticError,OverflowError,StopIteration): continue
            if out.rows in seen: continue
            seen.add(out.rows); preds.append(out); attempts+=1
            if len(preds)>=max_attempts: break
        if target is not None and any(out==target for out in preds): correct+=1
    return TaskScore(bool(task.test_inputs) and correct==len(task.test_inputs),len(task.test_inputs),correct,len(programs),attempts)


def run(directory,max_attempts=2,max_programs=64):
    paths=sorted(Path(directory).glob('*.json')); solved=errors=candidates=attempts=0
    for path in paths:
        try: result=score(load_task(path),max_attempts,max_programs)
        except Exception: errors+=1; continue
        solved+=int(result.solved); candidates+=result.candidate_programs; attempts+=result.attempts_emitted
    cases=len(paths); scored=max(0,cases-errors)
    return {'cases':cases,'scored':scored,'solved':solved,'solve_rate':solved/max(1,cases),'errors':errors,'mean_candidate_programs':candidates/max(1,scored),'mean_attempts_emitted':attempts/max(1,scored),'max_attempts':max_attempts,'max_programs':max_programs}
