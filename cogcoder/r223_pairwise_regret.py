from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from benchmarks.kfigg import r220_language_synthesis as r220

from .r220_operator_discovery import choose_operator_query, initial_proposal_supports
from .r222_counterfactual_trainer import (
    ACTIONS,
    _meta_state,
    _oracle_value,
    _proposal_library,
    _transition,
)
from .r222_voi_types import VerifierRegime, expand_meta_features, extract_meta_features
from .r222_value_model import RidgeValueModel
from .r223_information_anchor import expected_channel_information

PAIRS = ('cheap_minus_strong', 'stop_minus_strong')


@dataclass(frozen=True)
class PairwiseExample:
    regime_id: str
    features: tuple[float, ...]
    cheap_minus_strong: float
    stop_minus_strong: float

    def __post_init__(self) -> None:
        regime_id = str(self.regime_id).strip().lower()
        features = tuple(float(v) for v in self.features)
        if not regime_id:
            raise ValueError('regime_id must be non-empty')
        if not features:
            raise ValueError('features must be non-empty')
        object.__setattr__(self, 'regime_id', regime_id)
        object.__setattr__(self, 'features', features)
        object.__setattr__(self, 'cheap_minus_strong', float(self.cheap_minus_strong))
        object.__setattr__(self, 'stop_minus_strong', float(self.stop_minus_strong))


@dataclass(frozen=True)
class PairwiseMember:
    omitted_regime_id: str
    models: Mapping[str, RidgeValueModel]

    def __post_init__(self) -> None:
        if set(self.models) != set(PAIRS):
            raise ValueError('models must cover all pairwise targets')
        if not str(self.omitted_regime_id).strip():
            raise ValueError('omitted_regime_id must be non-empty')

    def to_payload(self) -> dict:
        return {
            'omitted_regime_id': str(self.omitted_regime_id),
            'models': {name: self.models[name].to_payload() for name in PAIRS},
        }


@dataclass(frozen=True)
class AdvantageDistribution:
    values: tuple[float, ...]
    mean: float
    q25: float
    q75: float
    spread: float


@dataclass(frozen=True)
class PairwiseRegretEnsemble:
    members: tuple[PairwiseMember, ...]
    training_regime_ids: tuple[str, ...]
    training_seed_count: int
    example_count: int
    lambda_cost: float
    rollout_depth: int
    max_steps: int
    l2: float
    unresolved_stop_penalty: float = 0.0

    def __post_init__(self) -> None:
        members = tuple(self.members)
        regime_ids = tuple(str(v) for v in self.training_regime_ids)
        if len(members) < 2:
            raise ValueError('ensemble requires at least two members')
        if {m.omitted_regime_id for m in members} != set(regime_ids):
            raise ValueError('members must omit each training regime exactly once')
        object.__setattr__(self, 'members', members)
        object.__setattr__(self, 'training_regime_ids', regime_ids)

    def advantage_distribution(self, features: Sequence[float], pair: str) -> AdvantageDistribution:
        if pair not in PAIRS:
            raise ValueError('unknown pairwise target')
        values = tuple(float(member.models[pair].predict(features)) for member in self.members)
        ordered = sorted(values)
        n = len(ordered)
        q25 = ordered[int(0.25 * (n - 1))]
        q75 = ordered[int(0.75 * (n - 1))]
        return AdvantageDistribution(
            values=values,
            mean=sum(values) / n,
            q25=q25,
            q75=q75,
            spread=max(values) - min(values),
        )

    def to_payload(self) -> dict:
        return {
            'schema_version': 1,
            'pairs': list(PAIRS),
            'members': [member.to_payload() for member in self.members],
            'training_regime_ids': list(self.training_regime_ids),
            'training_seed_count': int(self.training_seed_count),
            'example_count': int(self.example_count),
            'lambda_cost': float(self.lambda_cost),
            'rollout_depth': int(self.rollout_depth),
            'max_steps': int(self.max_steps),
            'l2': float(self.l2),
            'unresolved_stop_penalty': float(self.unresolved_stop_penalty),
        }

    def to_canonical_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, separators=(',', ':'), allow_nan=False)

    @property
    def bundle_hash(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode('utf-8')).hexdigest()


def _pairwise_features(supports, remaining, predictions, *, queries_used: int, max_queries: int,
                       accumulated_cost: float, regime: VerifierRegime) -> tuple[float, ...]:
    state = _meta_state(
        supports,
        remaining,
        predictions,
        queries_used=queries_used,
        max_queries=max_queries,
        accumulated_cost=accumulated_cost,
        regime=regime,
    )
    base = expand_meta_features(extract_meta_features(state))
    if not remaining:
        return tuple(base) + (0.0,) * 7
    proposals = _proposal_library()
    q = choose_operator_query(proposals, supports, remaining, predictions)
    labels = predictions[q]
    cheap = expected_channel_information(
        supports, labels, reliability=regime.cheap.reliability, cost=regime.cheap.cost,
    )
    strong = expected_channel_information(
        supports, labels, reliability=regime.strong.reliability, cost=regime.strong.cost,
    )
    analytic = (
        cheap.expected_entropy_reduction,
        cheap.expected_margin_gain,
        cheap.information_per_cost,
        strong.expected_entropy_reduction,
        strong.expected_margin_gain,
        strong.information_per_cost,
        cheap.information_per_cost - strong.information_per_cost,
    )
    return tuple(float(v) for v in (*base, *analytic))


def generate_pairwise_examples(
    training_regimes: Sequence[VerifierRegime],
    training_seeds: Sequence[int],
    *,
    lambda_cost: float,
    rollout_depth: int,
    max_steps: int,
    unresolved_stop_penalty: float = 0.0,
) -> tuple[PairwiseExample, ...]:
    regimes = tuple(training_regimes)
    seeds = tuple(int(seed) for seed in training_seeds)
    if len(regimes) < 2 or not seeds:
        raise ValueError('at least two regimes and one seed are required')
    if len({r.regime_id for r in regimes}) != len(regimes):
        raise ValueError('training regime ids must be unique')
    if int(rollout_depth) < 1 or int(max_steps) < 1:
        raise ValueError('rollout_depth and max_steps must be positive')

    proposals = _proposal_library()
    out: list[PairwiseExample] = []
    for regime in regimes:
        for seed in seeds:
            target = r220._target(seed)
            rows = r220._raw_rows(target, r220._latent_step_a)
            predictions = r220._predictions(proposals, rows, r220._latent_step_a)
            byrow = {row[0]: row for row in rows}
            equiv = set(r220._target_equiv(proposals, target, rows, r220._latent_step_a))
            supports = initial_proposal_supports(proposals, complexity_weight=r220.COMPLEXITY_WEIGHT)
            remaining = tuple(row[0] for row in rows)
            accumulated_cost = 0.0
            max_queries = min(int(max_steps), len(remaining))
            for step in range(max_queries):
                features = _pairwise_features(
                    supports, remaining, predictions,
                    queries_used=step, max_queries=max_queries,
                    accumulated_cost=accumulated_cost, regime=regime,
                )
                values = {
                    action: _oracle_value(
                        action=action,
                        seed=seed,
                        regime=regime,
                        supports=supports,
                        remaining=remaining,
                        predictions=predictions,
                        byrow=byrow,
                        proposals=proposals,
                        equiv=equiv,
                        lambda_cost=float(lambda_cost),
                        depth=int(rollout_depth),
                        cost_horizon=max_queries,
                    )
                    for action in ACTIONS
                }
                if abs(values['stop']) <= 1e-15 and float(unresolved_stop_penalty) > 0.0:
                    values['stop'] -= float(unresolved_stop_penalty)
                out.append(PairwiseExample(
                    regime_id=regime.regime_id,
                    features=features,
                    cheap_minus_strong=values['cheap'] - values['strong'],
                    stop_minus_strong=values['stop'] - values['strong'],
                ))
                best = max(ACTIONS, key=lambda action: (values[action], -ACTIONS.index(action)))
                if best == 'stop':
                    break
                supports, remaining, query_cost = _transition(
                    action=best,
                    seed=seed,
                    regime=regime,
                    supports=supports,
                    remaining=remaining,
                    predictions=predictions,
                    byrow=byrow,
                    proposals=proposals,
                )
                accumulated_cost += query_cost
                if not remaining:
                    break
    return tuple(out)


def train_pairwise_regret_ensemble(
    training_regimes: Sequence[VerifierRegime],
    training_seeds: Sequence[int],
    *,
    lambda_cost: float,
    rollout_depth: int,
    max_steps: int,
    l2: float,
    unresolved_stop_penalty: float = 0.0,
) -> PairwiseRegretEnsemble:
    regimes = tuple(training_regimes)
    seeds = tuple(int(seed) for seed in training_seeds)
    examples = generate_pairwise_examples(
        regimes,
        seeds,
        lambda_cost=float(lambda_cost),
        rollout_depth=int(rollout_depth),
        max_steps=int(max_steps),
        unresolved_stop_penalty=float(unresolved_stop_penalty),
    )
    members: list[PairwiseMember] = []
    for omitted in regimes:
        train_rows = tuple(row for row in examples if row.regime_id != omitted.regime_id)
        if not train_rows:
            raise ValueError('leave-one-regime-out split is empty')
        features = tuple(row.features for row in train_rows)
        models = {
            'cheap_minus_strong': RidgeValueModel.fit(
                features, tuple(row.cheap_minus_strong for row in train_rows), l2=float(l2),
            ),
            'stop_minus_strong': RidgeValueModel.fit(
                features, tuple(row.stop_minus_strong for row in train_rows), l2=float(l2),
            ),
        }
        members.append(PairwiseMember(omitted_regime_id=omitted.regime_id, models=models))
    return PairwiseRegretEnsemble(
        members=tuple(members),
        training_regime_ids=tuple(r.regime_id for r in regimes),
        training_seed_count=len(seeds),
        example_count=len(examples),
        lambda_cost=float(lambda_cost),
        rollout_depth=int(rollout_depth),
        max_steps=int(max_steps),
        l2=float(l2),
        unresolved_stop_penalty=float(unresolved_stop_penalty),
    )
