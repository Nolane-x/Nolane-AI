"""Goal/Design authority surface with truth-bound decision receipts.

The stable v1/v2 implementation is retained in ``_goal_design_base``. This
module extends that authority surface with first-class assumption references and
receipt v3 while preserving historical receipt identities and all existing
Goal/Design behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from . import _goal_design_base as _base
from ._goal_design_base import *  # noqa: F401,F403

__version__ = "0.3.0"


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


@dataclass(frozen=True)
class GoalSpec(_base.GoalSpec):
    """Goal authority plus explicit truth-maintained assumption dependencies."""

    assumption_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "assumption_refs", _refs(self.assumption_refs))


@dataclass(frozen=True)
class DesignOption(_base.DesignOption):
    """Design option plus explicit truth-maintained assumption dependencies."""

    assumption_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "assumption_refs", _refs(self.assumption_refs))


@dataclass(frozen=True)
class DecisionReceipt(_base.DecisionReceipt):
    """Content-addressed decision authority.

    v1 has the original identity fields, v2 adds the proof-carrying input
    manifest, and v3 additionally binds the exact assumption truth snapshot and
    transitive assumption dependency closure.
    """

    assumption_refs: tuple[str, ...] = ()
    assumption_state_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "assumption_refs", _refs(self.assumption_refs))
        object.__setattr__(self, "assumption_state_digest", str(self.assumption_state_digest).strip())


class GoalDesignCoherencePlane(_base.GoalDesignCoherencePlane):
    """Cross-plane coherence authority with optional assumption-truth binding."""

    def admit_decision(
        self,
        *,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        selected_option_id: str,
        snapshot: GoalDesignSnapshot,
        current_vector: GoalDesignVersionVector,
        proof_obligations: Sequence[ProofObligation] = (),
        uncertainties: Sequence[UncertaintyItem] = (),
        traceability: TraceabilityState | None = None,
        assumption_refs: Sequence[str] = (),
        assumption_state_digest: str = "",
    ) -> DecisionReceipt:
        selected = next(
            (option for option in options if option.option_id == selected_option_id),
            None,
        )
        if selected is None:
            raise CoherenceError(f"selected option {selected_option_id!r} does not exist")

        declared_assumptions = _refs(
            tuple(getattr(goal, "assumption_refs", ()))
            + tuple(getattr(selected, "assumption_refs", ()))
            + tuple(assumption_refs)
        )
        assumption_state_digest = str(assumption_state_digest).strip()
        if declared_assumptions and not assumption_state_digest:
            raise CoherenceError(
                "Goal/Design admission blocked: assumption dependencies require an assumption truth snapshot digest"
            )
        if assumption_state_digest and not declared_assumptions:
            raise CoherenceError(
                "Goal/Design admission blocked: assumption truth snapshot digest requires assumption dependencies"
            )

        base_receipt = super().admit_decision(
            goal=goal,
            scenarios=scenarios,
            options=options,
            selected_option_id=selected_option_id,
            snapshot=snapshot,
            current_vector=current_vector,
            proof_obligations=proof_obligations,
            uncertainties=uncertainties,
            traceability=traceability,
        )

        base_kwargs = {
            "goal_id": base_receipt.goal_id,
            "selected_option_id": base_receipt.selected_option_id,
            "snapshot_digest": base_receipt.snapshot_digest,
            "version_vector": dict(base_receipt.version_vector),
            "evaluation_digest": base_receipt.evaluation_digest,
            "proof_obligation_ids": tuple(base_receipt.proof_obligation_ids),
            "uncertainty_ids": tuple(base_receipt.uncertainty_ids),
            "evidence_refs": tuple(base_receipt.evidence_refs),
            "goal_digest": base_receipt.goal_digest,
            "scenario_set_digest": base_receipt.scenario_set_digest,
            "option_set_digest": base_receipt.option_set_digest,
            "proof_state_digest": base_receipt.proof_state_digest,
            "uncertainty_state_digest": base_receipt.uncertainty_state_digest,
            "traceability_digest": base_receipt.traceability_digest,
        }

        if not declared_assumptions:
            return DecisionReceipt(
                receipt_id=base_receipt.receipt_id,
                input_manifest_digest=base_receipt.input_manifest_digest,
                **base_kwargs,
            )

        input_manifest_payload = {
            "goal_digest": base_receipt.goal_digest,
            "scenario_set_digest": base_receipt.scenario_set_digest,
            "option_set_digest": base_receipt.option_set_digest,
            "proof_state_digest": base_receipt.proof_state_digest,
            "uncertainty_state_digest": base_receipt.uncertainty_state_digest,
            "traceability_digest": base_receipt.traceability_digest,
            "selected_option_id": selected_option_id,
            "snapshot_digest": snapshot.digest,
            "version_vector": snapshot.version_vector.tokens(),
            "assumption_refs": list(declared_assumptions),
            "assumption_state_digest": assumption_state_digest,
        }
        input_manifest_digest = stable_digest(
            {"goal_design_decision_input_manifest": input_manifest_payload}
        )
        receipt_payload = {
            "goal_id": base_receipt.goal_id,
            "selected_option_id": base_receipt.selected_option_id,
            "snapshot_digest": base_receipt.snapshot_digest,
            "version_vector": dict(base_receipt.version_vector),
            "evaluation_digest": base_receipt.evaluation_digest,
            "proof_obligation_ids": list(base_receipt.proof_obligation_ids),
            "uncertainty_ids": list(base_receipt.uncertainty_ids),
            "evidence_refs": list(base_receipt.evidence_refs),
            "goal_digest": base_receipt.goal_digest,
            "scenario_set_digest": base_receipt.scenario_set_digest,
            "option_set_digest": base_receipt.option_set_digest,
            "proof_state_digest": base_receipt.proof_state_digest,
            "uncertainty_state_digest": base_receipt.uncertainty_state_digest,
            "traceability_digest": base_receipt.traceability_digest,
            "input_manifest_digest": input_manifest_digest,
            "assumption_refs": list(declared_assumptions),
            "assumption_state_digest": assumption_state_digest,
        }
        return DecisionReceipt(
            receipt_id=stable_digest({"goal_design_decision": receipt_payload}),
            input_manifest_digest=input_manifest_digest,
            assumption_refs=declared_assumptions,
            assumption_state_digest=assumption_state_digest,
            **base_kwargs,
        )
