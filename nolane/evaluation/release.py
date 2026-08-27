from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.external_core.artifacts import ArtifactStore
from nolane.evaluation.evidence import EvaluationEvidenceLedger
from nolane.evaluation.parameters import ParameterScalingAuthority
from nolane.evaluation.regimes import BenchmarkRegimeRegistry
from nolane.evaluation.stress import LongHorizonStressLedger
from nolane.organization.identity import AgentRegistry
from nolane.core.canonical_digest import canonical_digest


@dataclass(frozen=True, slots=True)
class EvaluationReleaseReceipt:
    release_id: str
    release_version: str
    source_commit_sha: str
    regime_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    comparison_ids: tuple[str, ...]
    stress_assessment_ids: tuple[str, ...]
    parameter_report_id: str
    claim_assessment_ids: tuple[str, ...]
    scaling_decision_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    artifact_digests: tuple[str, ...]
    evaluator_protocol_version: str
    independent_evaluator_ids: tuple[str, ...]
    reproduction_command_digest: str
    environment_toolchain_digest: str
    created_logical_epoch: int
    evaluation_digest: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'release_id': self.release_id, 'release_version': self.release_version,
            'source_commit_sha': self.source_commit_sha, 'regime_ids': list(self.regime_ids),
            'observation_ids': list(self.observation_ids), 'comparison_ids': list(self.comparison_ids),
            'stress_assessment_ids': list(self.stress_assessment_ids), 'parameter_report_id': self.parameter_report_id,
            'claim_assessment_ids': list(self.claim_assessment_ids), 'scaling_decision_ids': list(self.scaling_decision_ids),
            'artifact_ids': list(self.artifact_ids), 'artifact_digests': list(self.artifact_digests),
            'evaluator_protocol_version': self.evaluator_protocol_version,
            'independent_evaluator_ids': list(self.independent_evaluator_ids),
            'reproduction_command_digest': self.reproduction_command_digest,
            'environment_toolchain_digest': self.environment_toolchain_digest,
            'created_logical_epoch': self.created_logical_epoch, 'evaluation_digest': self.evaluation_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'EvaluationReleaseReceipt':
        row = cls(
            release_id=str(state['release_id']), release_version=str(state['release_version']),
            source_commit_sha=str(state['source_commit_sha']), regime_ids=tuple(str(x) for x in state.get('regime_ids', ())),
            observation_ids=tuple(str(x) for x in state.get('observation_ids', ())),
            comparison_ids=tuple(str(x) for x in state.get('comparison_ids', ())),
            stress_assessment_ids=tuple(str(x) for x in state.get('stress_assessment_ids', ())),
            parameter_report_id=str(state['parameter_report_id']),
            claim_assessment_ids=tuple(str(x) for x in state.get('claim_assessment_ids', ())),
            scaling_decision_ids=tuple(str(x) for x in state.get('scaling_decision_ids', ())),
            artifact_ids=tuple(str(x) for x in state.get('artifact_ids', ())),
            artifact_digests=tuple(str(x) for x in state.get('artifact_digests', ())),
            evaluator_protocol_version=str(state['evaluator_protocol_version']),
            independent_evaluator_ids=tuple(str(x) for x in state.get('independent_evaluator_ids', ())),
            reproduction_command_digest=str(state['reproduction_command_digest']),
            environment_toolchain_digest=str(state['environment_toolchain_digest']),
            created_logical_epoch=int(state['created_logical_epoch']), evaluation_digest=str(state['evaluation_digest']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('evaluation release receipt digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ReproductionReceipt:
    reproduction_id: str
    release_id: str
    evaluator_id: str
    release_digest: str
    artifact_digest: str
    evaluator_protocol_version: str
    reproduction_command_digest: str
    environment_toolchain_digest: str
    passed: bool
    independent: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'reproduction_id': self.reproduction_id, 'release_id': self.release_id,
            'evaluator_id': self.evaluator_id, 'release_digest': self.release_digest,
            'artifact_digest': self.artifact_digest, 'evaluator_protocol_version': self.evaluator_protocol_version,
            'reproduction_command_digest': self.reproduction_command_digest,
            'environment_toolchain_digest': self.environment_toolchain_digest,
            'passed': self.passed, 'independent': self.independent,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ReproductionReceipt':
        row = cls(
            reproduction_id=str(state['reproduction_id']), release_id=str(state['release_id']),
            evaluator_id=str(state['evaluator_id']), release_digest=str(state['release_digest']),
            artifact_digest=str(state['artifact_digest']), evaluator_protocol_version=str(state['evaluator_protocol_version']),
            reproduction_command_digest=str(state['reproduction_command_digest']),
            environment_toolchain_digest=str(state['environment_toolchain_digest']), passed=bool(state['passed']),
            independent=bool(state['independent']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('evaluation reproduction receipt digest mismatch')
        return row


class EvaluationReleaseLedger:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        artifacts: ArtifactStore,
        regimes: BenchmarkRegimeRegistry,
        evidence: EvaluationEvidenceLedger,
        stress: LongHorizonStressLedger,
        parameters: ParameterScalingAuthority,
        releases: tuple[EvaluationReleaseReceipt, ...] = (),
        reproductions: tuple[ReproductionReceipt, ...] = (),
    ) -> None:
        self.registry = registry
        self.artifacts = artifacts
        self.regimes = regimes
        self.evidence = evidence
        self.stress = stress
        self.parameters = parameters
        self._releases: dict[str, EvaluationReleaseReceipt] = {}
        self._reproductions: dict[str, ReproductionReceipt] = {}
        for row in releases:
            self._validate_release(row)
            if row.release_id in self._releases:
                raise ValueError('duplicate evaluation release id')
            self._releases[row.release_id] = row
        for row in reproductions:
            self._validate_reproduction(row)
            if row.reproduction_id in self._reproductions:
                raise ValueError('duplicate reproduction id')
            self._reproductions[row.reproduction_id] = row

    def _organization_ids(self) -> set[str]:
        return {x.agent_id for x in self.registry.identities()}

    def _validate_release(self, row: EvaluationReleaseReceipt) -> None:
        if len(row.source_commit_sha) != 40 or any(ch not in '0123456789abcdefABCDEF' for ch in row.source_commit_sha):
            raise ValueError('release source commit must be a full 40-hex SHA')
        if not all(str(x).strip() for x in (
            row.release_id, row.release_version, row.parameter_report_id, row.evaluator_protocol_version,
            row.reproduction_command_digest, row.environment_toolchain_digest, row.evaluation_digest,
        )):
            raise ValueError('evaluation release identity/protocol/environment fields must be explicit')
        if row.created_logical_epoch < 0 or not row.regime_ids or not row.observation_ids or not row.artifact_ids:
            raise ValueError('evaluation release requires non-negative epoch and core evidence references')
        if len(row.artifact_ids) != len(row.artifact_digests):
            raise ValueError('release artifact id/digest cardinality mismatch')
        for regime_id in row.regime_ids:
            self.regimes.get(regime_id)
        for observation_id in row.observation_ids:
            self.evidence.get_observation(observation_id)
        for comparison_id in row.comparison_ids:
            self.evidence.get_comparison(comparison_id)
        for stress_id in row.stress_assessment_ids:
            self.stress.get_assessment(stress_id)
        self.parameters.get_report(row.parameter_report_id)
        for decision_id in row.scaling_decision_ids:
            self.parameters.get_decision(decision_id)
        expected_digests = tuple(self.artifacts.get(artifact_id).digest for artifact_id in row.artifact_ids)
        if expected_digests != row.artifact_digests:
            raise ValueError('release artifact digest mismatch')
        if any(evaluator in self._organization_ids() for evaluator in row.independent_evaluator_ids):
            raise PermissionError('release independent evaluator cannot be permanent organization identity')
        expected_eval_digest = canonical_digest({
            'regime_ids': list(row.regime_ids), 'observation_ids': list(row.observation_ids),
            'comparison_ids': list(row.comparison_ids), 'stress_assessment_ids': list(row.stress_assessment_ids),
            'parameter_report_id': row.parameter_report_id, 'claim_assessment_ids': list(row.claim_assessment_ids),
            'scaling_decision_ids': list(row.scaling_decision_ids), 'artifact_digests': list(row.artifact_digests),
        })
        if row.evaluation_digest != expected_eval_digest:
            raise ValueError('evaluation release aggregate digest mismatch')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('evaluation release receipt digest mismatch')

    def create_release(self, **kwargs: Any) -> EvaluationReleaseReceipt:
        regime_ids = tuple(str(x) for x in kwargs['regime_ids'])
        observation_ids = tuple(str(x) for x in kwargs['observation_ids'])
        comparison_ids = tuple(str(x) for x in kwargs['comparison_ids'])
        stress_ids = tuple(str(x) for x in kwargs['stress_assessment_ids'])
        claim_ids = tuple(str(x) for x in kwargs['claim_assessment_ids'])
        scaling_ids = tuple(str(x) for x in kwargs['scaling_decision_ids'])
        artifact_ids = tuple(str(x) for x in kwargs['artifact_ids'])
        artifact_digests = tuple(self.artifacts.get(x).digest for x in artifact_ids)
        parameter_report_id = str(kwargs['parameter_report_id'])
        evaluation_digest = canonical_digest({
            'regime_ids': list(regime_ids), 'observation_ids': list(observation_ids),
            'comparison_ids': list(comparison_ids), 'stress_assessment_ids': list(stress_ids),
            'parameter_report_id': parameter_report_id, 'claim_assessment_ids': list(claim_ids),
            'scaling_decision_ids': list(scaling_ids), 'artifact_digests': list(artifact_digests),
        })
        row0 = EvaluationReleaseReceipt(
            release_id=str(kwargs['release_id']), release_version=str(kwargs['release_version']),
            source_commit_sha=str(kwargs['source_commit_sha']), regime_ids=regime_ids, observation_ids=observation_ids,
            comparison_ids=comparison_ids, stress_assessment_ids=stress_ids, parameter_report_id=parameter_report_id,
            claim_assessment_ids=claim_ids, scaling_decision_ids=scaling_ids, artifact_ids=artifact_ids,
            artifact_digests=artifact_digests, evaluator_protocol_version=str(kwargs['evaluator_protocol_version']),
            independent_evaluator_ids=tuple(sorted({str(x) for x in kwargs['independent_evaluator_ids']})),
            reproduction_command_digest=str(kwargs['reproduction_command_digest']),
            environment_toolchain_digest=str(kwargs['environment_toolchain_digest']),
            created_logical_epoch=int(kwargs['created_logical_epoch']), evaluation_digest=evaluation_digest, digest='',
        )
        row = EvaluationReleaseReceipt(
            release_id=row0.release_id, release_version=row0.release_version, source_commit_sha=row0.source_commit_sha,
            regime_ids=row0.regime_ids, observation_ids=row0.observation_ids, comparison_ids=row0.comparison_ids,
            stress_assessment_ids=row0.stress_assessment_ids, parameter_report_id=row0.parameter_report_id,
            claim_assessment_ids=row0.claim_assessment_ids, scaling_decision_ids=row0.scaling_decision_ids,
            artifact_ids=row0.artifact_ids, artifact_digests=row0.artifact_digests,
            evaluator_protocol_version=row0.evaluator_protocol_version, independent_evaluator_ids=row0.independent_evaluator_ids,
            reproduction_command_digest=row0.reproduction_command_digest,
            environment_toolchain_digest=row0.environment_toolchain_digest,
            created_logical_epoch=row0.created_logical_epoch, evaluation_digest=row0.evaluation_digest,
            digest=canonical_digest(row0.payload()),
        )
        self._validate_release(row)
        existing = self._releases.get(row.release_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('evaluation release id cannot be rebound')
        self._releases[row.release_id] = row
        return row

    def get_release(self, release_id: str) -> EvaluationReleaseReceipt:
        try:
            return self._releases[str(release_id)]
        except KeyError as exc:
            raise KeyError(f'unknown evaluation release: {release_id}') from exc

    def _validate_reproduction(self, row: ReproductionReceipt) -> None:
        release = self.get_release(row.release_id)
        expected_independent = row.evaluator_id not in self._organization_ids()
        if row.independent != expected_independent:
            raise ValueError('reproduction independence flag is non-canonical')
        if row.release_digest != release.digest:
            raise ValueError('reproduction targets different release digest')
        if row.artifact_digest not in release.artifact_digests:
            raise ValueError('reproduction artifact digest is outside release')
        if row.evaluator_protocol_version != release.evaluator_protocol_version:
            raise ValueError('reproduction protocol mismatch')
        if row.reproduction_command_digest != release.reproduction_command_digest:
            raise ValueError('reproduction command mismatch')
        if row.environment_toolchain_digest != release.environment_toolchain_digest:
            raise ValueError('reproduction environment mismatch')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('reproduction receipt digest mismatch')

    def record_reproduction(self, **kwargs: Any) -> ReproductionReceipt:
        release = self.get_release(str(kwargs['release_id']))
        evaluator_id = str(kwargs['evaluator_id'])
        independent = evaluator_id not in self._organization_ids()
        payload0 = {
            'release_id': release.release_id, 'evaluator_id': evaluator_id,
            'release_digest': str(kwargs['release_digest']), 'artifact_digest': str(kwargs['artifact_digest']),
            'evaluator_protocol_version': str(kwargs['evaluator_protocol_version']),
            'reproduction_command_digest': str(kwargs['reproduction_command_digest']),
            'environment_toolchain_digest': str(kwargs['environment_toolchain_digest']),
            'passed': bool(kwargs['passed']), 'independent': independent,
        }
        reproduction_id = 'eval-reproduction-' + canonical_digest(payload0)[:24]
        payload = {'reproduction_id': reproduction_id, **payload0}
        row = ReproductionReceipt(
            reproduction_id=reproduction_id, release_id=release.release_id, evaluator_id=evaluator_id,
            release_digest=payload0['release_digest'], artifact_digest=payload0['artifact_digest'],
            evaluator_protocol_version=payload0['evaluator_protocol_version'],
            reproduction_command_digest=payload0['reproduction_command_digest'],
            environment_toolchain_digest=payload0['environment_toolchain_digest'], passed=payload0['passed'],
            independent=independent, digest=canonical_digest(payload),
        )
        self._validate_reproduction(row)
        self._reproductions.setdefault(row.reproduction_id, row)
        return self._reproductions[row.reproduction_id]

    def get_reproduction(self, reproduction_id: str) -> ReproductionReceipt:
        try:
            return self._reproductions[str(reproduction_id)]
        except KeyError as exc:
            raise KeyError(f'unknown reproduction receipt: {reproduction_id}') from exc

    def is_externally_reproducible(self, release_id: str) -> bool:
        release = self.get_release(release_id)
        return any(
            row.release_id == release.release_id and row.passed and row.independent
            for row in self._reproductions.values()
        )

    def is_reproduction_valid(self, reproduction_id: str) -> bool:
        try:
            row = self.get_reproduction(reproduction_id)
        except KeyError:
            return False
        return row.passed and row.independent and self.is_externally_reproducible(row.release_id)

    def to_state(self) -> dict[str, Any]:
        return {
            'releases': [self._releases[k].to_state() for k in sorted(self._releases)],
            'reproductions': [self._reproductions[k].to_state() for k in sorted(self._reproductions)],
        }

    @classmethod
    def from_state(
        cls, *, registry: AgentRegistry, artifacts: ArtifactStore, regimes: BenchmarkRegimeRegistry,
        evidence: EvaluationEvidenceLedger, stress: LongHorizonStressLedger,
        parameters: ParameterScalingAuthority, state: Mapping[str, Any]
    ) -> 'EvaluationReleaseLedger':
        return cls(
            registry=registry, artifacts=artifacts, regimes=regimes, evidence=evidence, stress=stress, parameters=parameters,
            releases=tuple(EvaluationReleaseReceipt.from_state(x) for x in state.get('releases', ())),
            reproductions=tuple(ReproductionReceipt.from_state(x) for x in state.get('reproductions', ())),
        )


COMPONENT_ID = "evaluation.release"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.evaluation_release"
