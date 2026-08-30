from __future__ import annotations

import pytest

from nolane.external_core.reasoning_invention import VerificationPlan


def _plan(threshold: float) -> VerificationPlan:
    return VerificationPlan(
        metric_id="metric.latency_ms",
        baseline_id="baseline.latency.v1",
        success_threshold=threshold,
        perturbation_ids=("probe.load",),
        negative_control_ids=("control.noop",),
        ablation_ids=("ablation.cache",),
        stop_condition_ids=("stop.budget",),
        max_cost=10.0,
        expected_information_gain=2.0,
    )


def test_verification_threshold_is_finite_but_metric_unit_agnostic() -> None:
    assert _plan(125.0).success_threshold == pytest.approx(125.0)
    assert _plan(-0.25).success_threshold == pytest.approx(-0.25)
