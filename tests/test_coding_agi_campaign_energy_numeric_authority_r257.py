from __future__ import annotations

from dataclasses import replace
import math

import pytest

from nolane.evaluation.campaign import EvaluationCampaignControlPlane
from nolane.evaluation.campaign_repository import RepositorySnapshotRegistry
from nolane.evaluation.campaign_runner import CampaignRunLedger, CampaignRunReceipt
from nolane.evaluation.campaign_tasks import CampaignPartition, CampaignTaskRegistry
from nolane.evaluation.regimes import BenchmarkDomain, EvaluationMode


_INVALID_NUMERIC_ALIASES = (True, "1.0", float("nan"), float("inf"), float("-inf"))


def _running_ledger() -> CampaignRunLedger:
    repositories = RepositorySnapshotRegistry()
    repositories.register(
        snapshot_id="r257-repository",
        repository="Nolane-x/Nolane-AI",
        revision="1234567890abcdef1234567890abcdef12345678",
        language="python",
        toolchain_digest="r257-toolchain",
        test_command_digest="r257-tests",
        contamination_policy_digest="r257-contamination",
        source_metadata={"campaign": "r257"},
    )
    tasks = CampaignTaskRegistry(repositories=repositories)
    tasks.register(
        task_id="r257-task",
        domain=BenchmarkDomain.CODING,
        repository_snapshot_id="r257-repository",
        objective="Preserve finite numeric campaign energy authority",
        acceptance_command_digest="r257-acceptance",
        difficulty="hard",
        allowed_tools=("pytest",),
        allowed_cores=("evaluation",),
        compute_budget_units=1,
        tool_call_budget=1,
        external_core_budget=1,
        wall_clock_budget_ms=1,
        active_agent_budget=1,
        evaluator_protocol_version="r257-protocol",
        contamination_tags=(),
    )
    tasks.assign_partition("r257-task", CampaignPartition.HELDOUT)
    tasks.freeze_partitions()

    campaigns = EvaluationCampaignControlPlane(repositories=repositories, tasks=tasks)
    campaigns.create_campaign(
        campaign_id="r257-campaign",
        benchmark_id="r257-benchmark",
        task_ids=("r257-task",),
        modes=(EvaluationMode.SINGLE_AGENT,),
        freshness_epoch=1,
        runner_protocol_version="r257-runner",
    )
    campaigns.freeze("r257-campaign")
    campaigns.start("r257-campaign")

    ledger = CampaignRunLedger(campaigns=campaigns, tasks=tasks)
    ledger.create_spec(
        run_id="r257-run",
        campaign_id="r257-campaign",
        task_id="r257-task",
        mode=EvaluationMode.SINGLE_AGENT,
        producer_revision="r257-producer",
        environment_digest="r257-environment",
        toolchain_digest="r257-toolchain",
    )
    return ledger


def _receipt(*, energy_joules: object | None = 1.0) -> CampaignRunReceipt:
    return _running_ledger().record_result(
        run_id="r257-run",
        passed=True,
        false_accepts=0,
        regressions=0,
        compute_units=1,
        tool_calls=1,
        external_core_calls=1,
        wall_clock_ms=1,
        energy_joules=energy_joules,
        active_agents=1,
        output_artifact_ids=("r257-artifact",),
        termination_reason="completed",
    )


@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_campaign_run_receipt_constructor_rejects_noncanonical_or_nonfinite_energy(alias: object) -> None:
    with pytest.raises(ValueError, match=r"energy_joules.*(exact numeric|finite)"):
        replace(_receipt(), energy_joules=alias)


@pytest.mark.parametrize("alias", (True, "1.0"))
def test_campaign_run_receipt_restore_rejects_numeric_alias_laundering(alias: object) -> None:
    state = _receipt().to_state()
    state["energy_joules"] = alias

    with pytest.raises(ValueError, match=r"energy_joules.*(exact numeric|finite)"):
        CampaignRunReceipt.from_state(state)


@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_campaign_run_result_rejects_numeric_alias_or_nonfinite_laundering(alias: object) -> None:
    ledger = _running_ledger()

    with pytest.raises(ValueError, match=r"energy_joules.*(exact numeric|finite)"):
        ledger.record_result(
            run_id="r257-run",
            passed=True,
            false_accepts=0,
            regressions=0,
            compute_units=1,
            tool_calls=1,
            external_core_calls=1,
            wall_clock_ms=1,
            energy_joules=alias,
            active_agents=1,
            output_artifact_ids=("r257-artifact",),
            termination_reason="completed",
        )


def test_campaign_energy_authority_normalizes_exact_builtin_int_to_float() -> None:
    receipt = _receipt(energy_joules=1)

    assert type(receipt.energy_joules) is float
    assert receipt.energy_joules == 1.0


def test_campaign_energy_authority_preserves_none_and_finite_roundtrip() -> None:
    none_receipt = _receipt(energy_joules=None)
    assert none_receipt.energy_joules is None
    assert CampaignRunReceipt.from_state(none_receipt.to_state()) == none_receipt

    receipt = _receipt(energy_joules=1.25)
    restored = CampaignRunReceipt.from_state(receipt.to_state())
    assert restored == receipt
    assert type(restored.energy_joules) is float
    assert math.isfinite(restored.energy_joules)
