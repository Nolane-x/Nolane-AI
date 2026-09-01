"""Proof-carrying semantic context for D. Goal / Design decisions.

This companion compiler turns already-authorized decision and integrity
artifacts into immutable semantic pins. It does not infer truth from prose and
does not rewrite historical Goal/Design receipt identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Iterable, Sequence

from . import _goal_design_base as _base
from .goal_design import (
    DecisionReceipt,
    DesignOption,
    DesignScenario,
    GoalSpec,
    ProofObligation,
    ProofStatus,
    UncertaintyItem,
    _base_goal,
    _base_option,
    stable_digest,
)
from .goal_design_authenticity import verify_decision_receipt
from .goal_design_integrity import (
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
    GoalIntegrityReceipt,
    verify_goal_integrity_receipt,
)

__version__ = "0.2.0"


def _text(name: str, value: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({_text("reference", value) for value in values}))


def _required_refs(name: str, values: Iterable[str]) -> tuple[str, ...]:
    refs = _refs(values)
    if not refs:
        raise ValueError(f"{name} requires references")
    return refs


def _bounded(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return value


class DecisionContextPinKind(str, Enum):
    TERMINAL_GOAL = "terminal_goal"
    HARD_CONSTRAINT = "hard_constraint"
    NON_GOAL = "non_goal"
    ANTI_GOAL = "anti_goal"
    SUCCESS_CRITERION = "success_criterion"
    CHAMPION = "champion"
    RIVAL = "rival"
    OPEN_PROOF = "open_proof"
    CRITICAL_UNKNOWN = "critical_unknown"
    CONTRADICTION = "contradiction"


class DecisionContextTrust(str, Enum):
    INTEGRITY_AUTHORITY = "integrity_authority"
    DECISION_AUTHORITY = "decision_authority"
    PROOF_STATE = "proof_state"
    UNCERTAINTY_STATE = "uncertainty_state"
    EVIDENCE_ASSERTION = "evidence_assertion"


_KIND_RANK = {kind: index for index, kind in enumerate(DecisionContextPinKind)}
_INTEGRITY_KIND_MAP = {
    GoalIntegrityClauseKind.TERMINAL_GOAL: DecisionContextPinKind.TERMINAL_GOAL,
    GoalIntegrityClauseKind.HARD_CONSTRAINT: DecisionContextPinKind.HARD_CONSTRAINT,
    GoalIntegrityClauseKind.NON_GOAL: DecisionContextPinKind.NON_GOAL,
    GoalIntegrityClauseKind.ANTI_GOAL: DecisionContextPinKind.ANTI_GOAL,
    GoalIntegrityClauseKind.SUCCESS_CRITERION: DecisionContextPinKind.SUCCESS_CRITERION,
}


@dataclass(frozen=True)
class DecisionContextPolicy:
    critical_uncertainty_threshold: float = 0.55
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "critical_uncertainty_threshold",
            _bounded("critical_uncertainty_threshold", self.critical_uncertainty_threshold),
        )
        object.__setattr__(
            self,
            "digest",
            stable_digest(
                {
                    "goal_design_decision_context_policy": {
                        "critical_uncertainty_threshold": self.critical_uncertainty_threshold,
                    }
                }
            ),
        )


@dataclass(frozen=True)
class DecisionContextContradiction:
    contradiction_id: str
    goal_id: str
    statement: str
    subject_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    provenance_ref: str
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contradiction_id", _text("contradiction_id", self.contradiction_id))
        object.__setattr__(self, "goal_id", _text("goal_id", self.goal_id))
        object.__setattr__(self, "statement", _text("statement", self.statement))
        object.__setattr__(self, "subject_refs", _required_refs("contradiction", self.subject_refs))
        object.__setattr__(self, "evidence_refs", _required_refs("contradiction evidence", self.evidence_refs))
        object.__setattr__(self, "provenance_ref", _text("provenance_ref", self.provenance_ref))
        payload = {
            "contradiction_id": self.contradiction_id,
            "goal_id": self.goal_id,
            "statement": self.statement,
            "subject_refs": self.subject_refs,
            "evidence_refs": self.evidence_refs,
            "provenance_ref": self.provenance_ref,
        }
        object.__setattr__(
            self,
            "digest",
            stable_digest({"goal_design_decision_context_contradiction": payload}),
        )


@dataclass(frozen=True)
class DecisionContextPin:
    goal_id: str
    kind: DecisionContextPinKind
    subject_ref: str
    statement: str
    trust: DecisionContextTrust
    authority_ref: str
    authority_digest: str
    provenance_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    blocking: bool = False
    salience: float | None = None
    pin_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", _text("goal_id", self.goal_id))
        if not isinstance(self.kind, DecisionContextPinKind):
            object.__setattr__(self, "kind", DecisionContextPinKind(str(self.kind)))
        if not isinstance(self.trust, DecisionContextTrust):
            object.__setattr__(self, "trust", DecisionContextTrust(str(self.trust)))
        for name in ("subject_ref", "statement", "authority_ref", "authority_digest"):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        object.__setattr__(self, "provenance_refs", _refs(self.provenance_refs))
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))
        if self.salience is not None:
            object.__setattr__(self, "salience", _bounded("salience", self.salience))
        payload = {
            "goal_id": self.goal_id,
            "kind": self.kind.value,
            "subject_ref": self.subject_ref,
            "statement": self.statement,
            "trust": self.trust.value,
            "authority_ref": self.authority_ref,
            "authority_digest": self.authority_digest,
            "provenance_refs": self.provenance_refs,
            "evidence_refs": self.evidence_refs,
            "blocking": bool(self.blocking),
            "salience": self.salience,
        }
        object.__setattr__(
            self,
            "pin_id",
            stable_digest({"goal_design_decision_context_pin": payload}),
        )


@dataclass(frozen=True)
class GoalDesignDecisionContext:
    decision_receipt_id: str
    goal_id: str
    selected_option_id: str
    snapshot_digest: str
    integrity_receipt_id: str
    integrity_contract_digest: str
    policy_digest: str
    goal_digest: str
    scenario_set_digest: str
    option_set_digest: str
    evaluation_digest: str
    proof_state_digest: str
    uncertainty_state_digest: str
    pins: tuple[DecisionContextPin, ...]
    evidence_refs: tuple[str, ...]
    context_id: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "decision_receipt_id",
            "goal_id",
            "selected_option_id",
            "snapshot_digest",
            "integrity_receipt_id",
            "integrity_contract_digest",
            "policy_digest",
            "goal_digest",
            "scenario_set_digest",
            "option_set_digest",
            "evaluation_digest",
            "proof_state_digest",
            "uncertainty_state_digest",
        ):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        pins = tuple(
            sorted(
                self.pins,
                key=lambda pin: (_KIND_RANK[pin.kind], pin.subject_ref, pin.pin_id),
            )
        )
        if len({pin.pin_id for pin in pins}) != len(pins):
            raise ValueError("duplicate Goal/Design decision context pin")
        if any(pin.goal_id != self.goal_id for pin in pins):
            raise ValueError("decision context pin belongs to a different goal")
        object.__setattr__(self, "pins", pins)
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))
        payload = {
            "decision_receipt_id": self.decision_receipt_id,
            "goal_id": self.goal_id,
            "selected_option_id": self.selected_option_id,
            "snapshot_digest": self.snapshot_digest,
            "integrity_receipt_id": self.integrity_receipt_id,
            "integrity_contract_digest": self.integrity_contract_digest,
            "policy_digest": self.policy_digest,
            "goal_digest": self.goal_digest,
            "scenario_set_digest": self.scenario_set_digest,
            "option_set_digest": self.option_set_digest,
            "evaluation_digest": self.evaluation_digest,
            "proof_state_digest": self.proof_state_digest,
            "uncertainty_state_digest": self.uncertainty_state_digest,
            "pin_ids": tuple(pin.pin_id for pin in pins),
            "evidence_refs": self.evidence_refs,
        }
        object.__setattr__(
            self,
            "context_id",
            stable_digest({"goal_design_decision_context": payload}),
        )


class GoalDesignDecisionContextCompiler:
    """Compile immutable semantic pins from already-authorized D artifacts."""

    def __init__(self, *, policy: DecisionContextPolicy | None = None) -> None:
        self.policy = policy or DecisionContextPolicy()

    @staticmethod
    def _integrity_pins(
        contract: GoalIntegrityContract,
        integrity_receipt: GoalIntegrityReceipt,
    ) -> tuple[DecisionContextPin, ...]:
        return tuple(
            DecisionContextPin(
                goal_id=contract.goal_id,
                kind=_INTEGRITY_KIND_MAP[clause.kind],
                subject_ref=clause.clause_id,
                statement=clause.statement,
                trust=DecisionContextTrust.INTEGRITY_AUTHORITY,
                authority_ref=integrity_receipt.receipt_id,
                authority_digest=contract.digest,
                provenance_refs=(clause.provenance_ref,),
                blocking=clause.kind
                in {
                    GoalIntegrityClauseKind.TERMINAL_GOAL,
                    GoalIntegrityClauseKind.HARD_CONSTRAINT,
                    GoalIntegrityClauseKind.NON_GOAL,
                    GoalIntegrityClauseKind.ANTI_GOAL,
                },
            )
            for clause in contract.clauses
        )

    @staticmethod
    def _option_pins(
        receipt: DecisionReceipt,
        options: Sequence[DesignOption],
    ) -> tuple[DecisionContextPin, ...]:
        pins: list[DecisionContextPin] = []
        for option in sorted(options, key=lambda item: item.option_id):
            kind = (
                DecisionContextPinKind.CHAMPION
                if option.option_id == receipt.selected_option_id
                else DecisionContextPinKind.RIVAL
            )
            pins.append(
                DecisionContextPin(
                    goal_id=receipt.goal_id,
                    kind=kind,
                    subject_ref=option.option_id,
                    statement=option.label,
                    trust=DecisionContextTrust.DECISION_AUTHORITY,
                    authority_ref=receipt.receipt_id,
                    authority_digest=receipt.evaluation_digest,
                    evidence_refs=tuple(option.evidence_refs),
                )
            )
        return tuple(pins)

    @staticmethod
    def _proof_pins(
        receipt: DecisionReceipt,
        proofs: Sequence[ProofObligation],
    ) -> tuple[DecisionContextPin, ...]:
        return tuple(
            DecisionContextPin(
                goal_id=receipt.goal_id,
                kind=DecisionContextPinKind.OPEN_PROOF,
                subject_ref=proof.proof_id,
                statement=proof.claim,
                trust=DecisionContextTrust.PROOF_STATE,
                authority_ref=receipt.receipt_id,
                authority_digest=receipt.proof_state_digest,
                evidence_refs=tuple(proof.evidence_refs),
                blocking=bool(proof.blocking),
            )
            for proof in sorted(proofs, key=lambda item: item.proof_id)
            if proof.status is ProofStatus.OPEN
        )

    def _uncertainty_pins(
        self,
        receipt: DecisionReceipt,
        uncertainties: Sequence[UncertaintyItem],
    ) -> tuple[DecisionContextPin, ...]:
        pins: list[DecisionContextPin] = []
        for item in sorted(uncertainties, key=lambda row: row.uncertainty_id):
            if item.resolved or item.risk_score < self.policy.critical_uncertainty_threshold:
                continue
            pins.append(
                DecisionContextPin(
                    goal_id=receipt.goal_id,
                    kind=DecisionContextPinKind.CRITICAL_UNKNOWN,
                    subject_ref=item.uncertainty_id,
                    statement=item.statement,
                    trust=DecisionContextTrust.UNCERTAINTY_STATE,
                    authority_ref=receipt.receipt_id,
                    authority_digest=receipt.uncertainty_state_digest,
                    evidence_refs=tuple(item.evidence_refs),
                    blocking=not bool(item.mitigation_ref),
                    salience=min(1.0, float(item.risk_score)),
                )
            )
        return tuple(pins)

    @staticmethod
    def _contradiction_pins(
        receipt: DecisionReceipt,
        contradictions: Sequence[DecisionContextContradiction],
    ) -> tuple[DecisionContextPin, ...]:
        pins: list[DecisionContextPin] = []
        seen: dict[str, DecisionContextContradiction] = {}
        for contradiction in sorted(contradictions, key=lambda item: item.contradiction_id):
            if contradiction.goal_id != receipt.goal_id:
                raise ValueError("decision context contradiction belongs to a different goal")
            existing = seen.get(contradiction.contradiction_id)
            if existing is not None and existing != contradiction:
                raise ValueError("decision context contradiction identity cannot be rebound")
            seen[contradiction.contradiction_id] = contradiction
            pins.append(
                DecisionContextPin(
                    goal_id=receipt.goal_id,
                    kind=DecisionContextPinKind.CONTRADICTION,
                    subject_ref=contradiction.contradiction_id,
                    statement=contradiction.statement,
                    trust=DecisionContextTrust.EVIDENCE_ASSERTION,
                    authority_ref=contradiction.provenance_ref,
                    authority_digest=contradiction.digest,
                    provenance_refs=(contradiction.provenance_ref,),
                    evidence_refs=contradiction.evidence_refs,
                    blocking=True,
                )
            )
        return tuple(pins)

    @staticmethod
    def _manifest_projection(
        version: str,
        goal: GoalSpec,
        options: Sequence[DesignOption],
        receipt: DecisionReceipt,
    ) -> tuple[object, tuple[object, ...]]:
        canonical_options = tuple(sorted(options, key=lambda item: item.option_id))
        if version == "v2":
            return _base_goal(goal), tuple(_base_option(option) for option in canonical_options)

        derived_assumptions = _refs(
            tuple(getattr(goal, "assumption_refs", ()))
            + tuple(
                ref
                for option in canonical_options
                for ref in getattr(option, "assumption_refs", ())
            )
        )
        if derived_assumptions != tuple(receipt.assumption_refs):
            raise ValueError("decision context v3 assumption closure does not bind the decision receipt")
        return goal, canonical_options

    @classmethod
    def _verify_manifest_inputs(
        cls,
        *,
        version: str,
        receipt: DecisionReceipt,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        proofs: Sequence[ProofObligation],
        uncertainties: Sequence[UncertaintyItem],
    ) -> None:
        canonical_scenarios = tuple(sorted(scenarios, key=lambda item: item.scenario_id))
        canonical_options = tuple(sorted(options, key=lambda item: item.option_id))
        canonical_proofs = tuple(sorted(proofs, key=lambda item: item.proof_id))
        canonical_uncertainties = tuple(
            sorted(uncertainties, key=lambda item: item.uncertainty_id)
        )
        manifest_goal, manifest_options = cls._manifest_projection(
            version,
            goal,
            canonical_options,
            receipt,
        )

        expected = {
            "goal": stable_digest({"goal": manifest_goal}),
            "scenario": stable_digest({"scenarios": canonical_scenarios}),
            "option": stable_digest({"options": manifest_options}),
            "proof": stable_digest({"proof_obligations": canonical_proofs}),
            "uncertainty": stable_digest({"uncertainties": canonical_uncertainties}),
        }
        observed = {
            "goal": receipt.goal_digest,
            "scenario": receipt.scenario_set_digest,
            "option": receipt.option_set_digest,
            "proof": receipt.proof_state_digest,
            "uncertainty": receipt.uncertainty_state_digest,
        }
        for name in ("goal", "scenario", "option", "proof", "uncertainty"):
            if expected[name] != observed[name]:
                raise ValueError(
                    f"decision context {name} manifest digest does not bind the decision receipt"
                )

        proof_ids = tuple(item.proof_id for item in canonical_proofs)
        if proof_ids != tuple(receipt.proof_obligation_ids):
            raise ValueError("decision context proof manifest ids do not bind the decision receipt")
        uncertainty_ids = tuple(item.uncertainty_id for item in canonical_uncertainties)
        if uncertainty_ids != tuple(receipt.uncertainty_ids):
            raise ValueError("decision context uncertainty manifest ids do not bind the decision receipt")

        evaluation = _base.GoalDesignCoherencePlane().evaluate_options(
            manifest_goal,
            canonical_scenarios,
            manifest_options,
        )
        if evaluation.digest != receipt.evaluation_digest:
            raise ValueError(
                "decision context evaluation digest does not bind the supplied goal/scenario/option manifest"
            )

    def compile(
        self,
        *,
        decision_receipt: DecisionReceipt,
        integrity_contract: GoalIntegrityContract,
        integrity_receipt: GoalIntegrityReceipt,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        proof_obligations: Sequence[ProofObligation] = (),
        uncertainties: Sequence[UncertaintyItem] = (),
        contradictions: Sequence[DecisionContextContradiction] = (),
    ) -> GoalDesignDecisionContext:
        version = verify_decision_receipt(decision_receipt)
        if version == "v1":
            raise ValueError("proof-carrying decision context requires a v2 or v3 decision manifest")
        verify_goal_integrity_receipt(integrity_receipt, decision_receipt)
        if integrity_contract.goal_id != decision_receipt.goal_id:
            raise ValueError("decision context integrity contract belongs to a different goal")
        if integrity_receipt.contract_digest != integrity_contract.digest:
            raise ValueError("decision context integrity receipt does not bind the supplied contract")
        if goal.goal_id != decision_receipt.goal_id:
            raise ValueError("decision context goal does not bind the decision receipt")

        canonical_scenarios = tuple(sorted(scenarios, key=lambda item: item.scenario_id))
        canonical_options = tuple(sorted(options, key=lambda item: item.option_id))
        canonical_proofs = tuple(sorted(proof_obligations, key=lambda item: item.proof_id))
        canonical_uncertainties = tuple(
            sorted(uncertainties, key=lambda item: item.uncertainty_id)
        )
        selected = [
            option
            for option in canonical_options
            if option.option_id == decision_receipt.selected_option_id
        ]
        if len(selected) != 1:
            raise ValueError("decision context exact option set must contain the selected champion once")

        self._verify_manifest_inputs(
            version=version,
            receipt=decision_receipt,
            goal=goal,
            scenarios=canonical_scenarios,
            options=canonical_options,
            proofs=canonical_proofs,
            uncertainties=canonical_uncertainties,
        )

        pins = (
            self._integrity_pins(integrity_contract, integrity_receipt)
            + self._option_pins(decision_receipt, canonical_options)
            + self._proof_pins(decision_receipt, canonical_proofs)
            + self._uncertainty_pins(decision_receipt, canonical_uncertainties)
            + self._contradiction_pins(decision_receipt, tuple(contradictions))
        )
        evidence_refs = _refs(
            tuple(decision_receipt.evidence_refs)
            + tuple(ref for pin in pins for ref in pin.evidence_refs)
        )
        return GoalDesignDecisionContext(
            decision_receipt_id=decision_receipt.receipt_id,
            goal_id=decision_receipt.goal_id,
            selected_option_id=decision_receipt.selected_option_id,
            snapshot_digest=decision_receipt.snapshot_digest,
            integrity_receipt_id=integrity_receipt.receipt_id,
            integrity_contract_digest=integrity_contract.digest,
            policy_digest=self.policy.digest,
            goal_digest=decision_receipt.goal_digest,
            scenario_set_digest=decision_receipt.scenario_set_digest,
            option_set_digest=decision_receipt.option_set_digest,
            evaluation_digest=decision_receipt.evaluation_digest,
            proof_state_digest=decision_receipt.proof_state_digest,
            uncertainty_state_digest=decision_receipt.uncertainty_state_digest,
            pins=pins,
            evidence_refs=evidence_refs,
        )


__all__ = [
    "DecisionContextContradiction",
    "DecisionContextPin",
    "DecisionContextPinKind",
    "DecisionContextPolicy",
    "DecisionContextTrust",
    "GoalDesignDecisionContext",
    "GoalDesignDecisionContextCompiler",
]
