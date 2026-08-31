from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.reasoning_invention"
COMPONENT_VERSION = "0.0.2"
SCHEMA_VERSION = "reasoning-review-v1"
DESIGN_LINEAGE = (
    "post-Epoch-0 fresh-context information partition and adversarial specification-gaming review; "
    "review evidence remains bounded to scope"
)


class FreshReviewVerdict(str, Enum):
    SUPPORTED_FOR_SCOPE = "supported_for_scope"
    REVISE = "revise"
    REJECTED = "rejected"
    ABSTAIN = "abstain"


def _nonempty(value: object, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return value


def _ids(value: object, name: str, *, minimum: int = 0) -> tuple[str, ...]:
    rows = tuple(_nonempty(row, name) for row in _sequence(value, name))
    if len(rows) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} values")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(rows))


def _identity(prefix: str, state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(state))}"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


@dataclass(frozen=True, slots=True)
class FreshContextReviewRequest:
    goal_id: str
    candidate_id: str
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
        object.__setattr__(self, "goal_id", _nonempty(self.goal_id, "review goal id"))
        object.__setattr__(self, "candidate_id", _nonempty(self.candidate_id, "review candidate id"))
        producer_agent = _nonempty(self.producer_agent_id, "producer agent id")
        reviewer_agent = _nonempty(self.reviewer_agent_id, "reviewer agent id")
        if producer_agent == reviewer_agent:
            raise ValueError("fresh-context reviewer must differ from producer")
        object.__setattr__(self, "producer_agent_id", producer_agent)
        object.__setattr__(self, "reviewer_agent_id", reviewer_agent)

        producer_session = _nonempty(self.producer_session_id, "producer session id")
        reviewer_session = _nonempty(self.reviewer_session_id, "reviewer session id")
        if producer_session == reviewer_session:
            raise ValueError("fresh-context reviewer session must differ from producer session")
        object.__setattr__(self, "producer_session_id", producer_session)
        object.__setattr__(self, "reviewer_session_id", reviewer_session)

        evidence = _ids(self.evidence_packet_ids, "evidence packet ids", minimum=1)
        review_context = _ids(self.review_context_ids, "review context ids", minimum=1)
        withheld = _ids(self.withheld_rationale_ids, "withheld rationale ids", minimum=1)
        checks = _ids(self.required_check_ids, "required review check ids", minimum=1)
        if not set(evidence).issubset(review_context):
            raise ValueError("review context must include the complete evidence packet")
        if set(review_context) & set(withheld):
            raise ValueError("review context and withheld rationale must not overlap")
        object.__setattr__(self, "evidence_packet_ids", evidence)
        object.__setattr__(self, "review_context_ids", review_context)
        object.__setattr__(self, "withheld_rationale_ids", withheld)
        object.__setattr__(self, "required_check_ids", checks)
        object.__setattr__(self, "request_id", _identity("fresh-context-review-request", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "goal_id": self.goal_id,
            "candidate_id": self.candidate_id,
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
    def from_state(cls, state: Mapping[str, object]) -> "FreshContextReviewRequest":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported fresh-context review request schema")
        row = cls(
            goal_id=state["goal_id"],
            candidate_id=state["candidate_id"],
            producer_agent_id=state["producer_agent_id"],
            reviewer_agent_id=state["reviewer_agent_id"],
            producer_session_id=state["producer_session_id"],
            reviewer_session_id=state["reviewer_session_id"],
            evidence_packet_ids=tuple(_sequence(state.get("evidence_packet_ids", ()), "evidence packet state")),
            review_context_ids=tuple(_sequence(state.get("review_context_ids", ()), "review context state")),
            withheld_rationale_ids=tuple(_sequence(state.get("withheld_rationale_ids", ()), "withheld rationale state")),
            required_check_ids=tuple(_sequence(state.get("required_check_ids", ()), "required check state")),
        )
        if str(state.get("request_id")) != row.request_id:
            raise ValueError("fresh-context review request identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical fresh-context review request state")
        return row


@dataclass(frozen=True, slots=True)
class SpecificationGamingFinding:
    requirement_id: str
    loophole_id: str
    gaming_behavior_id: str
    intent_violation_id: str
    blocking: bool
    finding_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_id", _nonempty(self.requirement_id, "requirement id"))
        object.__setattr__(self, "loophole_id", _nonempty(self.loophole_id, "loophole id"))
        object.__setattr__(self, "gaming_behavior_id", _nonempty(self.gaming_behavior_id, "gaming behavior id"))
        object.__setattr__(self, "intent_violation_id", _nonempty(self.intent_violation_id, "intent violation id"))
        if not isinstance(self.blocking, bool):
            raise TypeError("blocking must be bool")
        object.__setattr__(self, "finding_id", _identity("specification-gaming", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "requirement_id": self.requirement_id,
            "loophole_id": self.loophole_id,
            "gaming_behavior_id": self.gaming_behavior_id,
            "intent_violation_id": self.intent_violation_id,
            "blocking": self.blocking,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "finding_id": self.finding_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "SpecificationGamingFinding":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported specification-gaming finding schema")
        row = cls(
            requirement_id=state["requirement_id"],
            loophole_id=state["loophole_id"],
            gaming_behavior_id=state["gaming_behavior_id"],
            intent_violation_id=state["intent_violation_id"],
            blocking=state["blocking"],
        )
        if str(state.get("finding_id")) != row.finding_id:
            raise ValueError("specification-gaming finding identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical specification-gaming finding state")
        return row


@dataclass(frozen=True, slots=True)
class FreshContextReviewReceipt:
    request_id: str
    reviewer_agent_id: str
    reviewer_session_id: str
    verdict: FreshReviewVerdict
    completed_check_ids: tuple[str, ...]
    reproduced_evidence_ids: tuple[str, ...]
    objection_ids: tuple[str, ...]
    counterexample_ids: tuple[str, ...]
    gaming_findings: tuple[SpecificationGamingFinding, ...]
    reason: str
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _nonempty(self.request_id, "review request id"))
        object.__setattr__(self, "reviewer_agent_id", _nonempty(self.reviewer_agent_id, "reviewer agent id"))
        object.__setattr__(self, "reviewer_session_id", _nonempty(self.reviewer_session_id, "reviewer session id"))
        object.__setattr__(self, "verdict", FreshReviewVerdict(self.verdict))
        object.__setattr__(self, "completed_check_ids", _ids(self.completed_check_ids, "completed check ids", minimum=1))
        object.__setattr__(
            self,
            "reproduced_evidence_ids",
            _ids(self.reproduced_evidence_ids, "reproduced evidence ids", minimum=1),
        )
        object.__setattr__(self, "objection_ids", _ids(self.objection_ids, "review objection ids"))
        object.__setattr__(self, "counterexample_ids", _ids(self.counterexample_ids, "review counterexample ids"))

        findings = tuple(_sequence(self.gaming_findings, "specification-gaming findings"))
        if not all(isinstance(row, SpecificationGamingFinding) for row in findings):
            raise TypeError("specification-gaming findings must contain SpecificationGamingFinding values")
        finding_ids = tuple(row.finding_id for row in findings)
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("specification-gaming findings must not contain duplicates")
        object.__setattr__(self, "gaming_findings", tuple(sorted(findings, key=lambda row: row.finding_id)))
        object.__setattr__(self, "reason", _nonempty(self.reason, "review reason"))

        blocking = any(row.blocking for row in self.gaming_findings)
        if self.verdict is FreshReviewVerdict.SUPPORTED_FOR_SCOPE:
            if self.objection_ids or self.counterexample_ids or blocking:
                raise ValueError("supported review cannot contain objections, counterexamples, or blocking gaming findings")
        elif self.verdict is FreshReviewVerdict.REJECTED:
            if not (self.objection_ids or self.counterexample_ids or blocking):
                raise ValueError("rejected review requires an objection, counterexample, or blocking gaming finding")
        elif self.verdict is FreshReviewVerdict.REVISE:
            if not (self.objection_ids or self.gaming_findings):
                raise ValueError("revise review requires an objection or specification-gaming finding")

        object.__setattr__(self, "receipt_id", _identity("fresh-context-review", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "reviewer_agent_id": self.reviewer_agent_id,
            "reviewer_session_id": self.reviewer_session_id,
            "verdict": self.verdict.value,
            "completed_check_ids": list(self.completed_check_ids),
            "reproduced_evidence_ids": list(self.reproduced_evidence_ids),
            "objection_ids": list(self.objection_ids),
            "counterexample_ids": list(self.counterexample_ids),
            "gaming_findings": [row.to_state() for row in self.gaming_findings],
            "reason": self.reason,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "receipt_id": self.receipt_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "FreshContextReviewReceipt":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported fresh-context review receipt schema")
        findings = tuple(
            SpecificationGamingFinding.from_state(_mapping(raw, "specification-gaming finding state"))
            for raw in _sequence(state.get("gaming_findings", ()), "specification-gaming finding state rows")
        )
        row = cls(
            request_id=state["request_id"],
            reviewer_agent_id=state["reviewer_agent_id"],
            reviewer_session_id=state["reviewer_session_id"],
            verdict=FreshReviewVerdict(str(state["verdict"])),
            completed_check_ids=tuple(_sequence(state.get("completed_check_ids", ()), "completed check state")),
            reproduced_evidence_ids=tuple(_sequence(state.get("reproduced_evidence_ids", ()), "reproduced evidence state")),
            objection_ids=tuple(_sequence(state.get("objection_ids", ()), "objection state")),
            counterexample_ids=tuple(_sequence(state.get("counterexample_ids", ()), "counterexample state")),
            gaming_findings=findings,
            reason=state["reason"],
        )
        if str(state.get("receipt_id")) != row.receipt_id:
            raise ValueError("fresh-context review receipt identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical fresh-context review receipt state")
        return row


def bind_fresh_context_review(
    request: FreshContextReviewRequest,
    *,
    verdict: FreshReviewVerdict,
    completed_check_ids: Sequence[str],
    reproduced_evidence_ids: Sequence[str],
    objection_ids: Sequence[str] = (),
    counterexample_ids: Sequence[str] = (),
    gaming_findings: Sequence[SpecificationGamingFinding] = (),
    reason: str,
) -> FreshContextReviewReceipt:
    if not isinstance(request, FreshContextReviewRequest):
        raise TypeError("request must be FreshContextReviewRequest")
    checks = _ids(tuple(completed_check_ids), "completed check ids", minimum=1)
    if not set(request.required_check_ids).issubset(checks):
        raise ValueError("fresh-context review must complete every required check")
    reproduced = _ids(tuple(reproduced_evidence_ids), "reproduced evidence ids", minimum=1)
    if not set(reproduced).issubset(request.evidence_packet_ids):
        raise ValueError("reproduced evidence must come from the review evidence packet")

    return FreshContextReviewReceipt(
        request_id=request.request_id,
        reviewer_agent_id=request.reviewer_agent_id,
        reviewer_session_id=request.reviewer_session_id,
        verdict=FreshReviewVerdict(verdict),
        completed_check_ids=checks,
        reproduced_evidence_ids=reproduced,
        objection_ids=tuple(objection_ids),
        counterexample_ids=tuple(counterexample_ids),
        gaming_findings=tuple(gaming_findings),
        reason=reason,
    )


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "DESIGN_LINEAGE",
    "FreshReviewVerdict",
    "FreshContextReviewRequest",
    "SpecificationGamingFinding",
    "FreshContextReviewReceipt",
    "bind_fresh_context_review",
)
