from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .artifacts import ArtifactStore
from .assurance import AssuranceControlPlane, AssuranceDisposition
from .foundry_profiles import EphemeralIdentityManifest
from .registry import AgentRegistry
from .types import EvidenceRecord, canonical_digest


@dataclass(frozen=True, slots=True)
class FoundryOutputReceipt:
    output_id: str
    ephemeral_id: str
    sponsor_agent_id: str
    parent_task_id: str | None
    parent_lease_id: str | None
    parent_lease_epoch: int | None
    artifact_id: str
    kind: str
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'output_id': self.output_id,
            'ephemeral_id': self.ephemeral_id,
            'sponsor_agent_id': self.sponsor_agent_id,
            'parent_task_id': self.parent_task_id,
            'parent_lease_id': self.parent_lease_id,
            'parent_lease_epoch': self.parent_lease_epoch,
            'artifact_id': self.artifact_id,
            'kind': self.kind,
            'evidence_refs': list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FoundryOutputReceipt':
        row = cls(
            output_id=str(state['output_id']), ephemeral_id=str(state['ephemeral_id']),
            sponsor_agent_id=str(state['sponsor_agent_id']),
            parent_task_id=None if state.get('parent_task_id') is None else str(state['parent_task_id']),
            parent_lease_id=None if state.get('parent_lease_id') is None else str(state['parent_lease_id']),
            parent_lease_epoch=None if state.get('parent_lease_epoch') is None else int(state['parent_lease_epoch']),
            artifact_id=str(state['artifact_id']), kind=str(state['kind']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())), digest=str(state['digest']),
        )
        if not all(value.strip() for value in (row.output_id, row.ephemeral_id, row.sponsor_agent_id, row.artifact_id, row.kind)):
            raise ValueError('Foundry output identity must be explicit')
        if (row.parent_lease_id is None) != (row.parent_lease_epoch is None):
            raise ValueError('Foundry output parent lease id and epoch must appear together')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry output receipt digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class FoundryVerificationReceipt:
    verification_id: str
    output_id: str
    evidence: EvidenceRecord
    clean: bool
    independent: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'verification_id': self.verification_id,
            'output_id': self.output_id,
            'evidence': self.evidence.to_state(),
            'clean': self.clean,
            'independent': self.independent,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FoundryVerificationReceipt':
        row = cls(
            verification_id=str(state['verification_id']), output_id=str(state['output_id']),
            evidence=EvidenceRecord.from_state(state['evidence']), clean=bool(state['clean']),
            independent=bool(state['independent']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry verification receipt digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class FoundryHandoffReceipt:
    handoff_id: str
    output_id: str
    ephemeral_id: str
    sponsor_agent_id: str
    target_agent_id: str
    bridge_artifact_id: str
    verification_ids: tuple[str, ...]
    parent_task_id: str | None
    parent_lease_id: str | None
    parent_lease_epoch: int | None
    authorized: bool
    assurance_subject_id: str | None
    assurance_decision_id: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'handoff_id': self.handoff_id,
            'output_id': self.output_id,
            'ephemeral_id': self.ephemeral_id,
            'sponsor_agent_id': self.sponsor_agent_id,
            'target_agent_id': self.target_agent_id,
            'bridge_artifact_id': self.bridge_artifact_id,
            'verification_ids': list(self.verification_ids),
            'parent_task_id': self.parent_task_id,
            'parent_lease_id': self.parent_lease_id,
            'parent_lease_epoch': self.parent_lease_epoch,
            'authorized': self.authorized,
            'assurance_subject_id': self.assurance_subject_id,
            'assurance_decision_id': self.assurance_decision_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FoundryHandoffReceipt':
        row = cls(
            handoff_id=str(state['handoff_id']), output_id=str(state['output_id']),
            ephemeral_id=str(state['ephemeral_id']), sponsor_agent_id=str(state['sponsor_agent_id']),
            target_agent_id=str(state['target_agent_id']), bridge_artifact_id=str(state['bridge_artifact_id']),
            verification_ids=tuple(str(x) for x in state.get('verification_ids', ())),
            parent_task_id=None if state.get('parent_task_id') is None else str(state['parent_task_id']),
            parent_lease_id=None if state.get('parent_lease_id') is None else str(state['parent_lease_id']),
            parent_lease_epoch=None if state.get('parent_lease_epoch') is None else int(state['parent_lease_epoch']),
            authorized=bool(state.get('authorized', False)),
            assurance_subject_id=None if state.get('assurance_subject_id') is None else str(state['assurance_subject_id']),
            assurance_decision_id=None if state.get('assurance_decision_id') is None else str(state['assurance_decision_id']),
            digest=str(state['digest']),
        )
        if (row.parent_lease_id is None) != (row.parent_lease_epoch is None):
            raise ValueError('Foundry handoff parent lease id and epoch must appear together')
        if row.authorized and (row.assurance_subject_id is None or row.assurance_decision_id is None):
            raise ValueError('authorized Foundry handoff requires assurance lineage')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry handoff receipt digest mismatch')
        return row


class BenefitMode(str, Enum):
    BASELINE = 'baseline'
    EPHEMERAL_TEAM = 'ephemeral_team'


@dataclass(frozen=True, slots=True)
class FoundryBenefitObservation:
    observation_id: str
    mode: BenefitMode
    task_id: str
    benchmark_id: str
    regime_digest: str
    budget_digest: str
    budget_limit_units: int
    resource_units: int
    score: float
    false_accepts: int
    regressions: int
    team_id: str | None
    evidence: EvidenceRecord
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'observation_id': self.observation_id, 'mode': self.mode.value,
            'task_id': self.task_id, 'benchmark_id': self.benchmark_id,
            'regime_digest': self.regime_digest, 'budget_digest': self.budget_digest,
            'budget_limit_units': self.budget_limit_units, 'resource_units': self.resource_units,
            'score': self.score, 'false_accepts': self.false_accepts, 'regressions': self.regressions,
            'team_id': self.team_id, 'evidence': self.evidence.to_state(),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FoundryBenefitObservation':
        row = cls(
            observation_id=str(state['observation_id']), mode=BenefitMode(str(state['mode'])),
            task_id=str(state['task_id']), benchmark_id=str(state['benchmark_id']),
            regime_digest=str(state['regime_digest']), budget_digest=str(state['budget_digest']),
            budget_limit_units=int(state['budget_limit_units']), resource_units=int(state['resource_units']),
            score=float(state['score']), false_accepts=int(state['false_accepts']), regressions=int(state['regressions']),
            team_id=None if state.get('team_id') is None else str(state['team_id']),
            evidence=EvidenceRecord.from_state(state['evidence']), digest=str(state['digest']),
        )
        if row.budget_limit_units <= 0 or row.resource_units < 0 or not 0.0 <= row.score <= 1.0:
            raise ValueError('invalid Foundry benefit observation metrics')
        if row.false_accepts < 0 or row.regressions < 0:
            raise ValueError('invalid Foundry benefit safety counters')
        if row.mode is BenefitMode.EPHEMERAL_TEAM and row.team_id is None:
            raise ValueError('Foundry team observation requires team id')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry benefit observation digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class FoundryBenefitAssessment:
    baseline_observation_id: str
    team_observation_id: str
    improved: bool
    score_delta: float
    reason: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'baseline_observation_id': self.baseline_observation_id,
            'team_observation_id': self.team_observation_id,
            'improved': self.improved, 'score_delta': self.score_delta, 'reason': self.reason,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'FoundryBenefitAssessment':
        row = cls(
            baseline_observation_id=str(state['baseline_observation_id']),
            team_observation_id=str(state['team_observation_id']), improved=bool(state['improved']),
            score_delta=float(state['score_delta']), reason=str(state['reason']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry benefit assessment digest mismatch')
        return row


def _signed(row):
    return replace(row, digest=canonical_digest(row.payload()))


class FoundryEvidenceLedger:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        artifacts: ArtifactStore,
        assurance: AssuranceControlPlane,
        outputs: tuple[FoundryOutputReceipt, ...] = (),
        verifications: tuple[FoundryVerificationReceipt, ...] = (),
        handoffs: tuple[FoundryHandoffReceipt, ...] = (),
        observations: tuple[FoundryBenefitObservation, ...] = (),
        assessments: tuple[FoundryBenefitAssessment, ...] = (),
    ) -> None:
        self.registry = registry
        self.artifacts = artifacts
        self.assurance = assurance
        self._outputs = {row.output_id: row for row in outputs}
        self._verifications = {row.verification_id: row for row in verifications}
        self._verification_by_evidence: dict[str, str] = {}
        self._handoffs = {row.handoff_id: row for row in handoffs}
        self._observations = {row.observation_id: row for row in observations}
        self._assessments = list(assessments)
        if len(self._outputs) != len(outputs) or len(self._verifications) != len(verifications) or len(self._handoffs) != len(handoffs):
            raise ValueError('duplicate Foundry evidence identifiers')
        for row in outputs:
            artifact = self.artifacts.get(row.artifact_id)
            if artifact.producer_agent_id != row.ephemeral_id:
                raise ValueError('Foundry raw artifact producer provenance mismatch')
            self.registry.get(row.sponsor_agent_id)
        for row in verifications:
            output = self.get_output(row.output_id)
            self.registry.get(row.evidence.verifier_agent_id)
            expected_clean = row.evidence.passed and row.evidence.false_accepts == 0 and row.evidence.regressions == 0
            expected_independent = row.evidence.verifier_agent_id not in {output.sponsor_agent_id, output.ephemeral_id}
            if row.clean != expected_clean or row.independent != expected_independent:
                raise ValueError('Foundry verification disposition is non-canonical')
            previous = self._verification_by_evidence.get(row.evidence.evidence_id)
            if previous is not None and previous != row.verification_id:
                raise ValueError('Foundry verification evidence id is duplicated')
            self._verification_by_evidence[row.evidence.evidence_id] = row.verification_id
        for row in handoffs:
            output = self.get_output(row.output_id)
            if row.ephemeral_id != output.ephemeral_id or row.sponsor_agent_id != output.sponsor_agent_id:
                raise ValueError('Foundry handoff provenance mismatch')
            self.registry.get(row.target_agent_id)
            bridge = self.artifacts.get(row.bridge_artifact_id)
            if bridge.producer_agent_id != row.sponsor_agent_id:
                raise ValueError('Foundry handoff bridge producer mismatch')
            if row.authorized:
                subject = self.assurance.evidence.get_subject(row.assurance_subject_id or '')
                if subject.artifact_id != row.bridge_artifact_id:
                    raise ValueError('Foundry handoff assurance subject does not bind bridge artifact')
                if self.assurance.effective_disposition(subject.subject_id) is not AssuranceDisposition.VERIFIED:
                    raise ValueError('Foundry snapshot contains handoff without verified assurance')
        for row in observations:
            self.registry.get(row.evidence.verifier_agent_id)
            if not row.evidence.passed or row.evidence.false_accepts or row.evidence.regressions:
                raise PermissionError('Foundry benefit observation evidence must be clean')

    def emit_output(
        self,
        manifest: EphemeralIdentityManifest,
        *,
        kind: str,
        content: str,
        evidence_refs: tuple[str, ...],
    ) -> FoundryOutputReceipt:
        kind = str(kind).strip()
        if kind not in manifest.allowed_artifact_kinds:
            raise PermissionError('Foundry output kind exceeds manifest artifact envelope')
        if not str(content).strip() or not evidence_refs:
            raise ValueError('Foundry output requires content and evidence refs')
        artifact = self.artifacts.put(
            kind=f'foundry-{kind}', producer_agent_id=manifest.ephemeral_id,
            content=str(content), evidence_refs=tuple(str(x) for x in evidence_refs),
            metadata={
                'ephemeral_id': manifest.ephemeral_id, 'sponsor_agent_id': manifest.sponsor_agent_id,
                'team_id': manifest.team_id, 'parent_task_id': manifest.parent_task_id,
                'parent_lease_id': manifest.parent_lease_id, 'parent_lease_epoch': manifest.parent_lease_epoch,
                'template_id': manifest.template_id,
            },
        )
        payload = {
            'ephemeral_id': manifest.ephemeral_id, 'artifact_id': artifact.artifact_id,
            'kind': kind, 'artifact_digest': artifact.digest,
        }
        output_id = 'foundry-output-' + canonical_digest(payload)[:24]
        row = _signed(FoundryOutputReceipt(
            output_id=output_id, ephemeral_id=manifest.ephemeral_id,
            sponsor_agent_id=manifest.sponsor_agent_id, parent_task_id=manifest.parent_task_id,
            parent_lease_id=manifest.parent_lease_id, parent_lease_epoch=manifest.parent_lease_epoch,
            artifact_id=artifact.artifact_id, kind=kind,
            evidence_refs=tuple(str(x) for x in evidence_refs), digest='',
        ))
        existing = self._outputs.get(row.output_id)
        if existing is not None:
            return existing
        self._outputs[row.output_id] = row
        return row

    def get_output(self, output_id: str) -> FoundryOutputReceipt:
        try:
            return self._outputs[str(output_id)]
        except KeyError as exc:
            raise KeyError(f'unknown Foundry output: {output_id}') from exc

    def record_verification(self, output_id: str, evidence: EvidenceRecord) -> FoundryVerificationReceipt:
        output = self.get_output(output_id)
        self.registry.get(evidence.verifier_agent_id)
        existing_id = self._verification_by_evidence.get(evidence.evidence_id)
        if existing_id is not None:
            existing = self._verifications[existing_id]
            if existing.output_id != output.output_id or existing.evidence != evidence:
                raise ValueError('Foundry verification evidence id cannot be rebound')
            return existing
        clean = evidence.passed and evidence.false_accepts == 0 and evidence.regressions == 0
        independent = evidence.verifier_agent_id not in {output.sponsor_agent_id, output.ephemeral_id}
        verification_id = 'foundry-verification-' + canonical_digest({
            'output_id': output.output_id, 'evidence': evidence.to_state(),
        })[:24]
        row = _signed(FoundryVerificationReceipt(
            verification_id=verification_id, output_id=output.output_id,
            evidence=evidence, clean=clean, independent=independent, digest='',
        ))
        self._verifications[row.verification_id] = row
        self._verification_by_evidence[evidence.evidence_id] = row.verification_id
        return row

    def verifications_for(self, output_id: str) -> tuple[FoundryVerificationReceipt, ...]:
        return tuple(sorted(
            (row for row in self._verifications.values() if row.output_id == str(output_id)),
            key=lambda row: row.verification_id,
        ))

    def prepare_handoff(self, output_id: str, *, target_agent_id: str) -> FoundryHandoffReceipt:
        output = self.get_output(output_id)
        target = self.registry.get(target_agent_id)
        clean = tuple(row for row in self.verifications_for(output.output_id) if row.clean and row.independent)
        if not clean:
            raise PermissionError('Foundry handoff requires clean independent permanent verification')
        raw = self.artifacts.get(output.artifact_id)
        verification_ids = tuple(row.verification_id for row in clean)
        bridge = self.artifacts.put(
            kind='foundry-handoff', producer_agent_id=output.sponsor_agent_id,
            content=f'Foundry handoff for {output.output_id} -> {target.agent_id}',
            evidence_refs=tuple(row.evidence.evidence_id for row in clean),
            metadata={
                'raw_artifact_id': raw.artifact_id, 'raw_artifact_digest': raw.digest,
                'ephemeral_id': output.ephemeral_id, 'output_id': output.output_id,
                'sponsor_agent_id': output.sponsor_agent_id, 'target_agent_id': target.agent_id,
                'parent_task_id': output.parent_task_id, 'parent_lease_id': output.parent_lease_id,
                'parent_lease_epoch': output.parent_lease_epoch,
                'verification_ids': list(verification_ids),
                'limitations': ['Foundry output remains proposal/evidence until permanent authority accepts it'],
            },
        )
        handoff_id = 'foundry-handoff-' + canonical_digest({
            'output_id': output.output_id, 'target_agent_id': target.agent_id,
            'bridge_artifact_id': bridge.artifact_id,
        })[:24]
        row = _signed(FoundryHandoffReceipt(
            handoff_id=handoff_id, output_id=output.output_id, ephemeral_id=output.ephemeral_id,
            sponsor_agent_id=output.sponsor_agent_id, target_agent_id=target.agent_id,
            bridge_artifact_id=bridge.artifact_id, verification_ids=verification_ids,
            parent_task_id=output.parent_task_id, parent_lease_id=output.parent_lease_id,
            parent_lease_epoch=output.parent_lease_epoch, authorized=False,
            assurance_subject_id=None, assurance_decision_id=None, digest='',
        ))
        existing = self._handoffs.get(row.handoff_id)
        if existing is not None:
            return existing
        self._handoffs[row.handoff_id] = row
        return row

    def get_handoff(self, handoff_id: str) -> FoundryHandoffReceipt:
        try:
            return self._handoffs[str(handoff_id)]
        except KeyError as exc:
            raise KeyError(f'unknown Foundry handoff: {handoff_id}') from exc

    def authorize_handoff(self, handoff_id: str, *, assurance_decision_id: str) -> FoundryHandoffReceipt:
        old = self.get_handoff(handoff_id)
        decision = self.assurance.get_decision(assurance_decision_id)
        subject = self.assurance.evidence.get_subject(decision.subject_id)
        if subject.artifact_id != old.bridge_artifact_id or subject.producer_agent_id != old.sponsor_agent_id:
            raise PermissionError('Part-VIII assurance decision does not bind Foundry sponsor bridge')
        if decision.disposition is not AssuranceDisposition.VERIFIED:
            raise PermissionError('Foundry engineering handoff requires a VERIFIED Part-VIII decision')
        if self.assurance.effective_disposition(subject.subject_id) is not AssuranceDisposition.VERIFIED:
            raise PermissionError('Foundry handoff cannot treat overridden/rejected/pending assurance as verified')
        updated = _signed(replace(
            old, authorized=True, assurance_subject_id=subject.subject_id,
            assurance_decision_id=decision.decision_id, digest='',
        ))
        self._handoffs[old.handoff_id] = updated
        return updated

    def record_benefit_observation(
        self,
        *,
        observation_id: str,
        mode: BenefitMode,
        task_id: str,
        benchmark_id: str,
        regime_digest: str,
        budget_digest: str,
        budget_limit_units: int,
        resource_units: int,
        score: float,
        false_accepts: int,
        regressions: int,
        team_id: str | None,
        evidence: EvidenceRecord,
    ) -> FoundryBenefitObservation:
        self.registry.get(evidence.verifier_agent_id)
        if not evidence.passed or evidence.false_accepts or evidence.regressions:
            raise PermissionError('Foundry benefit observation evidence must be clean')
        if not all(str(value).strip() for value in (observation_id, task_id, benchmark_id, regime_digest, budget_digest)):
            raise ValueError('Foundry benefit observation identity/regime/budget must be explicit')
        row = _signed(FoundryBenefitObservation(
            observation_id=str(observation_id), mode=BenefitMode(mode), task_id=str(task_id),
            benchmark_id=str(benchmark_id), regime_digest=str(regime_digest), budget_digest=str(budget_digest),
            budget_limit_units=int(budget_limit_units), resource_units=int(resource_units), score=float(score),
            false_accepts=int(false_accepts), regressions=int(regressions),
            team_id=None if team_id is None else str(team_id), evidence=evidence, digest='',
        ))
        existing = self._observations.get(row.observation_id)
        if existing is not None:
            if existing != row:
                raise ValueError('Foundry benefit observation id cannot be rebound')
            return existing
        self._observations[row.observation_id] = row
        return row

    def get_observation(self, observation_id: str) -> FoundryBenefitObservation:
        try:
            return self._observations[str(observation_id)]
        except KeyError as exc:
            raise KeyError(f'unknown Foundry benefit observation: {observation_id}') from exc

    def assess_benefit(self, baseline_observation_id: str, team_observation_id: str) -> FoundryBenefitAssessment:
        baseline = self.get_observation(baseline_observation_id)
        team = self.get_observation(team_observation_id)
        if baseline.mode is not BenefitMode.BASELINE or team.mode is not BenefitMode.EPHEMERAL_TEAM:
            raise ValueError('Foundry benefit comparison requires baseline then ephemeral-team observation')
        if baseline.task_id != team.task_id or baseline.benchmark_id != team.benchmark_id:
            reason = 'incomparable_task'
        elif baseline.regime_digest != team.regime_digest:
            reason = 'incomparable_regime'
        elif baseline.budget_digest != team.budget_digest or baseline.budget_limit_units != team.budget_limit_units:
            reason = 'incomparable_budget'
        elif team.resource_units > team.budget_limit_units:
            reason = 'team_over_budget'
        elif team.false_accepts > baseline.false_accepts or team.regressions > baseline.regressions:
            reason = 'safety_regression'
        elif team.score <= baseline.score:
            reason = 'no_score_improvement'
        else:
            reason = 'matched_budget_improvement'
        improved = reason == 'matched_budget_improvement'
        delta = round(team.score - baseline.score, 12)
        row = _signed(FoundryBenefitAssessment(
            baseline_observation_id=baseline.observation_id,
            team_observation_id=team.observation_id, improved=improved,
            score_delta=delta, reason=reason, digest='',
        ))
        self._assessments.append(row)
        return row

    def outputs(self) -> tuple[FoundryOutputReceipt, ...]:
        return tuple(self._outputs[key] for key in sorted(self._outputs))

    def handoffs(self) -> tuple[FoundryHandoffReceipt, ...]:
        return tuple(self._handoffs[key] for key in sorted(self._handoffs))

    def observations(self) -> tuple[FoundryBenefitObservation, ...]:
        return tuple(self._observations[key] for key in sorted(self._observations))

    def to_state(self) -> dict[str, Any]:
        return {
            'outputs': [row.to_state() for row in self.outputs()],
            'verifications': [self._verifications[key].to_state() for key in sorted(self._verifications)],
            'handoffs': [row.to_state() for row in self.handoffs()],
            'observations': [row.to_state() for row in self.observations()],
            'assessments': [row.to_state() for row in self._assessments],
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        artifacts: ArtifactStore,
        assurance: AssuranceControlPlane,
        state: Mapping[str, Any],
    ) -> 'FoundryEvidenceLedger':
        return cls(
            registry=registry, artifacts=artifacts, assurance=assurance,
            outputs=tuple(FoundryOutputReceipt.from_state(x) for x in state.get('outputs', ())),
            verifications=tuple(FoundryVerificationReceipt.from_state(x) for x in state.get('verifications', ())),
            handoffs=tuple(FoundryHandoffReceipt.from_state(x) for x in state.get('handoffs', ())),
            observations=tuple(FoundryBenefitObservation.from_state(x) for x in state.get('observations', ())),
            assessments=tuple(FoundryBenefitAssessment.from_state(x) for x in state.get('assessments', ())),
        )
