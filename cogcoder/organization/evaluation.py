from __future__ import annotations

from typing import Any, Mapping

from .artifacts import ArtifactStore
from .evaluation_claims import ClaimBoundaryEngine
from .evaluation_evidence import EvaluationEvidenceLedger
from .evaluation_parameters import ParameterScalingAuthority
from .evaluation_regimes import BenchmarkRegimeRegistry
from .evaluation_release import EvaluationReleaseLedger
from .evaluation_stress import LongHorizonStressLedger
from .registry import AgentRegistry


class EvaluationScalingControlPlane:
    """Fail-closed Part-XV organization evaluation and future-scaling evidence boundary."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        artifacts: ArtifactStore,
        regimes: BenchmarkRegimeRegistry | None = None,
        evidence: EvaluationEvidenceLedger | None = None,
        stress: LongHorizonStressLedger | None = None,
        parameters: ParameterScalingAuthority | None = None,
        releases: EvaluationReleaseLedger | None = None,
        claims: ClaimBoundaryEngine | None = None,
    ) -> None:
        self.registry = registry
        self.artifacts = artifacts
        self.regimes = regimes or BenchmarkRegimeRegistry()
        self.evidence = evidence or EvaluationEvidenceLedger(registry=registry, regimes=self.regimes)
        self.stress = stress or LongHorizonStressLedger(registry=registry)
        self.parameters = parameters or ParameterScalingAuthority(registry=registry, evidence=self.evidence)
        self.releases = releases or EvaluationReleaseLedger(
            registry=registry,
            artifacts=artifacts,
            regimes=self.regimes,
            evidence=self.evidence,
            stress=self.stress,
            parameters=self.parameters,
        )
        self.claims = claims or ClaimBoundaryEngine(
            registry=registry,
            regimes=self.regimes,
            evidence=self.evidence,
            stress=self.stress,
            releases=self.releases,
        )
        self.claims.bind_release_ledger(self.releases)

    def is_empty(self) -> bool:
        state = self.to_state()
        return all(
            not value
            for section in state.values()
            for value in (
                section.get('regimes', ()) if isinstance(section, Mapping) else (),
                section.get('observations', ()) if isinstance(section, Mapping) else (),
                section.get('comparisons', ()) if isinstance(section, Mapping) else (),
                section.get('ablations', ()) if isinstance(section, Mapping) else (),
                section.get('assessments', ()) if isinstance(section, Mapping) else (),
                section.get('reports', ()) if isinstance(section, Mapping) else (),
                section.get('proposals', ()) if isinstance(section, Mapping) else (),
                section.get('decisions', ()) if isinstance(section, Mapping) else (),
                section.get('releases', ()) if isinstance(section, Mapping) else (),
                section.get('reproductions', ()) if isinstance(section, Mapping) else (),
                section.get('readiness_reports', ()) if isinstance(section, Mapping) else (),
            )
        )

    def to_state(self) -> dict[str, Any]:
        return {
            'regimes': self.regimes.to_state(),
            'evidence': self.evidence.to_state(),
            'stress': self.stress.to_state(),
            'parameters': self.parameters.to_state(),
            'releases': self.releases.to_state(),
            'claims': self.claims.to_state(),
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        artifacts: ArtifactStore,
        state: Mapping[str, Any],
    ) -> 'EvaluationScalingControlPlane':
        regimes = BenchmarkRegimeRegistry.from_state(state.get('regimes', {}))
        evidence = EvaluationEvidenceLedger.from_state(
            registry=registry, regimes=regimes, state=state.get('evidence', {}),
        )
        stress = LongHorizonStressLedger.from_state(
            registry=registry, state=state.get('stress', {}),
        )
        parameters = ParameterScalingAuthority.from_state(
            registry=registry, evidence=evidence, state=state.get('parameters', {}),
        )
        releases = EvaluationReleaseLedger.from_state(
            registry=registry, artifacts=artifacts, regimes=regimes, evidence=evidence,
            stress=stress, parameters=parameters, state=state.get('releases', {}),
        )
        claims = ClaimBoundaryEngine.from_state(
            registry=registry, regimes=regimes, evidence=evidence, stress=stress,
            releases=releases, state=state.get('claims', {}),
        )
        return cls(
            registry=registry, artifacts=artifacts, regimes=regimes, evidence=evidence,
            stress=stress, parameters=parameters, releases=releases, claims=claims,
        )
