from __future__ import annotations

import hashlib
import json
from typing import Any


COMPONENT_ID = "core.canonical_digest"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.types"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


__all__ = ("canonical_json", "canonical_digest")
