from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r28_repo_world import RepoWorldGraph


_EPSILON = 1e-12
_PROGRESS_BONUS: dict[str, float] = {
    'inspect_tree': 0.05,
    'search_code': 0.12,
    'read_context': 0.25,
    'reproduce_failure': 0.20,
    'query_docs': 0.05,
    'edit_small': 0.25,
    'edit_multi': 0.15,
    'run_targeted_tests': 0.30,
    'run_full_tests': 0.20,
    'inspect_diff': 0.20,
    'revert': 0.15,
    'finish': 0.50,
}


@dataclass(frozen=True, slots=True)
class DebugHypothesis:
    hypothesis_id: str
    target_nodes: frozenset[str]
    prior_probability: float

    def __post_init__(self) -> None:
        if not self.hypothesis_id:
            raise ValueError('hypothesis_id must be non-empty')
        if not self.target_nodes:
            raise ValueError('a hypothesis must target at least one repository node')
        if not 0.0 <= self.prior_probability <= 1.0:
            raise ValueError('prior_probability must be in [0, 1]')


@dataclass(frozen=True, slots=True)
class Evidence:
    source: str
    observed_positive: bool
    likelihood_positive: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError('evidence source must be non-empty')
        for hypothesis_id, likelihood in self.likelihood_positive.items():
            if not hypothesis_id:
                raise ValueError('evidence hypothesis id must be non-empty')
            if not 0.0 <= float(likelihood) <= 1.0:
                raise ValueError('evidence likelihoods must be in [0, 1]')


@dataclass(frozen=True, slots=True)
class EpistemicProbe:
    kind: str
    target_nodes: frozenset[str]
    likelihood_positive: Mapping[str, float]
    base_score: float = 0.0
    cost: float = 0.0
    risk: float = 0.0

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError('probe kind must be non-empty')
        if self.cost < 0.0:
            raise ValueError('probe cost must be non-negative')
        if self.risk < 0.0:
            raise ValueError('probe risk must be non-negative')
        for likelihood in self.likelihood_positive.values():
            if not 0.0 <= float(likelihood) <= 1.0:
                raise ValueError('probe likelihoods must be in [0, 1]')


class HypothesisLedger:
    """Normalized, public-evidence-only epistemic state for competing faults."""

    def __init__(self, hypotheses: Sequence[DebugHypothesis]) -> None:
        if not hypotheses:
            raise ValueError('at least one hypothesis is required')
        ids = [hypothesis.hypothesis_id for hypothesis in hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError('hypothesis ids must be unique')
        total = sum(float(hypothesis.prior_probability) for hypothesis in hypotheses)
        if total <= 0.0:
            raise ValueError('hypothesis priors must contain positive probability mass')
        self._hypotheses = {hypothesis.hypothesis_id: hypothesis for hypothesis in hypotheses}
        self._probabilities = {
            hypothesis.hypothesis_id: float(hypothesis.prior_probability) / total
            for hypothesis in hypotheses
        }

    @property
    def hypotheses(self) -> tuple[DebugHypothesis, ...]:
        return tuple(self._hypotheses.values())

    def probabilities(self) -> dict[str, float]:
        return dict(self._probabilities)

    def probability(self, hypothesis_id: str) -> float:
        return self._probabilities[hypothesis_id]

    def entropy(self) -> float:
        return _entropy(tuple(self._probabilities.values()))

    def update(self, evidence: Evidence) -> None:
        likelihoods = _validated_likelihoods(self._probabilities, evidence.likelihood_positive)
        weighted: dict[str, float] = {}
        for hypothesis_id, prior in self._probabilities.items():
            positive_likelihood = likelihoods[hypothesis_id]
            likelihood = positive_likelihood if evidence.observed_positive else (1.0 - positive_likelihood)
            weighted[hypothesis_id] = prior * likelihood
        total = sum(weighted.values())
        if total <= _EPSILON:
            raise ValueError('evidence has zero probability under every current hypothesis')
        self._probabilities = {
            hypothesis_id: value / total for hypothesis_id, value in weighted.items()
        }

    def target_probability_mass(self, target_nodes: frozenset[str]) -> float:
        if not target_nodes:
            return 0.0
        return sum(
            self._probabilities[hypothesis.hypothesis_id]
            for hypothesis in self._hypotheses.values()
            if hypothesis.target_nodes.intersection(target_nodes)
        )


class ActiveDebugger:
    """Ranks public coding probes by epistemic value, progress, cost and risk."""

    def __init__(
        self,
        *,
        information_gain_weight: float = 1.5,
        target_coverage_weight: float = 0.4,
        cost_weight: float = 0.25,
        risk_weight: float = 0.75,
    ) -> None:
        self.information_gain_weight = float(information_gain_weight)
        self.target_coverage_weight = float(target_coverage_weight)
        self.cost_weight = float(cost_weight)
        self.risk_weight = float(risk_weight)

    def expected_information_gain(
        self, ledger: HypothesisLedger, probe: EpistemicProbe
    ) -> float:
        priors = ledger.probabilities()
        likelihoods = _validated_likelihoods(priors, probe.likelihood_positive)
        current_entropy = _entropy(tuple(priors.values()))
        p_positive = sum(priors[hypothesis_id] * likelihoods[hypothesis_id] for hypothesis_id in priors)
        p_negative = 1.0 - p_positive

        expected_posterior_entropy = 0.0
        if p_positive > _EPSILON:
            positive_posterior = tuple(
                priors[hypothesis_id] * likelihoods[hypothesis_id] / p_positive
                for hypothesis_id in priors
            )
            expected_posterior_entropy += p_positive * _entropy(positive_posterior)
        if p_negative > _EPSILON:
            negative_posterior = tuple(
                priors[hypothesis_id] * (1.0 - likelihoods[hypothesis_id]) / p_negative
                for hypothesis_id in priors
            )
            expected_posterior_entropy += p_negative * _entropy(negative_posterior)
        return max(0.0, current_entropy - expected_posterior_entropy)

    def utility(
        self,
        graph: RepoWorldGraph,
        ledger: HypothesisLedger,
        probe: EpistemicProbe,
    ) -> float:
        information_gain = self.expected_information_gain(ledger, probe)
        target_coverage = ledger.target_probability_mass(probe.target_nodes)
        structural_risk = 0.0
        if probe.kind in {'edit_small', 'edit_multi'} and probe.target_nodes:
            structural_risk = graph.edit_risk(probe.target_nodes)
        total_risk = min(1.0, float(probe.risk) + structural_risk)
        progress = _PROGRESS_BONUS.get(probe.kind, 0.0)
        return (
            float(probe.base_score)
            + self.information_gain_weight * information_gain
            + self.target_coverage_weight * target_coverage
            + progress
            - self.cost_weight * float(probe.cost)
            - self.risk_weight * total_risk
        )

    def rank_probes(
        self,
        graph: RepoWorldGraph,
        ledger: HypothesisLedger,
        probes: Sequence[EpistemicProbe],
    ) -> list[tuple[EpistemicProbe, float]]:
        scored = [(probe, self.utility(graph, ledger, probe)) for probe in probes]
        return sorted(scored, key=lambda item: (-item[1], item[0].kind, tuple(sorted(item[0].target_nodes))))


def _validated_likelihoods(
    hypotheses: Mapping[str, float], likelihoods: Mapping[str, float]
) -> dict[str, float]:
    missing = set(hypotheses).difference(likelihoods)
    extra = set(likelihoods).difference(hypotheses)
    if missing or extra:
        raise ValueError(
            f'likelihood keys must exactly match hypotheses; missing={sorted(missing)}, extra={sorted(extra)}'
        )
    return {hypothesis_id: float(likelihoods[hypothesis_id]) for hypothesis_id in hypotheses}


def _entropy(probabilities: Sequence[float]) -> float:
    return -sum(probability * math.log2(probability) for probability in probabilities if probability > _EPSILON)
