"""Goal/Design authority surface with truth-bound and stress-gated decisions.

The stable v1/v2 implementation is retained in ``_goal_design_base``. This
module extends that authority surface with first-class assumption references,
receipt v3, and a quantified stress gate for non-trivial decisions while
preserving historical receipt identities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from . import _goal_design_base as _base
from ._goal_design_base import *  # noqa: F401,F403
from .goal_design_stress import (
    GoalDesignStressAuthority,
    RecoveryProfile,
    StressAdmissionToken,
    StressPolicy,
    StressWorldEvidence,
)

__version__ = "0.4.1"


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


def _base_goal(goal: GoalSpec) -> _base.GoalSpec:
    """Project a truth-capable goal onto the exact historical v2 schema."""

    return _base.GoalSpec(
        goal_id=goal.goal_id,
        statement=goal.statement,
        objectives=tuple(goal.objectives),
        non_goals=tuple(goal.non_goals),
        constraints=tuple(goal.constraints),
        success_metrics=tuple(goal.success_metrics),
        assumptions=tuple(goal.assumptions),
        evidence_refs=tuple(goal.evidence_refs),
    )


def _base_option(option: DesignOption) -> _base.DesignOption:
    """Project a truth-capable option onto the exact historical v2 schema."""

    return _base.DesignOption(
        option_id=option.option_id,
        label=option.label,
        utilities=option.utilities,
        objective_values=option.objective_values,
        decision_class=option.decision_class,
        rollback_ref=option.rollback_ref,
        evidence_refs=tuple(option.evidence_refs),
        requirement_refs=tuple(option.requirement_refs),
        component_refs=tuple(option.component_refs),
        assumptions=tuple(option.assumptions),
    )


class GoalDesignCoherencePlane(_base.GoalDesignCoherencePlane):
    """Cross-plane coherence authority with truth and stress admission gates."""

    def __init__(
        self,
        *,
        irreversible_uncertainty_threshold: float = 0.55,
        stress: GoalDesignStressAuthority | None = None,
    ) -> None:
        super().__init__(
            irreversible_uncertainty_threshold=irreversible_uncertainty_threshold
        )
        self.stress = stress or GoalDesignStressAuthority()

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
        stress_token: StressAdmissionToken | None = None,
        stress_worlds: Sequence[StressWorldEvidence] = (),
        recovery_profiles: Sequence[RecoveryProfile] = (),
        stress_policy: StressPolicy | None = None,
    ) -> DecisionReceipt:
        selected = next(
            (option for option in options if option.option_id == selected_option_id),
            None,
        )
        if selected is None:
            raise CoherenceError(f"selected option {selected_option_id!r} does not exist")

        declared_assumptions = _refs(
            tuple(getattr(goal, "assumption_refs", ()))
            + tuple(
                ref
                for option in options
                for ref in getattr(option, "assumption_refs", ())
            )
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

        # No truth binding means exact historical v2 semantics. Project the new
        # dataclass surface back to the pre-truth schema so empty v3 fields do
        # not perturb v2 goal/option/evaluation/input-manifest digests.
        if declared_assumptions:
            admission_goal = goal
            admission_options = options
        else:
            admission_goal = _base_goal(goal)
            admission_options = tuple(_base_option(option) for option in options)

        # Preserve the historical blocker ordering. The base admission is pure:
        # it mints an in-memory receipt but does not publish state. Therefore we
        # can first retain rollback/counterfactual/uncertainty diagnostics and
        # then reject an otherwise-admissible non-trivial decision at the new
        # quantified stress boundary before any authority is published.
        base_receipt = super().admit_decision(
            goal=admission_goal,
            scenarios=scenarios,
            options=admission_options,
            selected_option_id=selected_option_id,
            snapshot=snapshot,
            current_vector=current_vector,
            proof_obligations=proof_obligations,
            uncertainties=uncertainties,
            traceability=traceability,
        )

        if selected.decision_class is not DecisionClass.REVERSIBLE:
            if stress_token is None:
                raise CoherenceError(
                    "Goal/Design admission blocked by stress authority: "
                    "costly or irreversible decision requires quantified stress token"
                )
            try:
                verified = self.stress.verify_token(
                    stress_token,
                    goal=goal,
                    scenarios=scenarios,
                    options=options,
                    selected_option_id=selected_option_id,
                    worlds=tuple(stress_worlds),
                    recovery_profiles=tuple(recovery_profiles),
                    policy=stress_policy,
                )
            except (TypeError, ValueError) as exc:
                raise CoherenceError(
                    f"Goal/Design admission blocked by stress authority: {exc}"
                ) from exc
            if not verified.authorized:
                raise CoherenceError(
                    "Goal/Design admission blocked by stress authority: "
                    + "; ".join(verified.blockers)
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
