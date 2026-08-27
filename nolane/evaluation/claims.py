from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.evaluation.evidence import EvaluationEvidenceLedger
from nolane.evaluation.regimes import BenchmarkDomain, BenchmarkRegimeRegistry, EvidenceProvenanceClass, EvaluationMode
from nolane.evaluation.stress import LongHorizonStressLedger
from nolane.organization.identity import AgentRegistry
from nolane.core.canonical_digest import canonical_digest


class ClaimClass(str, Enum):
    INTERNAL_ENGINEERING_PROGRESS = 'internal_engineering_progress'
    DECLARED_BENCHMARK_IMPROVEMENT = 'declared_benchmark_improvement'
    ORGANIZATION_MATCHED_BUDGET_SUPERIORITY = 'organization_matched_budget_superiority'
    LONG_HORIZON_RELIABILITY = 'long_horizon_reliability'
    CROSS_DOMAIN_TRANSFER = 'cross_domain_transfer'
    EXTERNAL_REPRODUCIBLE_CAPABILITY = 'external_reproducible_capability'
    AGI = 'agi'
    FRONTIER_EQUIVALENCE = 'frontier_equivalence'


class ClaimDisposition(str, Enum):
    SUPPORTED = 'supported'
    LIMITED = 'limited'
    BLOCKED = 'blocked'


@dataclass(frozen=True, slots=True)
class ClaimAssessment:
    claim_id: str
    claim_class: ClaimClass
    disposition: ClaimDisposition
    observation_ids: tuple[str, ...]
    comparison_ids: tuple[str, ...]
    stress_assessment_id: str | None
    reproduction_receipt_id: str | None
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    override_effective: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'claim_id': self.claim_id, 'claim_class': self.claim_class.value,
            'disposition': self.disposition.value, 'observation_ids': list(self.observation_ids),
            'comparison_ids': list(self.comparison_ids), 'stress_assessment_id': self.stress_assessment_id,
            'reproduction_receipt_id': self.reproduction_receipt_id, 'reasons': list(self.reasons),
            'limitations': list(self.limitations), 'override_effective': self.override_effective,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ClaimAssessment':
        row = cls(
            claim_id=str(state['claim_id']), claim_class=ClaimClass(str(state['claim_class'])),
            disposition=ClaimDisposition(str(state['disposition'])),
            observation_ids=tuple(str(x) for x in state.get('observation_ids', ())),
            comparison_ids=tuple(str(x) for x in state.get('comparison_ids', ())),
            stress_assessment_id=None if state.get('stress_assessment_id') is None else str(state['stress_assessment_id']),
            reproduction_receipt_id=None if state.get('reproduction_receipt_id') is None else str(state['reproduction_receipt_id']),
            reasons=tuple(str(x) for x in state.get('reasons', ())),
            limitations=tuple(str(x) for x in state.get('limitations', ())),
            override_effective=bool(state.get('override_effective', False)), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('claim assessment digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class OrganizationReadinessReport:
    report_id: str
    claim_assessment_ids: tuple[str, ...]
    gates: Mapping[str, bool]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'report_id': self.report_id, 'claim_assessment_ids': list(self.claim_assessment_ids),
            'gates': dict(sorted((str(k), bool(v)) for k, v in self.gates.items())),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OrganizationReadinessReport':
        row = cls(
            report_id=str(state['report_id']),
            claim_assessment_ids=tuple(str(x) for x in state.get('claim_assessment_ids', ())),
            gates={str(k): bool(v) for k, v in state.get('gates', {}).items()}, digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('organization readiness report digest mismatch')
        return row


class ClaimBoundaryEngine:
    _HARD_BLOCKED = {ClaimClass.AGI, ClaimClass.FRONTIER_EQUIVALENCE}

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        regimes: BenchmarkRegimeRegistry,
        evidence: EvaluationEvidenceLedger,
        stress: LongHorizonStressLedger,
        releases=None,
        assessments: tuple[ClaimAssessment, ...] = (),
        readiness_reports: tuple[OrganizationReadinessReport, ...] = (),
    ) -> None:
        self.registry = registry
        self.regimes = regimes
        self.evidence = evidence
        self.stress = stress
        self.releases = releases
        self._assessments: dict[str, ClaimAssessment] = {}
        self._readiness: dict[str, OrganizationReadinessReport] = {}
        for row in assessments:
            self._validate_assessment_references(row)
            if row.claim_id in self._assessments:
                raise ValueError('duplicate claim assessment id')
            self._assessments[row.claim_id] = row
        for row in readiness_reports:
            for claim_id in row.claim_assessment_ids:
                self.get_assessment(claim_id)
            if row.report_id in self._readiness:
                raise ValueError('duplicate readiness report id')
            self._readiness[row.report_id] = row

    def bind_release_ledger(self, releases) -> None:
        self.releases = releases

    def _validate_assessment_references(self, row: ClaimAssessment) -> None:
        for observation_id in row.observation_ids:
            self.evidence.get_observation(observation_id)
        for comparison_id in row.comparison_ids:
            self.evidence.get_comparison(comparison_id)
        if row.stress_assessment_id is not None:
            self.stress.get_assessment(row.stress_assessment_id)
        if row.claim_class in self._HARD_BLOCKED:
            if row.disposition is not ClaimDisposition.BLOCKED or row.override_effective:
                raise ValueError('hard-disabled unrestricted claim has invalid persisted disposition')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('claim assessment digest mismatch')

    def get_assessment(self, claim_id: str) -> ClaimAssessment:
        try:
            return self._assessments[str(claim_id)]
        except KeyError as exc:
            raise KeyError(f'unknown claim assessment: {claim_id}') from exc

    def assessments(self) -> tuple[ClaimAssessment, ...]:
        return tuple(self._assessments[key] for key in sorted(self._assessments))

    def _external_observations(self, observation_ids: tuple[str, ...]):
        rows = tuple(self.evidence.get_observation(x) for x in observation_ids)
        return tuple(
            row for row in rows
            if row.provenance_class in (EvidenceProvenanceClass.EXTERNAL_REPRODUCED, EvidenceProvenanceClass.EXTERNAL_INDEPENDENT)
            and self.regimes.get(row.regime_id).fresh
        )

    def assess(
        self,
        claim_id: str,
        claim_class: ClaimClass,
        *,
        observation_ids: tuple[str, ...] = (),
        comparison_ids: tuple[str, ...] = (),
        stress_assessment_id: str | None = None,
        reproduction_receipt_id: str | None = None,
        central_override_id: str | None = None,
    ) -> ClaimAssessment:
        claim_id = str(claim_id).strip()
        if not claim_id:
            raise ValueError('claim id must be explicit')
        claim_class = ClaimClass(claim_class)
        observations = tuple(self.evidence.get_observation(x) for x in observation_ids)
        comparisons = tuple(self.evidence.get_comparison(x) for x in comparison_ids)
        stress_assessment = None if stress_assessment_id is None else self.stress.get_assessment(stress_assessment_id)
        reasons: list[str] = []
        limitations: list[str] = []
        disposition = ClaimDisposition.BLOCKED
        override_effective = False

        if claim_class in self._HARD_BLOCKED:
            reasons.append('hard_disabled_claim_class')
            limitations.append('unrestricted_claim_not_authorized_by_part15')
        elif claim_class is ClaimClass.INTERNAL_ENGINEERING_PROGRESS:
            if not observations:
                reasons.append('missing_observations')
            else:
                disposition = ClaimDisposition.LIMITED
                limitations.append('internal_engineering_evidence_only')
        elif claim_class is ClaimClass.DECLARED_BENCHMARK_IMPROVEMENT:
            external = self._external_observations(tuple(x.observation_id for x in observations))
            if not external:
                reasons.append('missing_fresh_external_evidence')
            elif any(x.false_accepts or x.regressions for x in external):
                reasons.append('dirty_external_evidence')
            else:
                disposition = ClaimDisposition.SUPPORTED
        elif claim_class is ClaimClass.ORGANIZATION_MATCHED_BUDGET_SUPERIORITY:
            modes = {x.baseline_mode for x in comparisons if x.comparable and x.improved}
            if {EvaluationMode.SINGLE_AGENT, EvaluationMode.FLAT_SWARM}.issubset(modes):
                disposition = ClaimDisposition.SUPPORTED
            else:
                reasons.append('requires_single_agent_and_flat_swarm_wins')
        elif claim_class is ClaimClass.LONG_HORIZON_RELIABILITY:
            if stress_assessment is None:
                reasons.append('missing_long_horizon_stress_suite')
            elif not stress_assessment.passed:
                reasons.append('long_horizon_stress_suite_failed')
            else:
                disposition = ClaimDisposition.SUPPORTED
        elif claim_class is ClaimClass.CROSS_DOMAIN_TRANSFER:
            external = self._external_observations(tuple(x.observation_id for x in observations))
            domains = {self.regimes.get(x.regime_id).domain for x in external if self.regimes.get(x.regime_id).domain is not BenchmarkDomain.CROSS_DOMAIN}
            heldout_cross = any(
                self.regimes.get(x.regime_id).domain is BenchmarkDomain.CROSS_DOMAIN
                and self.regimes.get(x.regime_id).heldout
                for x in external
            )
            if len(domains) >= 3 and heldout_cross:
                disposition = ClaimDisposition.SUPPORTED
            else:
                reasons.append('insufficient_cross_domain_heldout_coverage')
        elif claim_class is ClaimClass.EXTERNAL_REPRODUCIBLE_CAPABILITY:
            external_independent = [
                x for x in observations
                if x.provenance_class is EvidenceProvenanceClass.EXTERNAL_INDEPENDENT
                and self.regimes.get(x.regime_id).fresh
            ]
            reproduction_ok = bool(
                self.releases is not None and reproduction_receipt_id
                and self.releases.is_reproduction_valid(reproduction_receipt_id)
            )
            if not external_independent:
                reasons.append('missing_external_independent_observation')
            if not reproduction_ok:
                reasons.append('missing_independent_reproduction')
            if not reasons:
                disposition = ClaimDisposition.SUPPORTED
        else:
            reasons.append('unsupported_claim_class')

        payload0 = {
            'claim_class': claim_class.value, 'disposition': disposition.value,
            'observation_ids': [x.observation_id for x in observations],
            'comparison_ids': [x.comparison_id for x in comparisons],
            'stress_assessment_id': None if stress_assessment is None else stress_assessment.assessment_id,
            'reproduction_receipt_id': None if reproduction_receipt_id is None else str(reproduction_receipt_id),
            'reasons': reasons, 'limitations': limitations, 'override_effective': override_effective,
        }
        payload = {'claim_id': claim_id, **payload0}
        row = ClaimAssessment(
            claim_id=claim_id, claim_class=claim_class, disposition=disposition,
            observation_ids=tuple(payload0['observation_ids']), comparison_ids=tuple(payload0['comparison_ids']),
            stress_assessment_id=payload0['stress_assessment_id'],
            reproduction_receipt_id=payload0['reproduction_receipt_id'], reasons=tuple(reasons),
            limitations=tuple(limitations), override_effective=False, digest=canonical_digest(payload),
        )
        existing = self._assessments.get(row.claim_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('claim assessment id cannot be rebound')
        self._assessments[row.claim_id] = row
        return row

    def readiness(self, *, claim_assessment_ids: tuple[str, ...]) -> OrganizationReadinessReport:
        rows = tuple(self.get_assessment(x) for x in claim_assessment_ids)
        supported = {row.claim_class for row in rows if row.disposition is ClaimDisposition.SUPPORTED}
        gates = {
            'benchmark_coverage': bool(self.evidence.observations()),
            'matched_budget_superiority': ClaimClass.ORGANIZATION_MATCHED_BUDGET_SUPERIORITY in supported,
            'ablation_coverage': len({x.ablation_mode for x in self.evidence.ablations()}) >= 4,
            'long_horizon_reliability': ClaimClass.LONG_HORIZON_RELIABILITY in supported,
            'external_reproducibility': ClaimClass.EXTERNAL_REPRODUCIBLE_CAPABILITY in supported,
            'parameter_accounting_completeness': False,
            'safety_cleanliness': all(not x.false_accepts and not x.regressions for x in self.evidence.observations()),
            'scaling_evidence_completeness': False,
        }
        payload0 = {'claim_assessment_ids': sorted(x.claim_id for x in rows), 'gates': gates}
        report_id = 'org-readiness-' + canonical_digest(payload0)[:24]
        payload = {'report_id': report_id, **payload0}
        row = OrganizationReadinessReport(
            report_id=report_id, claim_assessment_ids=tuple(payload0['claim_assessment_ids']),
            gates=dict(gates), digest=canonical_digest(payload),
        )
        self._readiness.setdefault(row.report_id, row)
        return self._readiness[row.report_id]

    def to_state(self) -> dict[str, Any]:
        return {
            'assessments': [self._assessments[k].to_state() for k in sorted(self._assessments)],
            'readiness_reports': [self._readiness[k].to_state() for k in sorted(self._readiness)],
        }

    @classmethod
    def from_state(
        cls, *, registry: AgentRegistry, regimes: BenchmarkRegimeRegistry,
        evidence: EvaluationEvidenceLedger, stress: LongHorizonStressLedger,
        state: Mapping[str, Any], releases=None,
    ) -> 'ClaimBoundaryEngine':
        return cls(
            registry=registry, regimes=regimes, evidence=evidence, stress=stress, releases=releases,
            assessments=tuple(ClaimAssessment.from_state(x) for x in state.get('assessments', ())),
            readiness_reports=tuple(OrganizationReadinessReport.from_state(x) for x in state.get('readiness_reports', ())),
        )


COMPONENT_ID = "evaluation.claims"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.evaluation_claims"
