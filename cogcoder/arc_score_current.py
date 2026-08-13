from __future__ import annotations

from .arc_current import program_set
from .arc_eval import ParsedTask, TaskScore, load_task, parse_task
from .arc_ops import apply_program


def score_current(task: ParsedTask, *, max_attempts: int=2, max_programs: int=64) -> TaskScore:
    if max_attempts not in (1,2): raise ValueError('max_attempts must be 1 or 2')
    programs=program_set(task.train_pairs,limit=max_programs)
    correct=attempts=0
    for inp,target in zip(task.test_inputs,task.test_outputs):
        seen=set(); predictions=[]
        for program in programs:
            try: out=apply_program(program,inp)
            except (ValueError,ArithmeticError,OverflowError,StopIteration): continue
            if out.rows in seen: continue
            seen.add(out.rows); predictions.append(out); attempts+=1
            if len(predictions)>=max_attempts: break
        if target is not None and any(out==target for out in predictions): correct+=1
    return TaskScore(bool(task.test_inputs) and correct==len(task.test_inputs),len(task.test_inputs),correct,len(programs),attempts)


__all__=['ParsedTask','TaskScore','load_task','parse_task','score_current']
