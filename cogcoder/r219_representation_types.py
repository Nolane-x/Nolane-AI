from __future__ import annotations

import hashlib
from dataclasses import dataclass


def _norm_id(value: str, *, field: str) -> str:
    out = str(value).strip().lower()
    if not out:
        raise ValueError(f'{field} must be non-empty')
    return out


def _binary_tuple(values: tuple[int, ...], *, field: str) -> tuple[int, ...]:
    out = tuple(int(v) for v in tuple(values))
    if not out:
        raise ValueError(f'{field} must be non-empty')
    if any(v not in (0, 1) for v in out):
        raise ValueError(f'{field} must contain only 0/1')
    return out


@dataclass(frozen=True)
class RawTransition:
    query_id: str
    before: tuple[int, ...]
    after: tuple[int, ...]

    def __post_init__(self) -> None:
        qid = _norm_id(self.query_id, field='query_id')
        before = _binary_tuple(self.before, field='before')
        after = _binary_tuple(self.after, field='after')
        if len(before) != len(after):
            raise ValueError('before and after widths must match')
        object.__setattr__(self, 'query_id', qid)
        object.__setattr__(self, 'before', before)
        object.__setattr__(self, 'after', after)

    @property
    def width(self) -> int:
        return len(self.before)


@dataclass(frozen=True)
class RepresentationHypothesis:
    width: int
    permutation: tuple[int, ...]
    complement: tuple[int, ...]
    reverse_direction: bool = False

    def __post_init__(self) -> None:
        width = int(self.width)
        if width <= 0:
            raise ValueError('width must be positive')
        permutation = tuple(int(v) for v in tuple(self.permutation))
        complement = tuple(int(v) for v in tuple(self.complement))
        if len(permutation) != width or sorted(permutation) != list(range(width)):
            raise ValueError('permutation must be a width-sized bijection')
        if len(complement) != width or any(v not in (0, 1) for v in complement):
            raise ValueError('complement must be a width-sized binary tuple')
        object.__setattr__(self, 'width', width)
        object.__setattr__(self, 'permutation', permutation)
        object.__setattr__(self, 'complement', complement)
        object.__setattr__(self, 'reverse_direction', bool(self.reverse_direction))

    @property
    def representation_id(self) -> str:
        payload = '|'.join(
            (
                f'w={self.width}',
                'p=' + ','.join(map(str, self.permutation)),
                'c=' + ','.join(map(str, self.complement)),
                f'r={int(self.reverse_direction)}',
            )
        )
        return 'repr:' + hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class VerifierObservation:
    query_id: str
    observed_label: bool
    reliability: float

    def __post_init__(self) -> None:
        reliability = float(self.reliability)
        if not 0.5 < reliability <= 1.0:
            raise ValueError('reliability must be in (0.5, 1.0]')
        object.__setattr__(self, 'query_id', _norm_id(self.query_id, field='query_id'))
        object.__setattr__(self, 'observed_label', bool(self.observed_label))
        object.__setattr__(self, 'reliability', reliability)


@dataclass(frozen=True)
class HypothesisSupport:
    representation_id: str
    log_likelihood: float
    posterior: float

    def __post_init__(self) -> None:
        posterior = float(self.posterior)
        if not 0.0 <= posterior <= 1.0:
            raise ValueError('posterior must be in [0, 1]')
        object.__setattr__(self, 'representation_id', _norm_id(self.representation_id, field='representation_id'))
        object.__setattr__(self, 'log_likelihood', float(self.log_likelihood))
        object.__setattr__(self, 'posterior', posterior)


@dataclass(frozen=True)
class DiscoveryDecision:
    status: str
    representation_id: str | None
    posterior: float
    margin: float
    queries: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        status = str(self.status).strip().lower()
        if status not in {'accept', 'ambiguous', 'abstain'}:
            raise ValueError('invalid discovery status')
        representation_id = None if self.representation_id is None else _norm_id(self.representation_id, field='representation_id')
        posterior = float(self.posterior)
        margin = float(self.margin)
        if not 0.0 <= posterior <= 1.0:
            raise ValueError('posterior must be in [0, 1]')
        if not 0.0 <= margin <= 1.0:
            raise ValueError('margin must be in [0, 1]')
        if status == 'accept' and representation_id is None:
            raise ValueError('accepted decision requires representation_id')
        queries = tuple(_norm_id(q, field='query_id') for q in tuple(self.queries))
        object.__setattr__(self, 'status', status)
        object.__setattr__(self, 'representation_id', representation_id)
        object.__setattr__(self, 'posterior', posterior)
        object.__setattr__(self, 'margin', margin)
        object.__setattr__(self, 'queries', queries)
        object.__setattr__(self, 'reason', str(self.reason).strip())


@dataclass(frozen=True)
class LibraryAction:
    action: str
    representation_id: str | None
    skill_id: str | None
    reason: str

    def __post_init__(self) -> None:
        action = str(self.action).strip().lower()
        if action not in {'reuse', 'split', 'create', 'abstain'}:
            raise ValueError('invalid library action')
        object.__setattr__(self, 'action', action)
        object.__setattr__(self, 'representation_id', None if self.representation_id is None else _norm_id(self.representation_id, field='representation_id'))
        object.__setattr__(self, 'skill_id', None if self.skill_id is None else _norm_id(self.skill_id, field='skill_id'))
        object.__setattr__(self, 'reason', str(self.reason).strip())
