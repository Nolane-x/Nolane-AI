from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass
from typing import Iterable


def _state(bits: Iterable[int]) -> tuple[int, ...]:
    row = tuple(int(v) for v in bits)
    if not row or any(v not in (0, 1) for v in row):
        raise ValueError('state must be a non-empty binary tuple')
    return row


@dataclass(frozen=True, order=True)
class GeneratedQuery:
    query_id: str
    before: tuple[int, ...]
    after: tuple[int, ...]

    @staticmethod
    def create(before: Iterable[int], after: Iterable[int]) -> 'GeneratedQuery':
        before_row = _state(before)
        after_row = _state(after)
        if len(before_row) != len(after_row):
            raise ValueError('query states must have the same width')
        payload = ''.join(map(str, before_row)) + '>' + ''.join(map(str, after_row))
        query_id = 'gq:' + hashlib.sha256(payload.encode()).hexdigest()[:20]
        return GeneratedQuery(query_id, before_row, after_row)


def enumerate_query_universe(width: int) -> tuple[GeneratedQuery, ...]:
    width = int(width)
    if width <= 0:
        raise ValueError('width must be positive')
    states = tuple(itertools.product((0, 1), repeat=width))
    return tuple(GeneratedQuery.create(before, after) for before in states for after in states)


def initial_query_pool(
    universe: Iterable[GeneratedQuery],
    size: int,
    *,
    salt: str = 'initial',
) -> tuple[GeneratedQuery, ...]:
    rows = tuple(sorted(set(universe), key=lambda q: q.query_id))
    size = int(size)
    if not rows or size <= 0 or size >= len(rows):
        raise ValueError('initial pool size must be between 1 and universe_size-1')
    salt = str(salt)
    ranked = sorted(
        rows,
        key=lambda q: (hashlib.sha256(f'{salt}:{q.query_id}'.encode()).hexdigest(), q.query_id),
    )
    return tuple(sorted(ranked[:size], key=lambda q: q.query_id))


def synthesize_counterexample_probe(
    universe: Iterable[GeneratedQuery],
    supports,
    observed_query_ids,
    predictions,
) -> GeneratedQuery:
    posterior = {str(s.operator_id): float(s.posterior) for s in supports}
    if not posterior:
        raise ValueError('supports must be non-empty')
    total = sum(posterior.values())
    if total <= 0:
        raise ValueError('posterior mass must be positive')
    posterior = {k: v / total for k, v in posterior.items()}
    observed = {str(q) for q in observed_query_ids}
    scored = []
    for query in universe:
        if query.query_id in observed:
            continue
        row = predictions.get(query.query_id)
        if row is None or set(map(str, row)) != set(posterior):
            raise ValueError('prediction coverage mismatch')
        p_true = sum(posterior[oid] for oid, label in row.items() if bool(label))
        disagreement = 2.0 * p_true * (1.0 - p_true)
        scored.append((-disagreement, query.query_id, query))
    if not scored:
        raise ValueError('no unobserved legal query remains')
    return min(scored)[2]
