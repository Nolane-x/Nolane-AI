from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary
from .r269_causal_basis_adapter import PortableExperience

_ALLOWED_OPS = frozenset(('add', 'sub', 'mul', 'div', 'min', 'max'))
_ALLOWED_PHASES = frozenset(('diagnostic', 'challenge', 'terminal'))
_ALLOWED_PROVENANCE = frozenset(('transfer', 'scratch', 'shared'))


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f'{name} must be non-empty')
    return text


def _canonical_number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError('finite numeric value required')
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('finite numeric value required')
        if value.is_integer():
            return int(value)
    return value


def _context_values(signature: 'PublicTaskSignature', context: Mapping[str, object]) -> tuple[int | float, ...]:
    if set(map(str, context.keys())) != set(signature.role_names):
        raise ValueError('context keys must exactly match public role_names')
    values = tuple(_canonical_number(context[name]) for name in signature.role_names)
    if signature.numeric_domain == 'finite_integer':
        legal = frozenset(signature.finite_integer_values)
        if any(not isinstance(value, int) or value not in legal for value in values):
            raise ValueError('context is outside the declared finite integer query universe')
    return values


def _context_key(signature: 'PublicTaskSignature', context: Mapping[str, object]) -> str:
    values = _context_values(signature, context)
    return json.dumps(values, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def _binary_ops(expr: Expr) -> frozenset[str]:
    if isinstance(expr, (Field, Const)):
        return frozenset()
    if isinstance(expr, Unary):
        return _binary_ops(expr.arg)
    if isinstance(expr, Binary):
        return frozenset((expr.op,)) | _binary_ops(expr.left) | _binary_ops(expr.right)
    if isinstance(expr, IfElse):
        return _binary_ops(expr.condition) | _binary_ops(expr.when_true) | _binary_ops(expr.when_false)
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


@dataclass(frozen=True, slots=True)
class PublicTaskSignature:
    role_names: tuple[str, ...]
    numeric_domain: str
    allowed_binary_ops: tuple[str, ...]
    query_space_digest: str
    budget_contract: str
    finite_integer_values: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        roles = tuple(_nonempty(row, 'role name') for row in self.role_names)
        if not (1 <= len(roles) <= 8) or len(set(roles)) != len(roles):
            raise ValueError('role_names must contain 1..8 unique names')
        if any(name.startswith('__r') for name in roles):
            raise ValueError('target role_names must be surface roles, not portable role names')
        if self.numeric_domain not in ('finite_numeric', 'finite_integer'):
            raise ValueError('Phase A supports finite_numeric or finite_integer')
        raw_domain = tuple(self.finite_integer_values)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in raw_domain):
            raise ValueError('finite_integer_values must contain integers only')
        domain_values = tuple(sorted(set(raw_domain)))
        if self.numeric_domain == 'finite_integer' and len(domain_values) < 3:
            raise ValueError('finite_integer requires at least three declared legal values')
        if self.numeric_domain == 'finite_numeric' and domain_values:
            raise ValueError('finite_integer_values are only valid for finite_integer tasks')
        ops = tuple(map(str, self.allowed_binary_ops))
        if not ops or len(set(ops)) != len(ops) or any(op not in _ALLOWED_OPS for op in ops):
            raise ValueError('allowed_binary_ops must be a unique supported numeric op set')
        object.__setattr__(self, 'role_names', roles)
        object.__setattr__(self, 'finite_integer_values', domain_values)
        object.__setattr__(self, 'allowed_binary_ops', ops)
        object.__setattr__(self, 'query_space_digest', _nonempty(self.query_space_digest, 'query_space_digest'))
        object.__setattr__(self, 'budget_contract', _nonempty(self.budget_contract, 'budget_contract'))

    @property
    def structural_class_digest(self) -> str:
        payload = {
            'role_count': len(self.role_names),
            'numeric_domain': self.numeric_domain,
            'allowed_binary_ops': sorted(self.allowed_binary_ops),
            'query_space_digest': self.query_space_digest,
            'budget_contract': self.budget_contract,
            'finite_integer_values': list(self.finite_integer_values),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class MatchedPrior:
    portable: PortableExperience
    compatible: bool
    compatibility_score: int
    reason: str


def match_portable_experiences(
    priors: Sequence[PortableExperience],
    signature: PublicTaskSignature,
    *,
    quarantined_prior_digests: frozenset[str] = frozenset(),
) -> tuple[MatchedPrior, ...]:
    if not isinstance(signature, PublicTaskSignature):
        raise TypeError('signature must be PublicTaskSignature')
    out: list[MatchedPrior] = []
    allowed = frozenset(signature.allowed_binary_ops)
    for portable in priors:
        if not isinstance(portable, PortableExperience):
            raise TypeError('priors must contain PortableExperience')
        if portable.portable_digest in quarantined_prior_digests:
            out.append(MatchedPrior(portable, False, 0, 'prior_quarantined'))
            continue
        if portable.role_count != len(signature.role_names):
            out.append(MatchedPrior(portable, False, 0, 'role_cardinality_mismatch'))
            continue
        if portable.adapter_type == 'verified_meta_episode_v1':
            scope = frozenset(portable.claim_scope)
            domain_ok = f'numeric_domain={signature.numeric_domain}' in scope
            if signature.numeric_domain == 'finite_integer':
                exact_domain = 'finite_integer_values=' + ','.join(map(str, signature.finite_integer_values))
                domain_ok = domain_ok and exact_domain in scope
            if not domain_ok:
                out.append(MatchedPrior(portable, False, 0, 'verified_meta_domain_mismatch'))
                continue
        required = _binary_ops(portable.canonical_expression)
        if not required.issubset(allowed):
            out.append(MatchedPrior(portable, False, 0, 'operator_vocabulary_mismatch'))
            continue
        score = 100 + 5 * len(required)
        out.append(MatchedPrior(portable, True, score, 'public_structure_compatible'))
    return tuple(
        sorted(out, key=lambda row: (not row.compatible, -row.compatibility_score, row.portable.portable_digest))
    )


class _TrackedContext(dict[str, int | float]):
    __slots__ = ('mutation_attempted',)

    def __init__(self, values: Mapping[str, int | float]) -> None:
        super().__init__(values)
        self.mutation_attempted = False

    def __setitem__(self, key, value):
        self.mutation_attempted = True
        return super().__setitem__(key, value)

    def __delitem__(self, key):
        self.mutation_attempted = True
        return super().__delitem__(key)

    def clear(self):
        self.mutation_attempted = True
        return super().clear()

    def pop(self, key, *default):
        self.mutation_attempted = True
        return super().pop(key, *default)

    def popitem(self):
        self.mutation_attempted = True
        return super().popitem()

    def setdefault(self, key, default=0):
        self.mutation_attempted = True
        return super().setdefault(key, default)

    def update(self, *args, **kwargs):
        self.mutation_attempted = True
        return super().update(*args, **kwargs)

    def __ior__(self, other):
        self.mutation_attempted = True
        return super().__ior__(other)


@dataclass(frozen=True, slots=True)
class SharedObservation:
    context_key: str
    context_values: tuple[int | float, ...]
    phase: str
    provenance: str
    transfer_info_score: int
    scratch_info_score: int
    oracle_call_index: int
    status: str
    observed: int | float | None
    observation_digest: str


class SharedObservationLedger:
    def __init__(self, signature: PublicTaskSignature) -> None:
        if not isinstance(signature, PublicTaskSignature):
            raise TypeError('signature must be PublicTaskSignature')
        self.signature = signature
        self._rows: list[SharedObservation] = []
        self._by_key: dict[str, SharedObservation] = {}
        self.physical_oracle_calls = 0

    @property
    def observations(self) -> tuple[SharedObservation, ...]:
        return tuple(self._rows)

    def observe(
        self,
        context: Mapping[str, object],
        oracle: Callable[[Mapping[str, object]], object],
        *,
        phase: str,
        provenance: str,
        transfer_info_score: int,
        scratch_info_score: int,
    ) -> tuple[SharedObservation, bool]:
        if not callable(oracle):
            raise TypeError('oracle must be callable')
        phase = str(phase)
        provenance = str(provenance)
        if phase not in _ALLOWED_PHASES:
            raise ValueError('unsupported evidence phase')
        if provenance not in _ALLOWED_PROVENANCE:
            raise ValueError('unsupported evidence provenance')
        transfer_info_score = int(transfer_info_score)
        scratch_info_score = int(scratch_info_score)
        if transfer_info_score < 0 or scratch_info_score < 0:
            raise ValueError('information scores must be non-negative')
        values = _context_values(self.signature, context)
        key = json.dumps(values, separators=(',', ':'), allow_nan=False)
        existing = self._by_key.get(key)
        if existing is not None:
            if phase == 'terminal' or existing.phase == 'terminal':
                raise ValueError('terminal evidence must be semantically disjoint from earlier oracle queries')
            return existing, True

        semantic_context = dict(zip(self.signature.role_names, values, strict=True))
        tracked = _TrackedContext(semantic_context)
        before = json.dumps(dict(tracked), sort_keys=True, separators=(',', ':'), allow_nan=False)
        self.physical_oracle_calls += 1
        call_index = self.physical_oracle_calls
        status = 'ok'
        observed: int | float | None
        try:
            raw = oracle(tracked)
        except Exception:
            raw = None
            status = 'oracle_error'
        after = json.dumps(dict(tracked), sort_keys=True, separators=(',', ':'), allow_nan=False)
        if tracked.mutation_attempted or after != before:
            status = 'oracle_context_mutation'
            observed = None
        elif status == 'oracle_error':
            observed = None
        else:
            try:
                observed = _canonical_number(raw)
                if self.signature.numeric_domain == 'finite_integer' and not isinstance(observed, int):
                    status = 'invalid_oracle_output'
                    observed = None
            except (TypeError, ValueError):
                status = 'invalid_oracle_output'
                observed = None

        payload = {
            'context_key': key,
            'phase': phase,
            'oracle_call_index': call_index,
            'status': status,
            'observed': observed,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest()
        row = SharedObservation(
            context_key=key,
            context_values=values,
            phase=phase,
            provenance=provenance,
            transfer_info_score=transfer_info_score,
            scratch_info_score=scratch_info_score,
            oracle_call_index=call_index,
            status=status,
            observed=observed,
            observation_digest=digest,
        )
        self._rows.append(row)
        self._by_key[key] = row
        return row, False


from .r269_transfer_runtime import (
    MetaLearningConfig,
    MetaLearningReceipt,
    PriorRegistry,
    PriorState,
    run_cold_scratch,
    run_meta_learning_episode,
)
from .r269_meta_governance import (
    CapabilityGapLedger,
    CapabilityGapRecord,
    MetaCreditLedger,
    MetaCreditRecord,
    adjudicate_prior_credit,
    record_capability_gap,
)

__all__ = [
    'PublicTaskSignature',
    'MatchedPrior',
    'match_portable_experiences',
    'SharedObservation',
    'SharedObservationLedger',
    'MetaLearningConfig',
    'PriorState',
    'PriorRegistry',
    'MetaLearningReceipt',
    'run_meta_learning_episode',
    'run_cold_scratch',
    'MetaCreditRecord',
    'MetaCreditLedger',
    'CapabilityGapRecord',
    'CapabilityGapLedger',
    'adjudicate_prior_credit',
    'record_capability_gap',
]
