from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .types import canonical_digest


class BenchmarkDomain(str, Enum):
    CODING = 'coding'
    DEBUGGING = 'debugging'
    PLANNING = 'planning'
    UI_UX = 'ui_ux'
    SECURITY = 'security'
    RESEARCH = 'research'
    CROSS_DOMAIN = 'cross_domain'
    LONG_HORIZON = 'long_horizon'


class EvidenceProvenanceClass(str, Enum):
    INTERNAL_SYNTHETIC = 'internal_synthetic'
    INTERNAL_REAL_REPOSITORY = 'internal_real_repository'
    EXTERNAL_REPRODUCED = 'external_reproduced'
    EXTERNAL_INDEPENDENT = 'external_independent'


class EvaluationMode(str, Enum):
    SINGLE_AGENT = 'single_agent'
    FLAT_SWARM = 'flat_swarm'
    ORGANIZATION = 'organization'
    ORGANIZATION_NO_MEMORY = 'organization_no_memory'
    ORGANIZATION_NO_TOOLS = 'organization_no_tools'
    ORGANIZATION_NO_SPECIALIZATION = 'organization_no_specialization'
    ORGANIZATION_NO_COORDINATION = 'organization_no_coordination'


@dataclass(frozen=True, slots=True)
class BenchmarkRegime:
    regime_id: str
    benchmark_id: str
    domain: BenchmarkDomain
    task_set_digest: str
    repository_revision_digest: str
    tool_envelope_digest: str
    compute_budget_units: int
    tool_call_budget: int
    external_core_budget: int
    wall_clock_budget_ms: int
    active_agent_budget: int
    freshness_epoch: int
    evaluator_protocol_version: str
    provenance_class: EvidenceProvenanceClass
    fresh: bool
    heldout: bool
    budget_digest: str
    regime_digest: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.regime_id, 'regime_id'), (self.benchmark_id, 'benchmark_id'),
            (self.task_set_digest, 'task_set_digest'),
            (self.repository_revision_digest, 'repository_revision_digest'),
            (self.tool_envelope_digest, 'tool_envelope_digest'),
            (self.evaluator_protocol_version, 'evaluator_protocol_version'),
        ):
            if not str(value).strip():
                raise ValueError(f'{label} must be explicit')
        for value, label in (
            (self.compute_budget_units, 'compute budget'), (self.tool_call_budget, 'tool-call budget'),
            (self.external_core_budget, 'external-core budget'), (self.wall_clock_budget_ms, 'wall-clock budget'),
            (self.active_agent_budget, 'active-agent budget'),
        ):
            if int(value) <= 0:
                raise ValueError(f'{label} must be positive')
        if self.freshness_epoch < 0:
            raise ValueError('freshness epoch must be non-negative')
        if canonical_digest(self.budget_payload()) != self.budget_digest:
            raise ValueError('benchmark budget digest mismatch')
        if canonical_digest(self.regime_payload()) != self.regime_digest:
            raise ValueError('benchmark regime digest mismatch')

    def budget_payload(self) -> dict[str, Any]:
        return {
            'compute_budget_units': self.compute_budget_units,
            'tool_call_budget': self.tool_call_budget,
            'external_core_budget': self.external_core_budget,
            'wall_clock_budget_ms': self.wall_clock_budget_ms,
            'active_agent_budget': self.active_agent_budget,
        }

    def regime_payload(self) -> dict[str, Any]:
        return {
            'regime_id': self.regime_id,
            'benchmark_id': self.benchmark_id,
            'domain': self.domain.value,
            'task_set_digest': self.task_set_digest,
            'repository_revision_digest': self.repository_revision_digest,
            'tool_envelope_digest': self.tool_envelope_digest,
            'budget_digest': self.budget_digest,
            'freshness_epoch': self.freshness_epoch,
            'evaluator_protocol_version': self.evaluator_protocol_version,
            'provenance_class': self.provenance_class.value,
            'fresh': self.fresh,
            'heldout': self.heldout,
        }

    def registration_kwargs(self) -> dict[str, Any]:
        return {
            'regime_id': self.regime_id,
            'benchmark_id': self.benchmark_id,
            'domain': self.domain,
            'task_set_digest': self.task_set_digest,
            'repository_revision_digest': self.repository_revision_digest,
            'tool_envelope_digest': self.tool_envelope_digest,
            'compute_budget_units': self.compute_budget_units,
            'tool_call_budget': self.tool_call_budget,
            'external_core_budget': self.external_core_budget,
            'wall_clock_budget_ms': self.wall_clock_budget_ms,
            'active_agent_budget': self.active_agent_budget,
            'freshness_epoch': self.freshness_epoch,
            'evaluator_protocol_version': self.evaluator_protocol_version,
            'provenance_class': self.provenance_class,
            'fresh': self.fresh,
            'heldout': self.heldout,
        }

    def to_state(self) -> dict[str, Any]:
        return {
            **self.registration_kwargs(),
            'domain': self.domain.value,
            'provenance_class': self.provenance_class.value,
            'budget_digest': self.budget_digest,
            'regime_digest': self.regime_digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'BenchmarkRegime':
        return cls(
            regime_id=str(state['regime_id']), benchmark_id=str(state['benchmark_id']),
            domain=BenchmarkDomain(str(state['domain'])), task_set_digest=str(state['task_set_digest']),
            repository_revision_digest=str(state['repository_revision_digest']),
            tool_envelope_digest=str(state['tool_envelope_digest']),
            compute_budget_units=int(state['compute_budget_units']), tool_call_budget=int(state['tool_call_budget']),
            external_core_budget=int(state['external_core_budget']), wall_clock_budget_ms=int(state['wall_clock_budget_ms']),
            active_agent_budget=int(state['active_agent_budget']), freshness_epoch=int(state['freshness_epoch']),
            evaluator_protocol_version=str(state['evaluator_protocol_version']),
            provenance_class=EvidenceProvenanceClass(str(state['provenance_class'])),
            fresh=bool(state['fresh']), heldout=bool(state['heldout']),
            budget_digest=str(state['budget_digest']), regime_digest=str(state['regime_digest']),
        )


class BenchmarkRegimeRegistry:
    def __init__(self, regimes: tuple[BenchmarkRegime, ...] = ()) -> None:
        self._regimes: dict[str, BenchmarkRegime] = {}
        for row in regimes:
            if row.regime_id in self._regimes:
                raise ValueError('duplicate benchmark regime id')
            self._regimes[row.regime_id] = row

    def register(self, **kwargs: Any) -> BenchmarkRegime:
        domain = BenchmarkDomain(kwargs['domain'])
        provenance = EvidenceProvenanceClass(kwargs['provenance_class'])
        budget_payload = {
            'compute_budget_units': int(kwargs['compute_budget_units']),
            'tool_call_budget': int(kwargs['tool_call_budget']),
            'external_core_budget': int(kwargs['external_core_budget']),
            'wall_clock_budget_ms': int(kwargs['wall_clock_budget_ms']),
            'active_agent_budget': int(kwargs['active_agent_budget']),
        }
        budget_digest = canonical_digest(budget_payload)
        regime_payload = {
            'regime_id': str(kwargs['regime_id']),
            'benchmark_id': str(kwargs['benchmark_id']),
            'domain': domain.value,
            'task_set_digest': str(kwargs['task_set_digest']),
            'repository_revision_digest': str(kwargs['repository_revision_digest']),
            'tool_envelope_digest': str(kwargs['tool_envelope_digest']),
            'budget_digest': budget_digest,
            'freshness_epoch': int(kwargs['freshness_epoch']),
            'evaluator_protocol_version': str(kwargs['evaluator_protocol_version']),
            'provenance_class': provenance.value,
            'fresh': bool(kwargs['fresh']),
            'heldout': bool(kwargs['heldout']),
        }
        row = BenchmarkRegime(
            regime_id=regime_payload['regime_id'], benchmark_id=regime_payload['benchmark_id'],
            domain=domain, task_set_digest=regime_payload['task_set_digest'],
            repository_revision_digest=regime_payload['repository_revision_digest'],
            tool_envelope_digest=regime_payload['tool_envelope_digest'],
            compute_budget_units=budget_payload['compute_budget_units'], tool_call_budget=budget_payload['tool_call_budget'],
            external_core_budget=budget_payload['external_core_budget'], wall_clock_budget_ms=budget_payload['wall_clock_budget_ms'],
            active_agent_budget=budget_payload['active_agent_budget'], freshness_epoch=regime_payload['freshness_epoch'],
            evaluator_protocol_version=regime_payload['evaluator_protocol_version'], provenance_class=provenance,
            fresh=regime_payload['fresh'], heldout=regime_payload['heldout'], budget_digest=budget_digest,
            regime_digest=canonical_digest(regime_payload),
        )
        existing = self._regimes.get(row.regime_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('benchmark regime id cannot be rebound')
        self._regimes[row.regime_id] = row
        return row

    def get(self, regime_id: str) -> BenchmarkRegime:
        try:
            return self._regimes[str(regime_id)]
        except KeyError as exc:
            raise KeyError(f'unknown benchmark regime: {regime_id}') from exc

    def regimes(self) -> tuple[BenchmarkRegime, ...]:
        return tuple(self._regimes[key] for key in sorted(self._regimes))

    def to_state(self) -> dict[str, Any]:
        return {'regimes': [row.to_state() for row in self.regimes()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'BenchmarkRegimeRegistry':
        rows = tuple(BenchmarkRegime.from_state(raw) for raw in state.get('regimes', ()))
        return cls(rows)
