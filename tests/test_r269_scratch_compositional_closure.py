from __future__ import annotations

from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r269_meta_learning_kernel import MetaLearningConfig, PublicTaskSignature, run_cold_scratch


def test_roomy_scratch_can_express_balanced_four_role_depth_two_program():
    names = ("a", "b", "c", "d")
    a, b, c, d = map(Field, names)
    target = Binary("sub", Binary("add", a, b), Binary("add", c, d))
    signature = PublicTaskSignature(
        role_names=names,
        numeric_domain="finite_numeric",
        allowed_binary_ops=("add", "sub", "mul", "min", "max"),
        query_space_digest="r269.test.four-role-grid",
        budget_contract="diagnostic<=8;proof-distinct-candidate<=8192",
    )
    diagnostics = (
        {"a": 1, "b": 2, "c": 5, "d": 1},
        {"a": 2, "b": 7, "c": 3, "d": 4},
        {"a": -3, "b": 5, "c": 2, "d": 8},
        {"a": 9, "b": -2, "c": 4, "d": 1},
        {"a": 6, "b": 3, "c": -5, "d": 2},
        {"a": 11, "b": 4, "c": 7, "d": -3},
        {"a": -8, "b": 9, "c": 6, "d": 5},
        {"a": 13, "b": -7, "c": 2, "d": 10},
    )
    terminal = (
        {"a": 17, "b": 3, "c": 4, "d": 6},
        {"a": -11, "b": 8, "c": 5, "d": -2},
        {"a": 19, "b": -4, "c": 7, "d": 12},
    )
    oracle = lambda row: (row["a"] + row["b"]) - (row["c"] + row["d"])
    config = MetaLearningConfig(
        max_diagnostic_queries=8,
        transfer_candidate_cap=256,
        scratch_candidate_cap=8192,
        scratch_max_depth=2,
        min_scratch_partitions=2,
    )

    receipt = run_cold_scratch(signature, diagnostics, terminal, oracle, config)
    assert receipt.passed is True
    assert receipt.mode == "scratch"
    assert receipt.selected_expression == target or receipt.reason == "accepted_scratch"
    assert receipt.false_accepts == 0
