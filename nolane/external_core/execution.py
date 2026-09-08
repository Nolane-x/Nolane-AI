from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core._execution_base import (
    COMPONENT_ID as _BASE_COMPONENT_ID,
    COMPONENT_VERSION as _BASE_COMPONENT_VERSION,
    MIGRATED_FROM,
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    ExecutionTerminalReceipt as _BaseExecutionTerminalReceipt,
    OrganizationExecutionControlPlane as _BaseOrganizationExecutionControlPlane,
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
from nolane.external_core.execution_executor import ExternalCoreExecutor
from nolane.external_core.execution_types import AgentDecisionReceipt
from nolane.memory.context_intelligence import ContextCompilationReceipt
from nolane.neural.core_contract import CognitiveState, EvidenceRef
from nolane.neural.inference_bridge import CognitiveStateEncoder


COMPONENT_ID = _BASE_COMPONENT_ID
COMPONENT_VERSION = "0.0.14"
CONTEXT_PROVENANCE_ENCODER_VERSION = "organization-context-receipt-v2"


@dataclass(frozen=True, slots=True)
class ExecutionTerminalReceipt(_BaseExecutionTerminalReceipt):
    """Historical terminal receipt plus optional proof-v2 session authority."""

    execution_proof_version: int = 1
    initial_workspace_digest: str | None = None
    current_workspace_digest: str | None = None
    external_core_registry_digest: str | None = None
    workspace_epoch_id: str | None = None

    def __post_init__(self) -> None:
        version = int(self.execution_proof_version)
        if version not in {1, 2}:
            raise ValueError("unsupported execution terminal proof version")
        object.__setattr__(self, "execution_proof_version", version)
        values = {
            "initial_workspace_digest": self.initial_workspace_digest,
            "current_workspace_digest": self.current_workspace_digest,
            "external_core_registry_digest": self.external_core_registry_digest,
            "workspace_epoch_id": self.workspace_epoch_id,
        }
        normalized = {
            key: None if value is None else str(value).strip()
            for key, value in values.items()
        }
        if version == 1:
            if any(normalized.values()):
                raise ValueError("legacy execution terminal cannot carry modern proof")
            for key in normalized:
                object.__setattr__(self, key, None)
            return
        if any(not value for value in normalized.values()):
            raise ValueError("execution terminal proof v2 requires complete session proof")
        for key, value in normalized.items():
            object.__setattr__(self, key, value)

    def payload(self) -> dict[str, Any]:
        payload = _BaseExecutionTerminalReceipt.payload(self)
        if self.execution_proof_version >= 2:
            payload.update(
                {
                    "execution_proof_version": self.execution_proof_version,
                    "initial_workspace_digest": self.initial_workspace_digest,
                    "current_workspace_digest": self.current_workspace_digest,
                    "external_core_registry_digest": self.external_core_registry_digest,
                    "workspace_epoch_id": self.workspace_epoch_id,
                }
            )
        return payload

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExecutionTerminalReceipt":
        row = cls(
            receipt_id=str(state["receipt_id"]),
            session_id=str(state["session_id"]),
            agent_id=str(state["agent_id"]),
            task_id=str(state["task_id"]),
            state=ExecutionState(str(state["state"])),
            termination_reason=str(state["termination_reason"]),
            steps=int(state["steps"]),
            tool_calls=int(state["tool_calls"]),
            external_core_calls=int(state["external_core_calls"]),
            compute_units=int(state["compute_units"]),
            wall_clock_ms=int(state["wall_clock_ms"]),
            decision_receipt_ids=tuple(str(x) for x in state.get("decision_receipt_ids", ())),
            step_receipt_ids=tuple(str(x) for x in state.get("step_receipt_ids", ())),
            core_receipt_ids=tuple(str(x) for x in state.get("core_receipt_ids", ())),
            output_artifact_ids=tuple(str(x) for x in state.get("output_artifact_ids", ())),
            digest=str(state["digest"]),
            execution_proof_version=int(state.get("execution_proof_version", 1)),
            initial_workspace_digest=(
                None if state.get("initial_workspace_digest") is None
                else str(state["initial_workspace_digest"])
            ),
            current_workspace_digest=(
                None if state.get("current_workspace_digest") is None
                else str(state["current_workspace_digest"])
            ),
            external_core_registry_digest=(
                None if state.get("external_core_registry_digest") is None
                else str(state["external_core_registry_digest"])
            ),
            workspace_epoch_id=(
                None if state.get("workspace_epoch_id") is None
                else str(state["workspace_epoch_id"])
            ),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != "terminal-" + expected[:24]:
            raise ValueError("execution terminal receipt digest/id mismatch")
        return row

    @classmethod
    def bind_session_proof(
        cls,
        legacy: _BaseExecutionTerminalReceipt,
        session: ExecutionSession,
    ) -> "ExecutionTerminalReceipt":
        if session.execution_proof_version < 2:
            return cls.from_state(legacy.to_state())
        candidate = cls(
            receipt_id="",
            session_id=legacy.session_id,
            agent_id=legacy.agent_id,
            task_id=legacy.task_id,
            state=legacy.state,
            termination_reason=legacy.termination_reason,
            steps=legacy.steps,
            tool_calls=legacy.tool_calls,
            external_core_calls=legacy.external_core_calls,
            compute_units=legacy.compute_units,
            wall_clock_ms=legacy.wall_clock_ms,
            decision_receipt_ids=legacy.decision_receipt_ids,
            step_receipt_ids=legacy.step_receipt_ids,
            core_receipt_ids=legacy.core_receipt_ids,
            output_artifact_ids=legacy.output_artifact_ids,
            digest="",
            execution_proof_version=2,
            initial_workspace_digest=session.initial_workspace_digest,
            current_workspace_digest=session.current_workspace_digest,
            external_core_registry_digest=session.external_core_registry_digest,
            workspace_epoch_id=session.workspace_epoch_id,
        )
        digest = canonical_digest(candidate.payload())
        return replace(candidate, receipt_id="terminal-" + digest[:24], digest=digest)


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

    def _verified_context(self, capsule: Any):
        verifier = getattr(self._context, "verify_context_capsule", None)
        if not callable(verifier):
            return None
        verified = verifier(capsule)
        if verified is None:
            return None
        if getattr(verified, "capsule", None) != capsule:
            raise ValueError("verified execution context capsule does not match inference capsule")
        return verified

    def cognitive_state_for(self, capsule: Any) -> CognitiveState | None:
        verified = self._verified_context(capsule)
        if verified is None:
            return None
        return _cognitive_state_from_verified_context(verified)

    def build_request(self, *, cognitive_state: CognitiveState | None = None, **kwargs: Any):
        capsule = kwargs.get("capsule")
        if capsule is None:
            raise TypeError("provenance-aware execution encoder requires a context capsule")
        verified = self._verified_context(capsule)
        canonical_state = (
            None if verified is None else _cognitive_state_from_verified_context(verified)
        )
        if cognitive_state is None:
            cognitive_state = canonical_state
        elif canonical_state is not None and cognitive_state != canonical_state:
            raise ValueError("explicit cognitive state does not match canonical context provenance")
        request = self._base.build_request(cognitive_state=cognitive_state, **kwargs)
        if verified is None or canonical_state is None:
            return request
        return replace(
            request,
            context_digest=canonical_state.bind_context_digest(
                verified.receipt.capsule_digest
            ),
            encoder_version=CONTEXT_PROVENANCE_ENCODER_VERSION,
        )


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

    @staticmethod
    def _decision_has_context_provenance(decision: Any) -> bool:
        if getattr(decision, "request_provenance_version", 1) < 2:
            return False
        request = getattr(decision, "request", None)
        return (
            request is not None
            and request.encoder_version == CONTEXT_PROVENANCE_ENCODER_VERSION
            and request.cognitive_state_digest is not None
        )

    def _terminal(
        self,
        session: ExecutionSession,
        state: ExecutionState,
        reason: str,
        *,
        complete_task: bool = False,
    ) -> _BaseExecutionTerminalReceipt:
        legacy = super()._terminal(
            session,
            state,
            reason,
            complete_task=complete_task,
        )
        if session.execution_proof_version < 2:
            return legacy
        terminal = ExecutionTerminalReceipt.bind_session_proof(legacy, session)
        self._terminals.pop(legacy.receipt_id, None)
        existing = self._terminals.get(terminal.receipt_id)
        if existing is not None and existing != terminal:
            raise ValueError("execution terminal receipt id collision")
        self._terminals[terminal.receipt_id] = terminal
        updated = self._sessions[session.session_id]
        self._sessions[session.session_id] = replace(
            updated,
            terminal_receipt_id=terminal.receipt_id,
        )
        return terminal

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
        context_decision_ids = [
            receipt_id
            for receipt_id in sorted(self._decisions)
            if self._decision_has_context_provenance(self._decisions[receipt_id])
        ]
        if context_decision_ids:
            state["context_provenance_version"] = 2
            state["context_provenance_decision_ids"] = context_decision_ids
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

        context_provenance_version = int(state.get("context_provenance_version", 1))
        if context_provenance_version not in {1, 2}:
            raise ValueError("unsupported execution context provenance version")
        raw_context_decision_ids = state.get("context_provenance_decision_ids")
        if context_provenance_version >= 2:
            if not isinstance(raw_context_decision_ids, (list, tuple)):
                raise ValueError("execution context provenance binding is missing")
            context_decision_ids = tuple(
                str(receipt_id).strip() for receipt_id in raw_context_decision_ids
            )
            if (
                not context_decision_ids
                or any(not receipt_id for receipt_id in context_decision_ids)
                or context_decision_ids != tuple(sorted(set(context_decision_ids)))
            ):
                raise ValueError("execution context provenance binding is non-canonical")
        else:
            if raw_context_decision_ids is not None:
                raise ValueError("legacy execution context provenance state contains modern binding")
            context_decision_ids = ()

        encoder = CognitiveStateEncoder(
            version=str(state.get("encoder_version", "organization-context-digest-v1"))
        )
        executor = ExternalCoreExecutor.from_state(
            registry=registry,
            external_cores=external_cores,
            artifacts=artifacts,
            coding_patches=getattr(coding, "patches", None),
            code_claims=getattr(coding, "claims", None),
            state=state.get("executor", {}),
        )
        acting_executor = TransactionalExternalCoreExecutor.from_state(
            executor=executor,
            state=state.get("acting_executor", {}),
        )
        restored = cls(
            registry=registry,
            tasks=tasks,
            context=context,
            artifacts=artifacts,
            external_cores=external_cores,
            coding=coding,
            encoder=encoder,
            executor=executor,
            acting_executor=acting_executor,
            sessions=tuple(ExecutionSession.from_state(x) for x in state.get("sessions", ())),
            decisions=tuple(AgentDecisionReceipt.from_state(x) for x in state.get("decisions", ())),
            steps=tuple(ExecutionStepReceipt.from_state(x) for x in state.get("steps", ())),
            terminals=tuple(ExecutionTerminalReceipt.from_state(x) for x in state.get("terminals", ())),
            session_counter=int(state.get("session_counter", 0)),
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

        actual_context_decision_ids = tuple(
            receipt_id
            for receipt_id in sorted(restored._decisions)
            if cls._decision_has_context_provenance(restored._decisions[receipt_id])
        )
        if context_provenance_version >= 2:
            if context_decision_ids != actual_context_decision_ids:
                raise ValueError("execution context provenance binding mismatch")
        elif actual_context_decision_ids:
            raise ValueError("execution context provenance downgrade detected")
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
            if session.terminal_receipt_id is not None:
                terminal = self._terminals[session.terminal_receipt_id]
                terminal_proof_version = int(
                    getattr(terminal, "execution_proof_version", 1)
                )
                if session.execution_proof_version >= 2:
                    if terminal_proof_version < 2:
                        raise ValueError("execution terminal proof downgrade detected")
                    expected_terminal_proof = {
                        "initial_workspace_digest": session.initial_workspace_digest,
                        "current_workspace_digest": session.current_workspace_digest,
                        "external_core_registry_digest": session.external_core_registry_digest,
                        "workspace_epoch_id": session.workspace_epoch_id,
                    }
                    mismatches = [
                        field
                        for field, expected_value in expected_terminal_proof.items()
                        if getattr(terminal, field, None) != expected_value
                    ]
                    if mismatches:
                        raise ValueError(
                            "execution terminal proof binding mismatch: "
                            + ", ".join(mismatches)
                        )
                elif terminal_proof_version >= 2:
                    raise ValueError(
                        "legacy execution session references modern terminal proof"
                    )

            for receipt_id in session.decision_receipt_ids:
                decision = self._decisions[receipt_id]
                request = None
                if getattr(decision, "request_provenance_version", 1) >= 2:
                    request = self.get_inference_request(receipt_id)
                    if request.task_id != session.task_id:
                        raise ValueError(
                            "persisted inference request task binding mismatch with execution session"
                        )
                digest = getattr(decision, "cognitive_state_digest", None)
                if digest is None:
                    if (
                        request is not None
                        and request.encoder_version
                        == CONTEXT_PROVENANCE_ENCODER_VERSION
                    ):
                        raise ValueError(
                            "persisted inference request context provenance requires cognitive state"
                        )
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
                if (
                    request is not None
                    and request.encoder_version == CONTEXT_PROVENANCE_ENCODER_VERSION
                ):
                    if request.cognitive_state_digest != cognitive_state.digest:
                        raise ValueError(
                            "persisted inference request context provenance cognitive binding mismatch"
                        )
                    compiler = getattr(self.context, "context_intelligence", None)
                    receipt_lookup = getattr(compiler, "receipt", None)
                    if not callable(receipt_lookup):
                        raise ValueError(
                            "persisted inference request context provenance authority is unavailable"
                        )
                    receipt_id = str(
                        cognitive_state.payload["context_compilation_receipt_id"]
                    )
                    try:
                        receipt = receipt_lookup(receipt_id)
                    except KeyError as exc:
                        raise ValueError(
                            "persisted inference request context provenance receipt is unavailable"
                        ) from exc
                    if (
                        receipt.digest
                        != cognitive_state.payload["context_compilation_receipt_digest"]
                    ):
                        raise ValueError(
                            "persisted inference request context provenance receipt digest mismatch"
                        )
                    if receipt.agent_id != request.agent_id or receipt.task_id != request.task_id:
                        raise ValueError(
                            "persisted inference request context provenance receipt binding mismatch"
                        )
                    expected_context_digest = cognitive_state.bind_context_digest(
                        receipt.capsule_digest
                    )
                    if request.context_digest != expected_context_digest:
                        raise ValueError(
                            "persisted inference request context provenance digest mismatch"
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
