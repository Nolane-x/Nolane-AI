from __future__ import annotations

from pathlib import Path


PATH = Path('cogcoder/r268_cross_task_causal_transfer.py')

OLD_CONSTANTS = """_PROBE_ROLES = ('__p0', '__p1', '__p2')\n_NUMERIC_BINARY_OPS = ('add', 'sub', 'mul', 'div', 'min', 'max')\n"""
NEW_CONSTANTS = """_PROBE_ROLES = ('__p0', '__p1', '__p2')\n_NUMERIC_BINARY_OPS = ('add', 'sub', 'mul', 'div', 'min', 'max')\n_PROVEN_COMMUTATIVE_BINARY_OPS = frozenset(('add', 'mul', 'min', 'max', 'eq', 'ne', 'and', 'or'))\n"""

OLD_DEDUPE = '''def _dedupe_live_candidates(\n    candidates: Sequence[TransferCandidate],\n    diagnostic_contexts: Sequence[Mapping[str, object]],\n) -> list[TransferCandidate]:\n    by_signature: dict[tuple[str, ...], TransferCandidate] = {}\n    for candidate in candidates:\n        signature = tuple(\n            _prediction_key(_safe_prediction(candidate.expression, context))\n            for context in diagnostic_contexts\n        )\n        previous = by_signature.get(signature)\n        if previous is None or (\n            candidate.repair_distance,\n            candidate.role_permutation_distance,\n            candidate.candidate_id,\n        ) < (\n            previous.repair_distance,\n            previous.role_permutation_distance,\n            previous.candidate_id,\n        ):\n            by_signature[signature] = candidate\n    return sorted(\n        by_signature.values(),\n        key=lambda row: (row.repair_distance, row.role_permutation_distance, row.candidate_id),\n    )\n'''

NEW_DEDUPE = '''def _proven_structural_semantic_key(expr: Expr) -> str:\n    if isinstance(expr, Field):\n        return json.dumps(('field', expr.name), separators=(',', ':'), ensure_ascii=True)\n    if isinstance(expr, Const):\n        return json.dumps(('const', expr.to_data()), sort_keys=True, separators=(',', ':'), ensure_ascii=True)\n    if isinstance(expr, Unary):\n        return json.dumps(\n            ('unary', expr.op, _proven_structural_semantic_key(expr.arg)),\n            separators=(',', ':'),\n            ensure_ascii=True,\n        )\n    if isinstance(expr, Binary):\n        left = _proven_structural_semantic_key(expr.left)\n        right = _proven_structural_semantic_key(expr.right)\n        if expr.op in _PROVEN_COMMUTATIVE_BINARY_OPS and right < left:\n            left, right = right, left\n        return json.dumps(('binary', expr.op, left, right), separators=(',', ':'), ensure_ascii=True)\n    if isinstance(expr, IfElse):\n        return json.dumps(\n            (\n                'ifelse',\n                _proven_structural_semantic_key(expr.condition),\n                _proven_structural_semantic_key(expr.when_true),\n                _proven_structural_semantic_key(expr.when_false),\n            ),\n            separators=(',', ':'),\n            ensure_ascii=True,\n        )\n    raise TypeError(f'unsupported expression type: {type(expr).__name__}')\n\n\ndef _dedupe_live_candidates(\n    candidates: Sequence[TransferCandidate],\n    diagnostic_contexts: Sequence[Mapping[str, object]],\n) -> list[TransferCandidate]:\n    # Diagnostic predictions are evidence, not proof of program equivalence.\n    # Keep the argument for the shared solver interface, but never collapse\n    # distinct programs merely because a finite diagnostic surface aliases them.\n    del diagnostic_contexts\n    by_signature: dict[str, TransferCandidate] = {}\n    for candidate in candidates:\n        signature = _proven_structural_semantic_key(candidate.expression)\n        previous = by_signature.get(signature)\n        if previous is None or (\n            candidate.repair_distance,\n            candidate.role_permutation_distance,\n            candidate.candidate_id,\n        ) < (\n            previous.repair_distance,\n            previous.role_permutation_distance,\n            previous.candidate_id,\n        ):\n            by_signature[signature] = candidate\n    return sorted(\n        by_signature.values(),\n        key=lambda row: (row.repair_distance, row.role_permutation_distance, row.candidate_id),\n    )\n'''


def main() -> None:
    text = PATH.read_text(encoding='utf-8')
    if NEW_DEDUPE in text and NEW_CONSTANTS in text:
        print('R268T_DIAGNOSTIC_ALIAS_ALREADY_MATERIALIZED')
        return
    if text.count(OLD_CONSTANTS) != 1:
        raise SystemExit('unexpected constants insertion boundary')
    if text.count(OLD_DEDUPE) != 1:
        raise SystemExit('unexpected diagnostic dedupe boundary')
    text = text.replace(OLD_CONSTANTS, NEW_CONSTANTS, 1)
    text = text.replace(OLD_DEDUPE, NEW_DEDUPE, 1)
    PATH.write_text(text, encoding='utf-8')
    print('R268T_DIAGNOSTIC_ALIAS_MATERIALIZED')


if __name__ == '__main__':
    main()
