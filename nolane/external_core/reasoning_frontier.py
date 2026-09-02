from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.reasoning_invention"
COMPONENT_VERSION = "0.0.5"
SCHEMA_VERSION = "reasoning-frontier-v1"
DESIGN_LINEAGE = (
    "post-Epoch-0 decision-relevant unknown/rival frontier with bounded structural diversity; "
    "immutable reasoning snapshot only"
)


class UnknownKind(str, Enum):
    MISSING_EVIDENCE = "missing_evidence"
    RIVAL_EXPLANATION = "rival_explanation"
    ASSUMPTION = "assumption"
    REGIME_SHIFT = "regime_shift"
    SPECIFICATION_GAP = "specification_gap"
    UNKNOWN = "unknown"


class HypothesisCategory(str, Enum):
    LOCAL = "local"
    DEPENDENCY = "dependency"
    ENVIRONMENT = "environment"
    FRAMING = "framing"
    ADVERSARIAL = "adversarial"
    UNKNOWN = "unknown"


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


def _score(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a finite score")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a finite score") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return number


def _branch_budget(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("branch budget must be an integer")
    if value < 1 or value > 7:
        raise ValueError("branch budget must be in [1, 7]")
    return value


def _identity(prefix: str, state: Mapping[str, object]) -> str:
    return f"{prefix}:{canonical_digest(dict(state))}"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


@dataclass(frozen=True, slots=True)
class DecisionUnknown:
    description: str
    kind: UnknownKind
    impact: float
    uncertainty: float
    decision_relevance: float
    discovery_path_ids: tuple[str, ...]
    could_overturn_decision: bool
    unknown_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "description", _nonempty(self.description, "unknown description"))
        object.__setattr__(self, "kind", UnknownKind(self.kind))
        object.__setattr__(self, "impact", _score(self.impact, "unknown impact"))
        object.__setattr__(self, "uncertainty", _score(self.uncertainty, "unknown uncertainty"))
        object.__setattr__(
            self,
            "decision_relevance",
            _score(self.decision_relevance, "unknown decision relevance"),
        )
        object.__setattr__(
            self,
            "discovery_path_ids",
            _ids(self.discovery_path_ids, "unknown discovery path ids", minimum=1),
        )
        if not isinstance(self.could_overturn_decision, bool):
            raise TypeError("could_overturn_decision must be bool")
        object.__setattr__(self, "unknown_id", _identity("decision-unknown", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "description": self.description,
            "kind": self.kind.value,
            "impact": self.impact,
            "uncertainty": self.uncertainty,
            "decision_relevance": self.decision_relevance,
            "discovery_path_ids": list(self.discovery_path_ids),
            "could_overturn_decision": self.could_overturn_decision,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "unknown_id": self.unknown_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "DecisionUnknown":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported reasoning frontier unknown schema")
        row = cls(
            description=state["description"],
            kind=UnknownKind(str(state["kind"])),
            impact=state["impact"],
            uncertainty=state["uncertainty"],
            decision_relevance=state["decision_relevance"],
            discovery_path_ids=tuple(_sequence(state.get("discovery_path_ids", ()), "unknown discovery path state")),
            could_overturn_decision=state["could_overturn_decision"],
        )
        if str(state.get("unknown_id")) != row.unknown_id:
            raise ValueError("decision unknown identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical decision unknown state")
        return row


@dataclass(frozen=True, slots=True)
class RivalHypothesisRef:
    hypothesis_id: str
    category: HypothesisCategory
    structural_family_id: str
    prediction_ids: tuple[str, ...]
    falsifier_ids: tuple[str, ...]
    evidence_for_ids: tuple[str, ...] = ()
    evidence_against_ids: tuple[str, ...] = ()
    rival_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hypothesis_id", _nonempty(self.hypothesis_id, "rival hypothesis id"))
        object.__setattr__(self, "category", HypothesisCategory(self.category))
        object.__setattr__(
            self,
            "structural_family_id",
            _nonempty(self.structural_family_id, "structural family id"),
        )
        object.__setattr__(self, "prediction_ids", _ids(self.prediction_ids, "prediction ids", minimum=1))
        object.__setattr__(self, "falsifier_ids", _ids(self.falsifier_ids, "falsifier ids", minimum=1))
        object.__setattr__(self, "evidence_for_ids", _ids(self.evidence_for_ids, "evidence-for ids"))
        object.__setattr__(self, "evidence_against_ids", _ids(self.evidence_against_ids, "evidence-against ids"))
        object.__setattr__(self, "rival_id", _identity("rival-hypothesis", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "category": self.category.value,
            "structural_family_id": self.structural_family_id,
            "prediction_ids": list(self.prediction_ids),
            "falsifier_ids": list(self.falsifier_ids),
            "evidence_for_ids": list(self.evidence_for_ids),
            "evidence_against_ids": list(self.evidence_against_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "rival_id": self.rival_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "RivalHypothesisRef":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported reasoning frontier rival schema")
        row = cls(
            hypothesis_id=state["hypothesis_id"],
            category=HypothesisCategory(str(state["category"])),
            structural_family_id=state["structural_family_id"],
            prediction_ids=tuple(_sequence(state.get("prediction_ids", ()), "prediction id state")),
            falsifier_ids=tuple(_sequence(state.get("falsifier_ids", ()), "falsifier id state")),
            evidence_for_ids=tuple(_sequence(state.get("evidence_for_ids", ()), "evidence-for id state")),
            evidence_against_ids=tuple(_sequence(state.get("evidence_against_ids", ()), "evidence-against id state")),
        )
        if str(state.get("rival_id")) != row.rival_id:
            raise ValueError("rival hypothesis identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical rival hypothesis state")
        return row


@dataclass(frozen=True, slots=True)
class ReasoningFrontier:
    reasoning_receipt_id: str
    objective_id: str
    cognitive_library_digest: str
    unknowns: tuple[DecisionUnknown, ...]
    rivals: tuple[RivalHypothesisRef, ...]
    assumption_ids: tuple[str, ...]
    hard_constraint_ids: tuple[str, ...]
    branch_budget: int
    frontier_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reasoning_receipt_id",
            _nonempty(self.reasoning_receipt_id, "reasoning receipt id"),
        )
        object.__setattr__(self, "objective_id", _nonempty(self.objective_id, "objective id"))
        object.__setattr__(
            self,
            "cognitive_library_digest",
            _nonempty(self.cognitive_library_digest, "cognitive library digest"),
        )

        unknowns = tuple(_sequence(self.unknowns, "frontier unknowns"))
        if not all(isinstance(row, DecisionUnknown) for row in unknowns):
            raise TypeError("frontier unknowns must contain DecisionUnknown values")
        unknown_ids = tuple(row.unknown_id for row in unknowns)
        if len(unknown_ids) != len(set(unknown_ids)):
            raise ValueError("frontier unknowns must not contain duplicate unknown ids")
        object.__setattr__(self, "unknowns", tuple(sorted(unknowns, key=lambda row: row.unknown_id)))

        rivals = tuple(_sequence(self.rivals, "frontier rivals"))
        if not rivals or not all(isinstance(row, RivalHypothesisRef) for row in rivals):
            raise TypeError("frontier rivals must contain at least one RivalHypothesisRef")
        hypothesis_ids = tuple(row.hypothesis_id for row in rivals)
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise ValueError("frontier rivals must use unique hypothesis ids")
        rival_ids = tuple(row.rival_id for row in rivals)
        if len(rival_ids) != len(set(rival_ids)):
            raise ValueError("frontier rivals must not contain duplicate rival ids")

        budget = _branch_budget(self.branch_budget)
        if len(rivals) > budget:
            raise ValueError("frontier rival count exceeds branch budget")
        object.__setattr__(self, "branch_budget", budget)
        object.__setattr__(self, "rivals", tuple(sorted(rivals, key=lambda row: row.rival_id)))
        object.__setattr__(self, "assumption_ids", _ids(self.assumption_ids, "assumption ids"))
        object.__setattr__(self, "hard_constraint_ids", _ids(self.hard_constraint_ids, "hard constraint ids"))
        object.__setattr__(self, "frontier_id", _identity("reasoning-frontier", self._semantic_state()))

    @property
    def overturning_unknown_ids(self) -> tuple[str, ...]:
        return tuple(row.unknown_id for row in self.unknowns if row.could_overturn_decision)

    def _semantic_state(self) -> dict[str, object]:
        return {
            "reasoning_receipt_id": self.reasoning_receipt_id,
            "objective_id": self.objective_id,
            "cognitive_library_digest": self.cognitive_library_digest,
            "unknowns": [row.to_state() for row in self.unknowns],
            "rivals": [row.to_state() for row in self.rivals],
            "assumption_ids": list(self.assumption_ids),
            "hard_constraint_ids": list(self.hard_constraint_ids),
            "branch_budget": self.branch_budget,
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "frontier_id": self.frontier_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ReasoningFrontier":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported reasoning frontier schema")
        unknowns = tuple(
            DecisionUnknown.from_state(_mapping(row, "frontier unknown state row"))
            for row in _sequence(state.get("unknowns", ()), "frontier unknown state")
        )
        rivals = tuple(
            RivalHypothesisRef.from_state(_mapping(row, "frontier rival state row"))
            for row in _sequence(state.get("rivals", ()), "frontier rival state")
        )
        row = cls(
            reasoning_receipt_id=state["reasoning_receipt_id"],
            objective_id=state["objective_id"],
            cognitive_library_digest=state["cognitive_library_digest"],
            unknowns=unknowns,
            rivals=rivals,
            assumption_ids=tuple(_sequence(state.get("assumption_ids", ()), "assumption id state")),
            hard_constraint_ids=tuple(_sequence(state.get("hard_constraint_ids", ()), "hard constraint id state")),
            branch_budget=state["branch_budget"],
        )
        if str(state.get("frontier_id")) != row.frontier_id:
            raise ValueError("reasoning frontier identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical reasoning frontier state")
        return row


@dataclass(frozen=True, slots=True)
class AssumptionInversion:
    frontier_id: str
    assumption_id: str
    inversion_statement: str
    consequence_ids: tuple[str, ...]
    surviving_invariant_ids: tuple[str, ...]
    challenger_hypothesis_ids: tuple[str, ...]
    inversion_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frontier_id", _nonempty(self.frontier_id, "frontier id"))
        object.__setattr__(self, "assumption_id", _nonempty(self.assumption_id, "assumption id"))
        object.__setattr__(
            self,
            "inversion_statement",
            _nonempty(self.inversion_statement, "inversion statement"),
        )
        object.__setattr__(self, "consequence_ids", _ids(self.consequence_ids, "consequence ids", minimum=1))
        object.__setattr__(
            self,
            "surviving_invariant_ids",
            _ids(self.surviving_invariant_ids, "surviving invariant ids", minimum=1),
        )
        object.__setattr__(
            self,
            "challenger_hypothesis_ids",
            _ids(self.challenger_hypothesis_ids, "challenger hypothesis ids", minimum=1),
        )
        object.__setattr__(self, "inversion_id", _identity("assumption-inversion", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "frontier_id": self.frontier_id,
            "assumption_id": self.assumption_id,
            "inversion_statement": self.inversion_statement,
            "consequence_ids": list(self.consequence_ids),
            "surviving_invariant_ids": list(self.surviving_invariant_ids),
            "challenger_hypothesis_ids": list(self.challenger_hypothesis_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "inversion_id": self.inversion_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "AssumptionInversion":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported assumption inversion schema")
        row = cls(
            frontier_id=state["frontier_id"],
            assumption_id=state["assumption_id"],
            inversion_statement=state["inversion_statement"],
            consequence_ids=tuple(_sequence(state.get("consequence_ids", ()), "consequence id state")),
            surviving_invariant_ids=tuple(_sequence(state.get("surviving_invariant_ids", ()), "surviving invariant state")),
            challenger_hypothesis_ids=tuple(_sequence(state.get("challenger_hypothesis_ids", ()), "challenger hypothesis state")),
        )
        if str(state.get("inversion_id")) != row.inversion_id:
            raise ValueError("assumption inversion identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical assumption inversion state")
        return row


@dataclass(frozen=True, slots=True)
class RepresentationShift:
    frontier_id: str
    source_representation_id: str
    target_representation_id: str
    mapping_ids: tuple[str, ...]
    new_affordance_ids: tuple[str, ...]
    lost_information_ids: tuple[str, ...]
    challenger_hypothesis_ids: tuple[str, ...]
    shift_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frontier_id", _nonempty(self.frontier_id, "frontier id"))
        source = _nonempty(self.source_representation_id, "source representation id")
        target = _nonempty(self.target_representation_id, "target representation id")
        if source == target:
            raise ValueError("source and target representations must differ")
        object.__setattr__(self, "source_representation_id", source)
        object.__setattr__(self, "target_representation_id", target)
        object.__setattr__(self, "mapping_ids", _ids(self.mapping_ids, "representation mapping ids", minimum=1))
        object.__setattr__(
            self,
            "new_affordance_ids",
            _ids(self.new_affordance_ids, "new affordance ids", minimum=1),
        )
        object.__setattr__(self, "lost_information_ids", _ids(self.lost_information_ids, "lost information ids"))
        object.__setattr__(
            self,
            "challenger_hypothesis_ids",
            _ids(self.challenger_hypothesis_ids, "challenger hypothesis ids"),
        )
        object.__setattr__(self, "shift_id", _identity("representation-shift", self._semantic_state()))

    def _semantic_state(self) -> dict[str, object]:
        return {
            "frontier_id": self.frontier_id,
            "source_representation_id": self.source_representation_id,
            "target_representation_id": self.target_representation_id,
            "mapping_ids": list(self.mapping_ids),
            "new_affordance_ids": list(self.new_affordance_ids),
            "lost_information_ids": list(self.lost_information_ids),
            "challenger_hypothesis_ids": list(self.challenger_hypothesis_ids),
        }

    def to_state(self) -> dict[str, object]:
        return {"schema_version": SCHEMA_VERSION, "shift_id": self.shift_id, **self._semantic_state()}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "RepresentationShift":
        if str(state.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("unsupported representation shift schema")
        row = cls(
            frontier_id=state["frontier_id"],
            source_representation_id=state["source_representation_id"],
            target_representation_id=state["target_representation_id"],
            mapping_ids=tuple(_sequence(state.get("mapping_ids", ()), "representation mapping state")),
            new_affordance_ids=tuple(_sequence(state.get("new_affordance_ids", ()), "new affordance state")),
            lost_information_ids=tuple(_sequence(state.get("lost_information_ids", ()), "lost information state")),
            challenger_hypothesis_ids=tuple(_sequence(state.get("challenger_hypothesis_ids", ()), "challenger hypothesis state")),
        )
        if str(state.get("shift_id")) != row.shift_id:
            raise ValueError("representation shift identity does not match canonical content")
        if row.to_state() != dict(state):
            raise ValueError("non-canonical representation shift state")
        return row


def bind_assumption_inversion(
    frontier: ReasoningFrontier,
    *,
    assumption_id: str,
    inversion_statement: str,
    consequence_ids: Sequence[str],
    surviving_invariant_ids: Sequence[str],
    challenger_hypothesis_ids: Sequence[str],
) -> AssumptionInversion:
    if not isinstance(frontier, ReasoningFrontier):
        raise TypeError("frontier must be ReasoningFrontier")
    assumption = _nonempty(assumption_id, "assumption id")
    if assumption not in frontier.assumption_ids:
        raise ValueError("assumption inversion must target an assumption in the frontier")
    return AssumptionInversion(
        frontier_id=frontier.frontier_id,
        assumption_id=assumption,
        inversion_statement=inversion_statement,
        consequence_ids=tuple(consequence_ids),
        surviving_invariant_ids=tuple(surviving_invariant_ids),
        challenger_hypothesis_ids=tuple(challenger_hypothesis_ids),
    )


def bind_representation_shift(
    frontier: ReasoningFrontier,
    *,
    source_representation_id: str,
    target_representation_id: str,
    mapping_ids: Sequence[str],
    new_affordance_ids: Sequence[str],
    lost_information_ids: Sequence[str] = (),
    challenger_hypothesis_ids: Sequence[str] = (),
) -> RepresentationShift:
    if not isinstance(frontier, ReasoningFrontier):
        raise TypeError("frontier must be ReasoningFrontier")
    return RepresentationShift(
        frontier_id=frontier.frontier_id,
        source_representation_id=source_representation_id,
        target_representation_id=target_representation_id,
        mapping_ids=tuple(mapping_ids),
        new_affordance_ids=tuple(new_affordance_ids),
        lost_information_ids=tuple(lost_information_ids),
        challenger_hypothesis_ids=tuple(challenger_hypothesis_ids),
    )


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "SCHEMA_VERSION",
    "DESIGN_LINEAGE",
    "UnknownKind",
    "HypothesisCategory",
    "DecisionUnknown",
    "RivalHypothesisRef",
    "ReasoningFrontier",
    "AssumptionInversion",
    "RepresentationShift",
    "bind_assumption_inversion",
    "bind_representation_shift",
)
