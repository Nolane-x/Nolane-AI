"""Terminal-intent integrity authority for D. Goal / Design.

The existing GoalSpec and DecisionReceipt schemas remain historical authority.
This companion protocol adds an optional, content-addressed proof that the five
Goal/Design planes still preserve terminal intent, hard constraints, non-goals,
anti-goals, and success criteria without allowing optimization metrics to become
replacement goals.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from .goal_design import DecisionReceipt, stable_digest
from .goal_design_authenticity import verify_decision_receipt

__version__ = "0.1.0"

GOAL_DESIGN_PLANES = (
    "requirements",
    "planning",
    "architecture",
    "integration",
    "context",
)
_PLANE_RANK = {plane: index for index, plane in enumerate(GOAL_DESIGN_PLANES)}


class GoalIntegrityClauseKind(str, Enum):
    TERMINAL_GOAL = "terminal_goal"
    HARD_CONSTRAINT = "hard_constraint"
    NON_GOAL = "non_goal"
    ANTI_GOAL = "anti_goal"
    SUCCESS_CRITERION = "success_criterion"


_KIND_RANK = {
    GoalIntegrityClauseKind.TERMINAL_GOAL: 0,
    GoalIntegrityClauseKind.HARD_CONSTRAINT: 1,
    GoalIntegrityClauseKind.NON_GOAL: 2,
    GoalIntegrityClauseKind.ANTI_GOAL: 3,
    GoalIntegrityClauseKind.SUCCESS_CRITERION: 4,
}


def _text(name: str, value: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({_text("reference", value) for value in values}))


def _planes(values: Iterable[str]) -> tuple[str, ...]:
    normalized = {str(value).strip() for value in values if str(value).strip()}
    unknown = sorted(normalized - set(GOAL_DESIGN_PLANES))
    if unknown:
        raise ValueError(f"unknown Goal/Design plane: {unknown[0]}")
    if not normalized:
        raise ValueError("Goal/Design integrity clause requires at least one plane")
    return tuple(sorted(normalized, key=_PLANE_RANK.__getitem__))


@dataclass(frozen=True)
class GoalIntegrityClause:
    """One immutable clause of the terminal-intent contract."""

    clause_id: str
    goal_id: str
    kind: GoalIntegrityClauseKind
    statement: str
    provenance_ref: str
    required_planes: tuple[str, ...] = GOAL_DESIGN_PLANES

    def __post_init__(self) -> None:
        object.__setattr__(self, "clause_id", _text("clause_id", self.clause_id))
        object.__setattr__(self, "goal_id", _text("goal_id", self.goal_id))
        object.__setattr__(self, "statement", _text("statement", self.statement))
        object.__setattr__(
            self,
            "provenance_ref",
            _text("provenance_ref", self.provenance_ref),
        )
        if not isinstance(self.kind, GoalIntegrityClauseKind):
            object.__setattr__(self, "kind", GoalIntegrityClauseKind(str(self.kind)))
        object.__setattr__(self, "required_planes", _planes(self.required_planes))

    @property
    def digest(self) -> str:
        return stable_digest(
            {
                "goal_integrity_clause": {
                    "clause_id": self.clause_id,
                    "goal_id": self.goal_id,
                    "kind": self.kind.value,
                    "statement": self.statement,
                    "provenance_ref": self.provenance_ref,
                    "required_planes": self.required_planes,
                }
            }
        )


@dataclass(frozen=True)
class GoalIntegrityMetricBinding:
    """Bind a measurement proxy to a success criterion, never to terminal intent."""

    metric_id: str
    goal_id: str
    criterion_ref: str
    metric_ref: str
    provenance_ref: str

    def __post_init__(self) -> None:
        for field in (
            "metric_id",
            "goal_id",
            "criterion_ref",
            "metric_ref",
            "provenance_ref",
        ):
            object.__setattr__(self, field, _text(field, getattr(self, field)))

    @property
    def digest(self) -> str:
        return stable_digest(
            {
                "goal_integrity_metric_binding": {
                    "metric_id": self.metric_id,
                    "goal_id": self.goal_id,
                    "criterion_ref": self.criterion_ref,
                    "metric_ref": self.metric_ref,
                    "provenance_ref": self.provenance_ref,
                }
            }
        )


@dataclass(frozen=True)
class GoalIntegrityContract:
    """Content-addressed terminal-intent authority for one goal."""

    goal_id: str
    clauses: tuple[GoalIntegrityClause, ...]
    metric_bindings: tuple[GoalIntegrityMetricBinding, ...] = ()

    def __post_init__(self) -> None:
        goal_id = _text("goal_id", self.goal_id)
        object.__setattr__(self, "goal_id", goal_id)
        clauses = tuple(self.clauses)
        if not clauses:
            raise ValueError("goal integrity contract requires a terminal goal")
        clause_ids = [clause.clause_id for clause in clauses]
        if len(clause_ids) != len(set(clause_ids)):
            raise ValueError("duplicate clause identity in goal integrity contract")
        foreign = sorted(
            clause.clause_id for clause in clauses if clause.goal_id != goal_id
        )
        if foreign:
            raise ValueError(
                f"goal integrity clause {foreign[0]} is bound to a different goal"
            )
        terminals = [
            clause
            for clause in clauses
            if clause.kind is GoalIntegrityClauseKind.TERMINAL_GOAL
        ]
        if not terminals:
            raise ValueError("goal integrity contract requires at least one terminal goal")
        clauses = tuple(
            sorted(
                clauses,
                key=lambda clause: (_KIND_RANK[clause.kind], clause.clause_id),
            )
        )
        object.__setattr__(self, "clauses", clauses)

        bindings = tuple(self.metric_bindings)
        metric_ids = [binding.metric_id for binding in bindings]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("duplicate metric identity in goal integrity contract")
        clause_by_id = {clause.clause_id: clause for clause in clauses}
        for binding in bindings:
            if binding.goal_id != goal_id:
                raise ValueError(
                    f"goal integrity metric {binding.metric_id} is bound to a different goal"
                )
            target = clause_by_id.get(binding.criterion_ref)
            if target is None:
                raise ValueError(
                    f"goal integrity metric {binding.metric_id} references unknown criterion"
                )
            if target.kind is not GoalIntegrityClauseKind.SUCCESS_CRITERION:
                raise ValueError(
                    "goal integrity metric binding must target a success criterion, "
                    "not terminal intent or another clause kind"
                )
        object.__setattr__(
            self,
            "metric_bindings",
            tuple(sorted(bindings, key=lambda binding: binding.metric_id)),
        )

    @property
    def terminal_clause_ids(self) -> tuple[str, ...]:
        return tuple(
            clause.clause_id
            for clause in self.clauses
            if clause.kind is GoalIntegrityClauseKind.TERMINAL_GOAL
        )

    @property
    def digest(self) -> str:
        return stable_digest(
            {
                "goal_integrity_contract": {
                    "goal_id": self.goal_id,
                    "clauses": tuple(clause.digest for clause in self.clauses),
                    "metric_bindings": tuple(
                        binding.digest for binding in self.metric_bindings
                    ),
                }
            }
        )


@dataclass(frozen=True)
class GoalIntegrityAttestation:
    """One plane's immutable statement about preservation of an exact contract."""

    attestation_id: str
    goal_id: str
    plane: str
    subject_ref: str
    contract_digest: str
    preserved_clause_ids: tuple[str, ...]
    violated_clause_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in (
            "attestation_id",
            "goal_id",
            "subject_ref",
            "contract_digest",
        ):
            object.__setattr__(self, field, _text(field, getattr(self, field)))
        plane = str(self.plane).strip()
        if plane not in _PLANE_RANK:
            raise ValueError(f"unknown Goal/Design plane: {plane}")
        object.__setattr__(self, "plane", plane)
        preserved = _refs(self.preserved_clause_ids)
        violated = _refs(self.violated_clause_ids)
        overlap = sorted(set(preserved) & set(violated))
        if overlap:
            raise ValueError(
                f"clause {overlap[0]} cannot be both preserved and violated"
            )
        object.__setattr__(self, "preserved_clause_ids", preserved)
        object.__setattr__(self, "violated_clause_ids", violated)
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))

    @property
    def digest(self) -> str:
        return stable_digest(
            {
                "goal_integrity_attestation": {
                    "attestation_id": self.attestation_id,
                    "goal_id": self.goal_id,
                    "plane": self.plane,
                    "subject_ref": self.subject_ref,
                    "contract_digest": self.contract_digest,
                    "preserved_clause_ids": self.preserved_clause_ids,
                    "violated_clause_ids": self.violated_clause_ids,
                    "evidence_refs": self.evidence_refs,
                }
            }
        )


@dataclass(frozen=True)
class GoalIntegrityAssessment:
    """Deterministic fail-closed assessment of terminal-intent preservation."""

    authorized: bool
    goal_id: str
    contract_digest: str
    attestation_ids: tuple[str, ...]
    missing_preservations: tuple[tuple[str, str], ...]
    violated_clause_ids: tuple[str, ...]
    stale_attestation_ids: tuple[str, ...]

    @property
    def digest(self) -> str:
        return stable_digest(
            {
                "goal_integrity_assessment": {
                    "authorized": self.authorized,
                    "goal_id": self.goal_id,
                    "contract_digest": self.contract_digest,
                    "attestation_ids": self.attestation_ids,
                    "missing_preservations": self.missing_preservations,
                    "violated_clause_ids": self.violated_clause_ids,
                    "stale_attestation_ids": self.stale_attestation_ids,
                }
            }
        )


def assess_goal_integrity(
    contract: GoalIntegrityContract,
    attestations: Sequence[GoalIntegrityAttestation],
) -> GoalIntegrityAssessment:
    """Assess whether every required plane preserves the exact current contract."""

    same_goal = tuple(
        attestation
        for attestation in attestations
        if attestation.goal_id == contract.goal_id
    )
    identity_map: dict[str, GoalIntegrityAttestation] = {}
    for attestation in same_goal:
        existing = identity_map.get(attestation.attestation_id)
        if existing is not None and existing != attestation:
            raise ValueError(
                f"attestation identity {attestation.attestation_id} cannot be rebound"
            )
        identity_map[attestation.attestation_id] = attestation

    stale = tuple(
        sorted(
            attestation.attestation_id
            for attestation in identity_map.values()
            if attestation.contract_digest != contract.digest
        )
    )
    current = tuple(
        sorted(
            (
                attestation
                for attestation in identity_map.values()
                if attestation.contract_digest == contract.digest
            ),
            key=lambda attestation: (
                _PLANE_RANK[attestation.plane],
                attestation.attestation_id,
            ),
        )
    )
    by_plane: dict[str, GoalIntegrityAttestation] = {}
    for attestation in current:
        if attestation.plane in by_plane:
            raise ValueError(
                f"multiple current integrity attestations for plane {attestation.plane}"
            )
        by_plane[attestation.plane] = attestation

    known_clause_ids = {clause.clause_id for clause in contract.clauses}
    for attestation in current:
        unknown = sorted(
            (set(attestation.preserved_clause_ids) | set(attestation.violated_clause_ids))
            - known_clause_ids
        )
        if unknown:
            raise ValueError(
                f"integrity attestation references unknown clause {unknown[0]}"
            )

    missing: list[tuple[str, str]] = []
    for clause in contract.clauses:
        for plane in clause.required_planes:
            attestation = by_plane.get(plane)
            if (
                attestation is None
                or clause.clause_id not in attestation.preserved_clause_ids
            ):
                missing.append((plane, clause.clause_id))
    missing_tuple = tuple(
        sorted(missing, key=lambda item: (_PLANE_RANK[item[0]], item[1]))
    )
    violated = tuple(
        sorted(
            {
                clause_id
                for attestation in current
                for clause_id in attestation.violated_clause_ids
            }
        )
    )
    authorized = not missing_tuple and not violated
    return GoalIntegrityAssessment(
        authorized=authorized,
        goal_id=contract.goal_id,
        contract_digest=contract.digest,
        attestation_ids=tuple(
            sorted(attestation.attestation_id for attestation in current)
        ),
        missing_preservations=missing_tuple,
        violated_clause_ids=violated,
        stale_attestation_ids=stale,
    )


@dataclass(frozen=True)
class GoalIntegrityReceipt:
    """Companion authority binding terminal integrity to an existing decision."""

    receipt_id: str
    decision_receipt_id: str
    goal_id: str
    selected_option_id: str
    contract_digest: str
    assessment_digest: str
    attestation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "receipt_id",
            "decision_receipt_id",
            "goal_id",
            "selected_option_id",
            "contract_digest",
            "assessment_digest",
        ):
            object.__setattr__(self, field, _text(field, getattr(self, field)))
        object.__setattr__(self, "attestation_ids", _refs(self.attestation_ids))


def _integrity_receipt_payload(receipt: GoalIntegrityReceipt) -> dict[str, object]:
    return {
        "decision_receipt_id": receipt.decision_receipt_id,
        "goal_id": receipt.goal_id,
        "selected_option_id": receipt.selected_option_id,
        "contract_digest": receipt.contract_digest,
        "assessment_digest": receipt.assessment_digest,
        "attestation_ids": receipt.attestation_ids,
    }


def _expected_integrity_receipt_id(receipt: GoalIntegrityReceipt) -> str:
    return stable_digest({"goal_integrity_receipt": _integrity_receipt_payload(receipt)})


def mint_goal_integrity_receipt(
    *,
    decision_receipt: DecisionReceipt,
    contract: GoalIntegrityContract,
    assessment: GoalIntegrityAssessment,
) -> GoalIntegrityReceipt:
    """Mint integrity authority without rewriting the historical decision receipt."""

    verify_decision_receipt(decision_receipt)
    if decision_receipt.goal_id != contract.goal_id:
        raise ValueError("goal integrity contract does not bind the decision goal")
    if assessment.goal_id != contract.goal_id:
        raise ValueError("goal integrity assessment does not bind the contract goal")
    if assessment.contract_digest != contract.digest:
        raise ValueError("goal integrity assessment does not bind the current contract")
    if not assessment.authorized:
        raise ValueError("goal integrity assessment is not authorized")

    provisional = GoalIntegrityReceipt(
        receipt_id="pending",
        decision_receipt_id=decision_receipt.receipt_id,
        goal_id=decision_receipt.goal_id,
        selected_option_id=decision_receipt.selected_option_id,
        contract_digest=contract.digest,
        assessment_digest=assessment.digest,
        attestation_ids=assessment.attestation_ids,
    )
    return GoalIntegrityReceipt(
        receipt_id=_expected_integrity_receipt_id(provisional),
        decision_receipt_id=provisional.decision_receipt_id,
        goal_id=provisional.goal_id,
        selected_option_id=provisional.selected_option_id,
        contract_digest=provisional.contract_digest,
        assessment_digest=provisional.assessment_digest,
        attestation_ids=provisional.attestation_ids,
    )


def verify_goal_integrity_receipt(
    receipt: GoalIntegrityReceipt,
    decision_receipt: DecisionReceipt,
) -> None:
    """Prove exact companion-receipt identity and decision lineage."""

    verify_decision_receipt(decision_receipt)
    if receipt.decision_receipt_id != decision_receipt.receipt_id:
        raise ValueError("goal integrity receipt does not bind the decision receipt")
    if receipt.goal_id != decision_receipt.goal_id:
        raise ValueError("goal integrity receipt does not bind the decision goal")
    if receipt.selected_option_id != decision_receipt.selected_option_id:
        raise ValueError("goal integrity receipt selected option does not bind the decision")
    expected = _expected_integrity_receipt_id(receipt)
    if receipt.receipt_id != expected:
        raise ValueError("goal integrity receipt identity digest mismatch")


__all__ = [
    "GOAL_DESIGN_PLANES",
    "GoalIntegrityAssessment",
    "GoalIntegrityAttestation",
    "GoalIntegrityClause",
    "GoalIntegrityClauseKind",
    "GoalIntegrityContract",
    "GoalIntegrityMetricBinding",
    "GoalIntegrityReceipt",
    "assess_goal_integrity",
    "mint_goal_integrity_receipt",
    "verify_goal_integrity_receipt",
]
