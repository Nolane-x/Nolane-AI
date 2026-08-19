from __future__ import annotations

import itertools

from cogcoder.r256_operator_dsl import Binary, Field, evaluate_expr
from cogcoder.r269_meta_learning_kernel import MetaLearningConfig, PublicTaskSignature, run_cold_scratch


def test_roomy_scratch_can_express_balanced_four_role_program_in_declared_exact_domain():
    names = ("a", "b", "c", "d")
    domain = (-3, -1, 2, 5)
    a, b, c, d = map(Field, names)
    target = Binary("sub", Binary("add", a, b), Binary("add", c, d))
    signature = PublicTaskSignature(
        role_names=names,
        numeric_domain="finite_integer",
        allowed_binary_ops=("add", "sub", "mul", "min", "max"),
        query_space_digest="r269.test.complete-four-role-finite-integer-grid",
        budget_contract="diagnostic<=8;proof-distinct-candidate<=8192",
        finite_integer_values=domain,
    )
    values = tuple(itertools.product(domain, repeat=4))
    chosen = (values[1], values[9], values[23], values[41], values[66], values[97], values[138], values[173], values[201], values[228], values[254])
    contexts = tuple(dict(zip(names, row, strict=True)) for row in chosen)
    diagnostics, terminal = contexts[:8], contexts[8:]
    oracle = lambda row: (row["a"] + row["b"]) - (row["c"] + row["d"])
    config = MetaLearningConfig(
        max_diagnostic_queries=8,
        transfer_candidate_cap=256,
        scratch_candidate_cap=8192,
        scratch_max_depth=3,
        min_scratch_partitions=2,
    )

    receipt = run_cold_scratch(signature, diagnostics, terminal, oracle, config)
    assert receipt.passed is True
    assert receipt.mode == "scratch"
    assert receipt.selected_expression is not None
    assert receipt.false_accepts == 0

    for values_row in itertools.product(domain, repeat=4):
        context = dict(zip(names, values_row, strict=True))
        assert evaluate_expr(receipt.selected_expression, context) == evaluate_expr(target, context)
