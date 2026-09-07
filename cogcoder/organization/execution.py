"""Historical compatibility bridge for native execution-control authority."""

from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    ExecutionTerminalReceipt,
    OrganizationExecutionControlPlane as _NativeOrganizationExecutionControlPlane,
)


class OrganizationExecutionControlPlane(_NativeOrganizationExecutionControlPlane):
    """Historical import path for the native R2.4 cognition-aware execution authority."""


__all__ = (
    "ExecutionState",
    "ExecutionSession",
    "ExecutionStepReceipt",
    "ExecutionTerminalReceipt",
    "OrganizationExecutionControlPlane",
)
