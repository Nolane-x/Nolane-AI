from __future__ import annotations

from .campaign_runner import CampaignRunLedger, CampaignRunReceipt
from .execution import ExecutionTerminalReceipt


class ExecutionCampaignAdapter:
    """Map execution accounting into the existing campaign ledger without deriving evaluator truth."""

    def __init__(self, runs: CampaignRunLedger) -> None:
        self.runs = runs

    def record_terminal_result(
        self,
        *,
        run_id: str,
        terminal: ExecutionTerminalReceipt,
        evaluator_passed: bool,
        false_accepts: int,
        regressions: int,
        energy_joules: float | None,
        active_agents: int,
    ) -> CampaignRunReceipt:
        if not isinstance(evaluator_passed, bool):
            raise TypeError('campaign pass/fail must be supplied explicitly by evaluator')
        return self.runs.record_result(
            run_id=str(run_id),
            passed=evaluator_passed,
            false_accepts=int(false_accepts),
            regressions=int(regressions),
            compute_units=terminal.compute_units,
            tool_calls=terminal.tool_calls,
            external_core_calls=terminal.external_core_calls,
            wall_clock_ms=terminal.wall_clock_ms,
            energy_joules=energy_joules,
            active_agents=int(active_agents),
            output_artifact_ids=terminal.output_artifact_ids,
            termination_reason=terminal.termination_reason,
        )
