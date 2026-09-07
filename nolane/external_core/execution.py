from __future__ import annotations

from typing import Any, Mapping

from nolane.external_core._execution_base import (
    COMPONENT_ID as _BASE_COMPONENT_ID,
    COMPONENT_VERSION as _BASE_COMPONENT_VERSION,
    MIGRATED_FROM,
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    ExecutionTerminalReceipt,
    OrganizationExecutionControlPlane as _BaseOrganizationExecutionControlPlane,
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
from nolane.memory.context_intelligence import ContextCompilationReceipt
from nolane.neural.core_contract import CognitiveState, EvidenceRef
from nolane.neural.inference_bridge import CognitiveStateEncoder


COMPONENT_ID = _BASE_COMPONENT_ID
COMPONENT_VERSION = _BASE_COMPONENT_VERSION


def _cognitive_state_from_context_provenance(
    *,
    agent_id: str,
    task_id: str | None,
    receipt: Any,
    delta: Any,
) -> CognitiveState:
    """Build R2.4 cognition from canonical compilation receipt + semantic delta."""

    if receipt.agent_id != str(agent_id) or delta.agent_id != str(agent_id):
        raise ValueError("cognitive provenance agent binding mismatch")
    normalized_task_id = None if task_id is None else str(task_id)
    if receipt.task_id != normalized_task_id or delta.task_id != normalized_task_id:
        raise ValueError("cognitive provenance task binding mismatch")
    if receipt.semantic_delta_digest != delta.digest:
        raise ValueError("cognitive provenance receipt does not bind semantic delta")

    return CognitiveState.create(
        payload={
            "agent_id": str(agent_id),
            "task_id": normalized_task_id,
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


def _cognitive_state_from_verified_context(verified: Any) -> CognitiveState:
    """Build R2.4 cognition only from canonical context evidence."""

    capsule = verified.capsule
    receipt = verified.receipt
    delta = verified.delta
    if receipt.receipt_id != capsule.context_compilation_receipt_id:
        raise ValueError("verified receipt does not match context capsule provenance")
    if delta.digest != capsule.semantic_delta_digest:
        raise ValueError("verified semantic delta does not match context capsule provenance")
    return _cognitive_state_from_context_provenance(
        agent_id=capsule.agent_id,
        task_id=capsule.task_id,
        receipt=receipt,
        delta=delta,
    )


class _VerifiedContextCognitiveStateEncoder:
    """Bind requests to cognition resolved from the same verified context authority."""

    def __init__(self, *, base: CognitiveStateEncoder, context: Any) -> None:
        self._base = base
        self._context = context

    @property
    def version(self):
        return self._base.version

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


class OrganizationExecutionControlPlane(_BaseOrganizationExecutionControlPlane):
    """Native execution authority with fail-closed R2.4 cognition activation."""

    def __init__(
        self,
        *args: Any,
        context: Any,
        encoder: CognitiveStateEncoder | None = None,
        **kwargs: Any,
    ) -> None:
        if isinstance(encoder, _VerifiedContextCognitiveStateEncoder):
            if encoder._context is not context:
                raise ValueError("execution encoder context authority mismatch")
            wrapped_encoder = encoder
        else:
            base_encoder = encoder or CognitiveStateEncoder(
                version="organization-context-digest-v1"
            )
            wrapped_encoder = _VerifiedContextCognitiveStateEncoder(
                base=base_encoder,
                context=context,
            )
        super().__init__(
            *args,
            context=context,
            encoder=wrapped_encoder,
            **kwargs,
        )

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        if "acting_executor" not in state:
            raise ValueError("execution state is missing transactional acting authority")
        modern_decision_ids = [
            receipt_id
            for receipt_id in sorted(self._decisions)
            if getattr(self._decisions[receipt_id], "request_provenance_version", 1) >= 2
        ]
        state["request_provenance_version"] = 2
        state["request_provenance_decision_ids"] = modern_decision_ids
        return state

    @classmethod
    def from_state(
        cls,
        *,
        registry: Any,
        tasks: Any,
        context: Any,
        artifacts: Any,
        external_cores: Any,
        coding: Any,
        state: Mapping[str, Any],
    ) -> "OrganizationExecutionControlPlane":
        request_provenance_version = int(state.get("request_provenance_version", 1))
        if request_provenance_version not in {1, 2}:
            raise ValueError("unsupported execution request provenance version")

        raw_provenance_decision_ids = state.get("request_provenance_decision_ids")
        if request_provenance_version >= 2:
            if not isinstance(raw_provenance_decision_ids, (list, tuple)):
                raise ValueError("execution request provenance binding is missing")
            provenance_decision_ids = tuple(
                str(receipt_id).strip() for receipt_id in raw_provenance_decision_ids
            )
            if (
                any(not receipt_id for receipt_id in provenance_decision_ids)
                or provenance_decision_ids != tuple(sorted(set(provenance_decision_ids)))
            ):
                raise ValueError("execution request provenance binding is non-canonical")
        else:
            if raw_provenance_decision_ids is not None:
                raise ValueError("legacy execution request provenance state contains modern binding")
            provenance_decision_ids = ()

        restored = super().from_state(
            registry=registry,
            tasks=tasks,
            context=context,
            artifacts=artifacts,
            external_cores=external_cores,
            coding=coding,
            state=state,
        )
        canonical_acting = TransactionalExternalCoreExecutor.from_state(
            executor=restored.executor,
            state=state.get("acting_executor", {}),
        )
        if canonical_acting.to_state() != restored.acting_executor.to_state():
            raise ValueError("restored transactional acting authority mismatch")

        actual_modern_decision_ids = tuple(
            receipt_id
            for receipt_id in sorted(restored._decisions)
            if getattr(
                restored._decisions[receipt_id], "request_provenance_version", 1
            )
            >= 2
        )
        if request_provenance_version >= 2:
            if provenance_decision_ids != actual_modern_decision_ids:
                raise ValueError("execution request provenance binding mismatch")
        elif actual_modern_decision_ids:
            raise ValueError("execution request provenance downgrade detected")
        return restored

    def _compile_context_for_inference(
        self,
        agent_id: str,
        *,
        task_id: str | None = None,
    ) -> tuple[Any, CognitiveState | None]:
        capsule = super()._compile_context_capsule(agent_id, task_id=task_id)
        return capsule, self.encoder.cognitive_state_for(capsule)

    def resolve_cognitive_state(self, cognitive_state_digest: str) -> CognitiveState:
        """Resolve one persisted R2.4 cognition identity from canonical context authority.

        CognitiveState is deliberately not stored a second time by execution. The
        resolver reconstructs it from the persisted context compilation receipt and
        semantic delta so restore/replay has one provenance source of truth.
        """

        target_digest = str(cognitive_state_digest).strip()
        compiler = getattr(self.context, "context_intelligence", None)
        to_state = getattr(compiler, "to_state", None)
        receipt_lookup = getattr(compiler, "receipt", None)
        delta_lookup = getattr(compiler, "semantic_delta", None)
        if not (
            callable(to_state)
            and callable(receipt_lookup)
            and callable(delta_lookup)
        ):
            raise KeyError(f"unknown cognitive state digest: {target_digest}")

        snapshot = to_state()
        raw_receipts = snapshot.get("receipts", ())
        matches: list[CognitiveState] = []
        for raw_receipt in raw_receipts:
            canonical_snapshot = ContextCompilationReceipt.from_state(raw_receipt)
            receipt = receipt_lookup(canonical_snapshot.receipt_id)
            if receipt != canonical_snapshot:
                raise ValueError("persisted context receipt snapshot is not canonical")
            if receipt.compiler_version != getattr(compiler, "COMPILER_VERSION", None):
                raise ValueError("persisted context receipt compiler version mismatch")
            delta = delta_lookup(receipt.semantic_delta_digest)
            candidate = _cognitive_state_from_context_provenance(
                agent_id=receipt.agent_id,
                task_id=receipt.task_id,
                receipt=receipt,
                delta=delta,
            )
            if candidate.digest == target_digest:
                matches.append(candidate)

        if not matches:
            raise KeyError(f"unknown cognitive state digest: {target_digest}")
        if len(matches) != 1:
            raise ValueError("cognitive state digest does not resolve uniquely")
        return matches[0]

    def get_inference_request(self, decision_receipt_id: str):
        """Return the canonical request persisted by one modern decision receipt."""

        decision = self.get_decision(decision_receipt_id)
        if getattr(decision, "request_provenance_version", 1) < 2:
            raise KeyError(
                f"decision has no persisted inference request: {decision_receipt_id}"
            )
        request = getattr(decision, "request", None)
        if request is None:
            raise ValueError("modern decision is missing persisted inference request")
        if request.digest != decision.request_digest:
            raise ValueError("persisted inference request digest mismatch")
        return request

    def _validate_state(self) -> None:
        super()._validate_state()
        for session in self._sessions.values():
            for receipt_id in session.decision_receipt_ids:
                decision = self._decisions[receipt_id]
                if getattr(decision, "request_provenance_version", 1) >= 2:
                    request = self.get_inference_request(receipt_id)
                    if request.task_id != session.task_id:
                        raise ValueError(
                            "persisted inference request task binding mismatch with execution session"
                        )
                digest = getattr(decision, "cognitive_state_digest", None)
                if digest is None:
                    continue
                try:
                    cognitive_state = self.resolve_cognitive_state(digest)
                except KeyError as exc:
                    raise ValueError(
                        "persisted execution decision references unknown cognitive state"
                    ) from exc
                if cognitive_state.payload["agent_id"] != session.agent_id:
                    raise ValueError(
                        "persisted execution decision cognitive state agent binding mismatch"
                    )
                if cognitive_state.payload["task_id"] != session.task_id:
                    raise ValueError(
                        "persisted execution decision cognitive state task binding mismatch"
                    )

    @staticmethod
    def _attest_decision_receipt(receipt: Any, *, request: Any, backend: Any):
        canonical = _BaseOrganizationExecutionControlPlane._attest_decision_receipt(
            receipt,
            request=request,
            backend=backend,
        )
        if (
            getattr(canonical, "cognitive_state_digest", None)
            != getattr(request, "cognitive_state_digest", None)
        ):
            raise ValueError(
                "decision receipt authority mismatch: cognitive_state_digest"
            )
        return canonical


__all__ = (
    "ExecutionState",
    "ExecutionSession",
    "ExecutionStepReceipt",
    "ExecutionTerminalReceipt",
    "OrganizationExecutionControlPlane",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
