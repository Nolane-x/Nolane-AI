from __future__ import annotations

from pathlib import Path


PATH = Path('cogcoder/r268_cross_task_causal_transfer.py')

OLD_DEDUPE = '''def _dedupe_live_candidates(\n    candidates: Sequence[TransferCandidate],\n    diagnostic_contexts: Sequence[Mapping[str, object]],\n) -> list[TransferCandidate]:\n    by_signature: dict[tuple[str, ...], TransferCandidate] = {}\n    for candidate in candidates:\n        signature = tuple(\n            _prediction_key(_safe_prediction(candidate.expression, context))\n            for context in diagnostic_contexts\n        )\n        previous = by_signature.get(signature)\n        if previous is None or (\n            candidate.repair_distance,\n            candidate.role_permutation_distance,\n            candidate.candidate_id,\n        ) < (\n            previous.repair_distance,\n            previous.role_permutation_distance,\n            previous.candidate_id,\n        ):\n            by_signature[signature] = candidate\n    return sorted(\n        by_signature.values(),\n        key=lambda row: (row.repair_distance, row.role_permutation_distance, row.candidate_id),\n    )\n'''

NEW_DEDUPE = '''def _bounded_role_value_bank(\n    diagnostic_contexts: Sequence[Mapping[str, object]],\n    role: str,\n    *,\n    limit: int = 8,\n) -> tuple[int | float, ...]:\n    unique: dict[str, int | float] = {}\n    for context in diagnostic_contexts:\n        value = _canonical_number(context[role])\n        key = json.dumps(value, separators=(',', ':'), allow_nan=False)\n        unique[key] = value\n    ordered = sorted(unique.values(), key=float)\n    if len(ordered) <= limit:\n        return tuple(ordered)\n    if limit < 2:\n        raise ValueError('semantic closure role-value limit must be at least 2')\n    indices = sorted({round(index * (len(ordered) - 1) / (limit - 1)) for index in range(limit)})\n    return tuple(ordered[index] for index in indices)\n\n\ndef _diagnostic_semantic_closure(\n    diagnostic_contexts: Sequence[Mapping[str, object]],\n) -> tuple[dict[str, int | float], ...]:\n    banks = tuple(_bounded_role_value_bank(diagnostic_contexts, role) for role in _PROBE_ROLES)\n    rows: list[dict[str, int | float]] = []\n    seen: set[str] = set()\n    for values in itertools.product(*banks):\n        context = dict(zip(_PROBE_ROLES, values, strict=True))\n        key = _context_key(context)\n        if key in seen:\n            continue\n        seen.add(key)\n        rows.append(context)\n    return tuple(rows)\n\n\ndef _dedupe_live_candidates(\n    candidates: Sequence[TransferCandidate],\n    diagnostic_contexts: Sequence[Mapping[str, object]],\n) -> list[TransferCandidate]:\n    # A finite diagnostic table can contain accidental correlations (for\n    # example p0 == p1 on every observed row). Build a bounded, target-label-\n    # free counterfactual closure from the observed marginal values before\n    # treating two candidate programs as observational aliases. Terminal inputs\n    # and oracle outputs are deliberately excluded from this equivalence pass.\n    fingerprint_contexts = (\n        tuple(diagnostic_contexts)\n        + _diagnostic_semantic_closure(diagnostic_contexts)\n    )\n    by_signature: dict[tuple[str, ...], TransferCandidate] = {}\n    for candidate in candidates:\n        signature = tuple(\n            _prediction_key(_safe_prediction(candidate.expression, context))\n            for context in fingerprint_contexts\n        )\n        previous = by_signature.get(signature)\n        if previous is None or (\n            candidate.repair_distance,\n            candidate.role_permutation_distance,\n            candidate.candidate_id,\n        ) < (\n            previous.repair_distance,\n            previous.role_permutation_distance,\n            previous.candidate_id,\n        ):\n            by_signature[signature] = candidate\n    return sorted(\n        by_signature.values(),\n        key=lambda row: (row.repair_distance, row.role_permutation_distance, row.candidate_id),\n    )\n'''


def main() -> None:
    text = PATH.read_text(encoding='utf-8')
    if NEW_DEDUPE in text:
        print('R268T_DIAGNOSTIC_ALIAS_ALREADY_MATERIALIZED')
        return
    if text.count(OLD_DEDUPE) != 1:
        raise SystemExit('unexpected diagnostic dedupe boundary')
    PATH.write_text(text.replace(OLD_DEDUPE, NEW_DEDUPE, 1), encoding='utf-8')
    print('R268T_DIAGNOSTIC_ALIAS_MATERIALIZED')


if __name__ == '__main__':
    main()
