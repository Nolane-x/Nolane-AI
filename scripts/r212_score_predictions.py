from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from cogcoder.r212_real_repo_protocol import extract_gold_patch_files


def _mode_metrics(items: list[tuple[list[str], tuple[str, ...]]]) -> dict[str, float]:
    if not items:
        return {'hit1': 0.0, 'hit5': 0.0, 'mrr': 0.0, 'recall5': 0.0}
    hit1 = hit5 = 0.0
    mrr = recall5 = 0.0
    for ranked, gold_tuple in items:
        gold = set(gold_tuple)
        if not gold:
            continue
        positions = [i + 1 for i, path in enumerate(ranked) if path in gold]
        if positions:
            best = min(positions)
            hit1 += float(best == 1)
            hit5 += float(best <= 5)
            mrr += 1.0 / best
        recall5 += len(gold.intersection(ranked[:5])) / len(gold)
    n = float(len(items))
    return {
        'hit1': hit1 / n,
        'hit5': hit5 / n,
        'mrr': mrr / n,
        'recall5': recall5 / n,
    }


def score_prediction_rows(predictions: Iterable[dict[str, Any]], full_rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    preds = copy.deepcopy(list(predictions))
    gold_rows = copy.deepcopy(list(full_rows))
    by_pred = {row['instance_id']: row for row in preds}
    if len(by_pred) != len(preds):
        raise ValueError('duplicate prediction instance_id')

    path_items: list[tuple[list[str], tuple[str, ...]]] = []
    hybrid_items: list[tuple[list[str], tuple[str, ...]]] = []
    per_lang_items: dict[str, dict[str, list[tuple[list[str], tuple[str, ...]]]]] = defaultdict(lambda: {'path': [], 'hybrid': []})
    materialized = 0
    deterministic_count = 0
    rows_detail: list[dict[str, Any]] = []

    for row in gold_rows:
        instance_id = row['instance_id']
        if instance_id not in by_pred:
            raise ValueError(f'missing prediction for {instance_id}')
        pred = by_pred[instance_id]
        gold = extract_gold_patch_files(str(row.get('patch', '')))
        if not gold:
            raise ValueError(f'empty gold patch files for {instance_id}')
        path_rank = list(pred.get('path_top20', []))
        hybrid_rank = list(pred.get('hybrid_top20', []))
        ok = pred.get('status') == 'ok'
        materialized += int(ok)
        deterministic_count += int(bool(pred.get('deterministic')))
        path_items.append((path_rank, gold))
        hybrid_items.append((hybrid_rank, gold))
        language = str(row.get('language') or 'unknown')
        per_lang_items[language]['path'].append((path_rank, gold))
        per_lang_items[language]['hybrid'].append((hybrid_rank, gold))

        def first_rank(ranked: list[str]) -> int | None:
            hits = [i + 1 for i, path in enumerate(ranked) if path in set(gold)]
            return min(hits) if hits else None

        rows_detail.append({
            'instance_id': instance_id,
            'repo': row.get('repo'),
            'language': language,
            'status': pred.get('status'),
            'gold_files': list(gold),
            'path_first_gold_rank': first_rank(path_rank),
            'hybrid_first_gold_rank': first_rank(hybrid_rank),
            'path_top5': path_rank[:5],
            'hybrid_top5': hybrid_rank[:5],
            'deterministic': bool(pred.get('deterministic')),
        })

    path_metrics = _mode_metrics(path_items)
    hybrid_metrics = _mode_metrics(hybrid_items)
    tasks = len(gold_rows)
    per_language: dict[str, Any] = {}
    for language in sorted(per_lang_items):
        p = _mode_metrics(per_lang_items[language]['path'])
        h = _mode_metrics(per_lang_items[language]['hybrid'])
        per_language[language] = {
            'tasks': len(per_lang_items[language]['hybrid']),
            'path': p,
            'hybrid': h,
        }

    result = {
        'schema': 'nolane-r212-real-repo-score-v1',
        'tasks': tasks,
        'materialized_tasks': materialized,
        'prediction_determinism': (deterministic_count / tasks) if tasks else 0.0,
        'path': path_metrics,
        'hybrid': hybrid_metrics,
        'hit5_improvement_over_path_pp': 100.0 * (hybrid_metrics['hit5'] - path_metrics['hit5']),
        'mrr_improvement_over_path': hybrid_metrics['mrr'] - path_metrics['mrr'],
        'recall5_improvement_over_path': hybrid_metrics['recall5'] - path_metrics['recall5'],
        'per_language': per_language,
        'rows': rows_detail,
        'new_r212_neural_parameters': 0,
        'candidate_effective_parameters': 79_450_489,
        'external_issue_resolution_claim_allowed': False,
        'agi_claim_allowed': False,
    }
    digest_payload = copy.deepcopy(result)
    result['measurement_sha256'] = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--predictions', required=True)
    parser.add_argument('--gold', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    pred_payload = json.loads(Path(args.predictions).read_text(encoding='utf-8'))
    predictions = pred_payload['tasks'] if isinstance(pred_payload, dict) else pred_payload
    rows = json.loads(Path(args.gold).read_text(encoding='utf-8'))
    result = score_prediction_rows(predictions, rows)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
