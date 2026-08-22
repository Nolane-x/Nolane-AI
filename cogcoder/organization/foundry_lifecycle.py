from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .foundry_profiles import EphemeralIdentityManifest
from .registry import AgentRegistry
from .types import canonical_digest


class FoundryStatus(str, Enum):
    REQUESTED = 'requested'
    APPROVED = 'approved'
    INSTANTIATED = 'instantiated'
    ACTIVE = 'active'
    VERIFYING = 'verifying'
    HANDOFF = 'handoff'
    RETIRED = 'retired'
    REJECTED = 'rejected'
    EXHAUSTED = 'exhausted'
    QUARANTINED = 'quarantined'
    ABORTED = 'aborted'


_TERMINAL = {
    FoundryStatus.RETIRED,
    FoundryStatus.REJECTED,
    FoundryStatus.EXHAUSTED,
    FoundryStatus.QUARANTINED,
    FoundryStatus.ABORTED,
}

_ALLOWED: dict[FoundryStatus, set[FoundryStatus]] = {
    FoundryStatus.REQUESTED: {FoundryStatus.APPROVED, FoundryStatus.REJECTED},
    FoundryStatus.APPROVED: {FoundryStatus.INSTANTIATED, FoundryStatus.REJECTED},
    FoundryStatus.INSTANTIATED: {FoundryStatus.ACTIVE, FoundryStatus.ABORTED, FoundryStatus.QUARANTINED},
    FoundryStatus.ACTIVE: {
        FoundryStatus.VERIFYING, FoundryStatus.RETIRED, FoundryStatus.EXHAUSTED,
        FoundryStatus.QUARANTINED, FoundryStatus.ABORTED,
    },
    FoundryStatus.VERIFYING: {
        FoundryStatus.HANDOFF, FoundryStatus.RETIRED, FoundryStatus.EXHAUSTED,
        FoundryStatus.QUARANTINED, FoundryStatus.ABORTED,
    },
    FoundryStatus.HANDOFF: {
        FoundryStatus.RETIRED, FoundryStatus.QUARANTINED, FoundryStatus.ABORTED,
    },
}


@dataclass(frozen=True, slots=True)
class FoundryLifecycleReceipt:
    receipt_id: str
    sequence: int
    ephemeral_id: str
    actor_agent_id: str
    from_status: FoundryStatus
    to_status: FoundryStatus
    reason: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id,
            'sequence': self.sequence,
            'ephemeral_id': self.ephemeral_id,
            'actor_agent_id': self.actor_agent_id,
            'from_status': self.from_status.value,
            'to_status': self.to_status.value,
            'reason': self.reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FoundryLifecycleReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']), sequence=int(state['sequence']),
            ephemeral_id=str(state['ephemeral_id']), actor_agent_id=str(state['actor_agent_id']),
            from_status=FoundryStatus(str(state['from_status'])),
            to_status=FoundryStatus(str(state['to_status'])), reason=str(state['reason']),
            digest=str(state['digest']),
        )
        if row.sequence <= 0:
            raise ValueError('Foundry lifecycle sequence must be positive')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry lifecycle receipt digest mismatch')
        return row


class FoundryLifecycleLedger:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        manifests: tuple[EphemeralIdentityManifest, ...] = (),
        receipts: tuple[FoundryLifecycleReceipt, ...] = (),
        statuses: Mapping[str, str] | None = None,
        counter: int = 0,
    ) -> None:
        self.registry = registry
        self._manifests: dict[str, EphemeralIdentityManifest] = {}
        self._statuses: dict[str, FoundryStatus] = {}
        for manifest in manifests:
            self._install_manifest(manifest)
        self._receipts: list[FoundryLifecycleReceipt] = []
        last_sequence = 0
        for receipt in receipts:
            if receipt.sequence <= last_sequence:
                raise ValueError('Foundry lifecycle receipts are not strictly ordered')
            if receipt.ephemeral_id not in self._manifests:
                raise ValueError('Foundry lifecycle receipt references unknown manifest')
            self.registry.get(receipt.actor_agent_id)
            self._receipts.append(receipt)
            last_sequence = receipt.sequence
        if statuses is not None:
            normalized = {str(key): FoundryStatus(str(value)) for key, value in statuses.items()}
            if set(normalized) != set(self._manifests):
                raise ValueError('Foundry lifecycle status map does not match manifests')
            self._statuses = normalized
        elif receipts:
            reconstructed = {key: FoundryStatus.INSTANTIATED for key in self._manifests}
            for receipt in receipts:
                if reconstructed[receipt.ephemeral_id] is not receipt.from_status:
                    raise ValueError('Foundry lifecycle replay source status mismatch')
                if receipt.to_status not in _ALLOWED.get(receipt.from_status, set()):
                    raise ValueError('Foundry lifecycle replay contains invalid transition')
                reconstructed[receipt.ephemeral_id] = receipt.to_status
            self._statuses = reconstructed
        self._counter = int(counter)
        if self._counter < len(self._receipts) or self._counter < last_sequence:
            raise ValueError('Foundry lifecycle counter is not canonical')

    def _install_manifest(self, manifest: EphemeralIdentityManifest) -> None:
        if manifest.ephemeral_id in self._manifests:
            raise ValueError('duplicate Foundry lifecycle manifest')
        self.registry.get(manifest.sponsor_agent_id)
        self._manifests[manifest.ephemeral_id] = manifest
        self._statuses[manifest.ephemeral_id] = FoundryStatus.INSTANTIATED

    def register_manifest(self, manifest: EphemeralIdentityManifest) -> None:
        existing = self._manifests.get(manifest.ephemeral_id)
        if existing is not None:
            if existing != manifest:
                raise ValueError('Foundry lifecycle manifest cannot be rebound')
            return
        self._install_manifest(manifest)

    def manifest(self, ephemeral_id: str) -> EphemeralIdentityManifest:
        try:
            return self._manifests[str(ephemeral_id)]
        except KeyError as exc:
            raise KeyError(f'unknown Foundry lifecycle identity: {ephemeral_id}') from exc

    def status(self, ephemeral_id: str) -> FoundryStatus:
        self.manifest(ephemeral_id)
        return self._statuses[str(ephemeral_id)]

    def _authorized(self, ephemeral_id: str, actor_agent_id: str) -> str:
        manifest = self.manifest(ephemeral_id)
        actor = self.registry.get(actor_agent_id)
        if actor.agent_id != 'nolane.central' and actor.agent_id != manifest.sponsor_agent_id:
            raise PermissionError('Foundry lifecycle transition requires Central or the permanent sponsor')
        return actor.agent_id

    def transition(
        self,
        ephemeral_id: str,
        to_status: FoundryStatus,
        *,
        actor_agent_id: str,
        reason: str,
    ) -> FoundryLifecycleReceipt:
        actor = self._authorized(ephemeral_id, actor_agent_id)
        current = self.status(ephemeral_id)
        target = FoundryStatus(to_status)
        if current in _TERMINAL:
            raise PermissionError('terminal Foundry worker cannot be reactivated or transitioned')
        if target not in _ALLOWED.get(current, set()):
            raise PermissionError(f'invalid Foundry lifecycle transition {current.value}->{target.value}')
        reason = str(reason).strip()
        if not reason:
            raise ValueError('Foundry lifecycle transition requires an explicit reason')
        self._counter += 1
        temp = FoundryLifecycleReceipt(
            receipt_id=f'foundry-life-{self._counter:08d}', sequence=self._counter,
            ephemeral_id=str(ephemeral_id), actor_agent_id=actor,
            from_status=current, to_status=target, reason=reason, digest='',
        )
        receipt = replace(temp, digest=canonical_digest(temp.payload()))
        self._receipts.append(receipt)
        self._statuses[str(ephemeral_id)] = target
        return receipt

    def receipts(self) -> tuple[FoundryLifecycleReceipt, ...]:
        return tuple(self._receipts)

    def to_state(self) -> dict[str, Any]:
        return {
            'receipts': [row.to_state() for row in self._receipts],
            'statuses': {key: self._statuses[key].value for key in sorted(self._statuses)},
            'counter': self._counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        manifests: tuple[EphemeralIdentityManifest, ...],
        state: Mapping[str, Any],
    ) -> 'FoundryLifecycleLedger':
        receipts = tuple(FoundryLifecycleReceipt.from_state(x) for x in state.get('receipts', ()))
        return cls(
            registry=registry, manifests=manifests, receipts=receipts,
            statuses=state.get('statuses'), counter=int(state.get('counter', len(receipts))),
        )
