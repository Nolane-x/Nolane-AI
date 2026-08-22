from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .types import canonical_digest


class FoundryResourceKind(str, Enum):
    COMPUTE = 'compute'
    TOOL_CALL = 'tool_call'
    EXTERNAL_CORE_CALL = 'external_core_call'
    LIFETIME_TOKEN = 'lifetime_token'


@dataclass(frozen=True, slots=True)
class FoundryBudget:
    compute_units: int
    tool_calls: int
    external_core_calls: int
    max_workers: int
    lifetime_tokens: int

    def __post_init__(self) -> None:
        values = (
            self.compute_units,
            self.tool_calls,
            self.external_core_calls,
            self.max_workers,
            self.lifetime_tokens,
        )
        if any(isinstance(value, bool) or int(value) <= 0 for value in values):
            raise ValueError('Foundry budget values must be positive integers')
        if self.max_workers > 4:
            raise ValueError('first-generation Foundry team worker ceiling is 4')

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def limit_for(self, kind: FoundryResourceKind) -> int:
        kind = FoundryResourceKind(kind)
        return {
            FoundryResourceKind.COMPUTE: self.compute_units,
            FoundryResourceKind.TOOL_CALL: self.tool_calls,
            FoundryResourceKind.EXTERNAL_CORE_CALL: self.external_core_calls,
            FoundryResourceKind.LIFETIME_TOKEN: self.lifetime_tokens,
        }[kind]

    def to_state(self) -> dict[str, int]:
        return {
            'compute_units': self.compute_units,
            'tool_calls': self.tool_calls,
            'external_core_calls': self.external_core_calls,
            'max_workers': self.max_workers,
            'lifetime_tokens': self.lifetime_tokens,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FoundryBudget':
        return cls(
            compute_units=int(state['compute_units']),
            tool_calls=int(state['tool_calls']),
            external_core_calls=int(state['external_core_calls']),
            max_workers=int(state['max_workers']),
            lifetime_tokens=int(state['lifetime_tokens']),
        )


@dataclass(frozen=True, slots=True)
class ResourceUsageReceipt:
    receipt_id: str
    sequence: int
    ephemeral_id: str
    resource_kind: FoundryResourceKind
    units: int
    remaining: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id,
            'sequence': self.sequence,
            'ephemeral_id': self.ephemeral_id,
            'resource_kind': self.resource_kind.value,
            'units': self.units,
            'remaining': self.remaining,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ResourceUsageReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']),
            sequence=int(state['sequence']),
            ephemeral_id=str(state['ephemeral_id']),
            resource_kind=FoundryResourceKind(str(state['resource_kind'])),
            units=int(state['units']),
            remaining=int(state['remaining']),
            digest=str(state['digest']),
        )
        if row.sequence <= 0 or row.units <= 0 or row.remaining < 0:
            raise ValueError('invalid Foundry usage receipt counters')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry resource receipt digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class _Registration:
    ephemeral_id: str
    team_id: str
    sponsor_agent_id: str
    budget: FoundryBudget
    consumed: tuple[tuple[str, int], ...]
    active: bool
    digest: str

    def consumed_map(self) -> dict[FoundryResourceKind, int]:
        return {FoundryResourceKind(key): int(value) for key, value in self.consumed}

    def payload(self) -> dict[str, Any]:
        return {
            'ephemeral_id': self.ephemeral_id,
            'team_id': self.team_id,
            'sponsor_agent_id': self.sponsor_agent_id,
            'budget': self.budget.to_state(),
            'consumed': {key: value for key, value in self.consumed},
            'active': self.active,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> '_Registration':
        consumed_state = state.get('consumed', {})
        consumed = tuple(sorted((str(key), int(value)) for key, value in consumed_state.items()))
        row = cls(
            ephemeral_id=str(state['ephemeral_id']),
            team_id=str(state['team_id']),
            sponsor_agent_id=str(state['sponsor_agent_id']),
            budget=FoundryBudget.from_state(state['budget']),
            consumed=consumed,
            active=bool(state.get('active', False)),
            digest=str(state['digest']),
        )
        if not row.ephemeral_id.strip() or not row.team_id.strip() or not row.sponsor_agent_id.strip():
            raise ValueError('Foundry registration identity must be explicit')
        values = row.consumed_map()
        for kind in FoundryResourceKind:
            used = values.get(kind, 0)
            if used < 0 or used > row.budget.limit_for(kind):
                raise ValueError('Foundry registration consumed budget is invalid')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry registration digest mismatch')
        return row


def _signed_registration(
    *, ephemeral_id: str, team_id: str, sponsor_agent_id: str,
    budget: FoundryBudget, consumed: Mapping[FoundryResourceKind, int] | None = None,
    active: bool = False,
) -> _Registration:
    values = {
        kind.value: int((consumed or {}).get(kind, 0))
        for kind in FoundryResourceKind
    }
    temp = _Registration(
        ephemeral_id=str(ephemeral_id),
        team_id=str(team_id),
        sponsor_agent_id=str(sponsor_agent_id),
        budget=budget,
        consumed=tuple(sorted(values.items())),
        active=bool(active),
        digest='',
    )
    return replace(temp, digest=canonical_digest(temp.payload()))


class FoundryResourceGovernor:
    ORGANIZATION_ACTIVE_LIMIT = 12
    TEAM_ACTIVE_LIMIT = 4
    SPONSOR_ACTIVE_TEAM_LIMIT = 3

    def __init__(
        self,
        *,
        registrations: tuple[_Registration, ...] = (),
        receipts: tuple[ResourceUsageReceipt, ...] = (),
        counter: int = 0,
    ) -> None:
        self._registrations: dict[str, _Registration] = {}
        for row in registrations:
            if row.ephemeral_id in self._registrations:
                raise ValueError('duplicate Foundry resource registration')
            self._registrations[row.ephemeral_id] = row
        self._receipts: dict[str, ResourceUsageReceipt] = {}
        for row in receipts:
            if row.receipt_id in self._receipts:
                raise ValueError('duplicate Foundry usage receipt')
            if row.ephemeral_id not in self._registrations:
                raise ValueError('Foundry usage references unknown ephemeral identity')
            self._receipts[row.receipt_id] = row
        self._counter = int(counter)
        if self._counter < len(self._receipts):
            raise ValueError('Foundry resource counter is not canonical')
        self._validate_active_caps()

    def _validate_active_caps(self) -> None:
        active = [row for row in self._registrations.values() if row.active]
        if len(active) > self.ORGANIZATION_ACTIVE_LIMIT:
            raise ValueError('Foundry active organization limit violated in snapshot')
        by_team: dict[str, list[_Registration]] = {}
        by_sponsor: dict[str, set[str]] = {}
        for row in active:
            by_team.setdefault(row.team_id, []).append(row)
            by_sponsor.setdefault(row.sponsor_agent_id, set()).add(row.team_id)
        for rows in by_team.values():
            team_cap = min(self.TEAM_ACTIVE_LIMIT, min(row.budget.max_workers for row in rows))
            if len(rows) > team_cap:
                raise ValueError('Foundry active team limit violated in snapshot')
        if any(len(teams) > self.SPONSOR_ACTIVE_TEAM_LIMIT for teams in by_sponsor.values()):
            raise ValueError('Foundry active sponsor-team limit violated in snapshot')

    def register_manifest(
        self,
        ephemeral_id: str,
        *,
        team_id: str,
        sponsor_agent_id: str,
        budget: FoundryBudget,
    ) -> None:
        ephemeral_id = str(ephemeral_id)
        if not all(value.strip() for value in (ephemeral_id, str(team_id), str(sponsor_agent_id))):
            raise ValueError('Foundry resource registration identity must be explicit')
        row = _signed_registration(
            ephemeral_id=ephemeral_id,
            team_id=str(team_id),
            sponsor_agent_id=str(sponsor_agent_id),
            budget=budget,
        )
        existing = self._registrations.get(ephemeral_id)
        if existing is not None:
            if existing != row:
                raise ValueError('Foundry resource registration cannot be rebound')
            return
        self._registrations[ephemeral_id] = row

    def _get(self, ephemeral_id: str) -> _Registration:
        try:
            return self._registrations[str(ephemeral_id)]
        except KeyError as exc:
            raise KeyError(f'unknown Foundry resource registration: {ephemeral_id}') from exc

    def reserve_active(self, ephemeral_id: str) -> None:
        row = self._get(ephemeral_id)
        if row.active:
            return
        active = [value for value in self._registrations.values() if value.active]
        if len(active) >= self.ORGANIZATION_ACTIVE_LIMIT:
            raise PermissionError('Foundry organization active-worker budget exhausted')
        team_rows = [value for value in active if value.team_id == row.team_id]
        team_cap = min(self.TEAM_ACTIVE_LIMIT, row.budget.max_workers)
        if len(team_rows) >= team_cap:
            raise PermissionError('Foundry team active-worker budget exhausted')
        sponsor_teams = {value.team_id for value in active if value.sponsor_agent_id == row.sponsor_agent_id}
        if row.team_id not in sponsor_teams and len(sponsor_teams) >= self.SPONSOR_ACTIVE_TEAM_LIMIT:
            raise PermissionError('Foundry sponsor active-team budget exhausted')
        updated = _signed_registration(
            ephemeral_id=row.ephemeral_id,
            team_id=row.team_id,
            sponsor_agent_id=row.sponsor_agent_id,
            budget=row.budget,
            consumed=row.consumed_map(),
            active=True,
        )
        self._registrations[row.ephemeral_id] = updated

    def release_active(self, ephemeral_id: str) -> None:
        row = self._get(ephemeral_id)
        if not row.active:
            return
        self._registrations[row.ephemeral_id] = _signed_registration(
            ephemeral_id=row.ephemeral_id,
            team_id=row.team_id,
            sponsor_agent_id=row.sponsor_agent_id,
            budget=row.budget,
            consumed=row.consumed_map(),
            active=False,
        )

    def consume(
        self,
        ephemeral_id: str,
        resource_kind: FoundryResourceKind,
        units: int,
        *,
        actor_ephemeral_id: str,
    ) -> ResourceUsageReceipt:
        row = self._get(ephemeral_id)
        if not row.active:
            raise PermissionError('inactive Foundry worker cannot consume resources')
        if str(actor_ephemeral_id) != row.ephemeral_id:
            raise PermissionError('Foundry resource consumption is bound to the exact ephemeral identity')
        if isinstance(units, bool) or int(units) <= 0:
            raise ValueError('Foundry resource units must be a positive integer')
        kind = FoundryResourceKind(resource_kind)
        consumed = row.consumed_map()
        used = consumed.get(kind, 0)
        limit = row.budget.limit_for(kind)
        if used + int(units) > limit:
            raise PermissionError(f'Foundry {kind.value} budget exhausted')
        consumed[kind] = used + int(units)
        remaining = limit - consumed[kind]
        self._registrations[row.ephemeral_id] = _signed_registration(
            ephemeral_id=row.ephemeral_id,
            team_id=row.team_id,
            sponsor_agent_id=row.sponsor_agent_id,
            budget=row.budget,
            consumed=consumed,
            active=row.active,
        )
        self._counter += 1
        temp = ResourceUsageReceipt(
            receipt_id=f'foundry-usage-{self._counter:08d}',
            sequence=self._counter,
            ephemeral_id=row.ephemeral_id,
            resource_kind=kind,
            units=int(units),
            remaining=remaining,
            digest='',
        )
        receipt = replace(temp, digest=canonical_digest(temp.payload()))
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def remaining(self, ephemeral_id: str, resource_kind: FoundryResourceKind) -> int:
        row = self._get(ephemeral_id)
        kind = FoundryResourceKind(resource_kind)
        return row.budget.limit_for(kind) - row.consumed_map().get(kind, 0)

    def budget_for(self, ephemeral_id: str) -> FoundryBudget:
        return self._get(ephemeral_id).budget

    def active_ephemeral_ids(self) -> tuple[str, ...]:
        return tuple(sorted(row.ephemeral_id for row in self._registrations.values() if row.active))

    def receipts(self) -> tuple[ResourceUsageReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def to_state(self) -> dict[str, Any]:
        return {
            'registrations': {
                key: self._registrations[key].to_state()
                for key in sorted(self._registrations)
            },
            'receipts': [row.to_state() for row in self.receipts()],
            'counter': self._counter,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FoundryResourceGovernor':
        registrations = tuple(
            _Registration.from_state(value)
            for _, value in sorted(state.get('registrations', {}).items())
        )
        receipts = tuple(ResourceUsageReceipt.from_state(value) for value in state.get('receipts', ()))
        return cls(
            registrations=registrations,
            receipts=receipts,
            counter=int(state.get('counter', len(receipts))),
        )
