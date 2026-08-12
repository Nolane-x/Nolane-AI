import copy
import json

import pytest

from cogcoder.r17_benchmark import (
    R17_BENCHMARK_VERSION,
    R17_FAMILIES,
    evaluate_action_efficiency,
    make_r17_task,
    oracle_plan,
)


def _public_text(task):
    return json.dumps(task.observe(), sort_keys=True).lower()


def test_r17_split_namespace_is_disjoint_and_deterministic():
    a = make_r17_task("causal_laws", "train", 0)
    b = make_r17_task("causal_laws", "train", 0)
    dev = make_r17_task("causal_laws", "dev", 0)
    fresh = make_r17_task("causal_laws", "fresh", 0)
    assert a.task_id == b.task_id
    assert a.render_observation() == b.render_observation()
    assert a.task_id != dev.task_id != fresh.task_id
    assert a.task_id.startswith(f"{R17_BENCHMARK_VERSION}:train:causal_laws:")


def test_public_observation_contains_no_private_or_hidden_fields():
    forbidden = ("hidden", "oracle", "private", "answer", "target_program", "action_kind")
    for family in R17_FAMILIES:
        task = make_r17_task(family, "train", 2)
        text = _public_text(task)
        for token in forbidden:
            assert token not in text


def test_action_order_is_not_a_fixed_semantic_slot_contract():
    for family in R17_FAMILIES:
        orders = {make_r17_task(family, "train", index).action_descriptions for index in range(8)}
        assert len(orders) > 1, family


@pytest.mark.parametrize("family", R17_FAMILIES)
def test_oracle_exactly_solves_and_scores_full_efficiency(family):
    task = make_r17_task(family, "dev", 1)
    plan = oracle_plan(task)
    assert plan
    reference = len(plan)
    for action in plan:
        result = task.step(action)
        if result.done:
            break
    assert task.done and task.solved, (family, task.observe())
    metrics = evaluate_action_efficiency(reference_actions=reference, used_actions=task.step_count, solved=True)
    assert metrics["completion"] == 1.0
    assert metrics["action_efficiency"] == pytest.approx(1.0)


def test_wrong_submit_is_exact_failure_not_soft_judge():
    task = make_r17_task("causal_laws", "dev", 3)
    submit = task.action_descriptions.index("submit current hypothesis")
    result = task.step(submit)
    assert result.done
    assert result.failed
    assert not result.solved
    assert not task.solved


def test_goal_inference_exposes_progress_feedback_but_not_goal_vector():
    task = make_r17_task("goal_inference", "train", 4)
    obs = task.observe()
    assert "goal" not in obs
    assert "target" not in obs
    non_submit = next(i for i, d in enumerate(task.action_descriptions) if "submit" not in d)
    result = task.step(non_submit)
    assert -1.0 <= result.progress_delta <= 1.0
    assert isinstance(result.information_gain, float)


def test_causal_switch_public_context_changes_during_episode():
    task = make_r17_task("causal_switch", "train", 5)
    first_context = task.observe()["context"]
    for _ in range(task.switch_after):
        action = next(i for i, d in enumerate(task.action_descriptions) if "submit" not in d)
        result = task.step(action)
        if result.done:
            pytest.fail("task ended before public context switch")
    assert task.observe()["context"] != first_context


def test_composition_holdout_uses_split_specific_program_templates():
    train = {make_r17_task("composition_holdout", "train", i).oracle_program for i in range(12)}
    dev = {make_r17_task("composition_holdout", "dev", i).oracle_program for i in range(12)}
    assert train
    assert dev
    assert dev - train
