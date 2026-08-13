from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def _numeric_vector(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, list) or len(value) < 2:
        return None
    row: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not number.is_integer():
            return None
        row.append(int(number))
    return tuple(row)


def _parse(text: str) -> Any:
    payload = json.loads(text)
    if not isinstance(payload, (dict, list)):
        raise ValueError("public observation must decode to an object or list")
    return payload


def extract_shallow_numeric_vector(text: str) -> tuple[int, ...]:
    """Return the unique shallowest public numeric vector without using field names."""
    payload = _parse(text)
    candidates: list[tuple[int, tuple[int, ...]]] = []

    def visit(node: Any, depth: int) -> None:
        vector = _numeric_vector(node)
        if vector is not None:
            candidates.append((depth, vector))
            return
        if isinstance(node, Mapping):
            for value in node.values():
                visit(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                visit(value, depth + 1)

    visit(payload, 0)
    if not candidates:
        raise ValueError("no public numeric vector found")
    shallow = min(depth for depth, _ in candidates)
    rows = [vector for depth, vector in candidates if depth == shallow]
    if len(rows) != 1:
        raise ValueError("ambiguous shallow numeric vectors")
    return rows[0]


def extract_demonstration_vector_pairs(text: str) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """Find same-length vector pairs co-located in public mapping nodes.

    Pair orientation is deliberately not interpreted here. Program search must
    evaluate both global orientations rather than reading literal field names.
    """
    payload = _parse(text)
    pairs: list[tuple[tuple[int, ...], tuple[int, ...]]] = []

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            vectors = [vector for value in node.values() if (vector := _numeric_vector(value)) is not None]
            if len(vectors) == 2 and len(vectors[0]) == len(vectors[1]):
                pairs.append((vectors[0], vectors[1]))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            if _numeric_vector(node) is not None:
                return
            for value in node:
                visit(value)

    visit(payload)
    return pairs
