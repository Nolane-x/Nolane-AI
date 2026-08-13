from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .arc_grid import Grid
from .arc_ops import apply_program
from .arc_templates import fit_templates


@dataclass(frozen=True)
class ParsedTask:
    train_pairs: tuple[tuple[Grid,Grid], ...]
    test_inputs: tuple[Grid, ...]
    test_outputs: tuple[Grid | None, ...]


@dataclass(frozen=True)
class TaskScore:
    solved: bool
    test_inputs: int
    correct_test_inputs: int
    candidate_programs: int
    attempts_emitted: int


def parse_task(raw: dict[str, Any]) -> ParsedTask:
    if not isinstance(raw, dict) or not isinstance(raw.get('train'), list) or not isinstance(raw.get('test'), list):
        raise ValueError('ARC task must contain train/test lists')
    train=[]
    for pair in raw['train']:
        if 'input' not in pair or 'output' not in pair:
            raise ValueError('training pair requires input/output')
        train.append((Grid.from_rows(pair['input']), Grid.from_rows(pair['output'])))
    if not train:
        raise ValueError('ARC task requires demonstrations')
    inputs=[]; outputs=[]
    for pair in raw['test']:
        if 'input' not in pair:
            raise ValueError('test pair requires input')
        inputs.append(Grid.from_rows(pair['input']))
        outputs.append(Grid.from_rows(pair['output']) if 'output' in pair else None)
    if not inputs:
        raise ValueError('ARC task requires test input')
    return ParsedTask(tuple(train),tuple(inputs),tuple(outputs))


def load_task(path: str | Path) -> ParsedTask:
    return parse_task(json.loads(Path(path).read_text()))


def predict_task(task: ParsedTask, *, max_attempts: int = 2, max_programs: int = 64) -> tuple[tuple[Grid,...], ...]:
    if max_attempts < 1 or max_attempts > 2:
        raise ValueError('max_attempts must be 1 or 2')
    programs=fit_templates(task.train_pairs,limit=max_programs)
    all_predictions=[]
    for inp in task.test_inputs:
        preds=[]; seen=set()
        for program in programs:
            try: out=apply_program(program,inp)
            except (ValueError,ArithmeticError,OverflowError,StopIteration): continue
            if out.rows in seen: continue
            seen.add(out.rows); preds.append(out)
            if len(preds)>=max_attempts: break
        all_predictions.append(tuple(preds))
    return tuple(all_predictions)


def score_task(task: ParsedTask, *, max_attempts: int = 2, max_programs: int = 64) -> TaskScore:
    programs=fit_templates(task.train_pairs,limit=max_programs)
    predictions=[]
    for inp in task.test_inputs:
        rows=[]; seen=set()
        for p in programs:
            try: out=apply_program(p,inp)
            except (ValueError,ArithmeticError,OverflowError,StopIteration): continue
            if out.rows in seen: continue
            seen.add(out.rows); rows.append(out)
            if len(rows)>=max_attempts: break
        predictions.append(tuple(rows))
    correct=0
    for preds,target in zip(predictions,task.test_outputs):
        if target is not None and any(p==target for p in preds): correct+=1
    solved = bool(task.test_inputs) and correct==len(task.test_inputs)
    return TaskScore(solved,len(task.test_inputs),correct,len(programs),sum(len(x) for x in predictions))
