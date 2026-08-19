from __future__ import annotations

from pathlib import Path


SOURCE = Path('cogcoder/r268_cross_task_causal_transfer.py')
BENCHMARK = Path('benchmarks/kfigg/r268_cross_task_causal_transfer.py')

OLD_DEDUPE_BLOCK = '''def _bounded_role_value_bank(
    diagnostic_contexts: Sequence[Mapping[str, object]],
    role: str,
    *,
    limit: int = 8,
) -> tuple[int | float, ...]:
    unique: dict[str, int | float] = {}
    for context in diagnostic_contexts:
        value = _canonical_number(context[role])
        key = json.dumps(value, separators=(',', ':'), allow_nan=False)
        unique[key] = value
    ordered = sorted(unique.values())
    if len(ordered) <= limit:
        return tuple(ordered)
    if limit < 2:
        raise ValueError('semantic closure role-value limit must be at least 2')
    indices = tuple(index * (len(ordered) - 1) // (limit - 1) for index in range(limit))
    return tuple(ordered[index] for index in indices)


def _diagnostic_semantic_closure(
    diagnostic_contexts: Sequence[Mapping[str, object]],
) -> tuple[dict[str, int | float], ...]:
    banks = tuple(_bounded_role_value_bank(diagnostic_contexts, role) for role in _PROBE_ROLES)
    rows: list[dict[str, int | float]] = []
    seen: set[str] = set()
    for values in itertools.product(*banks):
        context = dict(zip(_PROBE_ROLES, values, strict=True))
        key = _context_key(context)
        if key in seen:
            continue
        seen.add(key)
        rows.append(context)
    return tuple(rows)


def _dedupe_live_candidates(
    candidates: Sequence[TransferCandidate],
    diagnostic_contexts: Sequence[Mapping[str, object]],
) -> list[TransferCandidate]:
    # A finite diagnostic table can contain accidental correlations (for
    # example p0 == p1 on every observed row). Build a bounded, target-label-
    # free counterfactual closure from the observed marginal values before
    # treating two candidate programs as observational aliases. Terminal inputs
    # and oracle outputs are deliberately excluded from this equivalence pass.
    fingerprint_contexts = (
        tuple(diagnostic_contexts)
        + _diagnostic_semantic_closure(diagnostic_contexts)
    )
    by_signature: dict[tuple[str, ...], TransferCandidate] = {}
    for candidate in candidates:
        signature = tuple(
            _prediction_key(_safe_prediction(candidate.expression, context))
            for context in fingerprint_contexts
        )
        previous = by_signature.get(signature)
        if previous is None or (
            candidate.repair_distance,
            candidate.role_permutation_distance,
            candidate.candidate_id,
        ) < (
            previous.repair_distance,
            previous.role_permutation_distance,
            previous.candidate_id,
        ):
            by_signature[signature] = candidate
    return sorted(
        by_signature.values(),
        key=lambda row: (row.repair_distance, row.role_permutation_distance, row.candidate_id),
    )
'''

NEW_DEDUPE_BLOCK = '''_PROVEN_COMMUTATIVE_NUMERIC_OPS = frozenset(('add', 'mul'))


def _proven_structural_alias_key(expr: Expr) -> str:
    if isinstance(expr, Field):
        return json.dumps(('field', expr.name), separators=(',', ':'), ensure_ascii=True)
    if isinstance(expr, Const):
        return json.dumps(('const', expr.value), separators=(',', ':'), ensure_ascii=True)
    if isinstance(expr, Unary):
        return json.dumps(
            ('unary', expr.op, _proven_structural_alias_key(expr.arg)),
            separators=(',', ':'),
            ensure_ascii=True,
        )
    if isinstance(expr, Binary):
        left = _proven_structural_alias_key(expr.left)
        right = _proven_structural_alias_key(expr.right)
        if expr.op in _PROVEN_COMMUTATIVE_NUMERIC_OPS and right < left:
            left, right = right, left
        return json.dumps(
            ('binary', expr.op, left, right),
            separators=(',', ':'),
            ensure_ascii=True,
        )
    if isinstance(expr, IfElse):
        return json.dumps(
            (
                'ifelse',
                _proven_structural_alias_key(expr.condition),
                _proven_structural_alias_key(expr.when_true),
                _proven_structural_alias_key(expr.when_false),
            ),
            separators=(',', ':'),
            ensure_ascii=True,
        )
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


def _dedupe_live_candidates(
    candidates: Sequence[TransferCandidate],
    diagnostic_contexts: Sequence[Mapping[str, object]],
) -> list[TransferCandidate]:
    # Finite behavioral agreement is evidence, not a proof of extensional
    # program equivalence. Collapse only structural aliases whose equality is
    # guaranteed on this numeric three-probe runtime. All remaining hypotheses
    # must be distinguished by real diagnostic oracle evidence or fail closed.
    del diagnostic_contexts
    by_signature: dict[str, TransferCandidate] = {}
    for candidate in candidates:
        signature = _proven_structural_alias_key(candidate.expression)
        previous = by_signature.get(signature)
        if previous is None or (
            candidate.repair_distance,
            candidate.role_permutation_distance,
            candidate.candidate_id,
        ) < (
            previous.repair_distance,
            previous.role_permutation_distance,
            previous.candidate_id,
        ):
            by_signature[signature] = candidate
    return sorted(
        by_signature.values(),
        key=lambda row: (row.repair_distance, row.role_permutation_distance, row.candidate_id),
    )
'''

OLD_DIAGNOSTICS = '''def _diagnostics() -> tuple[dict[str, int], ...]:
    return (
        {'__p0': 1, '__p1': 2, '__p2': 3},
        {'__p0': 2, '__p1': 4, '__p2': 1},
        {'__p0': -1, '__p1': 3, '__p2': 2},
        {'__p0': 5, '__p1': -2, '__p2': 4},
        {'__p0': 3, '__p1': 3, '__p2': 1},
        {'__p0': 6, '__p1': 2, '__p2': -3},
        {'__p0': -4, '__p1': 5, '__p2': 2},
    )
'''

NEW_DIAGNOSTICS = '''def _diagnostics() -> tuple[dict[str, int | float], ...]:
    return (
        {'__p0': 1, '__p1': 2, '__p2': 3},
        {'__p0': 2, '__p1': 4, '__p2': 1},
        {'__p0': -1, '__p1': 3, '__p2': 2},
        {'__p0': 5, '__p1': -2, '__p2': 4},
        {'__p0': 3, '__p1': 3, '__p2': 1},
        {'__p0': 6, '__p1': 2, '__p2': -3},
        {'__p0': -4, '__p1': 5, '__p2': 2},
        # Python floating subtraction is not reassociative. These public,
        # non-integral rows make that semantic distinction observable instead
        # of treating finite behavioral fingerprints as equivalence proofs.
        {'__p0': 1000000000000000.25, '__p1': 1000000000000000.125, '__p2': 0.1},
        {'__p0': 0.1, '__p1': 10000000000.1, '__p2': 10000000000.1},
    )
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one replacement boundary, found {count}')
    return text.replace(old, new, 1)


def main() -> None:
    source = SOURCE.read_text(encoding='utf-8')
    benchmark = BENCHMARK.read_text(encoding='utf-8')

    already = (
        '_proven_structural_alias_key' in source
        and '_diagnostic_semantic_closure' not in source
        and '1000000000000000.25' in benchmark
        and '10000000000.1' in benchmark
    )
    if already:
        print('R268T_FINITE_FINGERPRINT_AUTHORITY_ALREADY_MATERIALIZED')
        return

    source = replace_once(source, OLD_DEDUPE_BLOCK, NEW_DEDUPE_BLOCK, 'dedupe authority')
    benchmark = replace_once(benchmark, OLD_DIAGNOSTICS, NEW_DIAGNOSTICS, 'authored diagnostics')

    if '_diagnostic_semantic_closure' in source or '_bounded_role_value_bank' in source:
        raise SystemExit('finite behavioral fingerprint authority remains after patch')

    compile(source, str(SOURCE), 'exec')
    compile(benchmark, str(BENCHMARK), 'exec')
    SOURCE.write_text(source, encoding='utf-8')
    BENCHMARK.write_text(benchmark, encoding='utf-8')
    print('R268T_FINITE_FINGERPRINT_AUTHORITY_MATERIALIZED')


if __name__ == '__main__':
    main()
