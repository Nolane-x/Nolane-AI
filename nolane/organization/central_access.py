from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from nolane.organization.events import EventKind
from nolane.external_core.invokable import ExternalCoreRegistry
from nolane.organization.identity import AgentRegistry


# Historical Central actions were schema-preserving aliases rather than new
# EventKind enum values. Preserve that compatibility exactly during ownership
# migration so accepted state/event serialization remains unchanged.
for _name in (
    'CENTRAL_RESOURCE_ALLOCATED', 'CENTRAL_RESOURCE_RELEASED',
    'CENTRAL_CONFLICT_OPENED', 'CENTRAL_CONFLICT_RESOLVED',
    'CENTRAL_DIRECT_WORK', 'CENTRAL_CORE_LEASE_GRANTED', 'CENTRAL_CORE_LEASE_REVOKED',
):
    if not hasattr(EventKind, _name):
        setattr(EventKind, _name, EventKind.CENTRAL_INTERVENTION)


_DIRECT_CENTRAL_CORE_OWNERS = {'nolane.central', 'global-command', 'shared-governed-core'}


def _evidence(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(x).strip() for x in values if str(x).strip())


@dataclass(frozen=True, slots=True)
class CoreLease:
    lease_id: str
    core_id: str
    owner: str
    call_budget: int
    remaining_calls: int
    expires_at_token: int
    reason: str
    evidence_refs: tuple[str, ...]
    revoked: bool = False
    revoke_reason: str | None = None
    revoke_evidence_refs: tuple[str, ...] = ()

    def to_state(self) -> dict[str, Any]:
        return {
            'lease_id': self.lease_id, 'core_id': self.core_id, 'owner': self.owner,
            'call_budget': self.call_budget, 'remaining_calls': self.remaining_calls,
            'expires_at_token': self.expires_at_token, 'reason': self.reason,
            'evidence_refs': list(self.evidence_refs), 'revoked': self.revoked,
            'revoke_reason': self.revoke_reason, 'revoke_evidence_refs': list(self.revoke_evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CoreLease':
        return cls(
            lease_id=str(state['lease_id']), core_id=str(state['core_id']), owner=str(state['owner']),
            call_budget=int(state['call_budget']), remaining_calls=int(state['remaining_calls']),
            expires_at_token=int(state['expires_at_token']), reason=str(state['reason']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            revoked=bool(state.get('revoked', False)),
            revoke_reason=None if state.get('revoke_reason') is None else str(state['revoke_reason']),
            revoke_evidence_refs=tuple(str(x) for x in state.get('revoke_evidence_refs', ())),
        )


class CentralCoreAccessPolicy:
    def __init__(self, registry: AgentRegistry, cores: ExternalCoreRegistry) -> None:
        registry.get('nolane.central')
        self.registry = registry
        self.cores = cores
        self._leases: dict[str, CoreLease] = {}
        self._counter = 0

    def _direct(self, core_id: str) -> bool:
        return self.cores.get(core_id).owner_agent_or_region in _DIRECT_CENTRAL_CORE_OWNERS

    def can_invoke(self, core_id: str, *, token: int, lease_id: str | None = None) -> bool:
        if isinstance(token, bool) or not isinstance(token, int) or token < 0:
            raise ValueError('core-access token must be a non-negative integer')
        if self._direct(core_id):
            return True
        if lease_id is None:
            return False
        lease = self._leases.get(str(lease_id))
        return bool(
            lease is not None and lease.core_id == str(core_id) and not lease.revoked
            and token <= lease.expires_at_token and lease.remaining_calls > 0
        )

    def grant_lease(self, *, core_id: str, owner: str, call_budget: int, expires_at_token: int,
                    reason: str, evidence_refs: tuple[str, ...]) -> CoreLease:
        spec = self.cores.get(core_id)
        owner = str(owner).strip()
        if owner != spec.owner_agent_or_region:
            raise PermissionError('external-core lease owner does not match registered owner')
        if isinstance(call_budget, bool) or not isinstance(call_budget, int) or call_budget <= 0:
            raise ValueError('external-core call budget must be positive')
        if isinstance(expires_at_token, bool) or not isinstance(expires_at_token, int) or expires_at_token < 0:
            raise ValueError('lease expiry token must be non-negative')
        reason = str(reason).strip()
        evidence = _evidence(evidence_refs)
        if not reason or not evidence:
            raise ValueError('external-core lease requires reason and evidence')
        self._counter += 1
        row = CoreLease(
            lease_id=f'corelease-{self._counter:08d}', core_id=str(core_id), owner=owner,
            call_budget=call_budget, remaining_calls=call_budget, expires_at_token=expires_at_token,
            reason=reason, evidence_refs=evidence,
        )
        self._leases[row.lease_id] = row
        return row

    def get(self, lease_id: str) -> CoreLease:
        try:
            return self._leases[str(lease_id)]
        except KeyError as exc:
            raise KeyError(f'unknown core lease: {lease_id}') from exc

    def consume(self, lease_id: str, *, token: int) -> CoreLease:
        old = self.get(lease_id)
        if not self.can_invoke(old.core_id, token=token, lease_id=old.lease_id):
            raise PermissionError('external-core lease is not active for this call')
        row = replace(old, remaining_calls=old.remaining_calls - 1)
        self._leases[row.lease_id] = row
        return row

    def revoke(self, lease_id: str, *, reason: str, evidence_refs: tuple[str, ...]) -> CoreLease:
        old = self.get(lease_id)
        reason = str(reason).strip()
        evidence = _evidence(evidence_refs)
        if not reason or not evidence:
            raise ValueError('lease revoke requires reason and evidence')
        row = replace(old, revoked=True, revoke_reason=reason, revoke_evidence_refs=evidence)
        self._leases[row.lease_id] = row
        return row

    def leases(self) -> tuple[CoreLease, ...]:
        return tuple(self._leases[k] for k in sorted(self._leases))

    def to_state(self) -> dict[str, Any]:
        return {'leases': [x.to_state() for x in self.leases()], 'counter': self._counter}

    @classmethod
    def from_state(cls, registry: AgentRegistry, cores: ExternalCoreRegistry,
                   state: Mapping[str, Any]) -> 'CentralCoreAccessPolicy':
        policy = cls(registry, cores)
        rows = [CoreLease.from_state(x) for x in state.get('leases', ())]
        for expected, row in enumerate(rows, start=1):
            if row.lease_id != f'corelease-{expected:08d}':
                raise ValueError('core lease ids are not canonical')
            spec = cores.get(row.core_id)
            if row.owner != spec.owner_agent_or_region:
                raise ValueError('restored core lease owner mismatch')
            if row.call_budget <= 0 or not 0 <= row.remaining_calls <= row.call_budget:
                raise ValueError('restored core lease budget is invalid')
            policy._leases[row.lease_id] = row
        policy._counter = int(state.get('counter', len(rows)))
        if policy._counter != len(rows):
            raise ValueError('core lease counter is not canonical')
        return policy
