"""Historical compatibility bridge for native execution-control authority."""

from typing import Any

from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    ExecutionTerminalReceipt,
    OrganizationExecutionControlPlane as _NativeOrganizationExecutionControlPlane,
)


def _compile_context_capsule(
    context: Any,
    agent_id: str,
    *,
    task_id: str | None = None,
):
    """Compile one execution capsule through the strongest available context contract.

    Neural R2.4 context compilation returns a provenance-bearing result rather
    than a capsule directly. Execution must verify that provenance before the
    capsule can cross the inference boundary. Historical context authorities
    still expose ``compile`` and remain supported for replay compatibility.
    """

    compile_context = getattr(context, "compile_context", None)
    if callable(compile_context):
        verifier = getattr(context, "verify_context_capsule", None)
        if not callable(verifier):
            raise RuntimeError(
                "modern execution context requires context provenance verification"
            )
        compiled = compile_context(agent_id, task_id=task_id)
        capsule = getattr(compiled, "capsule", None)
        if capsule is None:
            raise TypeError("modern execution context returned no context capsule")
        verified = verifier(capsule)
        if verified is None:
            raise ValueError(
                "modern execution context returned an unverifiable context capsule"
            )
        if getattr(verified, "capsule", None) != capsule:
            raise ValueError("verified execution context capsule does not match compilation")
        return capsule

    legacy_compile = getattr(context, "compile", None)
    if not callable(legacy_compile):
        raise TypeError("execution context does not expose a supported compiler")
    return legacy_compile(agent_id, task_id=task_id)


def _bind_native_compile_surface(context: Any) -> Any:
    """Expose the native execution compiler surface on a modern context object.

    The native execution control plane intentionally keeps its historical
    ``context.compile`` call contract. Binding that one compatibility method at
    the bridge keeps the native authority unchanged while routing live runtime
    cognition through the provenance-verifying Neural R2.4 compiler.
    """

    if callable(getattr(context, "compile", None)):
        return context
    if not callable(getattr(context, "compile_context", None)):
        return context

    def compile_for_execution(agent_id: str, *, task_id: str | None = None):
        return _compile_context_capsule(context, agent_id, task_id=task_id)

    context.compile = compile_for_execution
    return context


class OrganizationExecutionControlPlane(_NativeOrganizationExecutionControlPlane):
    def __init__(self, *args: Any, context: Any, **kwargs: Any) -> None:
        super().__init__(
            *args,
            context=_bind_native_compile_surface(context),
            **kwargs,
        )

    def _compile_context_capsule(
        self,
        agent_id: str,
        *,
        task_id: str | None = None,
    ):
        return _compile_context_capsule(self.context, agent_id, task_id=task_id)


__all__ = (
    "ExecutionState",
    "ExecutionSession",
    "ExecutionStepReceipt",
    "ExecutionTerminalReceipt",
    "OrganizationExecutionControlPlane",
)
