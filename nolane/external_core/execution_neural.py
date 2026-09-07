from __future__ import annotations

from typing import Any

from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    ExecutionTerminalReceipt,
    OrganizationExecutionControlPlane as _NativeOrganizationExecutionControlPlane,
)
from nolane.neural.core_contract import CognitiveState, EvidenceRef
from nolane.neural.inference_bridge import CognitiveStateEncoder


COMPONENT_ID = "external.execution.neural"
COMPONENT_VERSION = "0.0.1"


def _cognitive_state_from_verified_context(verified: Any) -> CognitiveState:
    """Build R2.4 cognition only from canonical, externally issued context evidence."""

    capsule = verified.capsule
    receipt = verified.receipt
    delta = verified.delta
    if receipt.receipt_id != capsule.context_compilation_receipt_id:
        raise ValueError("verified receipt does not match context capsule provenance")
    if delta.digest != capsule.semantic_delta_digest:
        raise ValueError("verified semantic delta does not match context capsule provenance")
    if receipt.semantic_delta_digest != delta.digest:
        raise ValueError("verified receipt does not bind the canonical semantic delta")

    return CognitiveState.create(
        payload={
            "agent_id": capsule.agent_id,
            "task_id": capsule.task_id,
            "context_compilation_receipt_id": receipt.receipt_id,
            "context_compilation_receipt_digest": receipt.digest,
            "semantic_delta_id": delta.delta_id,
            "semantic_delta_digest": delta.digest,
        },
        provenance=(
            EvidenceRef.create(
                source_core="memory.context.compilation",
                receipt_id=receipt.receipt_id,
                digest=receipt.digest,
                authority="observation",
            ),
            EvidenceRef.create(
                source_core="memory.context.delta",
                receipt_id=delta.delta_id,
                digest=delta.digest,
                authority="observation",
            ),
        ),
    )


class _VerifiedContextCognitiveStateEncoder:
    """Resolve cognition from the same canonical context authority used by execution."""

    def __init__(self, *, base: CognitiveStateEncoder, context: Any) -> None:
        self._base = base
        self._context = context
        self.version = base.version

    def cognitive_state_for(self, capsule: Any) -> CognitiveState | None:
        verifier = getattr(self._context, "verify_context_capsule", None)
        if not callable(verifier):
            return None
        verified = verifier(capsule)
        if verified is None:
            return None
        if getattr(verified, "capsule", None) != capsule:
            raise ValueError("verified execution context capsule does not match inference capsule")
        return _cognitive_state_from_verified_context(verified)

    def build_request(self, *, cognitive_state: CognitiveState | None = None, **kwargs: Any):
        capsule = kwargs.get("capsule")
        if capsule is None:
            raise TypeError("provenance-aware execution encoder requires a context capsule")
        canonical_state = self.cognitive_state_for(capsule)
        if cognitive_state is None:
            cognitive_state = canonical_state
        elif canonical_state is not None and cognitive_state != canonical_state:
            raise ValueError("explicit cognitive state does not match canonical context provenance")
        return self._base.build_request(cognitive_state=cognitive_state, **kwargs)


class OrganizationExecutionControlPlane(_NativeOrganizationExecutionControlPlane):
    """Native execution specialization that activates R2.4 cognitive identity at inference."""

    def __init__(
        self,
        *args: Any,
        context: Any,
        encoder: CognitiveStateEncoder | None = None,
        **kwargs: Any,
    ) -> None:
        base_encoder = encoder or CognitiveStateEncoder(version="organization-context-digest-v1")
        super().__init__(
            *args,
            context=context,
            encoder=_VerifiedContextCognitiveStateEncoder(
                base=base_encoder,
                context=context,
            ),
            **kwargs,
        )

    def _compile_context_for_inference(
        self,
        agent_id: str,
        *,
        task_id: str | None = None,
    ) -> tuple[Any, CognitiveState | None]:
        capsule = super()._compile_context_capsule(agent_id, task_id=task_id)
        return capsule, self.encoder.cognitive_state_for(capsule)


__all__ = (
    "ExecutionState",
    "ExecutionSession",
    "ExecutionStepReceipt",
    "ExecutionTerminalReceipt",
    "OrganizationExecutionControlPlane",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)
