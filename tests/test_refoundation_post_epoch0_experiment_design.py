from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.experiment_design import (
    ExperimentDesign,
    ExperimentDesignExecutionReceipt,
    ExperimentProbeRole,
    PlannedExperimentProbe,
    bind_experiment_design_execution,
)
from nolane.external_core.experimentation import (
    ExperimentHypothesis,
    ExperimentProbe,
    VersionSpace,
    run_shadow_experiment,
)


def _probe(label: str) -> ExperimentProbe:
    return ExperimentProbe((label,))


def _planned_probe(
    label: str,
    role: ExperimentProbeRole,
    cost: float,
) -> PlannedExperimentProbe:
    return PlannedExperimentProbe(_probe(label), role, cost)


def _design(*, max_total_cost: float = 5.0) -> ExperimentDesign:
    return ExperimentDesign(
        reasoning_hypothesis_id="hypothesis:reasoning-1",
        verification_plan_id="verification-plan:vp-1",
        version_space_id="xspace:planned",
        probes=(
            _planned_probe("treatment", ExperimentProbeRole.TREATMENT, 2.0),
            _planned_probe("negative-control", ExperimentProbeRole.NEGATIVE_CONTROL, 1.0),
            _planned_probe("ablation", ExperimentProbeRole.ABLATION, 1.0),
            _planned_probe("verification", ExperimentProbeRole.INDEPENDENT_VERIFICATION, 1.0),
        ),
        max_selection_oracle_calls=2,
        max_total_cost=max_total_cost,
        stop_condition_ids=("stop.invalid-observation", "stop.budget"),
    )


def _accepted_shadow_receipt(design: ExperimentDesign):
    by_role = {row.role: row.probe for row in design.probes}
    treatment = by_role[ExperimentProbeRole.TREATMENT]
    control = by_role[ExperimentProbeRole.NEGATIVE_CONTROL]
    ablation = by_role[ExperimentProbeRole.ABLATION]
    verification = by_role[ExperimentProbeRole.INDEPENDENT_VERIFICATION]

    hypothesis_true = ExperimentHypothesis(
        (
            (treatment.probe_id, "T"),
            (control.probe_id, "same"),
            (ablation.probe_id, "same"),
            (verification.probe_id, "verified"),
        ),
        display_name="true",
    )
    hypothesis_alt = ExperimentHypothesis(
        (
            (treatment.probe_id, "ALT"),
            (control.probe_id, "same"),
            (ablation.probe_id, "same"),
            (verification.probe_id, "not-verified"),
        ),
        display_name="alternative",
    )
    version_space = VersionSpace((hypothesis_true, hypothesis_alt))

    rebound = ExperimentDesign(
        reasoning_hypothesis_id=design.reasoning_hypothesis_id,
        verification_plan_id=design.verification_plan_id,
        version_space_id=version_space.version_space_id,
        probes=design.probes,
        max_selection_oracle_calls=design.max_selection_oracle_calls,
        max_total_cost=design.max_total_cost,
        stop_condition_ids=design.stop_condition_ids,
    )

    observations = {
        treatment.probe_id: "T",
        control.probe_id: "same",
        ablation.probe_id: "same",
        verification.probe_id: "verified",
    }
    receipt = run_shadow_experiment(
        version_space,
        (treatment,),
        lambda probe: observations[probe.probe_id],
        verification_probes=(control, ablation, verification),
        max_selection_oracle_calls=rebound.max_selection_oracle_calls,
    )
    assert receipt.status == "accept"
    return rebound, receipt


def test_design_identity_is_content_addressed_and_order_invariant() -> None:
    first = _design()
    second = ExperimentDesign(
        reasoning_hypothesis_id=first.reasoning_hypothesis_id,
        verification_plan_id=first.verification_plan_id,
        version_space_id=first.version_space_id,
        probes=tuple(reversed(first.probes)),
        max_selection_oracle_calls=first.max_selection_oracle_calls,
        max_total_cost=first.max_total_cost,
        stop_condition_ids=tuple(reversed(first.stop_condition_ids)),
    )

    assert second.design_id == first.design_id
    assert second.to_state() == first.to_state()
    assert ExperimentDesign.from_state(first.to_state()) == first


def test_design_requires_treatment_control_ablation_and_independent_verification() -> None:
    base = _design()
    for missing in ExperimentProbeRole:
        with pytest.raises(ValueError):
            ExperimentDesign(
                reasoning_hypothesis_id=base.reasoning_hypothesis_id,
                verification_plan_id=base.verification_plan_id,
                version_space_id=base.version_space_id,
                probes=tuple(row for row in base.probes if row.role is not missing),
                max_selection_oracle_calls=base.max_selection_oracle_calls,
                max_total_cost=base.max_total_cost,
                stop_condition_ids=base.stop_condition_ids,
            )


def test_controls_and_ablations_are_mandatory_verification_phase_probes() -> None:
    design = _design()
    by_role = {row.role: row.probe.probe_id for row in design.probes}

    assert design.selection_probe_ids == (by_role[ExperimentProbeRole.TREATMENT],)
    assert set(design.verification_probe_ids) == {
        by_role[ExperimentProbeRole.NEGATIVE_CONTROL],
        by_role[ExperimentProbeRole.ABLATION],
        by_role[ExperimentProbeRole.INDEPENDENT_VERIFICATION],
    }


def test_design_rejects_duplicate_probes_and_invalid_budget_values() -> None:
    base = _design()
    with pytest.raises(ValueError):
        ExperimentDesign(
            reasoning_hypothesis_id=base.reasoning_hypothesis_id,
            verification_plan_id=base.verification_plan_id,
            version_space_id=base.version_space_id,
            probes=base.probes + (base.probes[0],),
            max_selection_oracle_calls=base.max_selection_oracle_calls,
            max_total_cost=base.max_total_cost,
            stop_condition_ids=base.stop_condition_ids,
        )

    for bad in (0.0, -1.0, float("nan"), float("inf"), True):
        with pytest.raises((TypeError, ValueError)):
            _design(max_total_cost=bad)


def test_design_must_cover_declared_worst_case_probe_cost() -> None:
    with pytest.raises(ValueError, match="worst-case"):
        _design(max_total_cost=4.5)


def test_design_state_rejects_tampered_identity() -> None:
    design = _design()
    state = deepcopy(design.to_state())
    state["design_id"] = "experiment-design:tampered"
    with pytest.raises(ValueError):
        ExperimentDesign.from_state(state)


def test_execution_binding_proves_authorization_cost_controls_and_independent_verification() -> None:
    design, shadow = _accepted_shadow_receipt(_design())
    bound = bind_experiment_design_execution(design, shadow)

    assert isinstance(bound, ExperimentDesignExecutionReceipt)
    assert bound.design_id == design.design_id
    assert bound.experiment_id == shadow.experiment_id
    assert bound.selected_hypothesis_id == shadow.selected.hypothesis_id
    assert bound.verification_oracle_calls == 3
    assert bound.actual_cost == pytest.approx(design.worst_case_cost)
    assert bound.actual_cost <= design.max_total_cost
    assert bound.promoted is False
    assert ExperimentDesignExecutionReceipt.from_state(bound.to_state()) == bound


def test_execution_binding_rejects_receipt_from_different_design() -> None:
    design, shadow = _accepted_shadow_receipt(_design())
    other = ExperimentDesign(
        reasoning_hypothesis_id=design.reasoning_hypothesis_id,
        verification_plan_id=design.verification_plan_id,
        version_space_id=design.version_space_id,
        probes=tuple(
            PlannedExperimentProbe(row.probe, row.role, row.estimated_cost + 1.0)
            if row.role is ExperimentProbeRole.TREATMENT
            else row
            for row in design.probes
        ),
        max_selection_oracle_calls=design.max_selection_oracle_calls,
        max_total_cost=6.0,
        stop_condition_ids=design.stop_condition_ids,
    )

    bound = bind_experiment_design_execution(other, shadow)
    assert bound.design_id == other.design_id
    assert bound.design_id != design.design_id
    assert bound.actual_cost == pytest.approx(other.worst_case_cost)


def test_execution_binding_rejects_unplanned_probe_authority() -> None:
    design, shadow = _accepted_shadow_receipt(_design())
    by_role = {row.role: row for row in design.probes}
    replacement = PlannedExperimentProbe(
        _probe("different-control"), ExperimentProbeRole.NEGATIVE_CONTROL, 1.0
    )
    incompatible = ExperimentDesign(
        reasoning_hypothesis_id=design.reasoning_hypothesis_id,
        verification_plan_id=design.verification_plan_id,
        version_space_id=design.version_space_id,
        probes=tuple(
            replacement if row.role is ExperimentProbeRole.NEGATIVE_CONTROL else row
            for row in design.probes
        ),
        max_selection_oracle_calls=design.max_selection_oracle_calls,
        max_total_cost=design.max_total_cost,
        stop_condition_ids=design.stop_condition_ids,
    )
    assert by_role[ExperimentProbeRole.NEGATIVE_CONTROL].probe.probe_id in shadow.verification_probe_ids
    with pytest.raises(ValueError, match="verification probes"):
        bind_experiment_design_execution(incompatible, shadow)
