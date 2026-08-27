from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.evaluation.evidence import EvaluationEvidenceLedger
from nolane.evaluation.regimes import EvidenceProvenanceClass
from nolane.organization.identity import AgentRegistry
from nolane.core.canonical_digest import canonical_digest


@dataclass(frozen=True, slots=True)
class ParameterFootprintReport:
    report_id: str
    active_agent_ids: tuple[str, ...]
    active_ephemeral_count: int
    shared_physical_parameters: int
    local_physical_parameters: int
    unique_stored_physical_parameters: int
    active_inference_physical_parameters: int
    logical_deployed_parameter_footprint: int
    compute_units: int
    latency_ms: int
    energy_joules: float | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'report_id': self.report_id, 'active_agent_ids': list(self.active_agent_ids),
            'active_ephemeral_count': self.active_ephemeral_count,
            'shared_physical_parameters': self.shared_physical_parameters,
            'local_physical_parameters': self.local_physical_parameters,
            'unique_stored_physical_parameters': self.unique_stored_physical_parameters,
            'active_inference_physical_parameters': self.active_inference_physical_parameters,
            'logical_deployed_parameter_footprint': self.logical_deployed_parameter_footprint,
            'compute_units': self.compute_units, 'latency_ms': self.latency_ms, 'energy_joules': self.energy_joules,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ParameterFootprintReport':
        row = cls(
            report_id=str(state['report_id']), active_agent_ids=tuple(str(x) for x in state.get('active_agent_ids', ())),
            active_ephemeral_count=int(state['active_ephemeral_count']),
            shared_physical_parameters=int(state['shared_physical_parameters']),
            local_physical_parameters=int(state['local_physical_parameters']),
            unique_stored_physical_parameters=int(state['unique_stored_physical_parameters']),
            active_inference_physical_parameters=int(state['active_inference_physical_parameters']),
            logical_deployed_parameter_footprint=int(state['logical_deployed_parameter_footprint']),
            compute_units=int(state['compute_units']), latency_ms=int(state['latency_ms']),
            energy_joules=None if state.get('energy_joules') is None else float(state['energy_joules']), digest=str(state['digest']),
        )
        row._validate()
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('parameter footprint digest mismatch')
        return row

    def _validate(self) -> None:
        if not self.report_id or not self.active_agent_ids:
            raise ValueError('parameter footprint requires report id and active agents')
        values = (
            self.active_ephemeral_count, self.shared_physical_parameters, self.local_physical_parameters,
            self.unique_stored_physical_parameters, self.active_inference_physical_parameters,
            self.logical_deployed_parameter_footprint, self.compute_units, self.latency_ms,
        )
        if min(values) < 0:
            raise ValueError('parameter/compute footprint values must be non-negative')
        if self.energy_joules is not None and self.energy_joules < 0:
            raise ValueError('energy estimate must be non-negative')
        if self.unique_stored_physical_parameters != self.shared_physical_parameters + self.local_physical_parameters:
            raise ValueError('unique stored parameter arithmetic mismatch')
        if self.active_inference_physical_parameters != self.unique_stored_physical_parameters:
            raise ValueError('active inference footprint must use unique active physical parameters')
        if self.logical_deployed_parameter_footprint < self.unique_stored_physical_parameters:
            raise ValueError('logical footprint cannot be below unique physical footprint')


class ScalingDecision(str, Enum):
    REJECTED = 'rejected'
    DEFERRED = 'deferred'
    AUTHORIZED_FOR_FUTURE_EXPERIMENT = 'authorized_for_future_experiment'


@dataclass(frozen=True, slots=True)
class ScalingProposal:
    proposal_id: str
    agent_id: str
    current_physical_parameters: int
    candidate_physical_parameters: int
    baseline_observation_id: str
    candidate_observation_id: str
    compute_cost_ratio: float
    storage_delta_bytes: int
    latency_delta_ms: int
    energy_delta_joules: float
    economic_capacity_digest: str
    verifier_ids: tuple[str, ...]
    external_evaluator_id: str
    evidence_ids: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'proposal_id': self.proposal_id, 'agent_id': self.agent_id,
            'current_physical_parameters': self.current_physical_parameters,
            'candidate_physical_parameters': self.candidate_physical_parameters,
            'baseline_observation_id': self.baseline_observation_id,
            'candidate_observation_id': self.candidate_observation_id,
            'compute_cost_ratio': self.compute_cost_ratio, 'storage_delta_bytes': self.storage_delta_bytes,
            'latency_delta_ms': self.latency_delta_ms, 'energy_delta_joules': self.energy_delta_joules,
            'economic_capacity_digest': self.economic_capacity_digest, 'verifier_ids': list(self.verifier_ids),
            'external_evaluator_id': self.external_evaluator_id, 'evidence_ids': list(self.evidence_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ScalingProposal':
        row = cls(
            proposal_id=str(state['proposal_id']), agent_id=str(state['agent_id']),
            current_physical_parameters=int(state['current_physical_parameters']),
            candidate_physical_parameters=int(state['candidate_physical_parameters']),
            baseline_observation_id=str(state['baseline_observation_id']), candidate_observation_id=str(state['candidate_observation_id']),
            compute_cost_ratio=float(state['compute_cost_ratio']), storage_delta_bytes=int(state['storage_delta_bytes']),
            latency_delta_ms=int(state['latency_delta_ms']), energy_delta_joules=float(state['energy_delta_joules']),
            economic_capacity_digest=str(state['economic_capacity_digest']),
            verifier_ids=tuple(str(x) for x in state.get('verifier_ids', ())),
            external_evaluator_id=str(state['external_evaluator_id']), evidence_ids=tuple(str(x) for x in state.get('evidence_ids', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('scaling proposal digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ScalingDecisionReceipt:
    decision_id: str
    proposal_id: str
    decision: ScalingDecision
    score_delta: float
    reasons: tuple[str, ...]
    verifier_regions: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'decision_id': self.decision_id, 'proposal_id': self.proposal_id,
            'decision': self.decision.value, 'score_delta': self.score_delta,
            'reasons': list(self.reasons), 'verifier_regions': list(self.verifier_regions),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ScalingDecisionReceipt':
        row = cls(
            decision_id=str(state['decision_id']), proposal_id=str(state['proposal_id']),
            decision=ScalingDecision(str(state['decision'])), score_delta=float(state['score_delta']),
            reasons=tuple(str(x) for x in state.get('reasons', ())),
            verifier_regions=tuple(str(x) for x in state.get('verifier_regions', ())), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('scaling decision digest mismatch')
        return row


class ParameterScalingAuthority:
    MIN_MARGINAL_GAIN = 0.03
    MAX_COMPUTE_RATIO = 1.75

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        evidence: EvaluationEvidenceLedger,
        reports: tuple[ParameterFootprintReport, ...] = (),
        proposals: tuple[ScalingProposal, ...] = (),
        decisions: tuple[ScalingDecisionReceipt, ...] = (),
    ) -> None:
        self.registry = registry
        self.evidence = evidence
        self._reports = {row.report_id: row for row in reports}
        self._proposals = {row.proposal_id: row for row in proposals}
        self._decisions = {row.decision_id: row for row in decisions}
        if len(self._reports) != len(reports) or len(self._proposals) != len(proposals) or len(self._decisions) != len(decisions):
            raise ValueError('duplicate parameter/scaling ids')
        for row in reports:
            self._validate_report_against_registry(row)
        for row in proposals:
            self._validate_proposal(row)
        for row in decisions:
            if row.proposal_id not in self._proposals:
                raise ValueError('scaling decision references unknown proposal')

    def _validate_report_against_registry(self, row: ParameterFootprintReport) -> None:
        row._validate()
        identities = [self.registry.get(agent_id) for agent_id in row.active_agent_ids]
        shared_values = {x.parameter_accounting.shared_physical_parameters for x in identities}
        if len(shared_values) != 1:
            raise ValueError('selected agents do not share one canonical physical substrate')
        expected_shared = next(iter(shared_values))
        expected_local = sum(x.parameter_accounting.local_physical_parameters for x in identities)
        expected_logical = sum(x.parameter_accounting.total_physical_parameters for x in identities)
        if (row.shared_physical_parameters, row.local_physical_parameters, row.logical_deployed_parameter_footprint) != (
            expected_shared, expected_local, expected_logical,
        ):
            raise ValueError('parameter footprint does not match registry accounting')

    def parameter_footprint(
        self,
        *,
        active_agent_ids: tuple[str, ...],
        active_ephemeral_count: int,
        compute_units: int,
        latency_ms: int,
        energy_joules: float | None,
    ) -> ParameterFootprintReport:
        ids = tuple(dict.fromkeys(str(x) for x in active_agent_ids))
        if not ids:
            raise ValueError('parameter footprint requires active permanent agents')
        identities = [self.registry.get(x) for x in ids]
        shared_values = {x.parameter_accounting.shared_physical_parameters for x in identities}
        if len(shared_values) != 1:
            raise ValueError('active agents must share one canonical substrate for this report')
        shared = next(iter(shared_values))
        local = sum(x.parameter_accounting.local_physical_parameters for x in identities)
        logical = sum(x.parameter_accounting.total_physical_parameters for x in identities)
        payload0 = {
            'active_agent_ids': list(ids), 'active_ephemeral_count': int(active_ephemeral_count),
            'shared_physical_parameters': shared, 'local_physical_parameters': local,
            'unique_stored_physical_parameters': shared + local,
            'active_inference_physical_parameters': shared + local,
            'logical_deployed_parameter_footprint': logical, 'compute_units': int(compute_units),
            'latency_ms': int(latency_ms), 'energy_joules': None if energy_joules is None else float(energy_joules),
        }
        report_id = 'parameter-footprint-' + canonical_digest(payload0)[:24]
        payload = {'report_id': report_id, **payload0}
        row = ParameterFootprintReport(
            report_id=report_id, active_agent_ids=ids, active_ephemeral_count=payload0['active_ephemeral_count'],
            shared_physical_parameters=shared, local_physical_parameters=local,
            unique_stored_physical_parameters=shared + local, active_inference_physical_parameters=shared + local,
            logical_deployed_parameter_footprint=logical, compute_units=payload0['compute_units'], latency_ms=payload0['latency_ms'],
            energy_joules=payload0['energy_joules'], digest=canonical_digest(payload),
        )
        self._validate_report_against_registry(row)
        self._reports.setdefault(row.report_id, row)
        return self._reports[row.report_id]

    def get_report(self, report_id: str) -> ParameterFootprintReport:
        try:
            return self._reports[str(report_id)]
        except KeyError as exc:
            raise KeyError(f'unknown parameter footprint report: {report_id}') from exc

    def _validate_proposal(self, row: ScalingProposal) -> None:
        identity = self.registry.get(row.agent_id)
        if row.current_physical_parameters != identity.parameter_accounting.total_physical_parameters:
            raise ValueError('scaling proposal current parameter count is stale')
        self.evidence.get_observation(row.baseline_observation_id)
        self.evidence.get_observation(row.candidate_observation_id)
        if not row.proposal_id or row.candidate_physical_parameters <= 0 or row.compute_cost_ratio <= 0:
            raise ValueError('scaling proposal identity/count/ratio must be positive')
        if min(row.storage_delta_bytes, row.latency_delta_ms) < 0 or row.energy_delta_joules < 0:
            raise ValueError('scaling proposal cost deltas must be non-negative')
        if not row.economic_capacity_digest or not row.verifier_ids or not row.external_evaluator_id or not row.evidence_ids:
            raise ValueError('scaling proposal requires economic, verifier, external evaluator and evidence basis')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('scaling proposal digest mismatch')

    def propose_scaling(self, **kwargs: Any) -> ScalingProposal:
        identity = self.registry.get(str(kwargs['agent_id']))
        row0 = ScalingProposal(
            proposal_id=str(kwargs['proposal_id']), agent_id=identity.agent_id,
            current_physical_parameters=identity.parameter_accounting.total_physical_parameters,
            candidate_physical_parameters=int(kwargs['candidate_physical_parameters']),
            baseline_observation_id=str(kwargs['baseline_observation_id']), candidate_observation_id=str(kwargs['candidate_observation_id']),
            compute_cost_ratio=float(kwargs['compute_cost_ratio']), storage_delta_bytes=int(kwargs['storage_delta_bytes']),
            latency_delta_ms=int(kwargs['latency_delta_ms']), energy_delta_joules=float(kwargs['energy_delta_joules']),
            economic_capacity_digest=str(kwargs['economic_capacity_digest']),
            verifier_ids=tuple(sorted({str(x) for x in kwargs['verifier_ids']})),
            external_evaluator_id=str(kwargs['external_evaluator_id']),
            evidence_ids=tuple(sorted({str(x) for x in kwargs['evidence_ids']})), digest='',
        )
        row = ScalingProposal(
            proposal_id=row0.proposal_id, agent_id=row0.agent_id, current_physical_parameters=row0.current_physical_parameters,
            candidate_physical_parameters=row0.candidate_physical_parameters, baseline_observation_id=row0.baseline_observation_id,
            candidate_observation_id=row0.candidate_observation_id, compute_cost_ratio=row0.compute_cost_ratio,
            storage_delta_bytes=row0.storage_delta_bytes, latency_delta_ms=row0.latency_delta_ms,
            energy_delta_joules=row0.energy_delta_joules, economic_capacity_digest=row0.economic_capacity_digest,
            verifier_ids=row0.verifier_ids, external_evaluator_id=row0.external_evaluator_id,
            evidence_ids=row0.evidence_ids, digest=canonical_digest(row0.payload()),
        )
        self._validate_proposal(row)
        existing = self._proposals.get(row.proposal_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('scaling proposal id cannot be rebound')
        self._proposals[row.proposal_id] = row
        return row

    def get_proposal(self, proposal_id: str) -> ScalingProposal:
        try:
            return self._proposals[str(proposal_id)]
        except KeyError as exc:
            raise KeyError(f'unknown scaling proposal: {proposal_id}') from exc

    def decide_scaling(self, proposal_id: str) -> ScalingDecisionReceipt:
        proposal = self.get_proposal(proposal_id)
        baseline = self.evidence.get_observation(proposal.baseline_observation_id)
        candidate = self.evidence.get_observation(proposal.candidate_observation_id)
        reasons: list[str] = []
        delta = candidate.score - baseline.score
        if baseline.regime_id != candidate.regime_id or baseline.regime_digest != candidate.regime_digest:
            reasons.append('regime_mismatch')
        if delta + 1e-12 < self.MIN_MARGINAL_GAIN:
            reasons.append('insufficient_marginal_gain')
        if candidate.false_accepts > baseline.false_accepts:
            reasons.append('false_accepts_worsened')
        if candidate.regressions > baseline.regressions:
            reasons.append('regressions_worsened')
        if proposal.compute_cost_ratio > self.MAX_COMPUTE_RATIO:
            reasons.append('efficiency_ratio_exceeded')
        if candidate.provenance_class is not EvidenceProvenanceClass.EXTERNAL_INDEPENDENT:
            reasons.append('candidate_not_external_independent')
        if candidate.external_evaluator_id != proposal.external_evaluator_id:
            reasons.append('external_evaluator_evidence_mismatch')
        organization_ids = {x.agent_id for x in self.registry.identities()}
        if proposal.external_evaluator_id in organization_ids:
            reasons.append('external_evaluator_not_independent')
        verifier_regions: set[str] = set()
        for verifier_id in proposal.verifier_ids:
            try:
                verifier_regions.add(self.registry.get(verifier_id).region)
            except KeyError:
                reasons.append('unknown_permanent_verifier')
        if len(set(proposal.verifier_ids)) < 2 or len(verifier_regions) < 2:
            reasons.append('insufficient_cross_region_verifiers')
        if not proposal.economic_capacity_digest or not proposal.evidence_ids:
            reasons.append('missing_economic_or_evidence_basis')
        reasons = list(dict.fromkeys(reasons))
        decision = ScalingDecision.AUTHORIZED_FOR_FUTURE_EXPERIMENT if not reasons else ScalingDecision.REJECTED
        payload0 = {
            'proposal_id': proposal.proposal_id, 'decision': decision.value, 'score_delta': delta,
            'reasons': reasons, 'verifier_regions': sorted(verifier_regions),
        }
        decision_id = 'scaling-decision-' + canonical_digest(payload0)[:24]
        payload = {'decision_id': decision_id, **payload0}
        row = ScalingDecisionReceipt(
            decision_id=decision_id, proposal_id=proposal.proposal_id, decision=decision,
            score_delta=delta, reasons=tuple(reasons), verifier_regions=tuple(sorted(verifier_regions)),
            digest=canonical_digest(payload),
        )
        self._decisions.setdefault(row.decision_id, row)
        return self._decisions[row.decision_id]

    def get_decision(self, decision_id: str) -> ScalingDecisionReceipt:
        try:
            return self._decisions[str(decision_id)]
        except KeyError as exc:
            raise KeyError(f'unknown scaling decision: {decision_id}') from exc

    def to_state(self) -> dict[str, Any]:
        return {
            'reports': [self._reports[k].to_state() for k in sorted(self._reports)],
            'proposals': [self._proposals[k].to_state() for k in sorted(self._proposals)],
            'decisions': [self._decisions[k].to_state() for k in sorted(self._decisions)],
        }

    @classmethod
    def from_state(
        cls, *, registry: AgentRegistry, evidence: EvaluationEvidenceLedger, state: Mapping[str, Any]
    ) -> 'ParameterScalingAuthority':
        return cls(
            registry=registry, evidence=evidence,
            reports=tuple(ParameterFootprintReport.from_state(x) for x in state.get('reports', ())),
            proposals=tuple(ScalingProposal.from_state(x) for x in state.get('proposals', ())),
            decisions=tuple(ScalingDecisionReceipt.from_state(x) for x in state.get('decisions', ())),
        )


COMPONENT_ID = "evaluation.parameters"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.evaluation_parameters"
