from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest

from .reasoning_metacontrol import MetaActionKind, MetareasoningBudget


COMPONENT_ID = "external.reasoning_invention"
COMPONENT_VERSION = "0.0.5"
SCHEMA_VERSION = "reasoning-policy-evolution-v1"
DESIGN_LINEAGE = (
    "C10 governed metareasoning-policy evolution: monotonic constraint-only policy "
    "deltas, disjoint development/holdout evidence, Pareto shadow evaluation, "
    "self-contained fresh-context review provenance, and external-only adoption/rollback authority"
)


class PolicyOperation(str, Enum):
    ADOPT = "adopt"
    ROLLBACK = "rollback"


class PolicyShadowVerdict(str, Enum):
    PARETO_NON_REGRESSING = "pareto_non_regressing"
    REJECTED = "rejected"


class PolicyReviewVerdict(str, Enum):
    SUPPORTED_FOR_ADOPTION = "supported_for_adoption"
    REVISE = "revise"
    REJECTED = "rejected"
    ABSTAIN = "abstain"


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


def _nonnegative_finite(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _score(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return number


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _identity(prefix: str, state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(state))}"


def _canonical(state: Mapping[str, object], actual: Mapping[str, object], name: str) -> None:
    if dict(state) != dict(actual):
        raise ValueError(f"non-canonical {name} state")


@dataclass(frozen=True, slots=True)
class MetareasoningPolicy:
    revision: int
    parent_policy_id: str | None
    max_remaining_actions: int
    max_remaining_cost: float
    minimum_actionable_gain_floor: float
    allowed_action_kinds: tuple[str, ...]
    policy_id: str = field(init=False)

    def __post_init__(self) -> None:
        revision = _positive_int(self.revision, "policy revision")
        parent = None if self.parent_policy_id is None else _text(self.parent_policy_id, "parent policy id")
        if revision == 1 and parent is not None:
            raise ValueError("root policy revision cannot have a parent")
        if revision > 1 and parent is None:
            raise ValueError("non-root policy revision requires a parent policy id")
        kinds = _ids(self.allowed_action_kinds, "allowed action kinds", minimum=1)
        for kind in kinds:
            try:
                MetaActionKind(kind)
            except ValueError as exc:
                raise ValueError(f"unknown metareasoning action kind: {kind}") from exc
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "parent_policy_id", parent)
        object.__setattr__(self, "max_remaining_actions", _nonnegative_int(self.max_remaining_actions, "max remaining actions"))
        object.__setattr__(self, "max_remaining_cost", _nonnegative_finite(self.max_remaining_cost, "max remaining cost"))
        object.__setattr__(self, "minimum_actionable_gain_floor", _score(self.minimum_actionable_gain_floor, "minimum actionable gain floor"))
        object.__setattr__(self, "allowed_action_kinds", kinds)
        object.__setattr__(self, "policy_id", _identity("reasoning-policy", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "parent_policy_id": self.parent_policy_id,
            "max_remaining_actions": self.max_remaining_actions,
            "max_remaining_cost": self.max_remaining_cost,
            "minimum_actionable_gain_floor": self.minimum_actionable_gain_floor,
            "allowed_action_kinds": list(self.allowed_action_kinds),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "policy_id": self.policy_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "MetareasoningPolicy":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported reasoning policy schema")
        row = cls(
            revision=state["revision"],
            parent_policy_id=state.get("parent_policy_id"),
            max_remaining_actions=state["max_remaining_actions"],
            max_remaining_cost=state["max_remaining_cost"],
            minimum_actionable_gain_floor=state["minimum_actionable_gain_floor"],
            allowed_action_kinds=tuple(_sequence(state.get("allowed_action_kinds", ()), "allowed action kind state")),
        )
        if state.get("policy_id") != row.policy_id:
            raise ValueError("reasoning policy identity does not match canonical content")
        _canonical(state, row.to_state(), "reasoning policy")
        return row


@dataclass(frozen=True, slots=True)
class PolicyEvidenceSplit:
    development_episode_ids: tuple[str, ...]
    holdout_episode_ids: tuple[str, ...]
    split_id: str = field(init=False)

    def __post_init__(self) -> None:
        development = _ids(self.development_episode_ids, "development episode ids", minimum=2)
        holdout = _ids(self.holdout_episode_ids, "holdout episode ids", minimum=2)
        if not set(development).isdisjoint(holdout):
            raise ValueError("development and holdout episode ids must be disjoint")
        object.__setattr__(self, "development_episode_ids", development)
        object.__setattr__(self, "holdout_episode_ids", holdout)
        object.__setattr__(self, "split_id", _identity("policy-evidence-split", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "development_episode_ids": list(self.development_episode_ids),
            "holdout_episode_ids": list(self.holdout_episode_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "split_id": self.split_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyEvidenceSplit":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy evidence split schema")
        row = cls(
            development_episode_ids=tuple(_sequence(state.get("development_episode_ids", ()), "development episode state")),
            holdout_episode_ids=tuple(_sequence(state.get("holdout_episode_ids", ()), "holdout episode state")),
        )
        if state.get("split_id") != row.split_id:
            raise ValueError("policy evidence split identity does not match canonical content")
        _canonical(state, row.to_state(), "policy evidence split")
        return row


@dataclass(frozen=True, slots=True)
class PolicyMetricVector:
    decision_accuracy: float
    information_gain: float
    uncertainty_reduction: float
    cost: float
    residual_risk: float
    regression_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_accuracy", _score(self.decision_accuracy, "decision accuracy"))
        object.__setattr__(self, "information_gain", _score(self.information_gain, "information gain"))
        object.__setattr__(self, "uncertainty_reduction", _score(self.uncertainty_reduction, "uncertainty reduction"))
        object.__setattr__(self, "cost", _nonnegative_finite(self.cost, "cost"))
        object.__setattr__(self, "residual_risk", _score(self.residual_risk, "residual risk"))
        object.__setattr__(self, "regression_count", _nonnegative_int(self.regression_count, "regression count"))

    def to_state(self) -> dict[str, object]:
        return {
            "decision_accuracy": self.decision_accuracy,
            "information_gain": self.information_gain,
            "uncertainty_reduction": self.uncertainty_reduction,
            "cost": self.cost,
            "residual_risk": self.residual_risk,
            "regression_count": self.regression_count,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyMetricVector":
        row = cls(
            decision_accuracy=state["decision_accuracy"],
            information_gain=state["information_gain"],
            uncertainty_reduction=state["uncertainty_reduction"],
            cost=state["cost"],
            residual_risk=state["residual_risk"],
            regression_count=state["regression_count"],
        )
        _canonical(state, row.to_state(), "policy metric vector")
        return row


@dataclass(frozen=True, slots=True)
class PolicyRevisionProposal:
    parent_policy_id: str
    candidate_policy_id: str
    revision: int
    evidence_split: PolicyEvidenceSplit
    learning_evidence_ids: tuple[str, ...]
    producer_agent_id: str
    producer_session_id: str
    rationale_ids: tuple[str, ...]
    proposal_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_policy_id", _text(self.parent_policy_id, "parent policy id"))
        object.__setattr__(self, "candidate_policy_id", _text(self.candidate_policy_id, "candidate policy id"))
        object.__setattr__(self, "revision", _positive_int(self.revision, "proposal revision"))
        if not isinstance(self.evidence_split, PolicyEvidenceSplit):
            raise TypeError("evidence split must be PolicyEvidenceSplit")
        object.__setattr__(self, "learning_evidence_ids", _ids(self.learning_evidence_ids, "learning evidence ids", minimum=1))
        object.__setattr__(self, "producer_agent_id", _text(self.producer_agent_id, "producer agent id"))
        object.__setattr__(self, "producer_session_id", _text(self.producer_session_id, "producer session id"))
        object.__setattr__(self, "rationale_ids", _ids(self.rationale_ids, "rationale ids", minimum=1))
        if self.parent_policy_id == self.candidate_policy_id:
            raise ValueError("policy proposal candidate must differ from parent")
        object.__setattr__(self, "proposal_id", _identity("reasoning-policy-proposal", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "parent_policy_id": self.parent_policy_id,
            "candidate_policy_id": self.candidate_policy_id,
            "revision": self.revision,
            "evidence_split": self.evidence_split.to_state(),
            "learning_evidence_ids": list(self.learning_evidence_ids),
            "producer_agent_id": self.producer_agent_id,
            "producer_session_id": self.producer_session_id,
            "rationale_ids": list(self.rationale_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "proposal_id": self.proposal_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyRevisionProposal":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy proposal schema")
        split_state = state.get("evidence_split")
        if not isinstance(split_state, Mapping):
            raise TypeError("policy proposal evidence split state must be a mapping")
        row = cls(
            parent_policy_id=state["parent_policy_id"],
            candidate_policy_id=state["candidate_policy_id"],
            revision=state["revision"],
            evidence_split=PolicyEvidenceSplit.from_state(split_state),
            learning_evidence_ids=tuple(_sequence(state.get("learning_evidence_ids", ()), "learning evidence state")),
            producer_agent_id=state["producer_agent_id"],
            producer_session_id=state["producer_session_id"],
            rationale_ids=tuple(_sequence(state.get("rationale_ids", ()), "rationale state")),
        )
        if state.get("proposal_id") != row.proposal_id:
            raise ValueError("policy proposal identity does not match canonical content")
        _canonical(state, row.to_state(), "policy proposal")
        return row


def propose_policy_revision(
    parent: MetareasoningPolicy,
    candidate: MetareasoningPolicy,
    *,
    evidence_split: PolicyEvidenceSplit,
    learning_evidence_ids: Sequence[str],
    producer_agent_id: str,
    producer_session_id: str,
    rationale_ids: Sequence[str],
) -> PolicyRevisionProposal:
    if not isinstance(parent, MetareasoningPolicy) or not isinstance(candidate, MetareasoningPolicy):
        raise TypeError("policy revision proposal requires MetareasoningPolicy values")
    if candidate.parent_policy_id != parent.policy_id:
        raise ValueError("candidate policy parent lineage does not match parent policy")
    if candidate.revision != parent.revision + 1:
        raise ValueError("candidate policy must advance exactly one revision")
    if candidate.max_remaining_actions > parent.max_remaining_actions:
        raise ValueError("candidate policy constraint cannot expand remaining actions")
    if candidate.max_remaining_cost > parent.max_remaining_cost:
        raise ValueError("candidate policy constraint cannot expand remaining cost")
    if candidate.minimum_actionable_gain_floor < parent.minimum_actionable_gain_floor:
        raise ValueError("candidate policy constraint cannot lower actionable-gain floor")
    if not set(candidate.allowed_action_kinds).issubset(parent.allowed_action_kinds):
        raise ValueError("candidate policy constraint cannot add action kinds")
    return PolicyRevisionProposal(
        parent_policy_id=parent.policy_id,
        candidate_policy_id=candidate.policy_id,
        revision=candidate.revision,
        evidence_split=evidence_split,
        learning_evidence_ids=tuple(learning_evidence_ids),
        producer_agent_id=producer_agent_id,
        producer_session_id=producer_session_id,
        rationale_ids=tuple(rationale_ids),
    )


def constrain_metareasoning_budget(policy: MetareasoningPolicy, caller_budget: MetareasoningBudget) -> MetareasoningBudget:
    if not isinstance(policy, MetareasoningPolicy):
        raise TypeError("policy must be MetareasoningPolicy")
    if not isinstance(caller_budget, MetareasoningBudget):
        raise TypeError("caller budget must be MetareasoningBudget")
    return MetareasoningBudget(
        frontier_id=caller_budget.frontier_id,
        remaining_actions=min(caller_budget.remaining_actions, policy.max_remaining_actions),
        remaining_cost=min(caller_budget.remaining_cost, policy.max_remaining_cost),
        minimum_actionable_gain=max(caller_budget.minimum_actionable_gain, policy.minimum_actionable_gain_floor),
    )


@dataclass(frozen=True, slots=True)
class PolicyShadowEvaluation:
    proposal_id: str
    evidence_split_id: str
    holdout_episode_ids: tuple[str, ...]
    parent_metrics: PolicyMetricVector
    candidate_metrics: PolicyMetricVector
    verdict: PolicyShadowVerdict
    regressed_metric_ids: tuple[str, ...]
    improved_metric_ids: tuple[str, ...]
    evaluation_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_id", _text(self.proposal_id, "proposal id"))
        object.__setattr__(self, "evidence_split_id", _text(self.evidence_split_id, "evidence split id"))
        object.__setattr__(self, "holdout_episode_ids", _ids(self.holdout_episode_ids, "holdout episode ids", minimum=2))
        if not isinstance(self.parent_metrics, PolicyMetricVector) or not isinstance(self.candidate_metrics, PolicyMetricVector):
            raise TypeError("shadow metrics must be PolicyMetricVector values")
        object.__setattr__(self, "verdict", PolicyShadowVerdict(self.verdict))
        object.__setattr__(self, "regressed_metric_ids", _ids(self.regressed_metric_ids, "regressed metric ids"))
        object.__setattr__(self, "improved_metric_ids", _ids(self.improved_metric_ids, "improved metric ids"))
        if set(self.regressed_metric_ids) & set(self.improved_metric_ids):
            raise ValueError("shadow metric cannot be both regressed and improved")
        if self.verdict is PolicyShadowVerdict.PARETO_NON_REGRESSING:
            if self.regressed_metric_ids or not self.improved_metric_ids:
                raise ValueError("Pareto non-regressing shadow requires no regressions and at least one improvement")
        object.__setattr__(self, "evaluation_id", _identity("reasoning-policy-shadow", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "evidence_split_id": self.evidence_split_id,
            "holdout_episode_ids": list(self.holdout_episode_ids),
            "parent_metrics": self.parent_metrics.to_state(),
            "candidate_metrics": self.candidate_metrics.to_state(),
            "verdict": self.verdict.value,
            "regressed_metric_ids": list(self.regressed_metric_ids),
            "improved_metric_ids": list(self.improved_metric_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "evaluation_id": self.evaluation_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyShadowEvaluation":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy shadow schema")
        parent_state = state.get("parent_metrics")
        candidate_state = state.get("candidate_metrics")
        if not isinstance(parent_state, Mapping) or not isinstance(candidate_state, Mapping):
            raise TypeError("policy shadow metric states must be mappings")
        row = cls(
            proposal_id=state["proposal_id"],
            evidence_split_id=state["evidence_split_id"],
            holdout_episode_ids=tuple(_sequence(state.get("holdout_episode_ids", ()), "holdout episode state")),
            parent_metrics=PolicyMetricVector.from_state(parent_state),
            candidate_metrics=PolicyMetricVector.from_state(candidate_state),
            verdict=PolicyShadowVerdict(state["verdict"]),
            regressed_metric_ids=tuple(_sequence(state.get("regressed_metric_ids", ()), "regressed metric state")),
            improved_metric_ids=tuple(_sequence(state.get("improved_metric_ids", ()), "improved metric state")),
        )
        if state.get("evaluation_id") != row.evaluation_id:
            raise ValueError("policy shadow identity does not match canonical content")
        _canonical(state, row.to_state(), "policy shadow")
        return row


def evaluate_policy_shadow(
    proposal: PolicyRevisionProposal,
    *,
    parent_metrics: PolicyMetricVector,
    candidate_metrics: PolicyMetricVector,
    holdout_episode_ids: Sequence[str],
) -> PolicyShadowEvaluation:
    if not isinstance(proposal, PolicyRevisionProposal):
        raise TypeError("shadow evaluation requires a PolicyRevisionProposal")
    if not isinstance(parent_metrics, PolicyMetricVector) or not isinstance(candidate_metrics, PolicyMetricVector):
        raise TypeError("shadow evaluation metrics must be PolicyMetricVector values")
    holdout = _ids(holdout_episode_ids, "holdout episode ids", minimum=2)
    if holdout != proposal.evidence_split.holdout_episode_ids:
        raise ValueError("shadow evaluation must use the exact declared holdout episode ids")
    if set(holdout) & set(proposal.evidence_split.development_episode_ids):
        raise ValueError("shadow holdout evidence must remain disjoint from development evidence")
    maximize = (
        ("decision_accuracy", parent_metrics.decision_accuracy, candidate_metrics.decision_accuracy),
        ("information_gain", parent_metrics.information_gain, candidate_metrics.information_gain),
        ("uncertainty_reduction", parent_metrics.uncertainty_reduction, candidate_metrics.uncertainty_reduction),
    )
    minimize = (
        ("cost", parent_metrics.cost, candidate_metrics.cost),
        ("residual_risk", parent_metrics.residual_risk, candidate_metrics.residual_risk),
        ("regression_count", float(parent_metrics.regression_count), float(candidate_metrics.regression_count)),
    )
    regressed = [name for name, before, after in maximize if after < before]
    regressed.extend(name for name, before, after in minimize if after > before)
    improved = [name for name, before, after in maximize if after > before]
    improved.extend(name for name, before, after in minimize if after < before)
    verdict = PolicyShadowVerdict.PARETO_NON_REGRESSING if not regressed and improved else PolicyShadowVerdict.REJECTED
    return PolicyShadowEvaluation(
        proposal_id=proposal.proposal_id,
        evidence_split_id=proposal.evidence_split.split_id,
        holdout_episode_ids=holdout,
        parent_metrics=parent_metrics,
        candidate_metrics=candidate_metrics,
        verdict=verdict,
        regressed_metric_ids=tuple(regressed),
        improved_metric_ids=tuple(improved),
    )


@dataclass(frozen=True, slots=True)
class PolicyReviewRequest:
    proposal_id: str
    shadow_evaluation_id: str
    producer_agent_id: str
    reviewer_agent_id: str
    producer_session_id: str
    reviewer_session_id: str
    evidence_packet_ids: tuple[str, ...]
    review_context_ids: tuple[str, ...]
    withheld_rationale_ids: tuple[str, ...]
    required_check_ids: tuple[str, ...]
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_id", _text(self.proposal_id, "proposal id"))
        object.__setattr__(self, "shadow_evaluation_id", _text(self.shadow_evaluation_id, "shadow evaluation id"))
        object.__setattr__(self, "producer_agent_id", _text(self.producer_agent_id, "producer agent id"))
        object.__setattr__(self, "reviewer_agent_id", _text(self.reviewer_agent_id, "reviewer agent id"))
        object.__setattr__(self, "producer_session_id", _text(self.producer_session_id, "producer session id"))
        object.__setattr__(self, "reviewer_session_id", _text(self.reviewer_session_id, "reviewer session id"))
        packet = _ids(self.evidence_packet_ids, "evidence packet ids", minimum=2)
        context = _ids(self.review_context_ids, "review context ids", minimum=2)
        withheld = _ids(self.withheld_rationale_ids, "withheld rationale ids", minimum=1)
        checks = _ids(self.required_check_ids, "required check ids", minimum=1)
        if self.producer_agent_id == self.reviewer_agent_id:
            raise ValueError("fresh-context reviewer must differ from producer")
        if self.producer_session_id == self.reviewer_session_id:
            raise ValueError("fresh-context review session must differ from producer session")
        if not set(packet).issubset(context):
            raise ValueError("fresh-context review context must contain the evidence packet")
        if not {self.proposal_id, self.shadow_evaluation_id}.issubset(packet):
            raise ValueError("evidence packet must bind proposal and shadow evaluation")
        if set(withheld) & set(context):
            raise ValueError("withheld rationale ids must remain outside review context")
        object.__setattr__(self, "evidence_packet_ids", packet)
        object.__setattr__(self, "review_context_ids", context)
        object.__setattr__(self, "withheld_rationale_ids", withheld)
        object.__setattr__(self, "required_check_ids", checks)
        object.__setattr__(self, "request_id", _identity("reasoning-policy-review-request", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "shadow_evaluation_id": self.shadow_evaluation_id,
            "producer_agent_id": self.producer_agent_id,
            "reviewer_agent_id": self.reviewer_agent_id,
            "producer_session_id": self.producer_session_id,
            "reviewer_session_id": self.reviewer_session_id,
            "evidence_packet_ids": list(self.evidence_packet_ids),
            "review_context_ids": list(self.review_context_ids),
            "withheld_rationale_ids": list(self.withheld_rationale_ids),
            "required_check_ids": list(self.required_check_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "request_id": self.request_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyReviewRequest":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy review request schema")
        row = cls(
            proposal_id=state["proposal_id"],
            shadow_evaluation_id=state["shadow_evaluation_id"],
            producer_agent_id=state["producer_agent_id"],
            reviewer_agent_id=state["reviewer_agent_id"],
            producer_session_id=state["producer_session_id"],
            reviewer_session_id=state["reviewer_session_id"],
            evidence_packet_ids=tuple(_sequence(state.get("evidence_packet_ids", ()), "evidence packet state")),
            review_context_ids=tuple(_sequence(state.get("review_context_ids", ()), "review context state")),
            withheld_rationale_ids=tuple(_sequence(state.get("withheld_rationale_ids", ()), "withheld rationale state")),
            required_check_ids=tuple(_sequence(state.get("required_check_ids", ()), "required check state")),
        )
        if state.get("request_id") != row.request_id:
            raise ValueError("policy review request identity does not match canonical content")
        _canonical(state, row.to_state(), "policy review request")
        return row


@dataclass(frozen=True, slots=True)
class PolicyReviewReceipt:
    proposal_id: str
    shadow_evaluation_id: str
    reviewer_agent_id: str
    reviewer_session_id: str
    verdict: PolicyReviewVerdict
    completed_check_ids: tuple[str, ...]
    reproduced_evidence_ids: tuple[str, ...]
    objection_ids: tuple[str, ...]
    gaming_finding_ids: tuple[str, ...]
    leakage_finding_ids: tuple[str, ...]
    reason: str
    request_id: str = ""
    producer_agent_id: str = ""
    producer_session_id: str = ""
    evidence_packet_ids: tuple[str, ...] = ()
    review_context_ids: tuple[str, ...] = ()
    withheld_rationale_ids: tuple[str, ...] = ()
    required_check_ids: tuple[str, ...] = ()
    authority: str = field(init=False, default="advisory_only")
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposal_id", _text(self.proposal_id, "proposal id"))
        object.__setattr__(self, "shadow_evaluation_id", _text(self.shadow_evaluation_id, "shadow evaluation id"))
        object.__setattr__(self, "reviewer_agent_id", _text(self.reviewer_agent_id, "reviewer agent id"))
        object.__setattr__(self, "reviewer_session_id", _text(self.reviewer_session_id, "reviewer session id"))
        object.__setattr__(self, "verdict", PolicyReviewVerdict(self.verdict))
        checks = _ids(self.completed_check_ids, "completed check ids", minimum=1)
        reproduced = _ids(self.reproduced_evidence_ids, "reproduced evidence ids", minimum=1)
        objections = _ids(self.objection_ids, "objection ids")
        gaming = _ids(self.gaming_finding_ids, "gaming finding ids")
        leakage = _ids(self.leakage_finding_ids, "leakage finding ids")
        object.__setattr__(self, "completed_check_ids", checks)
        object.__setattr__(self, "reproduced_evidence_ids", reproduced)
        object.__setattr__(self, "objection_ids", objections)
        object.__setattr__(self, "gaming_finding_ids", gaming)
        object.__setattr__(self, "leakage_finding_ids", leakage)
        object.__setattr__(self, "reason", _text(self.reason, "review reason"))
        if self.verdict is PolicyReviewVerdict.SUPPORTED_FOR_ADOPTION and (objections or gaming or leakage):
            raise ValueError("supported review cannot contain objections, gaming findings, or leakage findings")
        request_id = _text(self.request_id, "fresh-context request id")
        producer_agent = _text(self.producer_agent_id, "fresh-context producer agent id")
        producer_session = _text(self.producer_session_id, "fresh-context producer session id")
        packet = _ids(self.evidence_packet_ids, "receipt evidence packet ids", minimum=2)
        context = _ids(self.review_context_ids, "receipt review context ids", minimum=2)
        withheld = _ids(self.withheld_rationale_ids, "receipt withheld rationale ids", minimum=1)
        required = _ids(self.required_check_ids, "receipt required check ids", minimum=1)
        if producer_agent == self.reviewer_agent_id:
            raise ValueError("fresh-context receipt reviewer must differ from producer")
        if producer_session == self.reviewer_session_id:
            raise ValueError("fresh-context receipt session must differ from producer session")
        if not set(packet).issubset(context):
            raise ValueError("fresh-context receipt context must contain the evidence packet")
        if set(withheld) & set(context):
            raise ValueError("receipt withheld rationale ids must remain outside review context")
        if not set(required).issubset(checks):
            raise ValueError("receipt must complete every required review check")
        if not set(reproduced).issubset(packet):
            raise ValueError("reproduced evidence must come from the review evidence packet")
        if not {self.proposal_id, self.shadow_evaluation_id}.issubset(packet):
            raise ValueError("receipt evidence packet must bind proposal and shadow evaluation")
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "producer_agent_id", producer_agent)
        object.__setattr__(self, "producer_session_id", producer_session)
        object.__setattr__(self, "evidence_packet_ids", packet)
        object.__setattr__(self, "review_context_ids", context)
        object.__setattr__(self, "withheld_rationale_ids", withheld)
        object.__setattr__(self, "required_check_ids", required)
        object.__setattr__(self, "receipt_id", _identity("reasoning-policy-review", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "shadow_evaluation_id": self.shadow_evaluation_id,
            "request_id": self.request_id,
            "producer_agent_id": self.producer_agent_id,
            "producer_session_id": self.producer_session_id,
            "reviewer_agent_id": self.reviewer_agent_id,
            "reviewer_session_id": self.reviewer_session_id,
            "evidence_packet_ids": list(self.evidence_packet_ids),
            "review_context_ids": list(self.review_context_ids),
            "withheld_rationale_ids": list(self.withheld_rationale_ids),
            "required_check_ids": list(self.required_check_ids),
            "verdict": self.verdict.value,
            "completed_check_ids": list(self.completed_check_ids),
            "reproduced_evidence_ids": list(self.reproduced_evidence_ids),
            "objection_ids": list(self.objection_ids),
            "gaming_finding_ids": list(self.gaming_finding_ids),
            "leakage_finding_ids": list(self.leakage_finding_ids),
            "reason": self.reason,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "receipt_id": self.receipt_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyReviewReceipt":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy review receipt schema")
        row = cls(
            proposal_id=state["proposal_id"],
            shadow_evaluation_id=state["shadow_evaluation_id"],
            reviewer_agent_id=state["reviewer_agent_id"],
            reviewer_session_id=state["reviewer_session_id"],
            verdict=PolicyReviewVerdict(state["verdict"]),
            completed_check_ids=tuple(_sequence(state.get("completed_check_ids", ()), "completed check state")),
            reproduced_evidence_ids=tuple(_sequence(state.get("reproduced_evidence_ids", ()), "reproduced evidence state")),
            objection_ids=tuple(_sequence(state.get("objection_ids", ()), "objection state")),
            gaming_finding_ids=tuple(_sequence(state.get("gaming_finding_ids", ()), "gaming finding state")),
            leakage_finding_ids=tuple(_sequence(state.get("leakage_finding_ids", ()), "leakage finding state")),
            reason=state["reason"],
            request_id=state["request_id"],
            producer_agent_id=state["producer_agent_id"],
            producer_session_id=state["producer_session_id"],
            evidence_packet_ids=tuple(_sequence(state.get("evidence_packet_ids", ()), "receipt evidence packet state")),
            review_context_ids=tuple(_sequence(state.get("review_context_ids", ()), "receipt review context state")),
            withheld_rationale_ids=tuple(_sequence(state.get("withheld_rationale_ids", ()), "receipt withheld rationale state")),
            required_check_ids=tuple(_sequence(state.get("required_check_ids", ()), "receipt required check state")),
        )
        if state.get("authority") != row.authority:
            raise ValueError("policy review authority does not match advisory-only contract")
        if state.get("receipt_id") != row.receipt_id:
            raise ValueError("policy review receipt identity does not match canonical content")
        _canonical(state, row.to_state(), "policy review receipt")
        return row


def bind_policy_review(
    request: PolicyReviewRequest,
    *,
    verdict: PolicyReviewVerdict,
    completed_check_ids: Sequence[str],
    reproduced_evidence_ids: Sequence[str],
    reason: str,
    objection_ids: Sequence[str] = (),
    gaming_finding_ids: Sequence[str] = (),
    leakage_finding_ids: Sequence[str] = (),
) -> PolicyReviewReceipt:
    if not isinstance(request, PolicyReviewRequest):
        raise TypeError("policy review binding requires a PolicyReviewRequest")
    return PolicyReviewReceipt(
        proposal_id=request.proposal_id,
        shadow_evaluation_id=request.shadow_evaluation_id,
        reviewer_agent_id=request.reviewer_agent_id,
        reviewer_session_id=request.reviewer_session_id,
        verdict=verdict,
        completed_check_ids=tuple(completed_check_ids),
        reproduced_evidence_ids=tuple(reproduced_evidence_ids),
        objection_ids=tuple(objection_ids),
        gaming_finding_ids=tuple(gaming_finding_ids),
        leakage_finding_ids=tuple(leakage_finding_ids),
        reason=reason,
        request_id=request.request_id,
        producer_agent_id=request.producer_agent_id,
        producer_session_id=request.producer_session_id,
        evidence_packet_ids=request.evidence_packet_ids,
        review_context_ids=request.review_context_ids,
        withheld_rationale_ids=request.withheld_rationale_ids,
        required_check_ids=request.required_check_ids,
    )


@dataclass(frozen=True, slots=True)
class ExternalPolicyAuthorization:
    operation: PolicyOperation
    source_policy_id: str
    target_policy_id: str
    decision_artifact_id: str
    issuer_component_id: str
    issuer_authority_id: str
    authorization_evidence_ids: tuple[str, ...]
    authorization_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", PolicyOperation(self.operation))
        object.__setattr__(self, "source_policy_id", _text(self.source_policy_id, "source policy id"))
        object.__setattr__(self, "target_policy_id", _text(self.target_policy_id, "target policy id"))
        object.__setattr__(self, "decision_artifact_id", _text(self.decision_artifact_id, "decision artifact id"))
        issuer_component = _text(self.issuer_component_id, "issuer component id")
        if issuer_component == COMPONENT_ID:
            raise ValueError("reasoning policy change requires external authorization authority")
        object.__setattr__(self, "issuer_component_id", issuer_component)
        object.__setattr__(self, "issuer_authority_id", _text(self.issuer_authority_id, "issuer authority id"))
        object.__setattr__(self, "authorization_evidence_ids", _ids(self.authorization_evidence_ids, "authorization evidence ids", minimum=1))
        if self.source_policy_id == self.target_policy_id:
            raise ValueError("authorization source and target policies must differ")
        object.__setattr__(self, "authorization_id", _identity("reasoning-policy-authorization", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "operation": self.operation.value,
            "source_policy_id": self.source_policy_id,
            "target_policy_id": self.target_policy_id,
            "decision_artifact_id": self.decision_artifact_id,
            "issuer_component_id": self.issuer_component_id,
            "issuer_authority_id": self.issuer_authority_id,
            "authorization_evidence_ids": list(self.authorization_evidence_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "authorization_id": self.authorization_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ExternalPolicyAuthorization":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy authorization schema")
        row = cls(
            operation=PolicyOperation(state["operation"]),
            source_policy_id=state["source_policy_id"],
            target_policy_id=state["target_policy_id"],
            decision_artifact_id=state["decision_artifact_id"],
            issuer_component_id=state["issuer_component_id"],
            issuer_authority_id=state["issuer_authority_id"],
            authorization_evidence_ids=tuple(_sequence(state.get("authorization_evidence_ids", ()), "authorization evidence state")),
        )
        if state.get("authorization_id") != row.authorization_id:
            raise ValueError("policy authorization identity does not match canonical content")
        _canonical(state, row.to_state(), "policy authorization")
        return row


@dataclass(frozen=True, slots=True)
class PolicyAdoptionReceipt:
    source_policy_id: str
    adopted_policy_id: str
    proposal_id: str
    shadow_evaluation_id: str
    review_receipt_id: str
    authorization_id: str
    authority: str = field(init=False, default="policy_change_receipt_only")
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_policy_id", _text(self.source_policy_id, "source policy id"))
        object.__setattr__(self, "adopted_policy_id", _text(self.adopted_policy_id, "adopted policy id"))
        object.__setattr__(self, "proposal_id", _text(self.proposal_id, "proposal id"))
        object.__setattr__(self, "shadow_evaluation_id", _text(self.shadow_evaluation_id, "shadow evaluation id"))
        object.__setattr__(self, "review_receipt_id", _text(self.review_receipt_id, "review receipt id"))
        object.__setattr__(self, "authorization_id", _text(self.authorization_id, "authorization id"))
        if self.source_policy_id == self.adopted_policy_id:
            raise ValueError("adoption source and target policies must differ")
        object.__setattr__(self, "receipt_id", _identity("reasoning-policy-adoption", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "source_policy_id": self.source_policy_id,
            "adopted_policy_id": self.adopted_policy_id,
            "proposal_id": self.proposal_id,
            "shadow_evaluation_id": self.shadow_evaluation_id,
            "review_receipt_id": self.review_receipt_id,
            "authorization_id": self.authorization_id,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "receipt_id": self.receipt_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyAdoptionReceipt":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy adoption receipt schema")
        row = cls(
            source_policy_id=state["source_policy_id"],
            adopted_policy_id=state["adopted_policy_id"],
            proposal_id=state["proposal_id"],
            shadow_evaluation_id=state["shadow_evaluation_id"],
            review_receipt_id=state["review_receipt_id"],
            authorization_id=state["authorization_id"],
        )
        if state.get("authority") != row.authority:
            raise ValueError("policy adoption authority does not match receipt-only contract")
        if state.get("receipt_id") != row.receipt_id:
            raise ValueError("policy adoption receipt identity does not match canonical content")
        _canonical(state, row.to_state(), "policy adoption receipt")
        return row


def apply_authorized_policy_revision(
    parent: MetareasoningPolicy,
    candidate: MetareasoningPolicy,
    *,
    proposal: PolicyRevisionProposal,
    shadow: PolicyShadowEvaluation,
    review: PolicyReviewReceipt,
    authorization: ExternalPolicyAuthorization,
) -> PolicyAdoptionReceipt:
    if not isinstance(parent, MetareasoningPolicy) or not isinstance(candidate, MetareasoningPolicy):
        raise TypeError("policy adoption requires canonical policy values")
    if not isinstance(proposal, PolicyRevisionProposal) or not isinstance(shadow, PolicyShadowEvaluation):
        raise TypeError("policy adoption requires canonical proposal and shadow artifacts")
    if not isinstance(review, PolicyReviewReceipt) or not isinstance(authorization, ExternalPolicyAuthorization):
        raise TypeError("policy adoption requires canonical review and authorization artifacts")
    if candidate.parent_policy_id != parent.policy_id or candidate.revision != parent.revision + 1:
        raise ValueError("candidate policy lineage does not match parent")
    if proposal.parent_policy_id != parent.policy_id or proposal.candidate_policy_id != candidate.policy_id:
        raise ValueError("proposal does not bind the exact policy source and target")
    if shadow.proposal_id != proposal.proposal_id or shadow.evidence_split_id != proposal.evidence_split.split_id:
        raise ValueError("shadow evaluation does not bind the exact policy proposal")
    if shadow.verdict is not PolicyShadowVerdict.PARETO_NON_REGRESSING:
        raise ValueError("policy adoption requires a Pareto non-regressing shadow evaluation")
    if review.proposal_id != proposal.proposal_id or review.shadow_evaluation_id != shadow.evaluation_id:
        raise ValueError("policy review does not bind the exact proposal and shadow evaluation")
    if review.verdict is not PolicyReviewVerdict.SUPPORTED_FOR_ADOPTION:
        raise ValueError("policy adoption requires a supported fresh-context review")
    if authorization.operation is not PolicyOperation.ADOPT:
        raise ValueError("policy adoption requires ADOPT authorization")
    if authorization.source_policy_id != parent.policy_id:
        raise ValueError("policy adoption authorization source does not match parent")
    if authorization.target_policy_id != candidate.policy_id:
        raise ValueError("policy adoption authorization target does not match candidate")
    if authorization.decision_artifact_id != proposal.proposal_id:
        raise ValueError("policy adoption authorization decision artifact must be the proposal")
    return PolicyAdoptionReceipt(
        source_policy_id=parent.policy_id,
        adopted_policy_id=candidate.policy_id,
        proposal_id=proposal.proposal_id,
        shadow_evaluation_id=shadow.evaluation_id,
        review_receipt_id=review.receipt_id,
        authorization_id=authorization.authorization_id,
    )


@dataclass(frozen=True, slots=True)
class PolicyRollbackReceipt:
    rolled_back_policy_id: str
    restored_policy_id: str
    adoption_receipt_id: str
    authorization_id: str
    authority: str = field(init=False, default="policy_change_receipt_only")
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rolled_back_policy_id", _text(self.rolled_back_policy_id, "rolled back policy id"))
        object.__setattr__(self, "restored_policy_id", _text(self.restored_policy_id, "restored policy id"))
        object.__setattr__(self, "adoption_receipt_id", _text(self.adoption_receipt_id, "adoption receipt id"))
        object.__setattr__(self, "authorization_id", _text(self.authorization_id, "authorization id"))
        if self.rolled_back_policy_id == self.restored_policy_id:
            raise ValueError("rollback source and restored policies must differ")
        object.__setattr__(self, "receipt_id", _identity("reasoning-policy-rollback", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "rolled_back_policy_id": self.rolled_back_policy_id,
            "restored_policy_id": self.restored_policy_id,
            "adoption_receipt_id": self.adoption_receipt_id,
            "authorization_id": self.authorization_id,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "receipt_id": self.receipt_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "PolicyRollbackReceipt":
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported policy rollback receipt schema")
        row = cls(
            rolled_back_policy_id=state["rolled_back_policy_id"],
            restored_policy_id=state["restored_policy_id"],
            adoption_receipt_id=state["adoption_receipt_id"],
            authorization_id=state["authorization_id"],
        )
        if state.get("authority") != row.authority:
            raise ValueError("policy rollback authority does not match receipt-only contract")
        if state.get("receipt_id") != row.receipt_id:
            raise ValueError("policy rollback receipt identity does not match canonical content")
        _canonical(state, row.to_state(), "policy rollback receipt")
        return row


def rollback_policy_revision(
    current_policy: MetareasoningPolicy,
    restored_parent: MetareasoningPolicy,
    *,
    adoption: PolicyAdoptionReceipt,
    authorization: ExternalPolicyAuthorization,
) -> PolicyRollbackReceipt:
    if not isinstance(current_policy, MetareasoningPolicy) or not isinstance(restored_parent, MetareasoningPolicy):
        raise TypeError("policy rollback requires MetareasoningPolicy values")
    if not isinstance(adoption, PolicyAdoptionReceipt) or not isinstance(authorization, ExternalPolicyAuthorization):
        raise TypeError("policy rollback requires canonical adoption and authorization receipts")
    if current_policy.parent_policy_id != restored_parent.policy_id:
        raise ValueError("rollback parent lineage does not match current policy")
    if current_policy.revision != restored_parent.revision + 1:
        raise ValueError("rollback must restore the exact previous policy revision")
    if adoption.source_policy_id != restored_parent.policy_id or adoption.adopted_policy_id != current_policy.policy_id:
        raise ValueError("rollback adoption receipt does not match policy lineage")
    if authorization.operation is not PolicyOperation.ROLLBACK:
        raise ValueError("policy rollback requires ROLLBACK authorization")
    if authorization.source_policy_id != current_policy.policy_id:
        raise ValueError("policy rollback authorization source does not match current policy")
    if authorization.target_policy_id != restored_parent.policy_id:
        raise ValueError("policy rollback authorization target does not match restored policy")
    if authorization.decision_artifact_id != adoption.receipt_id:
        raise ValueError("policy rollback authorization must cite the exact adoption receipt")
    return PolicyRollbackReceipt(
        rolled_back_policy_id=current_policy.policy_id,
        restored_policy_id=restored_parent.policy_id,
        adoption_receipt_id=adoption.receipt_id,
        authorization_id=authorization.authorization_id,
    )
