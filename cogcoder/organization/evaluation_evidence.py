from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .evaluation_regimes import (
    BenchmarkRegimeRegistry,
    EvidenceProvenanceClass,
    EvaluationMode,
)
from .registry import AgentRegistry
from .types import EvidenceRecord, canonical_digest


@dataclass(frozen=True, slots=True)
class EvaluationObservation:
    observation_id: str
    regime_id: str
    regime_digest: str
    mode: EvaluationMode
    producer_revision: str
    score: float
    task_count: int
    pass_count: int
    false_accepts: int
    regressions: int
    compute_units: int
    tool_calls: int
    external_core_calls: int
    wall_clock_ms: int
    energy_joules: float | None
    active_agents: int
    evidence_artifact_ids: tuple[str, ...]
    evidence: EvidenceRecord
    external_evaluator_id: str | None
    provenance_class: EvidenceProvenanceClass
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'observation_id': self.observation_id, 'regime_id': self.regime_id,
            'regime_digest': self.regime_digest, 'mode': self.mode.value,
            'producer_revision': self.producer_revision, 'score': self.score,
            'task_count': self.task_count, 'pass_count': self.pass_count,
            'false_accepts': self.false_accepts, 'regressions': self.regressions,
            'compute_units': self.compute_units, 'tool_calls': self.tool_calls,
            'external_core_calls': self.external_core_calls, 'wall_clock_ms': self.wall_clock_ms,
            'energy_joules': self.energy_joules, 'active_agents': self.active_agents,
            'evidence_artifact_ids': list(self.evidence_artifact_ids),
            'evidence': self.evidence.to_state(), 'external_evaluator_id': self.external_evaluator_id,
            'provenance_class': self.provenance_class.value,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'EvaluationObservation':
        row = cls(
            observation_id=str(state['observation_id']), regime_id=str(state['regime_id']),
            regime_digest=str(state['regime_digest']), mode=EvaluationMode(str(state['mode'])),
            producer_revision=str(state['producer_revision']), score=float(state['score']),
            task_count=int(state['task_count']), pass_count=int(state['pass_count']),
            false_accepts=int(state['false_accepts']), regressions=int(state['regressions']),
            compute_units=int(state['compute_units']), tool_calls=int(state['tool_calls']),
            external_core_calls=int(state['external_core_calls']), wall_clock_ms=int(state['wall_clock_ms']),
            energy_joules=None if state.get('energy_joules') is None else float(state['energy_joules']),
            active_agents=int(state['active_agents']),
            evidence_artifact_ids=tuple(str(x) for x in state.get('evidence_artifact_ids', ())),
            evidence=EvidenceRecord.from_state(state['evidence']),
            external_evaluator_id=None if state.get('external_evaluator_id') is None else str(state['external_evaluator_id']),
            provenance_class=EvidenceProvenanceClass(str(state['provenance_class'])), digest=str(state['digest']),
        )
        row._validate()
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('evaluation observation digest mismatch')
        return row

    def _validate(self) -> None:
        if not all(str(x).strip() for x in (self.observation_id, self.regime_id, self.regime_digest, self.producer_revision)):
            raise ValueError('evaluation observation identity/regime/revision must be explicit')
        if not 0.0 <= self.score <= 1.0:
            raise ValueError('evaluation score must lie in [0,1]')
        if self.task_count <= 0 or self.pass_count < 0 or self.pass_count > self.task_count:
            raise ValueError('invalid task/pass counts')
        for value in (self.false_accepts, self.regressions, self.compute_units, self.tool_calls, self.external_core_calls, self.wall_clock_ms):
            if value < 0:
                raise ValueError('evaluation counters/resources must be non-negative')
        if self.active_agents <= 0:
            raise ValueError('evaluation observation requires a positive active-agent count')
        if self.energy_joules is not None and self.energy_joules < 0:
            raise ValueError('energy estimate must be non-negative')
        if not self.evidence_artifact_ids:
            raise ValueError('evaluation observation requires evidence artifacts')


@dataclass(frozen=True, slots=True)
class MatchedBudgetComparison:
    comparison_id: str
    organization_observation_id: str
    baseline_observation_id: str
    baseline_mode: EvaluationMode
    comparable: bool
    improved: bool
    score_delta: float
    reason: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'comparison_id': self.comparison_id,
            'organization_observation_id': self.organization_observation_id,
            'baseline_observation_id': self.baseline_observation_id,
            'baseline_mode': self.baseline_mode.value,
            'comparable': self.comparable, 'improved': self.improved,
            'score_delta': self.score_delta, 'reason': self.reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MatchedBudgetComparison':
        row = cls(
            comparison_id=str(state['comparison_id']),
            organization_observation_id=str(state['organization_observation_id']),
            baseline_observation_id=str(state['baseline_observation_id']),
            baseline_mode=EvaluationMode(str(state['baseline_mode'])), comparable=bool(state['comparable']),
            improved=bool(state['improved']), score_delta=float(state['score_delta']),
            reason=str(state['reason']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('matched-budget comparison digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class OrganizationSuperiorityAssessment:
    organization_observation_id: str
    comparison_ids: tuple[str, ...]
    supported: bool
    reason: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'organization_observation_id': self.organization_observation_id,
            'comparison_ids': list(self.comparison_ids), 'supported': self.supported, 'reason': self.reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}


@dataclass(frozen=True, slots=True)
class AblationAssessment:
    assessment_id: str
    full_observation_id: str
    ablation_observation_id: str
    ablation_mode: EvaluationMode
    comparable: bool
    score_delta: float
    false_accept_delta: int
    regression_delta: int
    compute_delta: int
    reason: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'assessment_id': self.assessment_id, 'full_observation_id': self.full_observation_id,
            'ablation_observation_id': self.ablation_observation_id, 'ablation_mode': self.ablation_mode.value,
            'comparable': self.comparable, 'score_delta': self.score_delta,
            'false_accept_delta': self.false_accept_delta, 'regression_delta': self.regression_delta,
            'compute_delta': self.compute_delta, 'reason': self.reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AblationAssessment':
        row = cls(
            assessment_id=str(state['assessment_id']), full_observation_id=str(state['full_observation_id']),
            ablation_observation_id=str(state['ablation_observation_id']),
            ablation_mode=EvaluationMode(str(state['ablation_mode'])), comparable=bool(state['comparable']),
            score_delta=float(state['score_delta']), false_accept_delta=int(state['false_accept_delta']),
            regression_delta=int(state['regression_delta']), compute_delta=int(state['compute_delta']),
            reason=str(state['reason']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('ablation assessment digest mismatch')
        return row


class EvaluationEvidenceLedger:
    _ABLATIONS = {
        EvaluationMode.ORGANIZATION_NO_MEMORY,
        EvaluationMode.ORGANIZATION_NO_TOOLS,
        EvaluationMode.ORGANIZATION_NO_SPECIALIZATION,
        EvaluationMode.ORGANIZATION_NO_COORDINATION,
    }

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        regimes: BenchmarkRegimeRegistry,
        observations: tuple[EvaluationObservation, ...] = (),
        comparisons: tuple[MatchedBudgetComparison, ...] = (),
        ablations: tuple[AblationAssessment, ...] = (),
    ) -> None:
        self.registry = registry
        self.regimes = regimes
        self._observations: dict[str, EvaluationObservation] = {}
        self._comparisons: dict[str, MatchedBudgetComparison] = {}
        self._ablations: dict[str, AblationAssessment] = {}
        for row in observations:
            self._validate_observation(row)
            if row.observation_id in self._observations:
                raise ValueError('duplicate evaluation observation id')
            self._observations[row.observation_id] = row
        for row in comparisons:
            self.get_observation(row.organization_observation_id)
            self.get_observation(row.baseline_observation_id)
            if canonical_digest(row.payload()) != row.digest:
                raise ValueError('matched-budget comparison digest mismatch')
            if row.comparison_id in self._comparisons:
                raise ValueError('duplicate matched-budget comparison id')
            self._comparisons[row.comparison_id] = row
        for row in ablations:
            self.get_observation(row.full_observation_id)
            self.get_observation(row.ablation_observation_id)
            if row.assessment_id in self._ablations:
                raise ValueError('duplicate ablation assessment id')
            self._ablations[row.assessment_id] = row

    @staticmethod
    def _clean(evidence: EvidenceRecord) -> bool:
        return evidence.passed and evidence.false_accepts == 0 and evidence.regressions == 0

    def _validate_observation(self, row: EvaluationObservation) -> None:
        row._validate()
        regime = self.regimes.get(row.regime_id)
        if row.regime_digest != regime.regime_digest or row.provenance_class is not regime.provenance_class:
            raise ValueError('evaluation observation regime provenance mismatch')
        self.registry.get(row.evidence.verifier_agent_id)
        if regime.provenance_class in (EvidenceProvenanceClass.EXTERNAL_REPRODUCED, EvidenceProvenanceClass.EXTERNAL_INDEPENDENT):
            if not self._clean(row.evidence):
                raise PermissionError('external evaluation observation requires clean permanent verification evidence')
        if regime.provenance_class is EvidenceProvenanceClass.EXTERNAL_INDEPENDENT:
            if not row.external_evaluator_id or row.external_evaluator_id in {x.agent_id for x in self.registry.identities()}:
                raise PermissionError('external-independent observation requires evaluator outside organization identities')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('evaluation observation digest mismatch')

    def record_observation(self, **kwargs: Any) -> EvaluationObservation:
        regime = self.regimes.get(str(kwargs['regime_id']))
        row0 = EvaluationObservation(
            observation_id=str(kwargs['observation_id']), regime_id=regime.regime_id, regime_digest=regime.regime_digest,
            mode=EvaluationMode(kwargs['mode']), producer_revision=str(kwargs['producer_revision']), score=float(kwargs['score']),
            task_count=int(kwargs['task_count']), pass_count=int(kwargs['pass_count']), false_accepts=int(kwargs['false_accepts']),
            regressions=int(kwargs['regressions']), compute_units=int(kwargs['compute_units']), tool_calls=int(kwargs['tool_calls']),
            external_core_calls=int(kwargs['external_core_calls']), wall_clock_ms=int(kwargs['wall_clock_ms']),
            energy_joules=None if kwargs.get('energy_joules') is None else float(kwargs['energy_joules']),
            active_agents=int(kwargs['active_agents']), evidence_artifact_ids=tuple(str(x) for x in kwargs['evidence_artifact_ids']),
            evidence=kwargs['evidence'], external_evaluator_id=None if kwargs.get('external_evaluator_id') is None else str(kwargs['external_evaluator_id']),
            provenance_class=regime.provenance_class, digest='',
        )
        row = EvaluationObservation(**{**row0.__dict__, 'digest': canonical_digest(row0.payload())}) if hasattr(row0, '__dict__') else EvaluationObservation(
            observation_id=row0.observation_id, regime_id=row0.regime_id, regime_digest=row0.regime_digest,
            mode=row0.mode, producer_revision=row0.producer_revision, score=row0.score, task_count=row0.task_count,
            pass_count=row0.pass_count, false_accepts=row0.false_accepts, regressions=row0.regressions,
            compute_units=row0.compute_units, tool_calls=row0.tool_calls, external_core_calls=row0.external_core_calls,
            wall_clock_ms=row0.wall_clock_ms, energy_joules=row0.energy_joules, active_agents=row0.active_agents,
            evidence_artifact_ids=row0.evidence_artifact_ids, evidence=row0.evidence,
            external_evaluator_id=row0.external_evaluator_id, provenance_class=row0.provenance_class,
            digest=canonical_digest(row0.payload()),
        )
        self._validate_observation(row)
        existing = self._observations.get(row.observation_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('evaluation observation id cannot be rebound')
        self._observations[row.observation_id] = row
        return row

    def get_observation(self, observation_id: str) -> EvaluationObservation:
        try:
            return self._observations[str(observation_id)]
        except KeyError as exc:
            raise KeyError(f'unknown evaluation observation: {observation_id}') from exc

    def get_comparison(self, comparison_id: str) -> MatchedBudgetComparison:
        try:
            return self._comparisons[str(comparison_id)]
        except KeyError as exc:
            raise KeyError(f'unknown matched-budget comparison: {comparison_id}') from exc

    def _within_budget(self, row: EvaluationObservation) -> bool:
        regime = self.regimes.get(row.regime_id)
        return (
            row.compute_units <= regime.compute_budget_units and row.tool_calls <= regime.tool_call_budget
            and row.external_core_calls <= regime.external_core_budget and row.wall_clock_ms <= regime.wall_clock_budget_ms
            and row.active_agents <= regime.active_agent_budget
        )

    def compare_matched_budget(self, organization_observation_id: str, baseline_observation_id: str) -> MatchedBudgetComparison:
        org = self.get_observation(organization_observation_id)
        baseline = self.get_observation(baseline_observation_id)
        if org.mode is not EvaluationMode.ORGANIZATION:
            raise ValueError('matched-budget comparison subject must be organization mode')
        if baseline.mode not in (EvaluationMode.SINGLE_AGENT, EvaluationMode.FLAT_SWARM):
            raise ValueError('matched-budget baseline must be single-agent or flat-swarm')
        delta = org.score - baseline.score
        comparable = True
        improved = False
        if org.regime_id != baseline.regime_id or org.regime_digest != baseline.regime_digest:
            comparable = False; reason = 'regime_mismatch'
        elif not self._within_budget(org) or not self._within_budget(baseline):
            reason = 'budget_exceeded'
        elif org.false_accepts > baseline.false_accepts:
            reason = 'false_accepts_worsened'
        elif org.regressions > baseline.regressions:
            reason = 'regressions_worsened'
        elif delta <= 0:
            reason = 'no_score_improvement'
        else:
            improved = True; reason = 'clean_matched_budget_improvement'
        payload0 = {
            'organization_observation_id': org.observation_id, 'baseline_observation_id': baseline.observation_id,
            'baseline_mode': baseline.mode.value, 'comparable': comparable, 'improved': improved,
            'score_delta': delta, 'reason': reason,
        }
        comparison_id = 'eval-compare-' + canonical_digest(payload0)[:24]
        payload = {'comparison_id': comparison_id, **payload0}
        row = MatchedBudgetComparison(
            comparison_id=comparison_id, organization_observation_id=org.observation_id,
            baseline_observation_id=baseline.observation_id, baseline_mode=baseline.mode,
            comparable=comparable, improved=improved, score_delta=delta, reason=reason,
            digest=canonical_digest(payload),
        )
        self._comparisons.setdefault(row.comparison_id, row)
        return self._comparisons[row.comparison_id]

    def organization_superiority(self, organization_observation_id: str, comparison_ids: tuple[str, ...]) -> OrganizationSuperiorityAssessment:
        seen: set[EvaluationMode] = set()
        valid_ids: list[str] = []
        for comparison_id in comparison_ids:
            row = self.get_comparison(comparison_id)
            if row.organization_observation_id != str(organization_observation_id):
                raise ValueError('superiority comparison targets a different organization observation')
            valid_ids.append(row.comparison_id)
            if row.comparable and row.improved:
                seen.add(row.baseline_mode)
        required = {EvaluationMode.SINGLE_AGENT, EvaluationMode.FLAT_SWARM}
        supported = required.issubset(seen)
        reason = 'single_and_flat_baselines_beaten' if supported else 'missing_clean_single_or_flat_baseline_win'
        payload = {
            'organization_observation_id': str(organization_observation_id), 'comparison_ids': sorted(valid_ids),
            'supported': supported, 'reason': reason,
        }
        return OrganizationSuperiorityAssessment(
            organization_observation_id=str(organization_observation_id), comparison_ids=tuple(sorted(valid_ids)),
            supported=supported, reason=reason, digest=canonical_digest(payload),
        )

    def assess_ablation(self, full_observation_id: str, ablation_observation_id: str) -> AblationAssessment:
        full = self.get_observation(full_observation_id)
        ablated = self.get_observation(ablation_observation_id)
        if full.mode is not EvaluationMode.ORGANIZATION or ablated.mode not in self._ABLATIONS:
            raise ValueError('ablation assessment requires full organization and declared ablation mode')
        comparable = full.regime_id == ablated.regime_id and full.regime_digest == ablated.regime_digest
        reason = 'same_regime_controlled_ablation' if comparable else 'regime_mismatch'
        payload0 = {
            'full_observation_id': full.observation_id, 'ablation_observation_id': ablated.observation_id,
            'ablation_mode': ablated.mode.value, 'comparable': comparable,
            'score_delta': full.score - ablated.score,
            'false_accept_delta': full.false_accepts - ablated.false_accepts,
            'regression_delta': full.regressions - ablated.regressions,
            'compute_delta': full.compute_units - ablated.compute_units, 'reason': reason,
        }
        assessment_id = 'eval-ablation-' + canonical_digest(payload0)[:24]
        payload = {'assessment_id': assessment_id, **payload0}
        row = AblationAssessment(
            assessment_id=assessment_id, full_observation_id=full.observation_id,
            ablation_observation_id=ablated.observation_id, ablation_mode=ablated.mode,
            comparable=comparable, score_delta=payload0['score_delta'], false_accept_delta=payload0['false_accept_delta'],
            regression_delta=payload0['regression_delta'], compute_delta=payload0['compute_delta'],
            reason=reason, digest=canonical_digest(payload),
        )
        self._ablations.setdefault(row.assessment_id, row)
        return self._ablations[row.assessment_id]

    def observations(self) -> tuple[EvaluationObservation, ...]:
        return tuple(self._observations[key] for key in sorted(self._observations))

    def comparisons(self) -> tuple[MatchedBudgetComparison, ...]:
        return tuple(self._comparisons[key] for key in sorted(self._comparisons))

    def ablations(self) -> tuple[AblationAssessment, ...]:
        return tuple(self._ablations[key] for key in sorted(self._ablations))

    def to_state(self) -> dict[str, Any]:
        return {
            'observations': [x.to_state() for x in self.observations()],
            'comparisons': [x.to_state() for x in self.comparisons()],
            'ablations': [x.to_state() for x in self.ablations()],
        }

    @classmethod
    def from_state(cls, *, registry: AgentRegistry, regimes: BenchmarkRegimeRegistry, state: Mapping[str, Any]) -> 'EvaluationEvidenceLedger':
        return cls(
            registry=registry, regimes=regimes,
            observations=tuple(EvaluationObservation.from_state(x) for x in state.get('observations', ())),
            comparisons=tuple(MatchedBudgetComparison.from_state(x) for x in state.get('comparisons', ())),
            ablations=tuple(AblationAssessment.from_state(x) for x in state.get('ablations', ())),
        )
