from __future__ import annotations

from pathlib import Path


TRANSFER = Path('cogcoder/r268_cross_task_causal_transfer.py')
SCRATCH = Path('cogcoder/r268_cross_task_transfer_baseline.py')
BENCHMARK = Path('benchmarks/kfigg/r268_cross_task_causal_transfer.py')

TRANSFER_OLD = '''    generated = generate_transfer_candidates(portable)[:max_candidates]
    live = _dedupe_live_candidates(generated, diagnostics)
'''
TRANSFER_NEW = '''    # max_candidates is a semantic-hypothesis budget. Proof-equivalent AST
    # representations cannot consume multiple slots before selection.
    generated = tuple(
        _dedupe_live_candidates(generate_transfer_candidates(portable), diagnostics)[:max_candidates]
    )
    live = list(generated)
'''

SCRATCH_IMPORT_OLD = '''    _failed_receipt,
    _safe_prediction,
)
'''
SCRATCH_IMPORT_NEW = '''    _failed_receipt,
    _proven_structural_alias_key,
    _safe_prediction,
)
'''

SCRATCH_SEEN_OLD = '''    out: list[TransferCandidate] = []
    seen: set[str] = set()

    def add(expr: Expr) -> bool:
        if len(out) >= max_candidates:
            return False
        from .r256_operator_dsl import expr_digest

        digest = expr_digest(expr)
        if digest in seen:
            return True
        seen.add(digest)
        ordinal = len(out)
'''
SCRATCH_SEEN_NEW = '''    out: list[TransferCandidate] = []
    seen_semantic_hypotheses: set[str] = set()

    def add(expr: Expr) -> bool:
        if len(out) >= max_candidates:
            return False
        from .r256_operator_dsl import expr_digest

        semantic_key = _proven_structural_alias_key(expr)
        if semantic_key in seen_semantic_hypotheses:
            return True
        seen_semantic_hypotheses.add(semantic_key)
        digest = expr_digest(expr)
        ordinal = len(out)
'''

BENCHMARK_ROW_OLD = '''        'transfer_candidate_budget': 96,
        'source_prior_ablation_candidate_budget': 96,
        'tight_scratch': _summary(tight_scratch),
        'roomy_scratch': _summary(roomy_scratch),
'''
BENCHMARK_ROW_NEW = '''        'transfer_candidate_budget': 96,
        'source_prior_ablation_candidate_budget': 96,
        'tight_scratch_candidate_budget': 96,
        'roomy_scratch_candidate_budget': 600,
        'tight_scratch': _summary(tight_scratch),
        'roomy_scratch': _summary(roomy_scratch),
'''

BENCHMARK_BUDGET_OLD = '''    source_prior_ablation_same_candidate_budget = all(
        int(row['transfer_candidate_budget']) == int(row['source_prior_ablation_candidate_budget']) == 96
        for row in positives
    )
    negative_transfer_abstained = sum(not bool(row['transfer']['passed']) for row in negatives)
'''
BENCHMARK_BUDGET_NEW = '''    source_prior_ablation_same_candidate_budget = all(
        int(row['transfer_candidate_budget']) == int(row['source_prior_ablation_candidate_budget']) == 96
        for row in positives
    )
    transfer_vs_tight_scratch_same_candidate_budget = all(
        int(row['transfer_candidate_budget']) == int(row['tight_scratch_candidate_budget']) == 96
        for row in positives
    )
    transfer_advantage_over_tight_scratch = positive_transfer_exact - tight_scratch_exact
    negative_transfer_abstained = sum(not bool(row['transfer']['passed']) for row in negatives)
'''

BENCHMARK_GATE_OLD = '''    all_gates_pass = (
        positive_transfer_exact == len(positives)
        and tight_scratch_exact == 0
        and roomy_scratch_exact == len(positives)
        and source_prior_ablation_exact == 0
        and source_prior_ablation_same_candidate_budget
        and negative_transfer_abstained == len(negatives)
        and diagnostic_order_invariance
        and false_accepts == 0
        and trainable_parameter_count == 0
    )
'''
BENCHMARK_GATE_NEW = '''    all_gates_pass = (
        positive_transfer_exact == len(positives)
        and tight_scratch_exact == 1
        and transfer_advantage_over_tight_scratch == 2
        and roomy_scratch_exact == len(positives)
        and source_prior_ablation_exact == 0
        and source_prior_ablation_same_candidate_budget
        and transfer_vs_tight_scratch_same_candidate_budget
        and negative_transfer_abstained == len(negatives)
        and diagnostic_order_invariance
        and false_accepts == 0
        and trainable_parameter_count == 0
    )
'''

BENCHMARK_RETURN_OLD = '''        'status': 'independent_research_candidate',
        'all_gates_pass': all_gates_pass,
        'positive_transfer_cases': len(positives),
'''
BENCHMARK_RETURN_NEW = '''        'status': 'independent_research_candidate',
        'candidate_budget_unit': 'proof_distinct_hypotheses',
        'all_gates_pass': all_gates_pass,
        'positive_transfer_cases': len(positives),
'''

BENCHMARK_FIELDS_OLD = '''        'source_prior_ablation_exact': source_prior_ablation_exact,
        'source_prior_ablation_same_candidate_budget': source_prior_ablation_same_candidate_budget,
        'diagnostic_order_invariance': diagnostic_order_invariance,
'''
BENCHMARK_FIELDS_NEW = '''        'source_prior_ablation_exact': source_prior_ablation_exact,
        'source_prior_ablation_same_candidate_budget': source_prior_ablation_same_candidate_budget,
        'transfer_vs_tight_scratch_same_candidate_budget': transfer_vs_tight_scratch_same_candidate_budget,
        'transfer_advantage_over_tight_scratch': transfer_advantage_over_tight_scratch,
        'diagnostic_order_invariance': diagnostic_order_invariance,
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one replacement boundary, found {count}')
    return text.replace(old, new, 1)


def main() -> None:
    transfer = TRANSFER.read_text(encoding='utf-8')
    scratch = SCRATCH.read_text(encoding='utf-8')
    benchmark = BENCHMARK.read_text(encoding='utf-8')

    code_already = (
        'generated = tuple(\n        _dedupe_live_candidates(generate_transfer_candidates(portable), diagnostics)[:max_candidates]' in transfer
        and 'seen_semantic_hypotheses' in scratch
        and '_proven_structural_alias_key,' in scratch
    )
    benchmark_already = (
        "'candidate_budget_unit': 'proof_distinct_hypotheses'" in benchmark
        and 'transfer_vs_tight_scratch_same_candidate_budget' in benchmark
        and 'transfer_advantage_over_tight_scratch' in benchmark
    )
    if code_already and benchmark_already:
        print('R268T_SEMANTIC_CANDIDATE_BUDGET_ALREADY_MATERIALIZED')
        return

    if not code_already:
        transfer = replace_once(transfer, TRANSFER_OLD, TRANSFER_NEW, 'transfer candidate budget')
        scratch = replace_once(scratch, SCRATCH_IMPORT_OLD, SCRATCH_IMPORT_NEW, 'scratch semantic-key import')
        scratch = replace_once(scratch, SCRATCH_SEEN_OLD, SCRATCH_SEEN_NEW, 'scratch candidate budget')
    if not benchmark_already:
        benchmark = replace_once(benchmark, BENCHMARK_ROW_OLD, BENCHMARK_ROW_NEW, 'benchmark row budgets')
        benchmark = replace_once(benchmark, BENCHMARK_BUDGET_OLD, BENCHMARK_BUDGET_NEW, 'benchmark budget comparison')
        benchmark = replace_once(benchmark, BENCHMARK_GATE_OLD, BENCHMARK_GATE_NEW, 'benchmark fair gate')
        benchmark = replace_once(benchmark, BENCHMARK_RETURN_OLD, BENCHMARK_RETURN_NEW, 'benchmark budget unit')
        benchmark = replace_once(benchmark, BENCHMARK_FIELDS_OLD, BENCHMARK_FIELDS_NEW, 'benchmark advantage fields')

    compile(transfer, str(TRANSFER), 'exec')
    compile(scratch, str(SCRATCH), 'exec')
    compile(benchmark, str(BENCHMARK), 'exec')
    TRANSFER.write_text(transfer, encoding='utf-8')
    SCRATCH.write_text(scratch, encoding='utf-8')
    BENCHMARK.write_text(benchmark, encoding='utf-8')
    print('R268T_SEMANTIC_CANDIDATE_BUDGET_MATERIALIZED')


if __name__ == '__main__':
    main()
