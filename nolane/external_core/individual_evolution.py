from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.assurance import AssuranceControlPlane
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.evolution_profiles import EvolutionProfileRegistry
from nolane.external_core.self_model import SelfModel, SelfModelRegistry
from nolane.external_core.verification import CandidateEvaluation, PromotionReceipt, RollbackReceipt, VerificationAuthority
from nolane.memory.experience import ExperienceLedger
from nolane.memory.skills import SkillEvolutionEngine, SkillRecord, SkillScope
from nolane.organization.identity import AgentRegistry


COMPONENT_ID = "external.individual_evolution"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.individual_evolution"


@dataclass(frozen=True, slots=True)
class EvolutionLineageEntry:
    sequence: int
    entry_id: str
    agent_id: str
    transition: str
    neural_version: str
    self_model_version: str
    specialization_signature: str
    evidence_ids: tuple[str, ...] = ()
    predecessor_version: str | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            'sequence': self.sequence, 'entry_id': self.entry_id, 'agent_id': self.agent_id,
            'transition': self.transition, 'neural_version': self.neural_version,
            'self_model_version': self.self_model_version,
            'specialization_signature': self.specialization_signature,
            'evidence_ids': list(self.evidence_ids), 'predecessor_version': self.predecessor_version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'EvolutionLineageEntry':
        return cls(
            sequence=int(state['sequence']), entry_id=str(state['entry_id']), agent_id=str(state['agent_id']),
            transition=str(state['transition']), neural_version=str(state['neural_version']),
            self_model_version=str(state['self_model_version']),
            specialization_signature=str(state['specialization_signature']),
            evidence_ids=tuple(str(x) for x in state.get('evidence_ids', ())),
            predecessor_version=None if state.get('predecessor_version') is None else str(state['predecessor_version']),
        )


@dataclass(frozen=True, slots=True)
class BenchmarkObservation:
    observation_id: str
    agent_id: str
    benchmark_id: str
    regime_digest: str
    score: float
    regressions: int
    evidence: EvidenceRecord

    def to_state(self) -> dict[str, Any]:
        return {
            'observation_id': self.observation_id, 'agent_id': self.agent_id,
            'benchmark_id': self.benchmark_id, 'regime_digest': self.regime_digest,
            'score': self.score, 'regressions': self.regressions, 'evidence': self.evidence.to_state(),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'BenchmarkObservation':
        return cls(
            observation_id=str(state['observation_id']), agent_id=str(state['agent_id']),
            benchmark_id=str(state['benchmark_id']), regime_digest=str(state['regime_digest']),
            score=float(state['score']), regressions=int(state['regressions']),
            evidence=EvidenceRecord.from_state(state['evidence']),
        )


@dataclass(frozen=True, slots=True)
class LongitudinalAssessment:
    improved: bool
    reason: str
    baseline_observation_id: str
    candidate_observation_id: str
    score_delta: float


class IndividualEvolutionControlPlane:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        events,
        evolution: SkillEvolutionEngine,
        self_models: SelfModelRegistry,
        verification: VerificationAuthority,
        assurance: AssuranceControlPlane,
        profiles: EvolutionProfileRegistry | None = None,
        experiences: ExperienceLedger | None = None,
        lineage: tuple[EvolutionLineageEntry, ...] = (),
        observations: tuple[BenchmarkObservation, ...] = (),
        initialize_lineage: bool = True,
    ) -> None:
        self.registry = registry
        self.events = events
        self.evolution = evolution
        self.self_models = self_models
        self.verification = verification
        self.assurance = assurance
        self.profiles = profiles or EvolutionProfileRegistry(registry=registry, self_models=self_models)
        self.experiences = experiences or ExperienceLedger(registry=registry, events=events)
        self._lineage: dict[str, list[EvolutionLineageEntry]] = {row.agent_id: [] for row in self.profiles.profiles()}
        self._lineage_counter = 0
        for row in lineage:
            self.registry.get(row.agent_id)
            self._lineage.setdefault(row.agent_id, []).append(row)
            self._lineage_counter = max(self._lineage_counter, row.sequence)
        self._observations = {row.observation_id: row for row in observations}
        if initialize_lineage and not lineage:
            for profile in self.profiles.profiles():
                self._append_lineage(profile.agent_id, 'initial')

    @staticmethod
    def _clean(evidence: EvidenceRecord) -> bool:
        return evidence.passed and evidence.false_accepts == 0 and evidence.regressions == 0

    def _append_lineage(
        self,
        agent_id: str,
        transition: str,
        *,
        evidence_ids: tuple[str, ...] = (),
        predecessor_version: str | None = None,
    ) -> EvolutionLineageEntry:
        profile = self.profiles.get(agent_id)
        self._lineage_counter += 1
        evidence = tuple(str(x) for x in evidence_ids)
        payload = {
            'sequence': self._lineage_counter, 'agent_id': profile.agent_id,
            'transition': str(transition), 'neural_version': profile.neural_version,
            'self_model_version': profile.self_model_version,
            'specialization_signature': profile.specialization_signature,
            'evidence_ids': list(evidence), 'predecessor_version': predecessor_version,
        }
        entry_id = 'evolution-lineage-' + canonical_digest(payload)[:24]
        row = EvolutionLineageEntry(
            sequence=self._lineage_counter, entry_id=entry_id, agent_id=profile.agent_id,
            transition=str(transition), neural_version=profile.neural_version,
            self_model_version=profile.self_model_version,
            specialization_signature=profile.specialization_signature,
            evidence_ids=evidence, predecessor_version=predecessor_version,
        )
        self._lineage.setdefault(profile.agent_id, []).append(row)
        return row

    def lineage_for(self, agent_id: str) -> tuple[EvolutionLineageEntry, ...]:
        self.registry.get(agent_id)
        return tuple(self._lineage.get(str(agent_id), ()))

    def propose_skill_from_attribution(self, *, agent_id: str, attribution_id: str, name: str, body: str) -> SkillRecord:
        identity = self.registry.get(agent_id)
        attribution = self.experiences.get_attribution(attribution_id)
        if attribution.agent_id != identity.agent_id:
            raise PermissionError('learning attribution cannot cross personal agent ownership')
        if not attribution.positive:
            raise PermissionError('negative or unverified attribution cannot become a skill candidate')
        return self.evolution.propose(owner_agent_id=identity.agent_id, region=identity.region, name=name, body=body)

    def verify_skill(self, skill_id: str, evidence: EvidenceRecord) -> SkillRecord:
        skill = self.evolution.get(skill_id)
        self.registry.get(evidence.verifier_agent_id)
        if self._clean(evidence) and evidence.verifier_agent_id == skill.owner_agent_id:
            raise PermissionError('skill producer cannot self-verify positive learning evidence')
        verified = self.evolution.verify(skill_id, evidence)
        if not self._clean(evidence):
            return self.evolution.quarantine(skill_id, reason='dirty_learning_evidence')
        return verified

    def promote_skill(self, skill_id: str, scope: SkillScope) -> SkillRecord:
        skill = self.evolution.get(skill_id)
        scope = SkillScope(scope)
        clean_external = {
            row.verifier_agent_id for row in skill.evidence
            if self._clean(row) and row.verifier_agent_id != skill.owner_agent_id
        }
        required = {SkillScope.PERSONAL: 1, SkillScope.REGIONAL: 2, SkillScope.GLOBAL: 3}.get(scope)
        if required is None:
            raise ValueError('candidate is not a promotion target')
        if len(clean_external) < required:
            raise PermissionError(f'{scope.value} learning promotion requires {required} clean external verifier(s)')
        if scope is SkillScope.GLOBAL:
            owner_region = self.registry.get(skill.owner_agent_id).region
            verifier_regions = {self.registry.get(verifier_id).region for verifier_id in clean_external}
            if not any(region != owner_region for region in verifier_regions):
                raise PermissionError('global learning promotion requires cross-region evidence')
        before_scope = skill.scope
        promoted = self.evolution.promote(skill_id, scope)
        if promoted.scope != before_scope:
            self._append_lineage(
                promoted.owner_agent_id, 'skill_promoted',
                evidence_ids=tuple(sorted(row.evidence_id for row in promoted.evidence)),
            )
        return promoted

    def update_self_model(self, *, agent_id: str, domain: str, score: float, evidence: EvidenceRecord) -> SelfModel:
        updated = self.self_models.update_competence(agent_id, domain=domain, score=score, evidence=evidence)
        self._append_lineage(agent_id, 'self_model_updated', evidence_ids=(evidence.evidence_id,))
        return updated

    def evaluate_neural_challenger(
        self, *, agent_id: str, candidate_version: str, physical_parameters: int,
        passed: bool, false_accepts: int, regressions: int, evidence_ids: tuple[str, ...],
    ) -> PromotionReceipt:
        return self.verification.evaluate_candidate(CandidateEvaluation(
            agent_id=str(agent_id), candidate_version=str(candidate_version),
            physical_parameters=int(physical_parameters), passed=bool(passed),
            false_accepts=int(false_accepts), regressions=int(regressions),
            evidence_ids=tuple(str(x) for x in evidence_ids),
        ))

    def promote_neural_challenger(
        self, *, agent_id: str, subject_id: str,
        assurance_evidence_ids: tuple[str, ...], candidate_receipt_id: str,
    ) -> PromotionReceipt:
        predecessor = self.registry.get(agent_id).neural_version
        authorization = self.assurance.authorize_promotion(
            subject_id=subject_id, evidence_ids=tuple(str(x) for x in assurance_evidence_ids),
            predecessor_version=predecessor,
        )
        if not authorization.authorized:
            raise PermissionError('neural challenger is not assurance-authorized: ' + ','.join(authorization.reasons))
        promoted = self.assurance.promote_neural_candidate(authorization.receipt_id, candidate_receipt_id)
        if promoted.agent_id != str(agent_id):
            raise ValueError('promoted challenger does not belong to requested agent')
        self._append_lineage(agent_id, 'neural_promoted', evidence_ids=authorization.evidence_ids, predecessor_version=predecessor)
        return promoted

    def rollback_neural(self, *, agent_id: str, reason: str) -> RollbackReceipt:
        rollback = self.verification.rollback(agent_id, reason=reason)
        self._append_lineage(agent_id, 'neural_rolled_back', predecessor_version=rollback.from_version)
        return rollback

    def record_benchmark_observation(
        self, *, observation_id: str, agent_id: str, benchmark_id: str,
        regime_digest: str, score: float, regressions: int, evidence: EvidenceRecord,
    ) -> BenchmarkObservation:
        self.registry.get(agent_id)
        self.registry.get(evidence.verifier_agent_id)
        if evidence.verifier_agent_id == str(agent_id) or not self._clean(evidence):
            raise PermissionError('longitudinal benchmark evidence must be clean and external to the producer')
        if not str(observation_id).strip() or not str(benchmark_id).strip() or not str(regime_digest).strip():
            raise ValueError('benchmark observation identity and regime must be explicit')
        if not 0.0 <= float(score) <= 1.0:
            raise ValueError('benchmark score must lie in [0, 1]')
        if int(regressions) < 0:
            raise ValueError('benchmark regressions must be non-negative')
        row = BenchmarkObservation(
            observation_id=str(observation_id), agent_id=str(agent_id), benchmark_id=str(benchmark_id),
            regime_digest=str(regime_digest), score=float(score), regressions=int(regressions), evidence=evidence,
        )
        existing = self._observations.get(row.observation_id)
        if existing is not None and existing != row:
            raise ValueError('benchmark observation id cannot be rebound')
        self._observations[row.observation_id] = row
        return row

    def assess_longitudinal_improvement(
        self, *, agent_id: str, baseline_observation_id: str, candidate_observation_id: str,
    ) -> LongitudinalAssessment:
        baseline = self._observations[str(baseline_observation_id)]
        candidate = self._observations[str(candidate_observation_id)]
        if baseline.agent_id != str(agent_id) or candidate.agent_id != str(agent_id):
            raise PermissionError('longitudinal observations must belong to the assessed agent')
        delta = candidate.score - baseline.score
        if baseline.benchmark_id != candidate.benchmark_id:
            return LongitudinalAssessment(False, 'benchmark_identity_mismatch', baseline.observation_id, candidate.observation_id, delta)
        if baseline.regime_digest != candidate.regime_digest:
            return LongitudinalAssessment(False, 'benchmark_regime_mismatch', baseline.observation_id, candidate.observation_id, delta)
        if candidate.regressions:
            return LongitudinalAssessment(False, 'candidate_regressions_detected', baseline.observation_id, candidate.observation_id, delta)
        if delta <= 0:
            return LongitudinalAssessment(False, 'no_score_improvement', baseline.observation_id, candidate.observation_id, delta)
        return LongitudinalAssessment(True, 'clean_same_regime_improvement', baseline.observation_id, candidate.observation_id, delta)

    def to_state(self) -> dict[str, Any]:
        return {
            'profiles': self.profiles.to_state(), 'experiences': self.experiences.to_state(),
            'lineage': [row.to_state() for agent_id in sorted(self._lineage) for row in self._lineage[agent_id]],
            'observations': [self._observations[key].to_state() for key in sorted(self._observations)],
            'lineage_counter': self._lineage_counter,
        }

    @classmethod
    def from_state(
        cls, *, registry: AgentRegistry, events, evolution: SkillEvolutionEngine,
        self_models: SelfModelRegistry, verification: VerificationAuthority,
        assurance: AssuranceControlPlane, state: Mapping[str, Any],
    ) -> 'IndividualEvolutionControlPlane':
        profiles = EvolutionProfileRegistry.from_state(registry=registry, self_models=self_models, state=state.get('profiles', {}))
        experiences = ExperienceLedger.from_state(registry=registry, events=events, state=state.get('experiences', {}))
        lineage = tuple(EvolutionLineageEntry.from_state(raw) for raw in state.get('lineage', ()))
        observations = tuple(BenchmarkObservation.from_state(raw) for raw in state.get('observations', ()))
        result = cls(
            registry=registry, events=events, evolution=evolution, self_models=self_models,
            verification=verification, assurance=assurance, profiles=profiles, experiences=experiences,
            lineage=lineage, observations=observations, initialize_lineage=not bool(lineage),
        )
        result._lineage_counter = max(int(state.get('lineage_counter', result._lineage_counter)), result._lineage_counter)
        return result


__all__ = (
    "EvolutionLineageEntry",
    "BenchmarkObservation",
    "LongitudinalAssessment",
    "IndividualEvolutionControlPlane",
)
