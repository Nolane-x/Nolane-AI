from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .registry import AgentRegistry


@dataclass(frozen=True, slots=True)
class AuthorityBlock:
    block_id: str
    artifact_id: str
    blocker_agent_id: str
    reason: str

    def to_state(self) -> dict[str, str]:
        return {
            'block_id': self.block_id,
            'artifact_id': self.artifact_id,
            'blocker_agent_id': self.blocker_agent_id,
            'reason': self.reason,
        }


@dataclass(frozen=True, slots=True)
class OverrideReceipt:
    override_id: str
    artifact_id: str
    actor_agent_id: str
    reason: str
    evidence_ids: tuple[str, ...]
    overrode_block: bool

    def to_state(self) -> dict[str, Any]:
        return {
            'override_id': self.override_id,
            'artifact_id': self.artifact_id,
            'actor_agent_id': self.actor_agent_id,
            'reason': self.reason,
            'evidence_ids': list(self.evidence_ids),
            'overrode_block': self.overrode_block,
        }


class AuthorityGraph:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self._owners: dict[str, str] = {}
        self._blocks: dict[str, list[AuthorityBlock]] = {}
        self._overrides: dict[str, OverrideReceipt] = {}
        self._block_counter = 0
        self._override_counter = 0

    def claim_owner(self, artifact_id: str, owner_agent_id: str) -> None:
        artifact = str(artifact_id).strip()
        if not artifact:
            raise ValueError('artifact id must be non-empty')
        self.registry.get(owner_agent_id)
        existing = self._owners.get(artifact)
        if existing is not None and existing != owner_agent_id:
            raise ValueError(f'artifact {artifact} already owned by {existing}')
        self._owners[artifact] = str(owner_agent_id)

    def owner_of(self, artifact_id: str) -> str | None:
        return self._owners.get(str(artifact_id))

    def record_block(self, artifact_id: str, blocker_agent_id: str, *, reason: str) -> AuthorityBlock:
        self.registry.get(blocker_agent_id)
        if not str(reason).strip():
            raise ValueError('block reason must be explicit')
        self._block_counter += 1
        row = AuthorityBlock(
            block_id=f'block-{self._block_counter:08d}',
            artifact_id=str(artifact_id),
            blocker_agent_id=str(blocker_agent_id),
            reason=str(reason),
        )
        self._blocks.setdefault(row.artifact_id, []).append(row)
        return row

    def blocks_for(self, artifact_id: str) -> tuple[AuthorityBlock, ...]:
        return tuple(self._blocks.get(str(artifact_id), ()))

    def central_override(self, *, artifact_id: str, reason: str, evidence_ids: tuple[str, ...]) -> OverrideReceipt:
        self.registry.get('nolane.central')
        if not str(reason).strip():
            raise ValueError('Central override requires an explicit reason')
        if not evidence_ids:
            raise ValueError('Central override requires explicit evidence ids')
        self._override_counter += 1
        row = OverrideReceipt(
            override_id=f'override-{self._override_counter:08d}',
            artifact_id=str(artifact_id),
            actor_agent_id='nolane.central',
            reason=str(reason),
            evidence_ids=tuple(str(value) for value in evidence_ids),
            overrode_block=bool(self._blocks.get(str(artifact_id))),
        )
        self._overrides[row.override_id] = row
        return row

    def can_write(self, actor_agent_id: str, artifact_id: str, *, override_id: str | None = None) -> bool:
        actor = self.registry.get(actor_agent_id)
        artifact = str(artifact_id)
        blocked = bool(self._blocks.get(artifact))
        if override_id is not None:
            receipt = self._overrides.get(str(override_id))
            return bool(
                receipt
                and receipt.actor_agent_id == actor.agent_id
                and receipt.artifact_id == artifact
                and actor.agent_id == 'nolane.central'
            )
        if blocked:
            return False
        if actor.agent_id == 'nolane.central':
            return True
        return self._owners.get(artifact) == actor.agent_id

    def require_write(self, actor_agent_id: str, artifact_id: str, *, override_id: str | None = None) -> None:
        if self.can_write(actor_agent_id, artifact_id, override_id=override_id):
            return
        if self._blocks.get(str(artifact_id)):
            raise PermissionError(f'artifact {artifact_id} is blocked by independent authority')
        raise PermissionError(f'agent {actor_agent_id} is not authorized to write artifact {artifact_id}')

    def to_state(self) -> dict[str, Any]:
        return {
            'owners': dict(sorted(self._owners.items())),
            'blocks': {
                key: [row.to_state() for row in value]
                for key, value in sorted(self._blocks.items())
            },
            'overrides': {
                key: value.to_state()
                for key, value in sorted(self._overrides.items())
            },
            'block_counter': self._block_counter,
            'override_counter': self._override_counter,
        }

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> 'AuthorityGraph':
        graph = cls(registry)
        for artifact_id, owner in state.get('owners', {}).items():
            graph._owners[str(artifact_id)] = str(owner)
        for artifact_id, rows in state.get('blocks', {}).items():
            graph._blocks[str(artifact_id)] = [
                AuthorityBlock(
                    block_id=str(row['block_id']),
                    artifact_id=str(row['artifact_id']),
                    blocker_agent_id=str(row['blocker_agent_id']),
                    reason=str(row['reason']),
                )
                for row in rows
            ]
        for override_id, row in state.get('overrides', {}).items():
            graph._overrides[str(override_id)] = OverrideReceipt(
                override_id=str(row['override_id']),
                artifact_id=str(row['artifact_id']),
                actor_agent_id=str(row['actor_agent_id']),
                reason=str(row['reason']),
                evidence_ids=tuple(str(value) for value in row.get('evidence_ids', ())),
                overrode_block=bool(row.get('overrode_block', False)),
            )
        graph._block_counter = int(state.get('block_counter', len([x for rows in graph._blocks.values() for x in rows])))
        graph._override_counter = int(state.get('override_counter', len(graph._overrides)))
        return graph
