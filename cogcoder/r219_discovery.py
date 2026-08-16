from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence

from .r219_representation_types import (
    DiscoveryDecision,
    HypothesisSupport,
    RepresentationHypothesis,
    VerifierObservation,
)

_EPS = 1e-15


def _normalize_supports(log_likelihoods: Mapping[str, float]) -> dict[str, float]:
    if not log_likelihoods:
        return {}
    finite = [v for v in log_likelihoods.values() if math.isfinite(v)]
    if not finite:
        n = len(log_likelihoods)
        return {key: 1.0 / n for key in log_likelihoods}
    max_ll = max(finite)
    weights = {key: (math.exp(value - max_ll) if math.isfinite(value) else 0.0) for key, value in log_likelihoods.items()}
    total = sum(weights.values())
    if total <= 0:
        n = len(weights)
        return {key: 1.0 / n for key in weights}
    return {key: value / total for key, value in weights.items()}


def initial_supports(hypotheses: Sequence[RepresentationHypothesis]) -> tuple[HypothesisSupport, ...]:
    hypotheses = tuple(hypotheses)
    if not hypotheses:
        raise ValueError('hypotheses must be non-empty')
    p = 1.0 / len(hypotheses)
    return tuple(HypothesisSupport(h.representation_id, 0.0, p) for h in hypotheses)


def update_supports(hypotheses: Sequence[RepresentationHypothesis], supports: Sequence[HypothesisSupport], observation: VerifierObservation, predicted_labels: Mapping[str, bool]) -> tuple[HypothesisSupport, ...]:
    hypotheses = tuple(hypotheses)
    by_support = {row.representation_id: row for row in supports}
    ids = {h.representation_id for h in hypotheses}
    if set(by_support) != ids:
        raise ValueError('supports must cover hypotheses exactly')
    if set(predicted_labels) != ids:
        raise ValueError('predicted_labels must cover hypotheses exactly')
    log_rows: dict[str, float] = {}
    reliability = observation.reliability
    for h in hypotheses:
        prior_ll = by_support[h.representation_id].log_likelihood
        predicted = bool(predicted_labels[h.representation_id])
        likelihood = reliability if predicted == observation.observed_label else 1.0 - reliability
        log_rows[h.representation_id] = prior_ll + math.log(max(_EPS, likelihood))
    posterior = _normalize_supports(log_rows)
    return tuple(HypothesisSupport(h.representation_id, log_rows[h.representation_id], posterior[h.representation_id]) for h in hypotheses)


def choose_query(hypotheses: Sequence[RepresentationHypothesis], supports: Sequence[HypothesisSupport], candidates: Sequence[str], predictions: Mapping[str, Mapping[str, bool]]) -> str:
    hypotheses = tuple(hypotheses)
    if not candidates:
        raise ValueError('candidates must be non-empty')
    by_support = {row.representation_id: row.posterior for row in supports}
    ids = {h.representation_id for h in hypotheses}
    if set(by_support) != ids:
        raise ValueError('supports must cover hypotheses exactly')
    scored: list[tuple[float, str]] = []
    for query_id in candidates:
        row = predictions[query_id]
        if set(row) != ids:
            raise ValueError('each prediction row must cover hypotheses exactly')
        p_true = sum(by_support[rid] for rid, label in row.items() if bool(label))
        disagreement = 2.0 * p_true * (1.0 - p_true)
        scored.append((-disagreement, str(query_id)))
    scored.sort()
    return scored[0][1]


def _top_two(supports: Sequence[HypothesisSupport]) -> tuple[HypothesisSupport, HypothesisSupport | None]:
    ranked = sorted(supports, key=lambda row: (-row.posterior, row.representation_id))
    return ranked[0], (ranked[1] if len(ranked) > 1 else None)


def discover_representation(hypotheses: Sequence[RepresentationHypothesis], query_ids: Sequence[str], predictions: Mapping[str, Mapping[str, bool]], *, verifier: Callable[[str], VerifierObservation], counterexample_check: Callable[[RepresentationHypothesis], bool], query_budget: int, accept_probability: float, accept_margin: float) -> DiscoveryDecision:
    hypotheses = tuple(hypotheses)
    if not hypotheses:
        raise ValueError('hypotheses must be non-empty')
    if int(query_budget) < 0:
        raise ValueError('query_budget must be non-negative')
    if not 0.0 < float(accept_probability) <= 1.0:
        raise ValueError('accept_probability must be in (0,1]')
    if not 0.0 <= float(accept_margin) <= 1.0:
        raise ValueError('accept_margin must be in [0,1]')
    by_h = {h.representation_id: h for h in hypotheses}
    supports = initial_supports(hypotheses)
    remaining = list(dict.fromkeys(str(q) for q in query_ids))
    queried: list[str] = []
    max_queries = min(int(query_budget), len(remaining))
    for _ in range(max_queries):
        query_id = choose_query(hypotheses, supports, remaining, predictions)
        observation = verifier(query_id)
        if observation.query_id != query_id:
            raise ValueError('verifier returned observation for wrong query')
        supports = update_supports(hypotheses, supports, observation, predictions[query_id])
        queried.append(query_id)
        remaining.remove(query_id)
        top, second = _top_two(supports)
        margin = top.posterior - (second.posterior if second else 0.0)
        if top.posterior >= accept_probability and margin >= accept_margin:
            candidate = by_h[top.representation_id]
            if counterexample_check(candidate):
                return DiscoveryDecision('accept', top.representation_id, top.posterior, margin, tuple(queried), 'unique_supported_representation_survived_counterexample')
            return DiscoveryDecision('abstain', None, top.posterior, margin, tuple(queried), 'counterexample_rejected_top_representation')
    top, second = _top_two(supports)
    margin = top.posterior - (second.posterior if second else 0.0)
    return DiscoveryDecision('abstain', None, top.posterior, margin, tuple(queried), 'insufficient_identifiability_or_budget')
