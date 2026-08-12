from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path

from cogcoder.r17_benchmark import (
    R17_BENCHMARK_VERSION,
    R17_FAMILIES,
    evaluate_action_efficiency,
    make_r17_task,
    oracle_plan,
)


def _run_oracle(task):
    reference = oracle_plan(copy.deepcopy(task))
    trace = []
    for action in reference:
        result = task.step(action)
        trace.append({"action": int(action), "description": task.action_descriptions[action], "progress_delta": float(result.progress_delta), "information_gain": float(result.information_gain), "failed": bool(result.failed), "done": bool(result.done)})
        if result.done:
            break
    metrics = evaluate_action_efficiency(reference_actions=len(reference), used_actions=task.step_count, solved=task.solved)
    return reference, trace, metrics


def _run_random(task, rng: random.Random):
    reference = oracle_plan(copy.deepcopy(task))
    trace = []
    while not task.done:
        action = rng.randrange(len(task.action_descriptions))
        result = task.step(action)
        trace.append({"action": int(action), "description": task.action_descriptions[action], "progress_delta": float(result.progress_delta), "information_gain": float(result.information_gain), "failed": bool(result.failed), "done": bool(result.done)})
    metrics = evaluate_action_efficiency(reference_actions=len(reference), used_actions=task.step_count, solved=task.solved)
    return reference, trace, metrics


def run_gate(*, split: str, start: int, count: int, mode: str, random_seed: int = 170017):
    if mode not in {"oracle", "random"}:
        raise ValueError("mode must be oracle or random")
    rng = random.Random(int(random_seed))
    rows = []
    for family in R17_FAMILIES:
        for index in range(start, start + count):
            task = make_r17_task(family, split, index)
            if mode == "oracle":
                reference, trace, metrics = _run_oracle(task)
            else:
                reference, trace, metrics = _run_random(task, rng)
            rows.append({"task_id": task.task_id, "family": family, "index": index, "solved": bool(task.solved), "used_actions": task.step_count, "reference_actions": len(reference), **metrics, "trace": trace})
    families = {}
    for family in R17_FAMILIES:
        subset = [row for row in rows if row["family"] == family]
        families[family] = {"solved": sum(int(row["solved"]) for row in subset), "total": len(subset), "mean_action_efficiency": sum(row["action_efficiency"] for row in subset) / len(subset)}
    summary = {"benchmark": R17_BENCHMARK_VERSION, "split": split, "slice": [start, start + count], "mode": mode, "solved": sum(int(row["solved"]) for row in rows), "total": len(rows), "mean_action_efficiency": sum(row["action_efficiency"] for row in rows) / len(rows), "families": families}
    return {"summary": summary, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "dev", "fresh"), required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--mode", choices=("oracle", "random"), required=True)
    parser.add_argument("--random-seed", type=int, default=170017)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = run_gate(split=args.split, start=args.start, count=args.count, mode=args.mode, random_seed=args.random_seed)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
