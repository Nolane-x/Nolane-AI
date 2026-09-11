from __future__ import annotations

from typing import Any

from nolane.external_core.execution_handler_authority import (
    OrganizationExecutionControlPlane as _HandlerExecutionControlPlane,
)


class OrganizationExecutionControlPlane(_HandlerExecutionControlPlane):
    """Reject decisions whose own execution-session frontier changed during inference."""

    def _attest_post_inference_task_authority(self, request: Any) -> None:
        if int(getattr(request, "execution_lineage_version", 1)) >= 2:
            session_id = str(
                getattr(request, "execution_session_id", "") or ""
            ).strip()
            if session_id:
                session = self.get_session(session_id)
                if (
                    request.step_index != session.step_index
                    or request.counters != session.counters
                ):
                    raise PermissionError(
                        "execution session frontier authority changed during inference"
                    )
        super()._attest_post_inference_task_authority(request)


__all__ = ("OrganizationExecutionControlPlane",)
