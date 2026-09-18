from __future__ import annotations

import copy

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord
from cogcoder.organization.evaluation_regimes import BenchmarkDomain, EvidenceProvenanceClass, EvaluationMode


def _release_fixture(runtime: OrganizationRuntime):
    control = runtime.evaluation_scaling
    regime = control.regimes.register(
        regime_id="r242-regime", benchmark_id="r242-bench", domain=BenchmarkDomain.CODING,
        task_set_digest="r242-tasks", repository_revision_digest="r242-repo-sha", tool_envelope_digest="r242-tools",
        compute_budget_units=100, tool_call_budget=10, external_core_budget=2,
        wall_clock_budget_ms=10_000, active_agent_budget=4, freshness_epoch=5,
        evaluator_protocol_version="r242-protocol-v1", provenance_class=EvidenceProvenanceClass.EXTERNAL_INDEPENDENT,
        fresh=True, heldout=True,
    )
    observation = control.evidence.record_observation(
        observation_id="r242-observation", regime_id=regime.regime_id, mode=EvaluationMode.ORGANIZATION,
        producer_revision="r242-system-v1", score=0.8, task_count=10, pass_count=8,
        false_accepts=0, regressions=0, compute_units=90, tool_calls=5, external_core_calls=1,
        wall_clock_ms=5_000, energy_joules=200.0, active_agents=4,
        evidence_artifact_ids=("r242-external-evidence-artifact",),
        evidence=EvidenceRecord("r242-evidence", "verification.chief", True),
        external_evaluator_id="r242-independent-lab-A",
    )
    report = control.parameters.parameter_footprint(
        active_agent_ids=("nolane.central", "verification.chief"), active_ephemeral_count=0,
        compute_units=90, latency_ms=5_000, energy_joules=200.0,
    )
    artifact = runtime.artifacts.put(
        kind="evaluation-release-bundle", producer_agent_id="verification.chief",
        content="R2.42 immutable evaluation bundle", evidence_refs=("r242-evidence",),
        metadata={"regime": regime.regime_digest},
    )
    release = control.releases.create_release(
        release_id="r242-release", release_version="1.0.0", source_commit_sha="a" * 40,
        regime_ids=(regime.regime_id,), observation_ids=(observation.observation_id,), comparison_ids=(),
        stress_assessment_ids=(), parameter_report_id=report.report_id, claim_assessment_ids=(),
        scaling_decision_ids=(), artifact_ids=(artifact.artifact_id,),
        evaluator_protocol_version="r242-protocol-v1", independent_evaluator_ids=("r242-independent-lab-A",),
        reproduction_command_digest="r242-command-digest", environment_toolchain_digest="r242-environment-digest",
        created_logical_epoch=10,
    )
    return control, artifact, release


def _record_reproduction(control, artifact, release, *, passed):
    return control.releases.record_reproduction(
        release_id=release.release_id, evaluator_id="r242-independent-lab-B",
        release_digest=release.digest, artifact_digest=artifact.digest,
        evaluator_protocol_version="r242-protocol-v1", reproduction_command_digest="r242-command-digest",
        environment_toolchain_digest="r242-environment-digest", passed=passed,
    )


@pytest.mark.parametrize("alias", ["false", "true", 0, 1])
def test_record_reproduction_rejects_non_boolean_passed_aliases(alias: object) -> None:
    runtime = OrganizationRuntime.first_generation()
    control, artifact, release = _release_fixture(runtime)
    with pytest.raises(ValueError, match="reproduction passed.*exact bool"):
        _record_reproduction(control, artifact, release, passed=alias)


def test_reproduction_receipt_restore_rejects_truthy_false_alias() -> None:
    from nolane.evaluation.release import ReproductionReceipt
    runtime = OrganizationRuntime.first_generation()
    control, artifact, release = _release_fixture(runtime)
    receipt = _record_reproduction(control, artifact, release, passed=True)
    state = receipt.to_state()
    state["passed"] = "false"
    with pytest.raises(ValueError, match="reproduction passed.*exact bool"):
        ReproductionReceipt.from_state(state)


def test_runtime_restore_rejects_truthy_false_reproduction_alias() -> None:
    runtime = OrganizationRuntime.first_generation()
    control, artifact, release = _release_fixture(runtime)
    receipt = _record_reproduction(control, artifact, release, passed=True)
    assert control.releases.is_reproduction_valid(receipt.reproduction_id)
    state = copy.deepcopy(runtime.to_state())
    state["evaluation_scaling"]["releases"]["reproductions"][0]["passed"] = "false"
    with pytest.raises(ValueError, match="reproduction passed.*exact bool"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "alias"),
    [
        ("passed", "false"),
        ("passed", 1),
        ("independent", "false"),
        ("independent", 1),
    ],
)
def test_reproduction_receipt_constructor_rejects_non_boolean_authority(
    field: str, alias: object
) -> None:
    from nolane.evaluation.release import ReproductionReceipt

    runtime = OrganizationRuntime.first_generation()
    control, artifact, release = _release_fixture(runtime)
    receipt = _record_reproduction(control, artifact, release, passed=True)
    values = receipt.to_state()
    values[field] = alias

    with pytest.raises(ValueError, match=f"reproduction {field}.*exact bool"):
        ReproductionReceipt(**values)


@pytest.mark.parametrize("alias", ["false", "true", 0, 1])
def test_reproduction_receipt_restore_rejects_non_boolean_independent_aliases(
    alias: object,
) -> None:
    from nolane.evaluation.release import ReproductionReceipt

    runtime = OrganizationRuntime.first_generation()
    control, artifact, release = _release_fixture(runtime)
    receipt = _record_reproduction(control, artifact, release, passed=True)
    state = receipt.to_state()
    state["independent"] = alias

    with pytest.raises(ValueError, match="reproduction independent.*exact bool"):
        ReproductionReceipt.from_state(state)


def test_runtime_restore_rejects_truthy_false_reproduction_independent_alias() -> None:
    runtime = OrganizationRuntime.first_generation()
    control, artifact, release = _release_fixture(runtime)
    receipt = _record_reproduction(control, artifact, release, passed=True)
    assert control.releases.is_reproduction_valid(receipt.reproduction_id)

    state = copy.deepcopy(runtime.to_state())
    state["evaluation_scaling"]["releases"]["reproductions"][0]["independent"] = "false"

    with pytest.raises(ValueError, match="reproduction independent.*exact bool"):
        OrganizationRuntime.from_state(state)
