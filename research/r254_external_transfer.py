from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cogcoder.r254_code_knowledge import PythonRepositoryIndexer
from cogcoder.r254_cognitive_retrieval import CognitiveRetrievalFabric, CognitiveRetrievalNeed


def _read_sources(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob('*.py')):
        files[path.relative_to(root).as_posix()] = path.read_text(encoding='utf-8')
    if not files:
        raise ValueError('no Python sources found')
    return files


def _case(fabric: CognitiveRetrievalFabric, symbol: str, expected_callee: str) -> dict[str, object]:
    receipt = fabric.retrieve(CognitiveRetrievalNeed(
        objective=f'trace the implementation dependency of {symbol}',
        deficit_kind='code_analysis_gap',
        query=symbol,
        symbols=frozenset({symbol}),
        context_tags=frozenset({'python', 'external-repository'}),
        required_kinds=frozenset({'code'}),
        min_sufficiency=0.20,
    ))
    callee_rows = [row for row in receipt.attachments if expected_callee in row.artifact_id.split(':')[-1] or expected_callee in row.text]
    graph_rows = [row for row in callee_rows if any(reason.startswith('graph:') for reason in row.rationale)]
    return {
        'symbol': symbol,
        'expected_callee': expected_callee,
        'passed': bool(graph_rows),
        'graph_hops_used': receipt.graph_hops_used,
        'policy_mode': receipt.policy_mode,
        'policy_seed_k': receipt.policy_seed_k,
        'accepted_artifact_ids': list(receipt.accepted_artifact_ids),
        'attachment_ids': [row.artifact_id for row in receipt.attachments],
        'graph_callee_attachment_ids': [row.artifact_id for row in graph_rows],
        'source_failures': list(receipt.source_failures),
    }


def run(source_dir: str, *, repository: str, commit: str) -> dict[str, object]:
    root = Path(source_dir)
    files = _read_sources(root)
    source = PythonRepositoryIndexer().build_source('external-repository', files)
    fabric = CognitiveRetrievalFabric((source,), max_rounds=1, max_results=6, max_graph_depth=2, max_graph_nodes=12)
    cases = (
        _case(fabric, 'chunked', 'take'),
        _case(fabric, 'nth_or_last', 'last'),
    )
    digests = {
        name: hashlib.sha256(text.encode('utf-8')).hexdigest()
        for name, text in files.items()
    }
    return {
        'milestone': 'R2.54',
        'validation': 'independently-sourced-real-repository-structural-retrieval',
        'repository': repository,
        'commit': commit,
        'source_file_count': len(files),
        'source_sha256': digests,
        'cases': list(cases),
        'passed': all(bool(case['passed']) for case in cases),
        'passed_cases': sum(bool(case['passed']) for case in cases),
        'total_cases': len(cases),
        'trainable_parameter_count': 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    result = run(args.source_dir, repository=args.repository, commit=args.commit)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + '\n', encoding='utf-8')
    print(text)
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
