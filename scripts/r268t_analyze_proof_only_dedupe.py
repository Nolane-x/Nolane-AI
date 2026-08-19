from __future__ import annotations

import json

import cogcoder.r268_cross_task_causal_transfer as transfer
from benchmarks.kfigg import r268_cross_task_causal_transfer as bench


def _filter(candidates, diagnostics, oracle):
    live = list(candidates)
    for context in diagnostics:
        observed = oracle(context)
        survivors = []
        for candidate in live:
            valid, predicted = transfer._safe_prediction(candidate.expression, context)
            if valid and transfer._equivalent(predicted, observed):
                survivors.append(candidate)
        live = survivors
    return live


def _row(candidate):
    return {
        'candidate_id': candidate.candidate_id,
        'repair_distance': candidate.repair_distance,
        'role_permutation_distance': candidate.role_permutation_distance,
        'expr': candidate.expression.to_data(),
    }


def main() -> None:
    portable = transfer.export_expression_prior(bench._source_expression())
    candidates = transfer.generate_transfer_candidates(portable)
    diagnostics = bench._diagnostics()

    def permuted_roles(context):
        return context['__p2'] + context['__p0'] - context['__p1']

    def one_operator_mul(context):
        return context['__p0'] * context['__p1'] - context['__p2']

    def one_operator_sub(context):
        return context['__p0'] - context['__p1'] - context['__p2']

    out = {}
    for name, oracle in (
        ('probe_role_permutation', permuted_roles),
        ('one_operator_mul_adaptation', one_operator_mul),
        ('one_operator_sub_adaptation', one_operator_sub),
    ):
        survivors = _filter(candidates, diagnostics, oracle)
        out[name] = {
            'count': len(survivors),
            'survivors': [_row(candidate) for candidate in survivors],
        }
    print('SURVIVOR_ANALYSIS=' + json.dumps(out, sort_keys=True))


if __name__ == '__main__':
    main()
