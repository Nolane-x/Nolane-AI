from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from nolane.external_core.execution_lineage import (
    OrganizationExecutionControlPlane as _LineageExecutionControlPlane,
)
from nolane.external_core.execution_types import ExecutionActionKind


class OrganizationExecutionControlPlane(_LineageExecutionControlPlane):
    """Bind TOOL decisions to the external-core handler authority seen before inference."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._active_external_core_handler_binding_authority_revisions: ContextVar[
            tuple[tuple[str, int], ...] | None
        ] = ContextVar(
            f"nolane-active-external-core-handler-binding-authority-revisions-{id(self)}",
            default=None,
        )
        super().__init__(*args, **kwargs)

    def external_core_handler_binding_authority_revision(self, tool_id: str) -> int:
        key = str(tool_id).strip()
        if not key:
            raise ValueError("external-core handler tool id must be explicit")
        handlers = getattr(self.executor, "_handlers", None)
        if not isinstance(handlers, dict):
            raise RuntimeError("external-core handler binding authority is unavailable")
        # register_handler() is canonical 0 -> 1 authority: first registration binds,
        # exact same-handler registration is idempotent, and replacement is rejected.
        return 1 if key in handlers else 0

    def step(self, session_id: str):
        binding_revisions = tuple(
            (
                tool_id,
                self.external_core_handler_binding_authority_revision(tool_id),
            )
            for tool_id in sorted(self.executor.external_core_ids)
        )
        token = self._active_external_core_handler_binding_authority_revisions.set(
            binding_revisions
        )
        try:
            return super().step(session_id)
        finally:
            self._active_external_core_handler_binding_authority_revisions.reset(token)

    def _attest_decision_receipt(
        self,
        receipt: Any,
        *,
        request: Any,
        backend: Any,
    ) -> Any:
        canonical = super()._attest_decision_receipt(
            receipt,
            request=request,
            backend=backend,
        )
        if canonical.action.kind is not ExecutionActionKind.TOOL:
            return canonical

        action = canonical.action.tool_action
        if action is None:
            raise ValueError("tool decision lacks tool action authority")
        tool_id = str(action.tool_id).strip()
        if tool_id not in self.executor.external_core_ids:
            return canonical

        captured = self._active_external_core_handler_binding_authority_revisions.get()
        if captured is None:
            raise RuntimeError(
                "post-inference external-core handler authority requires captured bindings"
            )
        expected = dict(captured)
        if tool_id not in expected:
            raise RuntimeError(
                "selected external-core handler authority was not captured before inference"
            )
        if (
            self.external_core_handler_binding_authority_revision(tool_id)
            != expected[tool_id]
        ):
            raise PermissionError(
                "external-core handler binding authority changed during inference"
            )
        return canonical


__all__ = ("OrganizationExecutionControlPlane",)
