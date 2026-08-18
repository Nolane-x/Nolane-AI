from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

from cogcoder.r253_external_cognition import CognitiveOperatorRegistry, ExternalWorkingState
from cogcoder.r255_lifecycle import ProcedureLifecycleLedger
from cogcoder.r256_operator_invention import AutonomousOperatorInventionEngine, OperatorExample, OperatorInventionNeed


def _load_module(path: Path) -> ModuleType:
    path = Path(path)
    spec = importlib.util.spec_from_file_location('r256_external_oracle', path)
    if spec is None or spec.loader is None:
        raise ValueError(f'cannot load external oracle: {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cases() -> tuple[tuple[int | float, int | float, int | float], ...]:
    return (
        (1, 0, 5), (-1, 0, 5), (101, 0, 5), (3, -2, 4),
        (8, -10, 10), (-9, -3, 2), (0, 0, 1), (5, 5, 8),
        (2, 0, 5), (-4, -2, 9), (11, 3, 7), (2, -8, -1),
        (7, 1, 7), (-5, -5, 0), (4, -1, 10), (15, 12, 14),
        (-20, -10, -2), (-10, -10, -2), (-2, -10, -2), (0, -10, -2),
        (1, -3, 3), (2, -3, 3), (3, -3, 3), (4, -3, 3),
        (9, 4, 12), (12, 4, 12), (13, 4, 12), (6, 6, 6),
        (-7, -6, 8), (-6, -6, 8), (8, -6, 8), (9, -6, 8),
        (100, 90, 110), (80, 90, 110), (95, 90, 110), (-1.5, -1.0, 2.5),
        (1.25, -1.0, 2.5), (2.75, -1.0, 2.5), (0.0, -0.5, 0.5), (0.75, -0.5, 0.5),
    )


def run_transfer(
    source_path: Path | str,
    *,
    repository: str,
    commit: str,
    function_name: str = 'clamp',
) -> dict[str, object]:
    source_path = Path(source_path)
    raw = source_path.read_bytes()
    module = _load_module(source_path)
    oracle = getattr(module, function_name, None)
    if not callable(oracle):
        raise ValueError(f'external oracle function not found: {function_name}')

    rows = _cases()
    examples = tuple(
        OperatorExample(
            f'case-{index:02d}',
            {'x': x, 'lower': lower, 'upper': upper},
            oracle(x, lower, upper),
        )
        for index, (x, lower, upper) in enumerate(rows)
    )
    training = examples[:8]
    challenges = examples[8:16]
    certification = examples[16:]

    lifecycle = ProcedureLifecycleLedger()
    engine = AutonomousOperatorInventionEngine(CognitiveOperatorRegistry(), lifecycle)
    need = OperatorInventionNeed(
        objective=f'invent pure operator matching external oracle {repository}:{function_name}',
        field_names=('x', 'lower', 'upper'),
        output_field='oracle_result',
        constants=(),
        max_depth=2,
        max_candidates=30000,
    )
    receipt = engine.synthesize_and_challenge(
        need,
        training,
        challenges,
        max_cegis_rounds=2,
    )
    if not receipt.passed or receipt.candidate is None:
        return {
            'milestone': 'R2.56',
            'passed': False,
            'repository': repository,
            'commit': commit,
            'function_name': function_name,
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'source_was_parsed_by_learner': False,
            'training_cases': len(training),
            'challenge_cases': len(challenges),
            'heldout_cases': len(certification),
            'heldout_exact': 0,
            'reason': receipt.reason,
            'trainable_parameter_count': 0,
        }

    promoted = engine.promote(receipt)
    exact = 0
    failures: list[dict[str, object]] = []
    for example in certification:
        state = ExternalWorkingState(context=dict(example.context))
        live = engine.execute_promoted(promoted.operator.operator_id, state)
        actual = state.context.get(need.output_field)
        passed = bool(live.success and actual == example.expected)
        exact += int(passed)
        if not passed:
            failures.append({
                'name': example.name,
                'context': dict(example.context),
                'expected': example.expected,
                'actual': actual,
                'reason': live.reason,
            })

    return {
        'milestone': 'R2.56',
        'validation': 'independently-sourced-pure-function-oracle-transfer',
        'passed': exact == len(certification) and not failures,
        'repository': repository,
        'commit': commit,
        'function_name': function_name,
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'source_was_parsed_by_learner': False,
        'training_cases': len(training),
        'challenge_cases': len(challenges),
        'heldout_cases': len(certification),
        'heldout_exact': exact,
        'cegis_rounds': receipt.cegis_rounds,
        'search_evaluations': receipt.search_evaluations,
        'expression_digest': receipt.candidate.expression_digest,
        'expression': receipt.candidate.expression.to_data(),
        'operator_id': promoted.operator.operator_id,
        'failures': failures,
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'The external source is executed only as an input/output oracle. The learner never parses its implementation. '
            'Success demonstrates bounded pure-DSL operator invention for this sampled function, not arbitrary code synthesis.'
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--function-name', default='clamp')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run_transfer(
        Path(args.source),
        repository=args.repository,
        commit=args.commit,
        function_name=args.function_name,
    )
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
