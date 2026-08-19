from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> bool:
    file = Path(path)
    text = file.read_text()
    if new in text:
        return False
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{path}: expected exactly one replacement target, found {count}')
    file.write_text(text.replace(old, new, 1))
    return True


def main() -> None:
    core = 'cogcoder/r268_cross_task_causal_transfer.py'
    benchmark = 'benchmarks/kfigg/r268_cross_task_causal_transfer.py'

    replace_once(
        core,
        """@dataclass(frozen=True, slots=True)\nclass PortableCausalProgram:\n    expression: Expr\n    expression_digest: str\n    probe_roles: tuple[str, str, str] = _PROBE_ROLES\n    trainable_parameter_count: int = 0\n\n    def to_data(self) -> dict[str, object]:\n""",
        """@dataclass(frozen=True, slots=True)\nclass PortableCausalProgram:\n    expression: Expr\n    expression_digest: str\n    probe_roles: tuple[str, str, str] = _PROBE_ROLES\n    trainable_parameter_count: int = 0\n\n    def __post_init__(self) -> None:\n        if not isinstance(self.expression, Expr):\n            raise TypeError('expression must be Expr')\n        if tuple(self.probe_roles) != _PROBE_ROLES:\n            raise ValueError('probe_roles must be the canonical three abstract probe roles')\n        if self.trainable_parameter_count != 0:\n            raise ValueError('trainable_parameter_count must remain zero')\n        if _used_fields(self.expression) != frozenset(_PROBE_ROLES):\n            raise ValueError('expression must depend on exactly three abstract probe roles')\n        expected = expr_digest(self.expression)\n        if self.expression_digest != expected:\n            raise ValueError('expression_digest must exactly match expression content')\n\n    def to_data(self) -> dict[str, object]:\n""",
    )

    replace_once(
        benchmark,
        """def _source_expression():\n    return Binary('sub', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))\n\n\n""",
        """def _source_expression():\n    return Binary('sub', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))\n\n\ndef _source_prior_ablation_expression():\n    # Same arity/depth and same transfer machinery, but a deliberately\n    # structure-shuffled prior. Reaching any positive target from this prior\n    # requires more than one local operator repair; role permutation alone\n    # cannot repair the association/operation mismatch.\n    return Binary('div', Field('__p0'), Binary('mul', Field('__p1'), Field('__p2')))\n\n\n""",
    )

    replace_once(
        benchmark,
        """def _run_positive(name: str, oracle: Oracle) -> dict[str, object]:\n    portable = export_expression_prior(_source_expression())\n    diagnostics = _diagnostics()\n""",
        """def _run_positive(name: str, oracle: Oracle) -> dict[str, object]:\n    portable = export_expression_prior(_source_expression())\n    ablated_portable = export_expression_prior(_source_prior_ablation_expression())\n    diagnostics = _diagnostics()\n""",
    )

    replace_once(
        benchmark,
        """    tight_scratch = solve_from_scratch(\n        diagnostic_contexts=diagnostics,\n""",
        """    source_prior_ablation = adapt_portable_program(\n        ablated_portable,\n        diagnostic_contexts=diagnostics,\n        terminal_contexts=terminals,\n        oracle=oracle,\n        max_selection_queries=3,\n        max_candidates=96,\n    )\n    tight_scratch = solve_from_scratch(\n        diagnostic_contexts=diagnostics,\n""",
    )

    replace_once(
        benchmark,
        """        'transfer': _summary(transfer),\n        'tight_scratch': _summary(tight_scratch),\n""",
        """        'transfer': _summary(transfer),\n        'source_prior_ablation': _summary(source_prior_ablation),\n        'transfer_candidate_budget': 96,\n        'source_prior_ablation_candidate_budget': 96,\n        'tight_scratch': _summary(tight_scratch),\n""",
    )

    replace_once(
        benchmark,
        """    roomy_scratch_exact = sum(bool(row['roomy_scratch']['passed']) for row in positives)\n    negative_transfer_abstained = sum(not bool(row['transfer']['passed']) for row in negatives)\n""",
        """    roomy_scratch_exact = sum(bool(row['roomy_scratch']['passed']) for row in positives)\n    source_prior_ablation_exact = sum(\n        bool(row['source_prior_ablation']['passed']) for row in positives\n    )\n    source_prior_ablation_same_candidate_budget = all(\n        int(row['transfer_candidate_budget']) == int(row['source_prior_ablation_candidate_budget']) == 96\n        for row in positives\n    )\n    negative_transfer_abstained = sum(not bool(row['transfer']['passed']) for row in negatives)\n""",
    )

    replace_once(
        benchmark,
        """    false_accepts = sum(int(row['transfer']['false_accepts']) for row in positives) + sum(\n        int(row['transfer']['false_accepts']) for row in negatives\n    )\n""",
        """    false_accepts = (\n        sum(int(row['transfer']['false_accepts']) for row in positives)\n        + sum(int(row['source_prior_ablation']['false_accepts']) for row in positives)\n        + sum(int(row['transfer']['false_accepts']) for row in negatives)\n    )\n""",
    )

    replace_once(
        benchmark,
        """        [int(row['transfer']['trainable_parameter_count']) for row in positives]\n        + [int(row['transfer']['trainable_parameter_count']) for row in negatives]\n""",
        """        [int(row['transfer']['trainable_parameter_count']) for row in positives]\n        + [int(row['source_prior_ablation']['trainable_parameter_count']) for row in positives]\n        + [int(row['transfer']['trainable_parameter_count']) for row in negatives]\n""",
    )

    replace_once(
        benchmark,
        """        and roomy_scratch_exact == len(positives)\n        and negative_transfer_abstained == len(negatives)\n""",
        """        and roomy_scratch_exact == len(positives)\n        and source_prior_ablation_exact == 0\n        and source_prior_ablation_same_candidate_budget\n        and negative_transfer_abstained == len(negatives)\n""",
    )

    replace_once(
        benchmark,
        """        'roomy_scratch_exact': roomy_scratch_exact,\n        'diagnostic_order_invariance': diagnostic_order_invariance,\n""",
        """        'roomy_scratch_exact': roomy_scratch_exact,\n        'source_prior_ablation_cases': len(positives),\n        'source_prior_ablation_exact': source_prior_ablation_exact,\n        'source_prior_ablation_same_candidate_budget': source_prior_ablation_same_candidate_budget,\n        'diagnostic_order_invariance': diagnostic_order_invariance,\n""",
    )

    print('R268_WORLD_HARDENING_APPLIED')


if __name__ == '__main__':
    main()
