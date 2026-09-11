from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from nolane.external_core.execution_frontier_authority import (
    OrganizationExecutionControlPlane as _FrontierExecutionControlPlane,
)


class OrganizationExecutionControlPlane(_FrontierExecutionControlPlane):
    """Reject decisions whose request-bound self-model authority became stale."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._active_self_model_authority: ContextVar[
            tuple[str, str, int] | None
        ] = ContextVar(
            f"nolane-active-self-model-authority-{id(self)}",
            default=None,
        )
        super().__init__(*args, **kwargs)

    def step(self, session_id: str):
        token = self._active_self_model_authority.set(None)
        try:
            return super().step(session_id)
        finally:
            self._active_self_model_authority.reset(token)

    def _compile_context_capsule(
        self,
        agent_id: str,
        *,
        task_id: str | None = None,
    ):
        agent_key = str(agent_id)
        revision_before = self.registry.self_model_authority_revision(agent_key)
        capsule = super()._compile_context_capsule(agent_key, task_id=task_id)
        revision_after = self.registry.self_model_authority_revision(agent_key)
        if revision_after != revision_before:
            raise PermissionError(
                "self-model authority changed during context compilation"
            )

        summary = tuple(getattr(capsule, "identity_summary", ()))
        self_model_rows = tuple(
            str(value).strip()
            for name, value in summary
            if str(name) == "self_model_version"
        )
        if len(self_model_rows) != 1 or not self_model_rows[0]:
            raise RuntimeError(
                "compiled context self-model authority is missing or non-canonical"
            )
        request_self_model_version = self_model_rows[0]
        identity = self.registry.get(agent_key)
        if identity.self_model_version != request_self_model_version:
            raise PermissionError(
                "self-model authority changed during context compilation"
            )

        self._active_self_model_authority.set(
            (identity.agent_id, request_self_model_version, revision_after)
        )
        return capsule

    def _attest_post_inference_task_authority(self, request: Any) -> None:
        if int(getattr(request, "execution_lineage_version", 1)) >= 2:
            captured = self._active_self_model_authority.get()
            if captured is None:
                raise RuntimeError(
                    "post-inference self-model authority requires request-bound capture"
                )
            expected_agent_id, expected_version, expected_revision = captured
            if str(request.agent_id) != expected_agent_id:
                raise PermissionError(
                    "request-bound self-model authority agent binding mismatch"
                )

            identity = self.registry.get(expected_agent_id)
            if identity.self_model_version != expected_version:
                raise PermissionError(
                    "self-model authority changed during inference"
                )
            if (
                self.registry.self_model_authority_revision(expected_agent_id)
                != expected_revision
            ):
                raise PermissionError(
                    "self-model authority revision changed during inference"
                )

        super()._attest_post_inference_task_authority(request)


__all__ = ("OrganizationExecutionControlPlane",)
