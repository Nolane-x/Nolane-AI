from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Mapping


def _normalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _normalize(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_normalize(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_normalize(v) for v in value),
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    return value


def truth_digest(value: Any) -> str:
    payload = json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ("truth_digest",)
