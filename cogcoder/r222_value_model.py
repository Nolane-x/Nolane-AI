from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from collections.abc import Sequence


def _solve_linear_system(a: list[list[float]], b: list[float]) -> tuple[float, ...]:
    n = len(a)
    if n == 0 or any(len(row) != n for row in a) or len(b) != n:
        raise ValueError('linear system must be square and non-empty')
    aug = [list(map(float, row)) + [float(rhs)] for row, rhs in zip(a, b)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: (abs(aug[r][col]), -r))
        if abs(aug[pivot][col]) < 1e-15:
            raise ValueError('singular linear system')
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [v / scale for v in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            if factor == 0.0:
                continue
            aug[row] = [x - factor * y for x, y in zip(aug[row], aug[col])]
    return tuple(row[-1] for row in aug)


@dataclass(frozen=True)
class RidgeValueModel:
    weights: tuple[float, ...]
    l2: float

    def __post_init__(self) -> None:
        weights = tuple(float(v) for v in self.weights)
        if not weights or not all(math.isfinite(v) for v in weights):
            raise ValueError('weights must be finite and non-empty')
        l2 = float(self.l2)
        if not math.isfinite(l2) or l2 < 0.0:
            raise ValueError('l2 must be finite and non-negative')
        object.__setattr__(self, 'weights', weights)
        object.__setattr__(self, 'l2', l2)

    @classmethod
    def fit(
        cls,
        rows: Sequence[Sequence[float]],
        targets: Sequence[float],
        *,
        l2: float,
    ) -> 'RidgeValueModel':
        rows = tuple(tuple(float(v) for v in row) for row in rows)
        targets = tuple(float(v) for v in targets)
        if not rows or len(rows) != len(targets):
            raise ValueError('rows and targets must be non-empty and aligned')
        width = len(rows[0])
        if width <= 0 or any(len(row) != width for row in rows):
            raise ValueError('all rows must share a positive feature width')
        if not all(math.isfinite(v) for row in rows for v in row):
            raise ValueError('features must be finite')
        if not all(math.isfinite(v) for v in targets):
            raise ValueError('targets must be finite')
        l2 = float(l2)
        if not math.isfinite(l2) or l2 < 0.0:
            raise ValueError('l2 must be finite and non-negative')

        xtx = [[0.0 for _ in range(width)] for _ in range(width)]
        xty = [0.0 for _ in range(width)]
        for row, target in zip(rows, targets):
            for i in range(width):
                xty[i] += row[i] * target
                for j in range(width):
                    xtx[i][j] += row[i] * row[j]
        for i in range(width):
            xtx[i][i] += l2
        weights = _solve_linear_system(xtx, xty)
        return cls(weights=weights, l2=l2)

    def predict(self, features: Sequence[float]) -> float:
        features = tuple(float(v) for v in features)
        if len(features) != len(self.weights):
            raise ValueError('feature width mismatch')
        if not all(math.isfinite(v) for v in features):
            raise ValueError('features must be finite')
        return sum(w * x for w, x in zip(self.weights, features))

    def to_payload(self) -> dict:
        return {
            'schema_version': 1,
            'l2': self.l2,
            'weights': list(self.weights),
        }

    def to_canonical_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, separators=(',', ':'), allow_nan=False)

    @property
    def model_hash(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode('utf-8')).hexdigest()
