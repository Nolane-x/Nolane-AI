from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_handler_authority import (
    OrganizationExecutionControlPlane as _HandlerExecutionControlPlane,
)


class OrganizationExecutionControlPlane(_HandlerExecutionControlPlane):
    """Reject decisions whose own execution-session frontier changed during inference."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._active_execution_session_frontier_digest: ContextVar[str | None] = ContextVar(
            f"nolane-active-execution-session-frontier-digest-{id(self)}",
            default=None,
        )
        super().__init__(*args, **kwargs)

    @staticmethod
    def _execution_session_frontier_digest(session: Any) -> str:
        return canonical_digest(session.to_state())

    def step(self, session_id: str):
        session = self.get_session(session_id)
        token = self._active_execution_session_frontier_digest.set(
            self._execution_session_frontier_digest(session)
        )
        try:
            return super().step(session_id)
        finally:
            self._active_execution_session_frontier_digest.reset(token)

    def _attest_post_inference_task_authority(self, request: Any) -> None:
        if int(getattr(request, "execution_lineage_version", 1)) >= 2:
            expected = self._active_execution_session_frontier_digest.get()
            if expected is None:
                raise RuntimeError(
                    "post-inference execution frontier authority requires captured session frontier"
                )
            session_id = str(
                getattr(request, "execution_session_id", "") or ""
            ).strip()
            if session_id:
                current = self._execution_session_frontier_digest(
                    self.get_session(session_id)
                )
                if current != expected:
                    raise PermissionError(
                        "execution session frontier authority changed during inference"
                    )
        super()._attest_post_inference_task_authority(request)


__all__ = ("OrganizationExecutionControlPlane",)
