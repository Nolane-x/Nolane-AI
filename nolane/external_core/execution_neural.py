"""Compatibility import path for the native cognition-aware execution authority."""

from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    ExecutionTerminalReceipt,
    OrganizationExecutionControlPlane as _NativeOrganizationExecutionControlPlane,
)


COMPONENT_ID = "external.execution.neural"
COMPONENT_VERSION = "0.0.2"


class OrganizationExecutionControlPlane(_NativeOrganizationExecutionControlPlane):
    """Historical Neural import path; cognition authority lives in execution.py."""


__all__ = (
    "ExecutionState",
    "ExecutionSession",
    "ExecutionStepReceipt",
    "ExecutionTerminalReceipt",
    "OrganizationExecutionControlPlane",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)
