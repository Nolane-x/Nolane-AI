from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from .r220_operator_discovery import ProposalSupport


@dataclass(frozen=True)
class ChannelInformation:
    observed_true_probability: float
    expected_entropy_reduction: float
    expected_margin_gain: float
    information_per_cost: float


def _entropy(probs: Sequence[float]) -> float:
    return -sum(p * math.log(max(float(p), 1e-15)) for p in probs)


def _margin(probs: Sequence[float]) -> float:
    ranked = sorted((float(p) for p in probs), reverse=True)
    if not ranked:
        return 0.0
    return ranked[0] - (ranked[1] if len(ranked) > 1 else 0.0)


def _posterior_for_observation(
    supports: Sequence[ProposalSupport],
    predicted_labels: Mapping[str, bool],
    *,
    reliability: float,
    observed_label: bool,
) -> tuple[float, ...]:
    weights = []
    for row in supports:
        predicted = bool(predicted_labels[row.operator_id])
        like = reliability if predicted == observed_label else 1.0 - reliability
        weights.append(float(row.posterior) * like)
    total = sum(weights)
    if total <= 0.0:
        raise ValueError('observation has zero probability under posterior')
    return tuple(w / total for w in weights)


def expected_channel_information(
    supports: Sequence[ProposalSupport],
    predicted_labels: Mapping[str, bool],
    *,
    reliability: float,
    cost: float,
) -> ChannelInformation:
    supports = tuple(supports)
    if not supports:
        raise ValueError('supports must be non-empty')
    ids = {row.operator_id for row in supports}
    if set(predicted_labels) != ids:
        raise ValueError('prediction coverage mismatch')
    reliability = float(reliability)
    cost = float(cost)
    if not 0.5 < reliability <= 1.0:
        raise ValueError('reliability must be in (0.5, 1.0]')
    if not math.isfinite(cost) or cost <= 0.0:
        raise ValueError('cost must be finite and positive')
    prior = tuple(float(row.posterior) for row in supports)
    total = sum(prior)
    if total <= 0.0 or not math.isfinite(total):
        raise ValueError('posterior mass must be finite and positive')
    prior = tuple(p / total for p in prior)
    p_true = sum(
        p * (reliability if bool(predicted_labels[row.operator_id]) else 1.0 - reliability)
        for row, p in zip(supports, prior)
    )
    p_false = 1.0 - p_true
    post_true = _posterior_for_observation(
        supports, predicted_labels, reliability=reliability, observed_label=True,
    )
    post_false = _posterior_for_observation(
        supports, predicted_labels, reliability=reliability, observed_label=False,
    )
    prior_entropy = _entropy(prior)
    expected_entropy = p_true * _entropy(post_true) + p_false * _entropy(post_false)
    entropy_reduction = max(0.0, prior_entropy - expected_entropy)
    prior_margin = _margin(prior)
    expected_margin = p_true * _margin(post_true) + p_false * _margin(post_false)
    margin_gain = expected_margin - prior_margin
    return ChannelInformation(
        observed_true_probability=float(p_true),
        expected_entropy_reduction=float(entropy_reduction),
        expected_margin_gain=float(margin_gain),
        information_per_cost=float(entropy_reduction / cost),
    )
