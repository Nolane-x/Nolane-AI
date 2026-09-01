from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest

from .reasoning_policy_evolution import (
    MetareasoningPolicy,
    PolicyAdoptionReceipt,
    PolicyMetricVector,
    PolicyRevisionProposal,
    PolicyShadowEvaluation,
)


COMPONENT_ID = "external.reasoning_invention"
COMPONENT_VERSION = "0.0.5"
SCHEMA_VERSION = "reasoning-policy-qualification-v1"
DESIGN_LINEAGE = (
    "C11 counterfactual policy qualification: exact matched contexts, tail-regression blocking, "
    "scope-bound applicability, and explicit out-of-scope abstention; Nolane World 0.12.0 is design provenance only"
)


class MatchedTrialVerdict(str, Enum):
    PARETO_NON_REGRESSING = "pareto_non_regressing"
    REGRESSION = "regression"
    INCONCLUSIVE = "inconclusive"


class PolicyApplicabilityVerdict(str, Enum):
    QUALIFIED_FOR_CONTEXT = "qualified_for_context"
    ABSTAIN_OUT_OF_SCOPE = "abstain_out_of_scope"


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return value


def _ids(value: object, name: str, *, minimum: int = 0) -> tuple[str, ...]:
    rows = tuple(_text(row, name) for row in _sequence(value, name))
    if len(rows) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} values")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(rows))


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a finite number") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _identity(prefix: str, state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(state))}"


def _canonical(state: Mapping[str, object], actual: Mapping[str, object], name: str) -> None:
    if dict(state) != dict(actual):
        raise ValueError(f"non-canonical {name} state")


@dataclass(frozen=True, slots=True)
class PolicyTrialContext:
    task_id: str
    objective_id: str
    environment_id: str
    world_revision_id: str
    ontology_revision_id: str
    evidence_root_id: str
    cognitive_library_digest: str
    action_class_id: str
    initial_frontier_id: str
    context_tag_ids: tuple[str, ...]
    context_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _text(self.task_id, "task id"))
        object.__setattr__(self, "objective_id", _text(self.objective_id, "objective id"))
        object.__setattr__(self, "environment_id", _text(self.environment_id, "environment id"))
        object.__setattr__(self, "world_revision_id", _text(self.world_revision_id, "world revision id"))
        object.__setattr__(self, "ontology_revision_id", _text(self.ontology_revision_id, "ontology revision id"))
        object.__setattr__(self, "evidence_root_id", _text(self.evidence_root_id, "evidence root id"))
        object.__setattr__(self, "cognitive_library_digest", _text(self.cognitive_library_digest, "cognitive library digest"))
        object.__setattr__(self, "action_class_id", _text(self.action_class_id, "action class id"))
        object.__setattr__(self, "initial_frontier_id", _text(self.initial_frontier_id, "initial frontier id"))
        object.__setattr__(self, "context_tag_ids", _ids(self.context_tag_ids, "context tag ids"))
        object.__setattr__(self, "context_id", _identity("reasoning-policy-trial-context", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "objective_id": self.objective_id,
            "environment_id": self.environment_id,
            "world_revision_id": self.world_revision_id,
            "ontology_revision_id": self.ontology_revision_id,
            "evidence_root_id": self.evidence_root_id,
            "cognitive_library_digest": self.cognitive_library_digest,
            "action_class_id": self.action_class_id,
            "initial_frontier_id": self.initial_frontier_id,
            "context_tag_ids": list(self.context_tag_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "context_id": self.context_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyTrialContext":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy trial context schema")
        row = cls(
            task_id=state["task_id"],
            objective_id=state["objective_id"],
            environment_id=state["environment_id"],
            world_revision_id=state["world_revision_id"],
            ontology_revision_id=state["ontology_revision_id"],
            evidence_root_id=state["evidence_root_id"],
            cognitive_library_digest=state["cognitive_library_digest"],
            action_class_id=state["action_class_id"],
            initial_frontier_id=state["initial_frontier_id"],
            context_tag_ids=tuple(_sequence(state.get("context_tag_ids", ()), "context tag state")),
        )
        if state.get("context_id") != row.context_id:
            raise ValueError("policy trial context identity does not match canonical content")
        _canonical(state, row.to_state(), "policy trial context")
        return row


@dataclass(frozen=True, slots=True)
class PolicyRegime:
    environment_id: str
    world_revision_id: str
    ontology_revision_id: str
    cognitive_library_digest: str
    action_class_id: str
    required_context_tag_ids: tuple[str, ...]
    regime_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment_id", _text(self.environment_id, "environment id"))
        object.__setattr__(self, "world_revision_id", _text(self.world_revision_id, "world revision id"))
        object.__setattr__(self, "ontology_revision_id", _text(self.ontology_revision_id, "ontology revision id"))
        object.__setattr__(self, "cognitive_library_digest", _text(self.cognitive_library_digest, "cognitive library digest"))
        object.__setattr__(self, "action_class_id", _text(self.action_class_id, "action class id"))
        object.__setattr__(self, "required_context_tag_ids", _ids(self.required_context_tag_ids, "required context tag ids"))
        object.__setattr__(self, "regime_id", _identity("reasoning-policy-regime", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "environment_id": self.environment_id,
            "world_revision_id": self.world_revision_id,
            "ontology_revision_id": self.ontology_revision_id,
            "cognitive_library_digest": self.cognitive_library_digest,
            "action_class_id": self.action_class_id,
            "required_context_tag_ids": list(self.required_context_tag_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "regime_id": self.regime_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyRegime":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy regime schema")
        row = cls(
            environment_id=state["environment_id"],
            world_revision_id=state["world_revision_id"],
            ontology_revision_id=state["ontology_revision_id"],
            cognitive_library_digest=state["cognitive_library_digest"],
            action_class_id=state["action_class_id"],
            required_context_tag_ids=tuple(_sequence(state.get("required_context_tag_ids", ()), "required context tag state")),
        )
        if state.get("regime_id") != row.regime_id:
            raise ValueError("policy regime identity does not match canonical content")
        _canonical(state, row.to_state(), "policy regime")
        return row


def context_matches_regime(context: PolicyTrialContext, regime: PolicyRegime) -> bool:
    if not isinstance(context, PolicyTrialContext) or not isinstance(regime, PolicyRegime):
        raise TypeError("policy regime matching requires canonical context and regime values")
    return (
        context.environment_id == regime.environment_id
        and context.world_revision_id == regime.world_revision_id
        and context.ontology_revision_id == regime.ontology_revision_id
        and context.cognitive_library_digest == regime.cognitive_library_digest
        and context.action_class_id == regime.action_class_id
        and set(regime.required_context_tag_ids).issubset(context.context_tag_ids)
    )


@dataclass(frozen=True, slots=True)
class PolicyEffectVector:
    decision_accuracy_gain: float
    information_gain_delta: float
    uncertainty_reduction_delta: float
    cost_reduction: float
    residual_risk_reduction: float
    regression_count_reduction: int
    effect_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_accuracy_gain", _finite(self.decision_accuracy_gain, "decision accuracy gain"))
        object.__setattr__(self, "information_gain_delta", _finite(self.information_gain_delta, "information gain delta"))
        object.__setattr__(self, "uncertainty_reduction_delta", _finite(self.uncertainty_reduction_delta, "uncertainty reduction delta"))
        object.__setattr__(self, "cost_reduction", _finite(self.cost_reduction, "cost reduction"))
        object.__setattr__(self, "residual_risk_reduction", _finite(self.residual_risk_reduction, "residual risk reduction"))
        object.__setattr__(self, "regression_count_reduction", _integer(self.regression_count_reduction, "regression count reduction"))
        object.__setattr__(self, "effect_id", _identity("reasoning-policy-effect", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "decision_accuracy_gain": self.decision_accuracy_gain,
            "information_gain_delta": self.information_gain_delta,
            "uncertainty_reduction_delta": self.uncertainty_reduction_delta,
            "cost_reduction": self.cost_reduction,
            "residual_risk_reduction": self.residual_risk_reduction,
            "regression_count_reduction": self.regression_count_reduction,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "effect_id": self.effect_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyEffectVector":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy effect schema")
        row = cls(
            decision_accuracy_gain=state["decision_accuracy_gain"],
            information_gain_delta=state["information_gain_delta"],
            uncertainty_reduction_delta=state["uncertainty_reduction_delta"],
            cost_reduction=state["cost_reduction"],
            residual_risk_reduction=state["residual_risk_reduction"],
            regression_count_reduction=state["regression_count_reduction"],
        )
        if state.get("effect_id") != row.effect_id:
            raise ValueError("policy effect identity does not match canonical content")
        _canonical(state, row.to_state(), "policy effect")
        return row


_METRIC_EFFECT_FIELDS: tuple[tuple[str, str], ...] = (
    ("decision_accuracy", "decision_accuracy_gain"),
    ("information_gain", "information_gain_delta"),
    ("uncertainty_reduction", "uncertainty_reduction_delta"),
    ("cost", "cost_reduction"),
    ("residual_risk", "residual_risk_reduction"),
    ("regression_count", "regression_count_reduction"),
)


def _effect(parent: PolicyMetricVector, candidate: PolicyMetricVector) -> PolicyEffectVector:
    return PolicyEffectVector(
        decision_accuracy_gain=candidate.decision_accuracy - parent.decision_accuracy,
        information_gain_delta=candidate.information_gain - parent.information_gain,
        uncertainty_reduction_delta=candidate.uncertainty_reduction - parent.uncertainty_reduction,
        cost_reduction=parent.cost - candidate.cost,
        residual_risk_reduction=parent.residual_risk - candidate.residual_risk,
        regression_count_reduction=parent.regression_count - candidate.regression_count,
    )


def _effect_axes(effect: PolicyEffectVector) -> tuple[tuple[str, ...], tuple[str, ...]]:
    improved: list[str] = []
    regressed: list[str] = []
    for metric_id, field_name in _METRIC_EFFECT_FIELDS:
        value = getattr(effect, field_name)
        if value > 0:
            improved.append(metric_id)
        elif value < 0:
            regressed.append(metric_id)
    return tuple(sorted(improved)), tuple(sorted(regressed))


@dataclass(frozen=True, slots=True)
class MatchedPolicyTrial:
    proposal_id: str
    shadow_evaluation_id: str
    parent_policy_id: str
    candidate_policy_id: str
    context: PolicyTrialContext
    parent_episode_id: str
    candidate_episode_id: str
    parent_metrics: PolicyMetricVector
    candidate_metrics: PolicyMetricVector
    effect: PolicyEffectVector
    verdict: MatchedTrialVerdict
    improved_metric_ids: tuple[str, ...]
    regressed_metric_ids: tuple[str, ...]
    trial_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_id", _text(self.proposal_id, "proposal id"))
        object.__setattr__(self, "shadow_evaluation_id", _text(self.shadow_evaluation_id, "shadow evaluation id"))
        object.__setattr__(self, "parent_policy_id", _text(self.parent_policy_id, "parent policy id"))
        object.__setattr__(self, "candidate_policy_id", _text(self.candidate_policy_id, "candidate policy id"))
        if self.parent_policy_id == self.candidate_policy_id:
            raise ValueError("matched trial policy source and candidate must differ")
        if not isinstance(self.context, PolicyTrialContext):
            raise TypeError("matched trial context must be PolicyTrialContext")
        object.__setattr__(self, "parent_episode_id", _text(self.parent_episode_id, "parent episode id"))
        object.__setattr__(self, "candidate_episode_id", _text(self.candidate_episode_id, "candidate episode id"))
        if self.parent_episode_id == self.candidate_episode_id:
            raise ValueError("matched trial requires distinct parent and candidate episode authority")
        if not isinstance(self.parent_metrics, PolicyMetricVector) or not isinstance(self.candidate_metrics, PolicyMetricVector):
            raise TypeError("matched trial metrics must be PolicyMetricVector values")
        if not isinstance(self.effect, PolicyEffectVector):
            raise TypeError("matched trial effect must be PolicyEffectVector")
        expected_effect = _effect(self.parent_metrics, self.candidate_metrics)
        if self.effect != expected_effect:
            raise ValueError("matched trial effect must be derived from exact parent/candidate metrics")
        verdict = MatchedTrialVerdict(self.verdict)
        improved = _ids(self.improved_metric_ids, "improved metric ids")
        regressed = _ids(self.regressed_metric_ids, "regressed metric ids")
        expected_improved, expected_regressed = _effect_axes(expected_effect)
        if improved != expected_improved or regressed != expected_regressed:
            raise ValueError("matched trial metric classifications must be derived from effect vector")
        expected_verdict = (
            MatchedTrialVerdict.REGRESSION
            if regressed
            else MatchedTrialVerdict.PARETO_NON_REGRESSING
            if improved
            else MatchedTrialVerdict.INCONCLUSIVE
        )
        if verdict is not expected_verdict:
            raise ValueError("matched trial verdict does not match derived effect vector")
        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(self, "improved_metric_ids", improved)
        object.__setattr__(self, "regressed_metric_ids", regressed)
        object.__setattr__(self, "trial_id", _identity("reasoning-policy-matched-trial", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "shadow_evaluation_id": self.shadow_evaluation_id,
            "parent_policy_id": self.parent_policy_id,
            "candidate_policy_id": self.candidate_policy_id,
            "context": self.context.to_state(),
            "parent_episode_id": self.parent_episode_id,
            "candidate_episode_id": self.candidate_episode_id,
            "parent_metrics": self.parent_metrics.to_state(),
            "candidate_metrics": self.candidate_metrics.to_state(),
            "effect": self.effect.to_state(),
            "verdict": self.verdict.value,
            "improved_metric_ids": list(self.improved_metric_ids),
            "regressed_metric_ids": list(self.regressed_metric_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "trial_id": self.trial_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "MatchedPolicyTrial":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported matched policy trial schema")
        context_state = state.get("context")
        parent_state = state.get("parent_metrics")
        candidate_state = state.get("candidate_metrics")
        effect_state = state.get("effect")
        if not all(isinstance(row, Mapping) for row in (context_state, parent_state, candidate_state, effect_state)):
            raise TypeError("matched trial nested states must be mappings")
        row = cls(
            proposal_id=state["proposal_id"],
            shadow_evaluation_id=state["shadow_evaluation_id"],
            parent_policy_id=state["parent_policy_id"],
            candidate_policy_id=state["candidate_policy_id"],
            context=PolicyTrialContext.from_state(context_state),
            parent_episode_id=state["parent_episode_id"],
            candidate_episode_id=state["candidate_episode_id"],
            parent_metrics=PolicyMetricVector.from_state(parent_state),
            candidate_metrics=PolicyMetricVector.from_state(candidate_state),
            effect=PolicyEffectVector.from_state(effect_state),
            verdict=MatchedTrialVerdict(state["verdict"]),
            improved_metric_ids=tuple(_sequence(state.get("improved_metric_ids", ()), "improved metric state")),
            regressed_metric_ids=tuple(_sequence(state.get("regressed_metric_ids", ()), "regressed metric state")),
        )
        if state.get("trial_id") != row.trial_id:
            raise ValueError("matched policy trial identity does not match canonical content")
        _canonical(state, row.to_state(), "matched policy trial")
        return row


def bind_matched_policy_trial(
    proposal: PolicyRevisionProposal,
    shadow: PolicyShadowEvaluation,
    *,
    parent_policy: MetareasoningPolicy,
    candidate_policy: MetareasoningPolicy,
    context: PolicyTrialContext,
    parent_episode_id: str,
    candidate_episode_id: str,
    parent_metrics: PolicyMetricVector,
    candidate_metrics: PolicyMetricVector,
) -> MatchedPolicyTrial:
    if not isinstance(proposal, PolicyRevisionProposal) or not isinstance(shadow, PolicyShadowEvaluation):
        raise TypeError("matched trial requires canonical proposal and shadow evaluation")
    if not isinstance(parent_policy, MetareasoningPolicy) or not isinstance(candidate_policy, MetareasoningPolicy):
        raise TypeError("matched trial requires canonical parent and candidate policies")
    if not isinstance(context, PolicyTrialContext):
        raise TypeError("matched trial requires PolicyTrialContext")
    if not isinstance(parent_metrics, PolicyMetricVector) or not isinstance(candidate_metrics, PolicyMetricVector):
        raise TypeError("matched trial requires PolicyMetricVector values")
    if candidate_policy.parent_policy_id != parent_policy.policy_id or candidate_policy.revision != parent_policy.revision + 1:
        raise ValueError("matched trial candidate lineage does not match parent policy")
    if proposal.parent_policy_id != parent_policy.policy_id or proposal.candidate_policy_id != candidate_policy.policy_id:
        raise ValueError("matched trial proposal does not bind exact policy lineage")
    if proposal.revision != candidate_policy.revision:
        raise ValueError("matched trial proposal revision does not match candidate policy")
    if shadow.proposal_id != proposal.proposal_id or shadow.evidence_split_id != proposal.evidence_split.split_id:
        raise ValueError("matched trial shadow does not bind exact proposal")
    if shadow.holdout_episode_ids != proposal.evidence_split.holdout_episode_ids:
        raise ValueError("matched trial shadow must preserve exact holdout split")
    parent_episode = _text(parent_episode_id, "parent episode id")
    candidate_episode = _text(candidate_episode_id, "candidate episode id")
    if parent_episode == candidate_episode:
        raise ValueError("matched trial requires distinct parent and candidate episode authority")
    holdout = set(shadow.holdout_episode_ids)
    if parent_episode not in holdout or candidate_episode not in holdout:
        raise ValueError("matched trial evidence must come from exact C10 holdout episodes")
    development = set(proposal.evidence_split.development_episode_ids)
    if parent_episode in development or candidate_episode in development:
        raise ValueError("matched trial cannot launder development evidence into qualification")
    effect = _effect(parent_metrics, candidate_metrics)
    improved, regressed = _effect_axes(effect)
    verdict = (
        MatchedTrialVerdict.REGRESSION
        if regressed
        else MatchedTrialVerdict.PARETO_NON_REGRESSING
        if improved
        else MatchedTrialVerdict.INCONCLUSIVE
    )
    return MatchedPolicyTrial(
        proposal_id=proposal.proposal_id,
        shadow_evaluation_id=shadow.evaluation_id,
        parent_policy_id=parent_policy.policy_id,
        candidate_policy_id=candidate_policy.policy_id,
        context=context,
        parent_episode_id=parent_episode,
        candidate_episode_id=candidate_episode,
        parent_metrics=parent_metrics,
        candidate_metrics=candidate_metrics,
        effect=effect,
        verdict=verdict,
        improved_metric_ids=improved,
        regressed_metric_ids=regressed,
    )


@dataclass(frozen=True, slots=True)
class PolicyRegimeQualification:
    proposal_id: str
    shadow_evaluation_id: str
    adoption_receipt_id: str
    source_policy_id: str
    candidate_policy_id: str
    regime: PolicyRegime
    trial_ids: tuple[str, ...]
    distinct_task_ids: tuple[str, ...]
    improved_metric_ids: tuple[str, ...]
    regressed_metric_ids: tuple[str, ...]
    authority: str = field(init=False, default="qualification_evidence_only")
    qualification_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_id", _text(self.proposal_id, "proposal id"))
        object.__setattr__(self, "shadow_evaluation_id", _text(self.shadow_evaluation_id, "shadow evaluation id"))
        object.__setattr__(self, "adoption_receipt_id", _text(self.adoption_receipt_id, "adoption receipt id"))
        object.__setattr__(self, "source_policy_id", _text(self.source_policy_id, "source policy id"))
        object.__setattr__(self, "candidate_policy_id", _text(self.candidate_policy_id, "candidate policy id"))
        if self.source_policy_id == self.candidate_policy_id:
            raise ValueError("qualification source and candidate policies must differ")
        if not isinstance(self.regime, PolicyRegime):
            raise TypeError("qualification regime must be PolicyRegime")
        object.__setattr__(self, "trial_ids", _ids(self.trial_ids, "qualification trial ids", minimum=2))
        object.__setattr__(self, "distinct_task_ids", _ids(self.distinct_task_ids, "qualification task ids", minimum=2))
        object.__setattr__(self, "improved_metric_ids", _ids(self.improved_metric_ids, "qualification improved metric ids", minimum=1))
        object.__setattr__(self, "regressed_metric_ids", _ids(self.regressed_metric_ids, "qualification regressed metric ids"))
        if self.regressed_metric_ids:
            raise ValueError("qualified policy regime cannot contain regressed metrics")
        object.__setattr__(self, "qualification_id", _identity("reasoning-policy-qualification", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "shadow_evaluation_id": self.shadow_evaluation_id,
            "adoption_receipt_id": self.adoption_receipt_id,
            "source_policy_id": self.source_policy_id,
            "candidate_policy_id": self.candidate_policy_id,
            "regime": self.regime.to_state(),
            "trial_ids": list(self.trial_ids),
            "distinct_task_ids": list(self.distinct_task_ids),
            "improved_metric_ids": list(self.improved_metric_ids),
            "regressed_metric_ids": list(self.regressed_metric_ids),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "qualification_id": self.qualification_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyRegimeQualification":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy regime qualification schema")
        regime_state = state.get("regime")
        if not isinstance(regime_state, Mapping):
            raise TypeError("qualification regime state must be a mapping")
        row = cls(
            proposal_id=state["proposal_id"],
            shadow_evaluation_id=state["shadow_evaluation_id"],
            adoption_receipt_id=state["adoption_receipt_id"],
            source_policy_id=state["source_policy_id"],
            candidate_policy_id=state["candidate_policy_id"],
            regime=PolicyRegime.from_state(regime_state),
            trial_ids=tuple(_sequence(state.get("trial_ids", ()), "qualification trial state")),
            distinct_task_ids=tuple(_sequence(state.get("distinct_task_ids", ()), "qualification task state")),
            improved_metric_ids=tuple(_sequence(state.get("improved_metric_ids", ()), "qualification improved metric state")),
            regressed_metric_ids=tuple(_sequence(state.get("regressed_metric_ids", ()), "qualification regressed metric state")),
        )
        if state.get("authority") != row.authority:
            raise ValueError("qualification authority does not match evidence-only contract")
        if state.get("qualification_id") != row.qualification_id:
            raise ValueError("policy regime qualification identity does not match canonical content")
        _canonical(state, row.to_state(), "policy regime qualification")
        return row


def qualify_policy_regime(
    proposal: PolicyRevisionProposal,
    shadow: PolicyShadowEvaluation,
    adoption: PolicyAdoptionReceipt,
    *,
    candidate_policy: MetareasoningPolicy,
    regime: PolicyRegime,
    trials: Sequence[MatchedPolicyTrial],
) -> PolicyRegimeQualification:
    if not isinstance(proposal, PolicyRevisionProposal) or not isinstance(shadow, PolicyShadowEvaluation):
        raise TypeError("policy qualification requires canonical proposal and shadow evaluation")
    if not isinstance(adoption, PolicyAdoptionReceipt):
        raise TypeError("policy qualification requires PolicyAdoptionReceipt")
    if not isinstance(candidate_policy, MetareasoningPolicy) or not isinstance(regime, PolicyRegime):
        raise TypeError("policy qualification requires canonical candidate policy and regime")
    rows = tuple(_sequence(trials, "matched policy trials"))
    if len(rows) < 2:
        raise ValueError("policy qualification requires at least two matched trials")
    if any(not isinstance(row, MatchedPolicyTrial) for row in rows):
        raise TypeError("policy qualification trials must be MatchedPolicyTrial values")
    if candidate_policy.policy_id != proposal.candidate_policy_id:
        raise ValueError("qualification candidate does not match proposal")
    if candidate_policy.parent_policy_id != proposal.parent_policy_id or candidate_policy.revision != proposal.revision:
        raise ValueError("qualification candidate lineage does not match proposal")
    if shadow.proposal_id != proposal.proposal_id or shadow.evidence_split_id != proposal.evidence_split.split_id:
        raise ValueError("qualification shadow does not bind exact proposal")
    if shadow.holdout_episode_ids != proposal.evidence_split.holdout_episode_ids:
        raise ValueError("qualification shadow must preserve exact holdout split")
    if adoption.source_policy_id != proposal.parent_policy_id:
        raise ValueError("qualification adoption source does not match proposal parent")
    if adoption.adopted_policy_id != candidate_policy.policy_id:
        raise ValueError("qualification requires the externally adopted candidate policy")
    if adoption.proposal_id != proposal.proposal_id or adoption.shadow_evaluation_id != shadow.evaluation_id:
        raise ValueError("qualification adoption receipt does not bind exact proposal and shadow")

    trial_ids = [row.trial_id for row in rows]
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("policy qualification cannot reuse duplicate matched trials")
    episode_ids: list[str] = []
    tasks: list[str] = []
    improved: set[str] = set()
    regressed: set[str] = set()
    for row in rows:
        if row.proposal_id != proposal.proposal_id or row.shadow_evaluation_id != shadow.evaluation_id:
            raise ValueError("qualification trial does not bind exact proposal and shadow")
        if row.parent_policy_id != proposal.parent_policy_id or row.candidate_policy_id != candidate_policy.policy_id:
            raise ValueError("qualification trial policy lineage mismatch")
        if not context_matches_regime(row.context, regime):
            raise ValueError("qualification trial context is outside declared policy regime")
        if row.verdict is not MatchedTrialVerdict.PARETO_NON_REGRESSING:
            raise ValueError("every qualification trial must be Pareto non-regressing")
        episode_ids.extend((row.parent_episode_id, row.candidate_episode_id))
        tasks.append(row.context.task_id)
        improved.update(row.improved_metric_ids)
        regressed.update(row.regressed_metric_ids)
    if len(episode_ids) != len(set(episode_ids)):
        raise ValueError("policy qualification cannot reuse episode authority across trials")
    task_ids = tuple(sorted(set(tasks)))
    if len(task_ids) < 2:
        raise ValueError("policy qualification requires at least two distinct task ids")
    if regressed:
        raise ValueError("policy qualification cannot hide tail regressions")
    if not improved:
        raise ValueError("policy qualification requires at least one matched improvement")
    return PolicyRegimeQualification(
        proposal_id=proposal.proposal_id,
        shadow_evaluation_id=shadow.evaluation_id,
        adoption_receipt_id=adoption.receipt_id,
        source_policy_id=proposal.parent_policy_id,
        candidate_policy_id=candidate_policy.policy_id,
        regime=regime,
        trial_ids=tuple(trial_ids),
        distinct_task_ids=task_ids,
        improved_metric_ids=tuple(improved),
        regressed_metric_ids=(),
    )


@dataclass(frozen=True, slots=True)
class PolicyApplicabilityReceipt:
    policy_id: str
    regime_id: str
    qualification_id: str
    context_id: str
    verdict: PolicyApplicabilityVerdict
    authority: str = field(init=False, default="qualification_evidence_only")
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy id"))
        object.__setattr__(self, "regime_id", _text(self.regime_id, "regime id"))
        object.__setattr__(self, "qualification_id", _text(self.qualification_id, "qualification id"))
        object.__setattr__(self, "context_id", _text(self.context_id, "context id"))
        object.__setattr__(self, "verdict", PolicyApplicabilityVerdict(self.verdict))
        object.__setattr__(self, "receipt_id", _identity("reasoning-policy-applicability", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "regime_id": self.regime_id,
            "qualification_id": self.qualification_id,
            "context_id": self.context_id,
            "verdict": self.verdict.value,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "receipt_id": self.receipt_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyApplicabilityReceipt":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy applicability receipt schema")
        row = cls(
            policy_id=state["policy_id"],
            regime_id=state["regime_id"],
            qualification_id=state["qualification_id"],
            context_id=state["context_id"],
            verdict=PolicyApplicabilityVerdict(state["verdict"]),
        )
        if state.get("authority") != row.authority:
            raise ValueError("policy applicability authority does not match evidence-only contract")
        if state.get("receipt_id") != row.receipt_id:
            raise ValueError("policy applicability receipt identity does not match canonical content")
        _canonical(state, row.to_state(), "policy applicability receipt")
        return row


def evaluate_policy_applicability(
    qualification: PolicyRegimeQualification,
    context: PolicyTrialContext,
) -> PolicyApplicabilityReceipt:
    if not isinstance(qualification, PolicyRegimeQualification) or not isinstance(context, PolicyTrialContext):
        raise TypeError("policy applicability requires canonical qualification and context")
    verdict = (
        PolicyApplicabilityVerdict.QUALIFIED_FOR_CONTEXT
        if context_matches_regime(context, qualification.regime)
        else PolicyApplicabilityVerdict.ABSTAIN_OUT_OF_SCOPE
    )
    return PolicyApplicabilityReceipt(
        policy_id=qualification.candidate_policy_id,
        regime_id=qualification.regime.regime_id,
        qualification_id=qualification.qualification_id,
        context_id=context.context_id,
        verdict=verdict,
    )
