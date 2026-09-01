from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


class ClaimMode(str, Enum):
    EXCLUSIVE_WRITE = 'exclusive_write'
    SHARED_READ = 'shared_read'


class ClaimStatus(str, Enum):
    ACTIVE = 'active'
    RELEASED = 'released'
    SUPERSEDED = 'superseded'
    ABORTED = 'aborted'


def _text(value: Any, *, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f'{field} must be explicit')
    return text


def _normalize_path(value: str) -> str:
    text = str(value).replace('\\', '/').strip()
    if not text:
        raise ValueError('claim path must be non-empty')
    normalized = str(PurePosixPath(text))
    while normalized.startswith('./'):
        normalized = normalized[2:]
    if normalized.startswith('/') or normalized == '..' or normalized.startswith('../'):
        raise ValueError('claim path must be repository-relative')
    return normalized


def _normalize_symbol(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError('claim symbol must be non-empty')
    return text


@dataclass(frozen=True, slots=True)
class CodeClaim:
    claim_id: str
    agent_id: str
    task_id: str
    file_paths: tuple[str, ...] = ()
    symbol_ids: tuple[str, ...] = ()
    directory_prefixes: tuple[str, ...] = ()
    mode: ClaimMode = ClaimMode.EXCLUSIVE_WRITE
    status: ClaimStatus = ClaimStatus.ACTIVE

    def to_state(self) -> dict[str, Any]:
        return {
            'claim_id': self.claim_id,
            'agent_id': self.agent_id,
            'task_id': self.task_id,
            'file_paths': list(self.file_paths),
            'symbol_ids': list(self.symbol_ids),
            'directory_prefixes': list(self.directory_prefixes),
            'mode': self.mode.value,
            'status': self.status.value,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodeClaim':
        return cls(
            claim_id=_text(state['claim_id'], field='claim id'),
            agent_id=_text(state['agent_id'], field='claim agent'),
            task_id=_text(state['task_id'], field='claim task'),
            file_paths=tuple(_normalize_path(x) for x in state.get('file_paths', ())),
            symbol_ids=tuple(_normalize_symbol(x) for x in state.get('symbol_ids', ())),
            directory_prefixes=tuple(
                _normalize_path(x).rstrip('/') for x in state.get('directory_prefixes', ())
            ),
            mode=ClaimMode(str(state.get('mode', ClaimMode.EXCLUSIVE_WRITE.value))),
            status=ClaimStatus(str(state.get('status', ClaimStatus.ACTIVE.value))),
        )


def _claim_intent_payload(
    *,
    agent_id: str,
    task_id: str,
    file_paths: tuple[str, ...],
    symbol_ids: tuple[str, ...],
    directory_prefixes: tuple[str, ...],
    mode: ClaimMode,
    source_revision: str,
) -> dict[str, Any]:
    return {
        'agent_id': agent_id,
        'task_id': task_id,
        'file_paths': list(file_paths),
        'symbol_ids': list(symbol_ids),
        'directory_prefixes': list(directory_prefixes),
        'mode': mode.value,
        'source_revision': source_revision,
    }


def _claim_intent_digest(claim: CodeClaim, *, source_revision: str) -> str:
    return canonical_digest(
        _claim_intent_payload(
            agent_id=claim.agent_id,
            task_id=claim.task_id,
            file_paths=claim.file_paths,
            symbol_ids=claim.symbol_ids,
            directory_prefixes=claim.directory_prefixes,
            mode=claim.mode,
            source_revision=source_revision,
        )
    )


@dataclass(frozen=True, slots=True)
class CodeClaimLease:
    lease_id: str
    claim_id: str
    operation_ref: str
    source_revision: str
    epoch: int
    intent_digest: str
    authority: str
    digest: str

    def __post_init__(self) -> None:
        _text(self.lease_id, field='claim lease id')
        _text(self.claim_id, field='claim lease claim id')
        _text(self.operation_ref, field='claim operation_ref')
        _text(self.source_revision, field='claim source revision')
        _text(self.intent_digest, field='claim intent digest')
        _text(self.digest, field='claim lease digest')
        if int(self.epoch) <= 0:
            raise ValueError('claim lease epoch must be positive')
        if self.authority != 'coordination_only':
            raise ValueError('claim lease cannot hold mutation authority')

    def payload(self) -> dict[str, Any]:
        return {
            'claim_id': self.claim_id,
            'operation_ref': self.operation_ref,
            'source_revision': self.source_revision,
            'epoch': int(self.epoch),
            'intent_digest': self.intent_digest,
            'authority': self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {'lease_id': self.lease_id, **self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodeClaimLease':
        row = cls(
            lease_id=_text(state['lease_id'], field='claim lease id'),
            claim_id=_text(state['claim_id'], field='claim lease claim id'),
            operation_ref=_text(state['operation_ref'], field='claim operation_ref'),
            source_revision=_text(state['source_revision'], field='claim source revision'),
            epoch=int(state['epoch']),
            intent_digest=_text(state['intent_digest'], field='claim intent digest'),
            authority=_text(state['authority'], field='claim lease authority'),
            digest=_text(state['digest'], field='claim lease digest'),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.lease_id != f'claim-lease-{expected[:20]}':
            raise ValueError('claim lease digest/id mismatch')
        return row


@dataclass(frozen=True, slots=True)
class CodeClaimHandoffReceipt:
    receipt_id: str
    operation_ref: str
    intent_digest: str
    old_claim_id: str
    old_lease_id: str
    old_lease_digest: str
    old_source_revision: str
    old_epoch: int
    new_claim_id: str
    new_lease_id: str
    new_lease_digest: str
    new_source_revision: str
    new_epoch: int
    actor_agent_id: str
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.receipt_id, 'claim handoff receipt id'),
            (self.operation_ref, 'claim handoff operation_ref'),
            (self.intent_digest, 'claim handoff intent digest'),
            (self.old_claim_id, 'old claim id'),
            (self.old_lease_id, 'old claim lease id'),
            (self.old_lease_digest, 'old claim lease digest'),
            (self.old_source_revision, 'old claim source revision'),
            (self.new_claim_id, 'new claim id'),
            (self.new_lease_id, 'new claim lease id'),
            (self.new_lease_digest, 'new claim lease digest'),
            (self.new_source_revision, 'new claim source revision'),
            (self.actor_agent_id, 'claim handoff actor'),
            (self.digest, 'claim handoff digest'),
        ):
            _text(value, field=field)
        if int(self.old_epoch) <= 0 or int(self.new_epoch) <= 0:
            raise ValueError('claim handoff epochs must be positive')
        if int(self.new_epoch) <= int(self.old_epoch):
            raise ValueError('claim handoff epoch must advance monotonically')
        if self.authority != 'coordination_only':
            raise ValueError('claim handoff receipt cannot hold mutation authority')

    def payload(self) -> dict[str, Any]:
        return {
            'operation_ref': self.operation_ref,
            'intent_digest': self.intent_digest,
            'old_claim_id': self.old_claim_id,
            'old_lease_id': self.old_lease_id,
            'old_lease_digest': self.old_lease_digest,
            'old_source_revision': self.old_source_revision,
            'old_epoch': int(self.old_epoch),
            'new_claim_id': self.new_claim_id,
            'new_lease_id': self.new_lease_id,
            'new_lease_digest': self.new_lease_digest,
            'new_source_revision': self.new_source_revision,
            'new_epoch': int(self.new_epoch),
            'actor_agent_id': self.actor_agent_id,
            'authority': self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {'receipt_id': self.receipt_id, **self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodeClaimHandoffReceipt':
        row = cls(
            receipt_id=_text(state['receipt_id'], field='claim handoff receipt id'),
            operation_ref=_text(state['operation_ref'], field='claim handoff operation_ref'),
            intent_digest=_text(state['intent_digest'], field='claim handoff intent digest'),
            old_claim_id=_text(state['old_claim_id'], field='old claim id'),
            old_lease_id=_text(state['old_lease_id'], field='old claim lease id'),
            old_lease_digest=_text(state['old_lease_digest'], field='old claim lease digest'),
            old_source_revision=_text(
                state['old_source_revision'], field='old claim source revision'
            ),
            old_epoch=int(state['old_epoch']),
            new_claim_id=_text(state['new_claim_id'], field='new claim id'),
            new_lease_id=_text(state['new_lease_id'], field='new claim lease id'),
            new_lease_digest=_text(state['new_lease_digest'], field='new claim lease digest'),
            new_source_revision=_text(
                state['new_source_revision'], field='new claim source revision'
            ),
            new_epoch=int(state['new_epoch']),
            actor_agent_id=_text(state['actor_agent_id'], field='claim handoff actor'),
            authority=_text(state['authority'], field='claim handoff authority'),
            digest=_text(state['digest'], field='claim handoff digest'),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f'claim-handoff-{expected[:20]}':
            raise ValueError('claim handoff receipt digest/id mismatch')
        return row


class CodeClaimLedger:
    def __init__(self) -> None:
        self._claims: dict[str, CodeClaim] = {}
        self._counter = 0
        self._epoch_counter = 0
        self._leases: dict[str, CodeClaimLease] = {}
        self._handoffs: dict[str, CodeClaimHandoffReceipt] = {}
        self._operations: dict[str, tuple[str, str, str]] = {}

    def claims(self) -> tuple[CodeClaim, ...]:
        return tuple(self._claims[key] for key in sorted(self._claims))

    def active_claims(self) -> tuple[CodeClaim, ...]:
        return tuple(row for row in self.claims() if row.status is ClaimStatus.ACTIVE)

    def leases(self) -> tuple[CodeClaimLease, ...]:
        return tuple(sorted(self._leases.values(), key=lambda row: (row.epoch, row.lease_id)))

    def handoffs(self) -> tuple[CodeClaimHandoffReceipt, ...]:
        return tuple(
            sorted(self._handoffs.values(), key=lambda row: (row.new_epoch, row.receipt_id))
        )

    def get(self, claim_id: str) -> CodeClaim:
        try:
            return self._claims[str(claim_id)]
        except KeyError as exc:
            raise KeyError(f'unknown code claim: {claim_id}') from exc

    def lease(self, claim_id: str) -> CodeClaimLease:
        try:
            return self._leases[str(claim_id)]
        except KeyError as exc:
            raise KeyError(f'code claim has no bound lease: {claim_id}') from exc

    def get_handoff(self, receipt_id: str) -> CodeClaimHandoffReceipt:
        try:
            return self._handoffs[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f'unknown code claim handoff receipt: {receipt_id}') from exc

    @staticmethod
    def _path_under(path: str, prefix: str) -> bool:
        prefix = prefix.rstrip('/')
        return path == prefix or path.startswith(prefix + '/')

    @classmethod
    def _overlap(cls, left: CodeClaim, right: CodeClaim) -> bool:
        if set(left.symbol_ids) & set(right.symbol_ids):
            return True
        if set(left.file_paths) & set(right.file_paths):
            return True
        for path in left.file_paths:
            if any(cls._path_under(path, prefix) for prefix in right.directory_prefixes):
                return True
        for path in right.file_paths:
            if any(cls._path_under(path, prefix) for prefix in left.directory_prefixes):
                return True
        for a in left.directory_prefixes:
            for b in right.directory_prefixes:
                if cls._path_under(a, b) or cls._path_under(b, a):
                    return True
        return False

    @staticmethod
    def _same_owner_context(left: CodeClaim, right: CodeClaim) -> bool:
        return left.agent_id == right.agent_id and left.task_id == right.task_id

    def _validate_candidate_conflicts(
        self,
        candidate: CodeClaim,
        *,
        ignore_claim_id: str | None = None,
    ) -> None:
        if candidate.mode is not ClaimMode.EXCLUSIVE_WRITE:
            return
        for active in self.active_claims():
            if ignore_claim_id is not None and active.claim_id == ignore_claim_id:
                continue
            if self._same_owner_context(active, candidate):
                continue
            if active.mode is ClaimMode.EXCLUSIVE_WRITE and self._overlap(active, candidate):
                raise PermissionError(f'exclusive code scope conflicts with {active.claim_id}')

    @staticmethod
    def _claim_request_intent(
        *,
        agent_id: str,
        task_id: str,
        file_paths: tuple[str, ...],
        symbol_ids: tuple[str, ...],
        directory_prefixes: tuple[str, ...],
        mode: ClaimMode,
        source_revision: str,
    ) -> str:
        return canonical_digest(
            _claim_intent_payload(
                agent_id=agent_id,
                task_id=task_id,
                file_paths=file_paths,
                symbol_ids=symbol_ids,
                directory_prefixes=directory_prefixes,
                mode=mode,
                source_revision=source_revision,
            )
        )

    @staticmethod
    def _handoff_request_intent(
        *,
        old_claim_id: str,
        actor_agent_id: str,
        new_agent_id: str,
        new_task_id: str,
        new_source_revision: str,
        expected_epoch: int,
    ) -> str:
        return canonical_digest(
            {
                'old_claim_id': old_claim_id,
                'actor_agent_id': actor_agent_id,
                'new_agent_id': new_agent_id,
                'new_task_id': new_task_id,
                'new_source_revision': new_source_revision,
                'expected_epoch': int(expected_epoch),
            }
        )

    @staticmethod
    def _make_lease(
        *,
        claim: CodeClaim,
        operation_ref: str,
        source_revision: str,
        epoch: int,
        intent_digest: str,
    ) -> CodeClaimLease:
        payload = {
            'claim_id': claim.claim_id,
            'operation_ref': operation_ref,
            'source_revision': source_revision,
            'epoch': int(epoch),
            'intent_digest': intent_digest,
            'authority': 'coordination_only',
        }
        digest = canonical_digest(payload)
        return CodeClaimLease(
            lease_id=f'claim-lease-{digest[:20]}',
            claim_id=claim.claim_id,
            operation_ref=operation_ref,
            source_revision=source_revision,
            epoch=int(epoch),
            intent_digest=intent_digest,
            authority='coordination_only',
            digest=digest,
        )

    def _existing_operation(
        self,
        *,
        operation_ref: str,
        kind: str,
        intent_digest: str,
    ) -> str | None:
        existing = self._operations.get(operation_ref)
        if existing is None:
            return None
        existing_kind, target_id, existing_intent = existing
        if existing_kind == kind and existing_intent == intent_digest:
            return target_id
        raise ValueError('operation_ref is already bound to a different claim operation')

    def claim(
        self,
        *,
        agent_id: str,
        task_id: str,
        file_paths: tuple[str, ...] = (),
        symbol_ids: tuple[str, ...] = (),
        directory_prefixes: tuple[str, ...] = (),
        mode: ClaimMode = ClaimMode.EXCLUSIVE_WRITE,
        source_revision: str | None = None,
        operation_ref: str | None = None,
    ) -> CodeClaim:
        agent = _text(agent_id, field='claim agent')
        task = _text(task_id, field='claim task')
        files = tuple(sorted(set(_normalize_path(x) for x in file_paths)))
        symbols = tuple(sorted(set(_normalize_symbol(x) for x in symbol_ids)))
        prefixes = tuple(
            sorted(set(_normalize_path(x).rstrip('/') for x in directory_prefixes))
        )
        if not files and not symbols and not prefixes:
            raise ValueError('code claim requires at least one source scope')
        claim_mode = ClaimMode(mode)

        if (source_revision is None) != (operation_ref is None):
            raise ValueError('bound code claim requires both source_revision and operation_ref')

        bound_revision: str | None = None
        bound_operation: str | None = None
        request_intent: str | None = None
        if source_revision is not None and operation_ref is not None:
            bound_revision = _text(source_revision, field='claim source revision')
            bound_operation = _text(operation_ref, field='claim operation_ref')
            request_intent = self._claim_request_intent(
                agent_id=agent,
                task_id=task,
                file_paths=files,
                symbol_ids=symbols,
                directory_prefixes=prefixes,
                mode=claim_mode,
                source_revision=bound_revision,
            )
            existing_claim_id = self._existing_operation(
                operation_ref=bound_operation,
                kind='claim',
                intent_digest=request_intent,
            )
            if existing_claim_id is not None:
                return self.get(existing_claim_id)

        candidate = CodeClaim(
            claim_id=f'claim-{self._counter + 1:08d}',
            agent_id=agent,
            task_id=task,
            file_paths=files,
            symbol_ids=symbols,
            directory_prefixes=prefixes,
            mode=claim_mode,
        )
        self._validate_candidate_conflicts(candidate)

        lease: CodeClaimLease | None = None
        if bound_revision is not None and bound_operation is not None and request_intent is not None:
            lease = self._make_lease(
                claim=candidate,
                operation_ref=bound_operation,
                source_revision=bound_revision,
                epoch=self._epoch_counter + 1,
                intent_digest=request_intent,
            )

        self._counter += 1
        self._claims[candidate.claim_id] = candidate
        if lease is not None:
            self._epoch_counter = lease.epoch
            self._leases[candidate.claim_id] = lease
            self._operations[lease.operation_ref] = ('claim', candidate.claim_id, lease.intent_digest)
        return candidate

    def handoff(
        self,
        claim_id: str,
        *,
        actor_agent_id: str,
        new_agent_id: str,
        new_task_id: str,
        new_source_revision: str,
        operation_ref: str,
        expected_epoch: int,
    ) -> CodeClaimHandoffReceipt:
        old = self.get(claim_id)
        actor = _text(actor_agent_id, field='claim handoff actor')
        new_agent = _text(new_agent_id, field='new claim agent')
        new_task = _text(new_task_id, field='new claim task')
        new_revision = _text(new_source_revision, field='new claim source revision')
        op_ref = _text(operation_ref, field='claim handoff operation_ref')
        epoch = int(expected_epoch)
        if epoch <= 0:
            raise ValueError('expected claim epoch must be positive')

        request_intent = self._handoff_request_intent(
            old_claim_id=old.claim_id,
            actor_agent_id=actor,
            new_agent_id=new_agent,
            new_task_id=new_task,
            new_source_revision=new_revision,
            expected_epoch=epoch,
        )
        existing_receipt_id = self._existing_operation(
            operation_ref=op_ref,
            kind='handoff',
            intent_digest=request_intent,
        )
        if existing_receipt_id is not None:
            return self.get_handoff(existing_receipt_id)

        if old.status is not ClaimStatus.ACTIVE:
            raise ValueError('only active code claims may be handed off')
        if actor not in {old.agent_id, 'coding.chief', 'nolane.central'}:
            raise PermissionError('claim handoff requires owner, Coding Chief or Nolane Central')
        old_lease = self.lease(old.claim_id)
        if old_lease.epoch != epoch:
            raise ValueError('stale claim epoch cannot authorize handoff')

        candidate = CodeClaim(
            claim_id=f'claim-{self._counter + 1:08d}',
            agent_id=new_agent,
            task_id=new_task,
            file_paths=old.file_paths,
            symbol_ids=old.symbol_ids,
            directory_prefixes=old.directory_prefixes,
            mode=old.mode,
        )
        self._validate_candidate_conflicts(candidate, ignore_claim_id=old.claim_id)

        new_intent = self._claim_request_intent(
            agent_id=candidate.agent_id,
            task_id=candidate.task_id,
            file_paths=candidate.file_paths,
            symbol_ids=candidate.symbol_ids,
            directory_prefixes=candidate.directory_prefixes,
            mode=candidate.mode,
            source_revision=new_revision,
        )
        internal_claim_operation_ref = op_ref + ':claim'
        if internal_claim_operation_ref in self._operations:
            raise ValueError('operation_ref derived for handoff claim is already bound')
        new_lease = self._make_lease(
            claim=candidate,
            operation_ref=internal_claim_operation_ref,
            source_revision=new_revision,
            epoch=self._epoch_counter + 1,
            intent_digest=new_intent,
        )

        receipt_payload = {
            'operation_ref': op_ref,
            'intent_digest': request_intent,
            'old_claim_id': old.claim_id,
            'old_lease_id': old_lease.lease_id,
            'old_lease_digest': old_lease.digest,
            'old_source_revision': old_lease.source_revision,
            'old_epoch': old_lease.epoch,
            'new_claim_id': candidate.claim_id,
            'new_lease_id': new_lease.lease_id,
            'new_lease_digest': new_lease.digest,
            'new_source_revision': new_lease.source_revision,
            'new_epoch': new_lease.epoch,
            'actor_agent_id': actor,
            'authority': 'coordination_only',
        }
        receipt_digest = canonical_digest(receipt_payload)
        receipt = CodeClaimHandoffReceipt(
            receipt_id=f'claim-handoff-{receipt_digest[:20]}',
            operation_ref=op_ref,
            intent_digest=request_intent,
            old_claim_id=old.claim_id,
            old_lease_id=old_lease.lease_id,
            old_lease_digest=old_lease.digest,
            old_source_revision=old_lease.source_revision,
            old_epoch=old_lease.epoch,
            new_claim_id=candidate.claim_id,
            new_lease_id=new_lease.lease_id,
            new_lease_digest=new_lease.digest,
            new_source_revision=new_lease.source_revision,
            new_epoch=new_lease.epoch,
            actor_agent_id=actor,
            authority='coordination_only',
            digest=receipt_digest,
        )

        self._claims[old.claim_id] = replace(old, status=ClaimStatus.SUPERSEDED)
        self._counter += 1
        self._claims[candidate.claim_id] = candidate
        self._epoch_counter = new_lease.epoch
        self._leases[candidate.claim_id] = new_lease
        self._handoffs[receipt.receipt_id] = receipt
        self._operations[op_ref] = ('handoff', receipt.receipt_id, request_intent)
        self._operations[new_lease.operation_ref] = ('claim', candidate.claim_id, new_lease.intent_digest)
        return receipt

    def release(self, claim_id: str, *, actor_agent_id: str) -> CodeClaim:
        old = self.get(claim_id)
        actor = str(actor_agent_id)
        if old.status is not ClaimStatus.ACTIVE:
            raise ValueError('only active code claims may be released')
        if actor not in {old.agent_id, 'coding.chief', 'nolane.central'}:
            raise PermissionError('claim release requires owner, Coding Chief or Nolane Central')
        row = replace(old, status=ClaimStatus.RELEASED)
        self._claims[row.claim_id] = row
        return row

    def abort(self, claim_id: str, *, actor_agent_id: str) -> CodeClaim:
        old = self.get(claim_id)
        actor = str(actor_agent_id)
        if old.status is not ClaimStatus.ACTIVE:
            raise ValueError('only active code claims may be aborted')
        if actor not in {old.agent_id, 'coding.chief', 'nolane.central'}:
            raise PermissionError('claim abort requires owner, Coding Chief or Nolane Central')
        row = replace(old, status=ClaimStatus.ABORTED)
        self._claims[row.claim_id] = row
        return row

    def covers(
        self,
        *,
        agent_id: str,
        task_id: str,
        file_paths: tuple[str, ...],
        symbol_ids: tuple[str, ...],
    ) -> bool:
        files = tuple(_normalize_path(x) for x in file_paths)
        symbols = tuple(_normalize_symbol(x) for x in symbol_ids)
        active = [
            row for row in self.active_claims()
            if row.agent_id == str(agent_id) and row.task_id == str(task_id)
        ]
        for path in files:
            if not any(
                path in row.file_paths
                or any(self._path_under(path, prefix) for prefix in row.directory_prefixes)
                for row in active
            ):
                return False
        for symbol in symbols:
            if not any(symbol in row.symbol_ids for row in active):
                return False
        return True

    def covers_current(
        self,
        *,
        agent_id: str,
        task_id: str,
        file_paths: tuple[str, ...],
        symbol_ids: tuple[str, ...],
        current_source_revision: str,
        min_claim_epoch: int,
    ) -> bool:
        files = tuple(_normalize_path(x) for x in file_paths)
        symbols = tuple(_normalize_symbol(x) for x in symbol_ids)
        revision = _text(current_source_revision, field='current source revision')
        minimum = int(min_claim_epoch)
        if minimum <= 0:
            raise ValueError('minimum claim epoch must be positive')

        active: list[CodeClaim] = []
        for row in self.active_claims():
            if row.agent_id != str(agent_id) or row.task_id != str(task_id):
                continue
            lease = self._leases.get(row.claim_id)
            if lease is None or lease.source_revision != revision or lease.epoch < minimum:
                continue
            active.append(row)

        for path in files:
            if not any(
                path in row.file_paths
                or any(self._path_under(path, prefix) for prefix in row.directory_prefixes)
                for row in active
            ):
                return False
        for symbol in symbols:
            if not any(symbol in row.symbol_ids for row in active):
                return False
        return True

    def to_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            'counter': self._counter,
            'claims': [row.to_state() for row in self.claims()],
        }
        if self._epoch_counter or self._leases or self._handoffs:
            state.update(
                {
                    'epoch_counter': self._epoch_counter,
                    'leases': [row.to_state() for row in self.leases()],
                    'handoffs': [row.to_state() for row in self.handoffs()],
                }
            )
        return state

    @classmethod
    def _validate_active_conflicts(cls, ledger: 'CodeClaimLedger') -> None:
        active = list(ledger.active_claims())
        for index, left in enumerate(active):
            if left.mode is not ClaimMode.EXCLUSIVE_WRITE:
                continue
            for right in active[index + 1:]:
                if right.mode is not ClaimMode.EXCLUSIVE_WRITE:
                    continue
                if cls._same_owner_context(left, right):
                    continue
                if cls._overlap(left, right):
                    raise ValueError('snapshot contains conflicting active exclusive code claims')

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodeClaimLedger':
        ledger = cls()

        raw_leases = list(state.get('leases', ()))
        raw_handoffs = list(state.get('handoffs', ()))
        seen_operation_refs: set[str] = set()
        for value in [*raw_leases, *raw_handoffs]:
            operation_ref = _text(value['operation_ref'], field='claim operation_ref')
            if operation_ref in seen_operation_refs:
                raise ValueError('operation_ref cannot be rebound in claim snapshot')
            seen_operation_refs.add(operation_ref)

        for value in state.get('claims', ()):
            row = CodeClaim.from_state(value)
            if row.claim_id in ledger._claims:
                raise ValueError('duplicate code claim id in snapshot')
            ledger._claims[row.claim_id] = row

        ledger._counter = int(state.get('counter', len(ledger._claims)))
        expected_max = 0
        for claim_id in ledger._claims:
            try:
                expected_max = max(expected_max, int(claim_id.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical code claim id') from exc
        if ledger._counter < expected_max:
            raise ValueError('code claim counter is behind claim history')

        cls._validate_active_conflicts(ledger)

        seen_epochs: set[int] = set()
        for value in raw_leases:
            lease = CodeClaimLease.from_state(value)
            claim = ledger._claims.get(lease.claim_id)
            if claim is None:
                raise ValueError('claim lease references unknown claim')
            if lease.claim_id in ledger._leases:
                raise ValueError('claim snapshot contains duplicate lease for claim')
            if lease.epoch in seen_epochs:
                raise ValueError('claim lease epoch cannot be reused')
            if lease.intent_digest != _claim_intent_digest(claim, source_revision=lease.source_revision):
                raise ValueError('claim lease intent lineage mismatch')
            seen_epochs.add(lease.epoch)
            ledger._leases[lease.claim_id] = lease
            ledger._operations[lease.operation_ref] = ('claim', lease.claim_id, lease.intent_digest)

        max_epoch = max(seen_epochs, default=0)
        ledger._epoch_counter = int(state.get('epoch_counter', max_epoch))
        if ledger._epoch_counter != max_epoch:
            raise ValueError('claim epoch counter does not match lease history')

        seen_handoff_ids: set[str] = set()
        incoming_claim_ids: set[str] = set()
        for value in raw_handoffs:
            receipt = CodeClaimHandoffReceipt.from_state(value)
            if receipt.receipt_id in seen_handoff_ids:
                raise ValueError('duplicate claim handoff receipt id')
            old = ledger._claims.get(receipt.old_claim_id)
            new = ledger._claims.get(receipt.new_claim_id)
            if old is None or new is None:
                raise ValueError('claim handoff references unknown claim')
            if receipt.new_claim_id in incoming_claim_ids:
                raise ValueError('claim cannot have multiple handoff origins')
            old_lease = ledger._leases.get(old.claim_id)
            new_lease = ledger._leases.get(new.claim_id)
            if old_lease is None or new_lease is None:
                raise ValueError('claim handoff requires bound old and new leases')
            if (
                receipt.old_lease_id != old_lease.lease_id
                or receipt.old_lease_digest != old_lease.digest
                or receipt.old_source_revision != old_lease.source_revision
                or receipt.old_epoch != old_lease.epoch
            ):
                raise ValueError('claim handoff old lease lineage mismatch')
            if (
                receipt.new_lease_id != new_lease.lease_id
                or receipt.new_lease_digest != new_lease.digest
                or receipt.new_source_revision != new_lease.source_revision
                or receipt.new_epoch != new_lease.epoch
            ):
                raise ValueError('claim handoff new lease lineage mismatch')
            if old.status is not ClaimStatus.SUPERSEDED:
                raise ValueError('claim handoff old claim must remain superseded')
            if (
                old.file_paths != new.file_paths
                or old.symbol_ids != new.symbol_ids
                or old.directory_prefixes != new.directory_prefixes
                or old.mode is not new.mode
            ):
                raise ValueError('claim handoff scope lineage mismatch')
            if receipt.actor_agent_id not in {old.agent_id, 'coding.chief', 'nolane.central'}:
                raise ValueError('claim handoff actor lineage mismatch')
            expected_intent = cls._handoff_request_intent(
                old_claim_id=old.claim_id,
                actor_agent_id=receipt.actor_agent_id,
                new_agent_id=new.agent_id,
                new_task_id=new.task_id,
                new_source_revision=receipt.new_source_revision,
                expected_epoch=receipt.old_epoch,
            )
            if receipt.intent_digest != expected_intent:
                raise ValueError('claim handoff intent lineage mismatch')
            if receipt.operation_ref in ledger._operations:
                raise ValueError('operation_ref cannot be rebound in claim snapshot')

            seen_handoff_ids.add(receipt.receipt_id)
            incoming_claim_ids.add(receipt.new_claim_id)
            ledger._handoffs[receipt.receipt_id] = receipt
            ledger._operations[receipt.operation_ref] = ('handoff', receipt.receipt_id, receipt.intent_digest)

        return ledger


COMPONENT_ID = 'external.coding.claims'
COMPONENT_VERSION = '0.0.2'
MIGRATED_FROM = 'cogcoder.organization.code_claims'

__all__ = [
    'COMPONENT_ID',
    'COMPONENT_VERSION',
    'MIGRATED_FROM',
    'ClaimMode',
    'ClaimStatus',
    'CodeClaim',
    'CodeClaimLease',
    'CodeClaimHandoffReceipt',
    'CodeClaimLedger',
]
