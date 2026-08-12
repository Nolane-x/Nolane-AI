from cogcoder.r17_benchmark import make_r17_task, oracle_plan


def test_causal_law_oracle_is_solvable_across_broad_train_dev_sample():
    for split in ("train", "dev"):
        for index in range(48):
            task = make_r17_task("causal_laws", split, index)
            plan = oracle_plan(task)
            assert plan, (split, index, task.task_id)
            for action in plan:
                result = task.step(action)
                if result.done:
                    break
            assert task.solved, (split, index, task.task_id, task.observe())
