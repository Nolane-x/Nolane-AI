import copy
import json

from cogcoder.r18_benchmark import (
    R18_BENCHMARK_VERSION,
    R18_FAMILIES,
    R18_SPLIT_BASE_SEEDS,
    lock_r18_tasks,
    make_r18_task,
    oracle_plan,
)


def test_r18_namespace_is_new_and_split_seed_ranges_are_disjoint_without_opening_fresh():
    assert R18_BENCHMARK_VERSION == "nolane-figg18-v1"
    assert tuple(R18_FAMILIES) == (
        "conditional_regimes",
        "regime_switch",
        "implicit_goal_regimes",
        "causal_prerequisites",
    )
    assert R18_SPLIT_BASE_SEEDS["train"] == 18_100_000
    assert R18_SPLIT_BASE_SEEDS["dev"] == 18_200_000
    assert R18_SPLIT_BASE_SEEDS["fresh"] == 18_900_000
    assert len(set(R18_SPLIT_BASE_SEEDS.values())) == 3


def test_r18_action_surface_is_shuffled_and_public_observation_excludes_private_laws():
    orders = set()
    for index in range(8):
        task = make_r18_task("conditional_regimes", "train", index)
        orders.add(task.action_descriptions)
        obs = task.observe()
        assert obs["benchmark"] == R18_BENCHMARK_VERSION
        assert "family" not in obs
        assert "laws" not in obs
        assert "oracle" not in obs
        assert "private_goal" not in obs
        assert "state" in obs and "target" in obs and "regime" in obs
    assert len(orders) >= 3


def test_regime_switch_exposes_multiple_public_context_changes_and_old_context_returns_later():
    task = make_r18_task("regime_switch", "train", 3)
    submit = next(i for i, d in enumerate(task.action_descriptions) if "submit" in d.lower())
    non_submit = next(i for i in range(len(task.action_descriptions)) if i != submit)
    seen = [task.observe()["regime"]]
    for _ in range(12):
        if task.done:
            break
        task.step(non_submit)
        seen.append(task.observe()["regime"])
    assert len(set(seen)) >= 3
    assert seen[0] in seen[5:]


def test_implicit_goal_regimes_never_exposes_target_but_progress_feedback_is_public():
    task = make_r18_task("implicit_goal_regimes", "train", 5)
    obs0 = task.observe()
    assert "target" not in obs0
    assert "progress_signal" in obs0
    submit = next(i for i, d in enumerate(task.action_descriptions) if "submit" in d.lower())
    non_submit = [i for i in range(len(task.action_descriptions)) if i != submit]
    before = float(obs0["progress_signal"])
    changed = False
    for action in non_submit:
        probe = copy.deepcopy(task)
        result = probe.step(action)
        assert "target" not in result.observation
        if abs(float(result.observation["progress_signal"]) - before) > 1e-9:
            changed = True
            break
    assert changed


def test_prerequisite_world_has_public_blocked_effect_and_public_unlock_sequence():
    task = make_r18_task("causal_prerequisites", "train", 7)
    assert "resources" in task.observe()
    submit = next(i for i, d in enumerate(task.action_descriptions) if "submit" in d.lower())
    non_submit = [i for i in range(len(task.action_descriptions)) if i != submit]
    blocked_action = None
    for action in non_submit:
        probe = copy.deepcopy(task)
        before = tuple(probe.observe()["state"])
        result = probe.step(action)
        after = tuple(result.observation["state"])
        if before == after and result.observation["resources"] == task.observe()["resources"]:
            blocked_action = action
            break
    assert blocked_action is not None
    plan = oracle_plan(copy.deepcopy(task))
    assert plan[-1] == submit
    for action in plan:
        result = task.step(action)
    assert result.solved


def test_oracle_solves_128_sampled_train_and_dev_worlds_without_using_fresh():
    checked = 0
    for split in ("train", "dev"):
        for family in R18_FAMILIES:
            for index in range(16):
                task = make_r18_task(family, split, index)
                plan = oracle_plan(copy.deepcopy(task))
                assert plan
                assert len(plan) <= task.budget_remaining + 1
                for action in plan:
                    result = task.step(action)
                assert result.solved, task.task_id
                checked += 1
    assert checked == 128


def test_lock_payload_is_deterministic_and_contains_no_private_state():
    tasks = [make_r18_task("conditional_regimes", "dev", i) for i in range(3)]
    a = lock_r18_tasks(tasks)
    b = lock_r18_tasks([make_r18_task("conditional_regimes", "dev", i) for i in range(3)])
    assert a == b
    raw = json.dumps(a, sort_keys=True)
    assert "_goal" not in raw
    assert "_laws" not in raw
    assert len(a["sha256"]) == 64
