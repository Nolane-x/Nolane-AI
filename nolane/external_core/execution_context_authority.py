from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from nolane.external_core.context import authoritative_artifacts_for
from nolane.external_core.execution_self_model_authority import (
    OrganizationExecutionControlPlane as _SelfModelExecutionControlPlane,
)


class OrganizationExecutionControlPlane(_SelfModelExecutionControlPlane):
    """Reject decisions whose request-bound context authority became stale."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._active_context_authority: ContextVar[
            tuple[str, str | None, tuple[tuple[str, Any], ...]] | None
        ] = ContextVar(
            f"nolane-active-request-context-authority-{id(self)}",
            default=None,
        )
        super().__init__(*args, **kwargs)

    def step(self, session_id: str):
        token = self._active_context_authority.set(None)
        try:
            return super().step(session_id)
        finally:
            self._active_context_authority.reset(token)

    def _compile_context_capsule(
        self,
        agent_id: str,
        *,
        task_id: str | None = None,
    ):
        capsule = super()._compile_context_capsule(agent_id, task_id=task_id)
        artifacts = tuple(getattr(capsule, "authoritative_artifacts", ()))
        if not artifacts:
            raise RuntimeError(
                "compiled request context authority artifacts are missing"
            )
        names = tuple(str(name).strip() for name, _ in artifacts)
        if any(not name for name in names) or len(set(names)) != len(names):
            raise RuntimeError(
                "compiled request context authority artifacts are non-canonical"
            )
        self._active_context_authority.set(
            (
                str(capsule.agent_id),
                None if capsule.task_id is None else str(capsule.task_id),
                artifacts,
            )
        )
        return capsule

    def _attest_post_inference_task_authority(self, request: Any) -> None:
        if int(getattr(request, "execution_lineage_version", 1)) >= 2:
            captured = self._active_context_authority.get()
            if captured is None:
                raise RuntimeError(
                    "post-inference context authority requires request-bound capture"
                )
            expected_agent_id, expected_task_id, expected_artifacts = captured
            if (
                str(request.agent_id) != expected_agent_id
                or request.task_id != expected_task_id
            ):
                raise PermissionError(
                    "request-bound context authority scope binding mismatch"
                )
            current_artifacts = authoritative_artifacts_for(
                self.context,
                expected_agent_id,
                task_id=expected_task_id,
            )
            if current_artifacts != expected_artifacts:
                raise PermissionError(
                    "request-bound context authority artifacts changed during inference"
                )

        super()._attest_post_inference_task_authority(request)


__all__ = ("OrganizationExecutionControlPlane",)
