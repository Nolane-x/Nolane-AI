from __future__ import annotations

import json
from pathlib import Path

import torch

from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_program_induction import infer_functional_program, execute_functional_program_hypothesis
from cogcoder.r17_training import load_r17_checkpoint, sha256_file


def main() -> None:
    torch.set_num_threads(4)
    root = Path(__file__).resolve().parents[1]
    r12 = root / 'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'
    r16 = root / 'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'
    parent = root / 'checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt'
    model, meta = load_r17_checkpoint(
        parent,
        expected_r1_2_checkpoint=r12,
        expected_r1_6_parent_checkpoint=r16,
    )
    model.eval()
    rows = []
    exact_count = solved_count = false_exact_count = 0
    efficiency_sum = 0.0
    solved_efficiency_count = 0
    for index in range(522, 586):
        task = make_r17_task('composition_holdout', 'train', index)
        reference_actions = len(task.oracle_program)
        hypothesis = infer_functional_program(
            model, task.render_observation(), task.action_descriptions, max_horizon=4
        )
        result = execute_functional_program_hypothesis(task, hypothesis)
        exact = bool(hypothesis.exact)
        solved = bool(result['solved'])
        exact_count += int(exact)
        solved_count += int(solved)
        false_exact_count += int(exact and not solved)
        if solved:
            pre_submit = int(result['pre_submit_actions'])
            efficiency = min(1.0, reference_actions / max(1, pre_submit))
            efficiency_sum += efficiency
            solved_efficiency_count += 1
        else:
            efficiency = 0.0
        rows.append({
            'index': index,
            'task_id': task.task_id,
            'exact': exact,
            'solved': solved,
            'sequence': list(hypothesis.sequence),
            'horizon': hypothesis.horizon,
            'orientation': hypothesis.orientation,
            'matched_elements': hypothesis.matched_elements,
            'total_elements': hypothesis.total_elements,
            'pre_submit_actions': int(result['pre_submit_actions']),
            'action_efficiency': efficiency,
        })
    total = len(rows)
    demo_exact_rate = exact_count / total
    task_solve_rate = solved_count / total
    false_exact_rate = false_exact_count / total
    mean_efficiency = efficiency_sum / max(1, solved_efficiency_count)
    accepted = demo_exact_rate >= 0.95 and task_solve_rate >= 0.90 and false_exact_rate <= 0.05
    report = {
        'version': 'r1.7-functional-program-search-internal-v1',
        'protocol': {'split': 'train', 'family': 'composition_holdout', 'indices': [522, 586], 'max_horizon': 4, 'trainable_parameters': 0},
        'operator_executor_sha256': sha256_file(parent),
        'operator_executor_candidate_effective_parameters': meta['candidate_effective_parameters'],
        'worlds': total,
        'demo_exact_rate': demo_exact_rate,
        'task_solve_rate': task_solve_rate,
        'false_exact_rate': false_exact_rate,
        'mean_action_efficiency': mean_efficiency,
        'accepted_for_dev_gate': accepted,
        'rows': rows,
    }
    out = root / 'results/r1_7_functional_program_search_internal.json'
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('worlds','demo_exact_rate','task_solve_rate','false_exact_rate','mean_action_efficiency','accepted_for_dev_gate')}, sort_keys=True))
    if not accepted:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
