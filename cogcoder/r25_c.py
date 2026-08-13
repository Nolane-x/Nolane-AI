from __future__ import annotations

from .arc_current_c import program_set
from .arc_eval import ParsedTask, TaskScore
from .arc_ops_view import apply_program


def score(task: ParsedTask, max_attempts=2, max_programs=64):
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
