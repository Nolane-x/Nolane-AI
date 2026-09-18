from __future__ import annotations

from dataclasses import replace

import pytest

from nolane.evaluation.campaign import EvaluationCampaign, EvaluationCampaignControlPlane
from nolane.evaluation.campaign_repository import RepositorySnapshotRegistry
from nolane.evaluation.campaign_runner import CampaignRunLedger, CampaignRunReceipt
from nolane.evaluation.campaign_tasks import CampaignPartition, CampaignTaskManifest, CampaignTaskRegistry
from nolane.evaluation.regimes import BenchmarkDomain, EvaluationMode


_TASK_INTEGER_FIELDS = (
    "compute_budget_units",
    "tool_call_budget",
    "external_core_budget",
    "wall_clock_budget_ms",
    "active_agent_budget",
)
_RUN_INTEGER_FIELDS = (
    "false_accepts",
    "regressions",
    "compute_units",
    "tool_calls",
    "external_core_calls",
    "wall_clock_ms",
    "active_agents",
)
_CONSTRUCTOR_ALIASES = (True, 1.0)
_INGRESS_ALIASES = (True, 1.0, "1")


def _repositories() -> RepositorySnapshotRegistry:
    repositories = RepositorySnapshotRegistry()
    repositories.register(
        snapshot_id="r256-repository",
        repository="Nolane-x/Nolane-AI",
        revision="1234567890abcdef1234567890abcdef12345678",
        language="python",
        toolchain_digest="r256-toolchain",
        test_command_digest="r256-tests",
        contamination_policy_digest="r256-contamination",
        source_metadata={"campaign": "r256"},
    )
    return repositories


def _tasks() -> CampaignTaskRegistry:
    tasks = CampaignTaskRegistry(repositories=_repositories())
    tasks.register(
        task_id="r256-task",
        domain=BenchmarkDomain.CODING,
        repository_snapshot_id="r256-repository",
        objective="Preserve exact integer campaign authority",
        acceptance_command_digest="r256-acceptance",
        difficulty="hard",
        allowed_tools=("pytest",),
        allowed_cores=("evaluation",),
        compute_budget_units=1,
        tool_call_budget=1,
        external_core_budget=1,
        wall_clock_budget_ms=1,
        active_agent_budget=1,
        evaluator_protocol_version="r256-protocol",
        contamination_tags=(),
    )
    return tasks


def _task() -> CampaignTaskManifest:
    return _tasks().get("r256-task")


def _campaign_plane() -> EvaluationCampaignControlPlane:
    tasks = _tasks()
    return EvaluationCampaignControlPlane(repositories=tasks.repositories, tasks=tasks)


def _campaign() -> EvaluationCampaign:
    plane = _campaign_plane()
    return plane.create_campaign(
        campaign_id="r256-campaign",
        benchmark_id="r256-benchmark",
        task_ids=("r256-task",),
        modes=(EvaluationMode.SINGLE_AGENT,),
        freshness_epoch=1,
        runner_protocol_version="r256-runner",
    )


def _running_ledger() -> CampaignRunLedger:
    plane = _campaign_plane()
    plane.tasks.assign_partition("r256-task", CampaignPartition.HELDOUT)
    plane.tasks.freeze_partitions()
    plane.create_campaign(
        campaign_id="r256-campaign",
        benchmark_id="r256-benchmark",
        task_ids=("r256-task",),
        modes=(EvaluationMode.SINGLE_AGENT,),
        freshness_epoch=1,
        runner_protocol_version="r256-runner",
    )
    plane.freeze("r256-campaign")
    plane.start("r256-campaign")
    ledger = CampaignRunLedger(campaigns=plane, tasks=plane.tasks)
    ledger.create_spec(
        run_id="r256-run",
        campaign_id="r256-campaign",
        task_id="r256-task",
        mode=EvaluationMode.SINGLE_AGENT,
        producer_revision="r256-producer",
        environment_digest="r256-environment",
        toolchain_digest="r256-toolchain",
    )
    return ledger


def _receipt() -> CampaignRunReceipt:
    ledger = _running_ledger()
    return ledger.record_result(
        run_id="r256-run",
        passed=True,
        false_accepts=1,
        regressions=1,
        compute_units=1,
        tool_calls=1,
        external_core_calls=1,
        wall_clock_ms=1,
        energy_joules=1.0,
        active_agents=1,
        output_artifact_ids=("r256-artifact",),
        termination_reason="completed",
    )


@pytest.mark.parametrize("field", _TASK_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _CONSTRUCTOR_ALIASES)
def test_campaign_task_constructor_rejects_non_exact_integer_authority(
    field: str,
    alias: object,
) -> None:
    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        replace(_task(), **{field: alias})


@pytest.mark.parametrize("field", _TASK_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_campaign_task_restore_rejects_integer_alias_laundering(
    field: str,
    alias: object,
) -> None:
    state = _task().to_state()
    state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        CampaignTaskManifest.from_state(state)


@pytest.mark.parametrize("field", _TASK_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_campaign_task_registration_rejects_integer_alias_laundering(
    field: str,
    alias: object,
) -> None:
    tasks = CampaignTaskRegistry(repositories=_repositories())
    kwargs: dict[str, object] = {
        "task_id": "r256-task",
        "domain": BenchmarkDomain.CODING,
        "repository_snapshot_id": "r256-repository",
        "objective": "Preserve exact integer campaign authority",
        "acceptance_command_digest": "r256-acceptance",
        "difficulty": "hard",
        "allowed_tools": ("pytest",),
        "allowed_cores": ("evaluation",),
        "compute_budget_units": 1,
        "tool_call_budget": 1,
        "external_core_budget": 1,
        "wall_clock_budget_ms": 1,
        "active_agent_budget": 1,
        "evaluator_protocol_version": "r256-protocol",
        "contamination_tags": (),
    }
    kwargs[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        tasks.register(**kwargs)


@pytest.mark.parametrize("alias", _CONSTRUCTOR_ALIASES)
def test_campaign_constructor_rejects_non_exact_freshness_epoch(alias: object) -> None:
    with pytest.raises(ValueError, match=r"freshness_epoch.*exact int"):
        replace(_campaign(), freshness_epoch=alias)


@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_campaign_restore_rejects_freshness_epoch_alias_laundering(alias: object) -> None:
    state = _campaign().to_state()
    state["freshness_epoch"] = alias

    with pytest.raises(ValueError, match=r"freshness_epoch.*exact int"):
        EvaluationCampaign.from_state(state)


@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_campaign_creation_rejects_freshness_epoch_alias_laundering(alias: object) -> None:
    plane = _campaign_plane()

    with pytest.raises(ValueError, match=r"freshness_epoch.*exact int"):
        plane.create_campaign(
            campaign_id="r256-campaign",
            benchmark_id="r256-benchmark",
            task_ids=("r256-task",),
            modes=(EvaluationMode.SINGLE_AGENT,),
            freshness_epoch=alias,
            runner_protocol_version="r256-runner",
        )


@pytest.mark.parametrize("field", _RUN_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _CONSTRUCTOR_ALIASES)
def test_campaign_run_receipt_constructor_rejects_non_exact_integer_authority(
    field: str,
    alias: object,
) -> None:
    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        replace(_receipt(), **{field: alias})


@pytest.mark.parametrize("field", _RUN_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_campaign_run_receipt_restore_rejects_integer_alias_laundering(
    field: str,
    alias: object,
) -> None:
    state = _receipt().to_state()
    state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        CampaignRunReceipt.from_state(state)


@pytest.mark.parametrize("field", _RUN_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_campaign_run_result_rejects_integer_alias_laundering(
    field: str,
    alias: object,
) -> None:
    ledger = _running_ledger()
    kwargs: dict[str, object] = {
        "run_id": "r256-run",
        "passed": True,
        "false_accepts": 1,
        "regressions": 1,
        "compute_units": 1,
        "tool_calls": 1,
        "external_core_calls": 1,
        "wall_clock_ms": 1,
        "energy_joules": 1.0,
        "active_agents": 1,
        "output_artifact_ids": ("r256-artifact",),
        "termination_reason": "completed",
    }
    kwargs[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        ledger.record_result(**kwargs)


def test_campaign_integer_authority_preserves_canonical_roundtrips() -> None:
    task = _task()
    task_restored = CampaignTaskManifest.from_state(task.to_state())
    assert task_restored == task
    for field in _TASK_INTEGER_FIELDS:
        assert type(getattr(task_restored, field)) is int

    campaign = _campaign()
    campaign_restored = EvaluationCampaign.from_state(campaign.to_state())
    assert campaign_restored == campaign
    assert type(campaign_restored.freshness_epoch) is int

    receipt = _receipt()
    receipt_restored = CampaignRunReceipt.from_state(receipt.to_state())
    assert receipt_restored == receipt
    for field in _RUN_INTEGER_FIELDS:
        assert type(getattr(receipt_restored, field)) is int
