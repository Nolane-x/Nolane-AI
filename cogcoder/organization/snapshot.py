from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .runtime import OrganizationRuntime
from .types import canonical_digest, canonical_json


SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class OrganizationSnapshot:
    schema_version: int
    state_json: str
    digest: str

    @classmethod
    def capture(cls, runtime: OrganizationRuntime) -> 'OrganizationSnapshot':
        state = runtime.to_state()
        state_json = canonical_json(state)
        payload = {'schema_version': SNAPSHOT_SCHEMA_VERSION, 'state': json.loads(state_json)}
        return cls(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            state_json=state_json,
            digest=canonical_digest(payload),
        )

    def to_json(self) -> str:
        return canonical_json(
            {
                'schema_version': self.schema_version,
                'state': json.loads(self.state_json),
            }
        )

    @classmethod
    def from_json(cls, text: str) -> 'OrganizationSnapshot':
        value = json.loads(str(text))
        if not isinstance(value, dict):
            raise ValueError('snapshot must decode to an object')
        schema_version = int(value.get('schema_version', 0))
        if schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f'unsupported organization snapshot schema: {schema_version}')
        state = value.get('state')
        if not isinstance(state, dict):
            raise ValueError('snapshot state must be an object')
        state_json = canonical_json(state)
        canonical_payload = {'schema_version': schema_version, 'state': json.loads(state_json)}
        return cls(
            schema_version=schema_version,
            state_json=state_json,
            digest=canonical_digest(canonical_payload),
        )

    def restore(self) -> OrganizationRuntime:
        state: Mapping[str, Any] = json.loads(self.state_json)
        return OrganizationRuntime.from_state(state)
