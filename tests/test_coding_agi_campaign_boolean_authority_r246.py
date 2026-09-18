from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.evaluation.campaign import EvaluationCampaignControlPlane
from nolane.evaluation.campaign_reproduction import (
    CampaignReproductionLedger,
    CampaignReproductionReceipt,
)
from nolane.evaluation.campaign_repository import RepositorySnapshotRegistry
from nolane.evaluation.campaign_runner import CampaignRunLedger, CampaignRunReceipt
from nolane.evaluation.campaign_tasks import CampaignPartition, CampaignTaskRegistry
from nolane.evaluation.regimes import BenchmarkDomain, EvaluationMode


_FALSEY_AND_TRUTHY_ALIASES = (0, 0.0, "", "false")


def _campaign_fixture(*, modes: tuple[EvaluationMode, ...] = (EvaluationMode.ORGANIZATION,)):
    repos = RepositorySnapshotRegistry()
    repos.register(
        snapshot_id="repo-r246",
        repository="example/r246",
        revision="a" * 40,
        language="python",
        toolchain_digest="toolchain-r246",
        test_command_digest="pytest-r246",
        contamination_policy_digest="contam-r246",
        source_metadata={},
    )
    tasks = CampaignTaskRegistry(repositories=repos)
    tasks.register(
        task_id="task-r246",
        domain=BenchmarkDomain.CODING,
        repository_snapshot_id="repo-r246",
        objective="Prove exact boolean campaign authority",
        acceptance_command_digest="accept-r246",
        difficulty="medium",
        allowed_tools=("pytest",),
        allowed_cores=("lsp",),
        compute_budget_units=100,
        tool_call_budget=20,
        external_core_budget=10,
        wall_clock_budget_ms=60_000,
        active_agent_budget=8,
        evaluator_protocol_version="campaign-eval-r246",
        contamination_tags=(),
    )
    tasks.assign_partition("task-r246", CampaignPartition.HELDOUT)
    tasks.freeze_partitions()
    campaigns = EvaluationCampaignControlPlane(repositories=repos, tasks=tasks)
    campaigns.create_campaign(
        campaign_id="campaign-r246",
        benchmark_id="benchmark-r246",
        task_ids=("task-r246",),
        modes=modes,
        freshness_epoch=1,
        runner_protocol_version="campaign-runner-r246",
    )
    campaigns.freeze("campaign-r246")
    return repos, tasks, campaigns


def _run_ledger():
    _repos, tasks, campaigns = _campaign_fixture()
    campaigns.start("campaign-r246")
    runs = CampaignRunLedger(campaigns=campaigns, tasks=tasks)
    spec = runs.create_spec(
        run_id="run-r246",
        campaign_id="campaign-r246",
        task_id="task-r246",
        mode=EvaluationMode.ORGANIZATION,
        producer_revision="revision-r246",
        environment_digest="env-r246",
        toolchain_digest="toolchain-r246",
    )
    return runs, spec


def _record_run(runs: CampaignRunLedger, *, passed: object) -> CampaignRunReceipt:
    return runs.record_result(
        run_id="run-r246",
        passed=passed,
        false_accepts=0,
        regressions=0,
        compute_units=10,
        tool_calls=2,
        external_core_calls=1,
        wall_clock_ms=100,
        energy_joules=None,
        active_agents=1,
        output_artifact_ids=("artifact-r246",),
        termination_reason="completed",
    )


def _run_receipt(*, passed: object) -> CampaignRunReceipt:
    return CampaignRunReceipt(
        run_id="run-r246",
        spec_digest="spec-r246",
        passed=passed,
        false_accepts=0,
        regressions=0,
        compute_units=10,
        tool_calls=2,
        external_core_calls=1,
        wall_clock_ms=100,
        energy_joules=None,
        active_agents=1,
        output_artifact_ids=("artifact-r246",),
        termination_reason="completed",
        digest="digest-r246",
    )


def _canonical_run_state() -> dict[str, object]:
    row = _run_receipt(passed=False)
    payload = row.payload()
    return {**payload, "digest": canonical_digest(payload)}


def _reproduction_fixture():
    runtime = OrganizationRuntime.first_generation()
    _repos, _tasks, campaigns = _campaign_fixture()
    artifact = runtime.artifacts.put(
        kind="campaign-bundle",
        producer_agent_id="verification.integration-e2e.01",
        content="r246-bundle",
        evidence_refs=(),
        metadata={},
    )
    ledger = CampaignReproductionLedger(
        registry=runtime.registry,
        artifacts=runtime.artifacts,
        campaigns=campaigns,
    )
    package = ledger.create_package(
        package_id="pkg-r246",
        campaign_id="campaign-r246",
        observation_ids=("observation-r246",),
        source_revision_digests=("a" * 40,),
        task_set_digest="task-set-r246",
        runner_protocol_digest="runner-protocol-r246",
        environment_digest="env-r246",
        command_manifest_digest="commands-r246",
        artifact_ids=(artifact.artifact_id,),
    )
    return ledger, package


def _reproduction_receipt(*, reproduced: object, independent: object = True) -> CampaignReproductionReceipt:
    return CampaignReproductionReceipt(
        reproduction_id="repro-r246",
        package_id="pkg-r246",
        evaluator_id="external-lab-r246",
        reproduced=reproduced,
        independent=independent,
        artifact_bundle_digest="bundle-r246",
        digest="digest-r246",
    )


def _canonical_reproduction_state() -> dict[str, object]:
    row = _reproduction_receipt(reproduced=False, independent=True)
    payload = row.payload()
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize("alias", _FALSEY_AND_TRUTHY_ALIASES)
def test_campaign_run_record_result_rejects_non_bool_passed_aliases(alias: object) -> None:
    runs, _spec = _run_ledger()

    with pytest.raises(ValueError, match="passed.*exact bool"):
        _record_run(runs, passed=alias)


@pytest.mark.parametrize("alias", _FALSEY_AND_TRUTHY_ALIASES)
def test_campaign_run_receipt_constructor_rejects_non_bool_passed_aliases(alias: object) -> None:
    with pytest.raises(ValueError, match="passed.*exact bool"):
        _run_receipt(passed=alias)


@pytest.mark.parametrize("alias", (0, 0.0))
def test_campaign_run_receipt_restore_rejects_digest_preserving_false_aliases(alias: object) -> None:
    state = _canonical_run_state()
    state["passed"] = alias

    with pytest.raises(ValueError, match="passed.*exact bool"):
        CampaignRunReceipt.from_state(state)


@pytest.mark.parametrize("alias", _FALSEY_AND_TRUTHY_ALIASES)
def test_campaign_reproduction_api_rejects_non_bool_reproduced_aliases(alias: object) -> None:
    ledger, package = _reproduction_fixture()

    with pytest.raises(ValueError, match="reproduced.*exact bool"):
        ledger.record_reproduction(
            reproduction_id="repro-r246",
            package_id=package.package_id,
            evaluator_id="external-lab-r246",
            reproduced=alias,
            artifact_bundle_digest=package.artifact_bundle_digest,
        )


@pytest.mark.parametrize("alias", _FALSEY_AND_TRUTHY_ALIASES)
def test_campaign_reproduction_receipt_constructor_rejects_non_bool_reproduced_aliases(alias: object) -> None:
    with pytest.raises(ValueError, match="reproduced.*exact bool"):
        _reproduction_receipt(reproduced=alias)


@pytest.mark.parametrize("alias", (1, 1.0, "true"))
def test_campaign_reproduction_receipt_constructor_rejects_non_bool_independent_aliases(alias: object) -> None:
    with pytest.raises(ValueError, match="independent.*exact bool"):
        _reproduction_receipt(reproduced=False, independent=alias)


@pytest.mark.parametrize("alias", (0, 0.0))
def test_campaign_reproduction_restore_rejects_digest_preserving_reproduced_aliases(alias: object) -> None:
    state = _canonical_reproduction_state()
    state["reproduced"] = alias

    with pytest.raises(ValueError, match="reproduced.*exact bool"):
        CampaignReproductionReceipt.from_state(state)


@pytest.mark.parametrize("alias", (1, 1.0))
def test_campaign_reproduction_restore_rejects_digest_preserving_independent_aliases(alias: object) -> None:
    state = _canonical_reproduction_state()
    state["independent"] = alias

    with pytest.raises(ValueError, match="independent.*exact bool"):
        CampaignReproductionReceipt.from_state(state)


def test_campaign_boolean_authority_preserves_canonical_bool_round_trips() -> None:
    run_state = _canonical_run_state()
    reproduction_state = _canonical_reproduction_state()

    assert CampaignRunReceipt.from_state(run_state).to_state() == run_state
    assert CampaignReproductionReceipt.from_state(reproduction_state).to_state() == reproduction_state
