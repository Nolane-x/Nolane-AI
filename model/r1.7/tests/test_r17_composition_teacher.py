import copy

from cogcoder.r17_benchmark import make_r17_task, oracle_plan
from scripts.train_r17_causal_law_policy import _build_episode


def test_composition_teacher_replays_initial_oracle_plan_once_in_order():
    for index in range(8):
        task = make_r17_task('composition_holdout', 'train', index)
        expected = oracle_plan(copy.deepcopy(task))
        episode = _build_episode('composition_holdout', index, exploration_steps=0, max_steps=8)
        assert [step.label for step in episode.steps] == expected
        assert len(episode.steps) == len(expected) == 3
