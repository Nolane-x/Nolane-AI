from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_HEX64 = re.compile(r'^[0-9a-f]{64}$')
_DOMAIN_STATES = frozenset({'candidate', 'active', 'quarantined'})
_RECORD_STATES = frozenset({'active', 'retired'})


def _norm_text(value: str, *, field: str) -> str:
    out = str(value).strip().lower()
    if not out:
        raise ValueError(f'{field} must be non-empty')
    return out


def _norm_tuple(values: tuple[str, ...], *, field: str, allow_empty: bool = True) -> tuple[str, ...]:
    out = tuple(sorted({_norm_text(value, field=field) for value in tuple(values)}))
    if not allow_empty and not out:
        raise ValueError(f'{field} must be non-empty')
    return out


@dataclass(frozen=True)
class DomainDescriptor:
    domain_id: str
    mechanism_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, 'domain_id', _norm_text(self.domain_id, field='domain_id'))
        object.__setattr__(
            self,
            'mechanism_tags',
            _norm_tuple(self.mechanism_tags, field='mechanism_tags', allow_empty=False),
        )


@dataclass(frozen=True)
class TransferSkill:
    kind: str
    mechanism_tags: tuple[str, ...]
    behavior_digest: str
    payload_refs: tuple[str, ...]
    provenance_lineages: tuple[str, ...]
    source_domains: tuple[str, ...]
    capacity_cost: int = 1

    def __post_init__(self) -> None:
        kind = _norm_text(self.kind, field='kind')
        tags = _norm_tuple(self.mechanism_tags, field='mechanism_tags', allow_empty=False)
        digest = str(self.behavior_digest).strip()
        if not _HEX64.fullmatch(digest):
            raise ValueError('behavior_digest must be a 64-character lowercase hex sha256')
        if int(self.capacity_cost) <= 0:
            raise ValueError('capacity_cost must be positive')
        object.__setattr__(self, 'kind', kind)
        object.__setattr__(self, 'mechanism_tags', tags)
        object.__setattr__(self, 'behavior_digest', digest)
        object.__setattr__(self, 'payload_refs', _norm_tuple(self.payload_refs, field='payload_refs'))
        object.__setattr__(
            self, 'provenance_lineages', _norm_tuple(self.provenance_lineages, field='provenance_lineages')
        )
        object.__setattr__(
            self, 'source_domains', _norm_tuple(self.source_domains, field='source_domains', allow_empty=False)
        )
        object.__setattr__(self, 'capacity_cost', int(self.capacity_cost))

    @property
    def skill_id(self) -> str:
        identity = '|'.join((self.kind, ','.join(self.mechanism_tags), self.behavior_digest))
        return 'skill:' + hashlib.sha256(identity.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class DomainEvidence:
    domain_id: str
    state: str
    task_ids: tuple[str, ...] = ()
    successes: int = 0
    failures: int = 0
    false_accepts: int = 0
    baseline_cost_total: int = 0
    assisted_cost_total: int = 0
    reason: str = ''

    def __post_init__(self) -> None:
        domain_id = _norm_text(self.domain_id, field='domain_id')
        state = str(self.state).strip().lower()
        if state not in _DOMAIN_STATES:
            raise ValueError('invalid domain evidence state')
        counts = (self.successes, self.failures, self.false_accepts, self.baseline_cost_total, self.assisted_cost_total)
        if any(int(value) < 0 for value in counts):
            raise ValueError('domain evidence counts and costs must be non-negative')
        object.__setattr__(self, 'domain_id', domain_id)
        object.__setattr__(self, 'state', state)
        object.__setattr__(self, 'task_ids', _norm_tuple(self.task_ids, field='task_ids'))
        object.__setattr__(self, 'successes', int(self.successes))
        object.__setattr__(self, 'failures', int(self.failures))
        object.__setattr__(self, 'false_accepts', int(self.false_accepts))
        object.__setattr__(self, 'baseline_cost_total', int(self.baseline_cost_total))
        object.__setattr__(self, 'assisted_cost_total', int(self.assisted_cost_total))
        object.__setattr__(self, 'reason', str(self.reason).strip())

    @property
    def cost_reduction(self) -> float:
        if self.baseline_cost_total <= 0:
            return 0.0
        return 1.0 - self.assisted_cost_total / self.baseline_cost_total


@dataclass(frozen=True)
class GovernedSkillRecord:
    skill: TransferSkill
    state: str
    domain_evidence: tuple[DomainEvidence, ...] = ()
    reason: str = ''

    def __post_init__(self) -> None:
        state = str(self.state).strip().lower()
        if state not in _RECORD_STATES:
            raise ValueError('invalid governed skill record state')
        by_domain: dict[str, DomainEvidence] = {}
        for row in tuple(self.domain_evidence):
            if row.domain_id in by_domain and by_domain[row.domain_id] != row:
                raise ValueError('conflicting duplicate domain evidence')
            by_domain[row.domain_id] = row
        object.__setattr__(self, 'state', state)
        object.__setattr__(self, 'domain_evidence', tuple(by_domain[key] for key in sorted(by_domain)))
        object.__setattr__(self, 'reason', str(self.reason).strip())

    def evidence_for(self, domain_id: str) -> DomainEvidence | None:
        target = _norm_text(domain_id, field='domain_id')
        return next((row for row in self.domain_evidence if row.domain_id == target), None)


@dataclass(frozen=True)
class OpenEndedLibraryVersion:
    version: int
    records: tuple[GovernedSkillRecord, ...]
    parent_version: int | None = None
    rollback_of: int | None = None
    reason: str = ''

    def __post_init__(self) -> None:
        if int(self.version) < 0:
            raise ValueError('version must be non-negative')
        by_id: dict[str, GovernedSkillRecord] = {}
        for record in tuple(self.records):
            sid = record.skill.skill_id
            if sid in by_id and by_id[sid] != record:
                raise ValueError('conflicting duplicate skill record')
            by_id[sid] = record
        object.__setattr__(self, 'version', int(self.version))
        object.__setattr__(self, 'records', tuple(by_id[key] for key in sorted(by_id)))
        object.__setattr__(self, 'reason', str(self.reason).strip())

    @property
    def capacity_used(self) -> int:
        return sum(record.skill.capacity_cost for record in self.records if record.state != 'retired')


@dataclass(frozen=True)
class TransferObservation:
    task_id: str
    domain_id: str
    skill_id: str
    baseline_correct: bool
    assisted_correct: bool
    baseline_cost: int
    assisted_cost: int
    false_accept: bool = False
    budget_exhausted: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, 'task_id', _norm_text(self.task_id, field='task_id'))
        object.__setattr__(self, 'domain_id', _norm_text(self.domain_id, field='domain_id'))
        object.__setattr__(self, 'skill_id', _norm_text(self.skill_id, field='skill_id'))
        if int(self.baseline_cost) < 0 or int(self.assisted_cost) < 0:
            raise ValueError('observation costs must be non-negative')
        object.__setattr__(self, 'baseline_cost', int(self.baseline_cost))
        object.__setattr__(self, 'assisted_cost', int(self.assisted_cost))


@dataclass(frozen=True)
class RouteDecision:
    skill_id: str
    mode: str
    overlap: float
    reason: str
    capacity_cost: int

    def __post_init__(self) -> None:
        mode = str(self.mode).strip().lower()
        if mode not in {'active', 'trial'}:
            raise ValueError('route mode must be active or trial')
        if not 0.0 <= float(self.overlap) <= 1.0:
            raise ValueError('overlap must be in [0, 1]')
        if int(self.capacity_cost) <= 0:
            raise ValueError('capacity_cost must be positive')
        object.__setattr__(self, 'skill_id', _norm_text(self.skill_id, field='skill_id'))
        object.__setattr__(self, 'mode', mode)
        object.__setattr__(self, 'overlap', float(self.overlap))
        object.__setattr__(self, 'reason', str(self.reason).strip())
        object.__setattr__(self, 'capacity_cost', int(self.capacity_cost))
