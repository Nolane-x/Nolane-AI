"""Live Goal/Design runtime with first-class assumption truth maintenance.

The stable five-plane runtime remains in ``_goal_design_runtime_base``. This
module extends it with truth-bound admission, persistent assumption dependency
lookup, causal truth-change invalidation, and truth-aware revalidation while
preserving v1/v2 decision behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Sequence

from . import _goal_design_runtime_base as _base
from ._goal_design_runtime_base import *  # noqa: F401,F403
from .goal_design import (
    CoherenceError,
    DecisionReceipt,
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignSnapshot,
    GoalSpec,
    ProofObligation,
    UncertaintyItem,
    stable_digest,
)
from .goal_design_ledger import GoalDesignLedger
from .goal_design_truth import AssumptionImpactReport, AssumptionTruthMaintenance

__version__ = "0.4.2"


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


@dataclass(frozen=True)
class AssumptionRuntimeImpact:
    """Authority result for one explicit assumption-truth change."""

    changed_assumption_ids: tuple[str, ...]
    affected_assumption_ids: tuple[str, ...]
    requirement_refs: tuple[str, ...]
    plan_refs: tuple[str, ...]
    component_refs: tuple[str, ...]
    integration_candidate_refs: tuple[str, ...]
    invalidated_decision_ids: tuple[str, ...]
    authority_event_id: str
    digest: str


class DecisionAuthorityIndex(_base.DecisionAuthorityIndex):
    """v3-capable persistent index over immutable decision receipts."""

    @staticmethod
    def _receipt_to_state(receipt: DecisionReceipt) -> dict[str, Any]:
        state = _base.DecisionAuthorityIndex._receipt_to_state(receipt)
        state["assumption_refs"] = list(getattr(receipt, "assumption_refs", ()))
        state["assumption_state_digest"] = str(
            getattr(receipt, "assumption_state_digest", "")
        )
        return state

    @staticmethod
    def _receipt_from_state(state: Mapping[str, Any]) -> DecisionReceipt:
        receipt = _base.DecisionAuthorityIndex._receipt_from_state(state)
        return replace(
            receipt,
            assumption_refs=_refs(state.get("assumption_refs", ())),
            assumption_state_digest=str(state.get("assumption_state_digest", "")).strip(),
        )

    def affected_by_assumptions(self, assumption_ids: Iterable[str]) -> tuple[str, ...]:
        changed = set(_refs(assumption_ids))
        if not changed:
            return ()
        affected = []
        for record in self.active():
            receipt_refs = set(getattr(record.receipt, "assumption_refs", ()))
            if changed.intersection(receipt_refs):
                affected.append(record.receipt.receipt_id)
        return tuple(sorted(affected))


class GoalDesignRuntime(_base.GoalDesignRuntime):
    """Operational five-plane membrane plus assumption truth-maintenance seam."""

    def __init__(
        self,
        *,
        requirements: Any,
        planning: Any,
        architecture: Any,
        integration: Any,
        context: Any,
        truth: AssumptionTruthMaintenance | None = None,
        authority: GoalDesignCoherencePlane | None = None,
        ledger: GoalDesignLedger | None = None,
        decisions: DecisionAuthorityIndex | None = None,
    ) -> None:
        if decisions is None:
            decisions = DecisionAuthorityIndex()
        super().__init__(
            requirements=requirements,
            planning=planning,
            architecture=architecture,
            integration=integration,
            context=context,
            authority=authority,
            ledger=ledger,
            decisions=decisions,
        )
        self.truth = truth

    @staticmethod
    def _binding_assumption_refs(
        goal: GoalSpec,
        options: Sequence[DesignOption],
    ) -> tuple[str, ...]:
        """Assumptions whose truth state participates in decision identity.

        Every evaluated option contributes semantics to robust/Pareto evaluation,
        even when it is not selected. The receipt must therefore bind the truth
        state of the goal plus the complete evaluated option set.
        """

        return _refs(
            tuple(getattr(goal, "assumption_refs", ()))
            + tuple(
                ref
                for option in options
                for ref in getattr(option, "assumption_refs", ())
            )
        )

    def admit(
        self,
        *,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        selected_option_id: str,
        snapshot: GoalDesignSnapshot,
        proof_obligations: Sequence[ProofObligation] = (),
        uncertainties: Sequence[UncertaintyItem] = (),
    ) -> DecisionReceipt:
        selected = next(
            (option for option in options if option.option_id == selected_option_id),
            None,
        )
        if selected is None:
            raise CoherenceError(f"selected option {selected_option_id!r} does not exist")

        binding_assumptions = self._binding_assumption_refs(goal, options)
        bound_assumptions: tuple[str, ...] = ()
        assumption_state_digest = ""
        if binding_assumptions:
            if self.truth is None:
                raise CoherenceError(
                    "Goal/Design admission blocked: truth authority is required for assumption-bound decisions"
                )
            try:
                truth_snapshot = self.truth.snapshot(binding_assumptions)
                # Every evaluated option participates in robust/Pareto scoring.
                # Its assumption state therefore cannot be known-refuted while
                # remaining an admissible semantic input. The existing policy
                # remains reversibility-sensitive for UNKNOWN/CONTESTED state.
                truth_blockers = self.truth.decision_blockers(
                    binding_assumptions,
                    selected.decision_class,
                )
            except ValueError as exc:
                raise CoherenceError(
                    f"Goal/Design admission blocked by assumption truth authority: {exc}"
                ) from exc
            if truth_blockers:
                raise CoherenceError(
                    "Goal/Design admission blocked by assumption truth authority: "
                    + "; ".join(truth_blockers)
                )
            bound_assumptions = truth_snapshot.assumption_ids
            assumption_state_digest = truth_snapshot.digest

        bundle = self.observe()
        admission_kwargs: dict[str, Any] = {}
        if bound_assumptions:
            admission_kwargs.update(
                assumption_refs=bound_assumptions,
                assumption_state_digest=assumption_state_digest,
            )
        receipt = self.authority.admit_decision(
            goal=goal,
            scenarios=scenarios,
            options=options,
            selected_option_id=selected_option_id,
            snapshot=snapshot,
            current_vector=bundle.version_vector,
            proof_obligations=proof_obligations,
            uncertainties=uncertainties,
            traceability=bundle.traceability,
            **admission_kwargs,
        )
        dependencies = tuple(
            sorted(set(selected.requirement_refs) | set(selected.component_refs))
        )
        snapshot_event_id = self._ensure_snapshot_event(snapshot)
        decision_event = self.ledger.record_decision(
            receipt,
            parent_ids=(snapshot_event_id,),
        )
        self.decisions.register(
            receipt,
            dependency_refs=dependencies,
            authority_event_id=decision_event.event_id,
        )
        return receipt

    def apply_assumption_change(
        self,
        changed_assumption_ids: Iterable[str],
    ) -> AssumptionRuntimeImpact:
        """Propagate an explicit truth change into decision lifecycle authority."""

        if self.truth is None:
            raise CoherenceError(
                "Goal/Design truth authority is unavailable; assumption change cannot be applied"
            )
        try:
            report: AssumptionImpactReport = self.truth.analyze_change(
                changed_assumption_ids
            )
        except ValueError as exc:
            raise CoherenceError(
                f"Goal/Design assumption change rejected by truth authority: {exc}"
            ) from exc

        truth_event = self.ledger.record_assumption_change(
            changed_assumption_ids=report.changed_assumption_ids,
            affected_assumption_ids=report.affected_assumption_ids,
            truth_state_digest=self.truth.digest,
            impact_digest=report.digest,
        )

        impacted_assumptions = set(report.affected_assumption_ids)
        invalidated: list[str] = []
        for record in self.decisions.active():
            receipt_refs = set(getattr(record.receipt, "assumption_refs", ()))
            overlap = tuple(sorted(impacted_assumptions.intersection(receipt_refs)))
            if not overlap:
                continue
            reasons = (
                "assumption truth impact: " + ", ".join(overlap),
            )
            self.decisions.mark_stale(record.receipt.receipt_id, reasons)
            parents = tuple(
                parent
                for parent in (record.authority_event_id, truth_event.event_id)
                if parent
            )
            self.ledger.record_invalidation(
                receipt_id=record.receipt.receipt_id,
                snapshot_digest=record.snapshot_digest,
                reasons=reasons,
                parent_ids=parents,
            )
            invalidated.append(record.receipt.receipt_id)

        payload = {
            "changed_assumption_ids": list(report.changed_assumption_ids),
            "affected_assumption_ids": list(report.affected_assumption_ids),
            "requirement_refs": list(report.requirement_refs),
            "plan_refs": list(report.plan_refs),
            "component_refs": list(report.component_refs),
            "integration_candidate_refs": list(report.integration_candidate_refs),
            "invalidated_decision_ids": sorted(invalidated),
            "authority_event_id": truth_event.event_id,
            "truth_state_digest": self.truth.digest,
            "truth_impact_digest": report.digest,
        }
        return AssumptionRuntimeImpact(
            changed_assumption_ids=report.changed_assumption_ids,
            affected_assumption_ids=report.affected_assumption_ids,
            requirement_refs=report.requirement_refs,
            plan_refs=report.plan_refs,
            component_refs=report.component_refs,
            integration_candidate_refs=report.integration_candidate_refs,
            invalidated_decision_ids=tuple(payload["invalidated_decision_ids"]),
            authority_event_id=truth_event.event_id,
            digest=stable_digest({"goal_design_assumption_runtime_impact": payload}),
        )

    def revalidate_decisions(self) -> tuple[str, ...]:
        """Revalidate both the five-plane vector and any v3 truth snapshots."""

        stale = set(super().revalidate_decisions())
        for record in self.decisions.active():
            receipt_refs = tuple(getattr(record.receipt, "assumption_refs", ()))
            bound_digest = str(
                getattr(record.receipt, "assumption_state_digest", "")
            ).strip()
            if not receipt_refs and not bound_digest:
                continue

            reasons: tuple[str, ...] = ()
            if not receipt_refs or not bound_digest:
                reasons = ("decision carries a partial assumption truth binding",)
            elif self.truth is None:
                reasons = ("assumption truth authority is unavailable",)
            else:
                try:
                    current_digest = self.truth.snapshot(receipt_refs).digest
                except ValueError as exc:
                    reasons = (f"assumption truth revalidation failed: {exc}",)
                else:
                    if current_digest != bound_digest:
                        reasons = (
                            "assumption truth snapshot changed after decision admission: "
                            f"{bound_digest} -> {current_digest}",
                        )
            if not reasons:
                continue
            self.decisions.mark_stale(record.receipt.receipt_id, reasons)
            self._record_invalidation(record, reasons)
            stale.add(record.receipt.receipt_id)
        return tuple(sorted(stale))


__all__ = tuple(_base.__all__) + ("AssumptionRuntimeImpact",)
