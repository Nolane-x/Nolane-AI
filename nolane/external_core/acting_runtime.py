from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (
    ActionBudget,
    ActionPhase,
    ActionRecord,
    ActingProtocolLedger,
    EffectClass,
    ExecutionContract,
    ExecutionRisk,
    ProtocolViolation,
    VerifierLevel,
    execution_risk_rank,
    minimum_risk_for_effect,
)
from nolane.external_core.execution_types import ToolAction
from nolane.external_core.execution_workspace import RepositoryWorkspace, WorkspaceCheckpoint


COMPONENT_ID = "external.acting.runtime"
COMPONENT_VERSION = "0.1.6"


class CoreReceipt(Protocol):
    receipt_id: str
    agent_id: str
    task_id: str
    tool_id: str
    operation: str
    input_digest: str
    authorized: bool
    success: bool
    failure_kind: str | None
    before_workspace_digest: str
    after_workspace_digest: str
    output_artifact_ids: tuple[str, ...]
    evidence_artifact_id: str
    core_contract_digest: str
    workspace_epoch_id: str


class CoreExecutor(Protocol):
    def invoke(
        self,
        *,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action: ToolAction,
        **kwargs: Any,
    ) -> CoreReceipt: ...

    def get_receipt(self, receipt_id: str) -> CoreReceipt: ...


@dataclass(frozen=True, slots=True)
class ActingInvocationResult:
    record: ActionRecord
    core_receipt_id: str
    output_artifact_ids: tuple[str, ...]
    replayed: bool = False


class TransactionalExternalCoreExecutor:
    """Transactional gate around the concrete ExternalCoreExecutor.

    This class is the E. Acting execution boundary. Upstream systems choose and
    authorize an action; this kernel only enforces execution contracts, leases,
    capabilities, effect budgets, evidence gates, idempotency and recovery.
    """

    def __init__(self, *, executor: CoreExecutor, protocol: ActingProtocolLedger | None = None) -> None:
        self.executor = executor
        self.protocol = protocol or ActingProtocolLedger()

    @staticmethod
    def _default_budget(effect_class: EffectClass) -> ActionBudget:
        effect = EffectClass(effect_class)
        return ActionBudget(
            max_attempts=1,
            max_local_mutations=1 if effect is EffectClass.LOCAL_MUTATION else 0,
            max_external_effects=1 if effect in {EffectClass.EXTERNAL_MUTATION, EffectClass.IRREVERSIBLE} else 0,
        )

    @staticmethod
    def minimum_effect_class(action: ToolAction) -> EffectClass:
        """Return the fail-closed physical effect floor for a concrete tool action.

        Only built-in operations whose implementations are bounded reads are
        admitted as READ. Repository-local filesystem writes are reversible local
        mutations. Process tools, registered/custom handlers, and unknown future
        operations are external-like because the repository workspace is not an OS
        sandbox and E cannot prove their side effects stay local.
        """

        tool_id = str(action.tool_id)
        operation = str(action.operation)
        if tool_id == "filesystem":
            if operation == "read_text" and not action.mutation_paths:
                return EffectClass.READ
            if action.mutation_paths:
                return EffectClass.LOCAL_MUTATION
            return EffectClass.EXTERNAL_MUTATION
        if tool_id == "git":
            if operation in {"status", "diff", "rev-parse-head"} and not action.mutation_paths:
                return EffectClass.READ
            return EffectClass.EXTERNAL_MUTATION
        if tool_id == "code-search":
            if not action.mutation_paths:
                return EffectClass.READ
            return EffectClass.EXTERNAL_MUTATION
        return EffectClass.EXTERNAL_MUTATION

    @staticmethod
    def _effect_rank(effect_class: EffectClass | str) -> int:
        return {
            EffectClass.READ: 0,
            EffectClass.LOCAL_MUTATION: 1,
            EffectClass.EXTERNAL_MUTATION: 2,
            EffectClass.IRREVERSIBLE: 3,
        }[EffectClass(effect_class)]

    @staticmethod
    def _action_id(*, agent_id: str, task_id: str, idempotency_key: str) -> str:
        digest = canonical_digest(
            {
                "agent_id": str(agent_id),
                "task_id": str(task_id),
                "idempotency_key": str(idempotency_key),
            }
        )
        return "acting-action-" + digest[:24]

    @staticmethod
    def _validate_core_receipt(
        receipt: CoreReceipt,
        *,
        agent_id: str,
        task_id: str,
        action: ToolAction,
        input_digest: str,
        before_workspace_digest: str,
        after_workspace_digest: str,
        core_contract_digest: str,
        workspace_epoch_id: str,
    ) -> None:
        expected = {
            "agent_id": str(agent_id),
            "task_id": str(task_id),
            "tool_id": action.tool_id,
            "operation": action.operation,
            "input_digest": str(input_digest),
            "before_workspace_digest": str(before_workspace_digest),
            "after_workspace_digest": str(after_workspace_digest),
            "core_contract_digest": str(core_contract_digest),
            "workspace_epoch_id": str(workspace_epoch_id),
        }
        mismatches = [
            field
            for field, expected_value in expected.items()
            if getattr(receipt, field, None) != expected_value
        ]
        if getattr(receipt, "authorized", None) is not True:
            mismatches.append("authorized")
        if not str(getattr(receipt, "receipt_id", "")).strip():
            mismatches.append("receipt_id")
        if mismatches:
            raise ValueError(
                "core receipt provenance mismatch: " + ", ".join(dict.fromkeys(mismatches))
            )

    @staticmethod
    def _validate_replay_core_receipt(
        receipt: CoreReceipt,
        *,
        receipt_id: str,
        agent_id: str,
        task_id: str,
        action: ToolAction,
        input_digest: str,
        workspace_digest: str,
        core_contract_digest: str,
        workspace_epoch_id: str,
    ) -> None:
        expected = {
            "receipt_id": str(receipt_id),
            "agent_id": str(agent_id),
            "task_id": str(task_id),
            "tool_id": action.tool_id,
            "operation": action.operation,
            "input_digest": str(input_digest),
            "after_workspace_digest": str(workspace_digest),
            "core_contract_digest": str(core_contract_digest),
            "workspace_epoch_id": str(workspace_epoch_id),
        }
        mismatches = [
            field
            for field, expected_value in expected.items()
            if getattr(receipt, field, None) != expected_value
        ]
        if getattr(receipt, "authorized", None) is not True:
            mismatches.append("authorized")
        if getattr(receipt, "success", None) is not True:
            mismatches.append("success")
        if mismatches:
            raise ValueError(
                "replay core receipt provenance mismatch: "
                + ", ".join(dict.fromkeys(mismatches))
            )

    def _replay(
        self,
        row: ActionRecord,
        *,
        expected_action_id: str,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action: ToolAction,
        core_contract_digest: str,
        workspace_epoch_id: str,
    ) -> ActingInvocationResult:
        if row.action_id != str(expected_action_id):
            raise PermissionError("replay action authority mismatch")
        if row.phase not in {
            ActionPhase.COMMITTED,
            ActionPhase.ROLLED_BACK,
            ActionPhase.DEGRADED,
            ActionPhase.CANCELLED,
        }:
            raise ProtocolViolation(
                "idempotent action is already in progress; explicit resume/recovery is required"
            )
        if row.phase is not ActionPhase.COMMITTED:
            return ActingInvocationResult(
                record=row,
                core_receipt_id="",
                output_artifact_ids=(),
                replayed=True,
            )
        receipt_id = str(row.outcome_ref).strip()
        if not receipt_id or row.commit_ref != receipt_id:
            raise ValueError("replay committed action lacks exact committed receipt authority")
        receipt = self.executor.get_receipt(receipt_id)
        self._validate_replay_core_receipt(
            receipt,
            receipt_id=receipt_id,
            agent_id=str(agent_id),
            task_id=str(task_id),
            action=action,
            input_digest=row.contract.input_digest,
            workspace_digest=workspace.digest,
            core_contract_digest=str(core_contract_digest),
            workspace_epoch_id=str(workspace_epoch_id),
        )
        return ActingInvocationResult(
            record=row,
            core_receipt_id=receipt_id,
            output_artifact_ids=tuple(str(x) for x in receipt.output_artifact_ids),
            replayed=True,
        )

    @staticmethod
    def _safe_release(workspace: RepositoryWorkspace, checkpoint: WorkspaceCheckpoint | None) -> None:
        if checkpoint is None:
            return
        try:
            workspace.release_checkpoint(checkpoint)
        except FileNotFoundError:
            return

    def _recover_after_effect(
        self,
        *,
        action_id: str,
        workspace: RepositoryWorkspace,
        checkpoint: WorkspaceCheckpoint | None,
        effect_class: EffectClass,
        failure_reason: str,
        recovery_evidence_ref: str,
    ) -> ActionRecord:
        effect = EffectClass(effect_class)
        if effect is EffectClass.LOCAL_MUTATION:
            if checkpoint is None:
                return self.protocol.degrade(
                    action_id,
                    recovery_ref=recovery_evidence_ref,
                    failure_reason="local mutation has no rollback checkpoint: " + failure_reason,
                )
            try:
                restored = workspace.restore(checkpoint)
            except Exception as exc:
                return self.protocol.degrade(
                    action_id,
                    recovery_ref=recovery_evidence_ref,
                    failure_reason=f"workspace rollback failed: {type(exc).__name__}: {exc}; original={failure_reason}",
                )
            finally:
                self._safe_release(workspace, checkpoint)
            return self.protocol.rollback(
                action_id,
                rollback_ref=f"{checkpoint.checkpoint_id}:{restored}",
                failure_reason=failure_reason,
            )
        if effect is EffectClass.READ:
            return self.protocol.rollback(
                action_id,
                rollback_ref="no-side-effect:" + recovery_evidence_ref,
                failure_reason=failure_reason,
            )
        return self.protocol.degrade(
            action_id,
            recovery_ref=recovery_evidence_ref,
            failure_reason=failure_reason,
        )

    def invoke(
        self,
        *,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action: ToolAction,
        risk_class: ExecutionRisk,
        effect_class: EffectClass,
        required_capabilities: Iterable[str],
        capability_grants: Iterable[str],
        authorization_ref: str,
        preconditions: Iterable[str] = (),
        precondition_evidence_refs: Iterable[str] = (),
        postconditions: Iterable[str] = (),
        postcondition_evidence_refs: Iterable[str] = (),
        verifier_level: VerifierLevel | int | str = VerifierLevel.V1,
        idempotency_key: str,
        recovery_plan: str = "",
        core_contract_digest: str = "",
        workspace_epoch_id: str = "",
        budget: ActionBudget | None = None,
        now_ms: int,
        lease_ttl_ms: int,
        timeout_seconds: float = 30.0,
        max_output_chars: int = 200_000,
    ) -> ActingInvocationResult:
        effect = EffectClass(effect_class)
        risk = ExecutionRisk(risk_class)
        physical_effect_floor = self.minimum_effect_class(action)
        if self._effect_rank(effect) < self._effect_rank(physical_effect_floor):
            raise PermissionError(
                "effect classification downgrade: "
                f"{action.tool_id}.{action.operation} requires at least "
                f"{physical_effect_floor.value}, got {effect.value}"
            )
        minimum_risk = minimum_risk_for_effect(effect)
        if execution_risk_rank(risk) < execution_risk_rank(minimum_risk):
            raise PermissionError(
                "risk classification downgrade: "
                f"{effect.value} requires at least {minimum_risk.value}, got {risk.value}"
            )
        resolved_verifier_level = VerifierLevel.coerce(verifier_level)
        minimum_verifier_level = self.protocol.minimum_verifier_level(risk)
        if resolved_verifier_level < minimum_verifier_level:
            raise PermissionError(
                f'{risk.value} postcondition verification requires {minimum_verifier_level.name}'
            )
        key = str(idempotency_key).strip()
        if not key:
            raise ValueError("transactional invocation requires an idempotency key")
        epoch_id = str(workspace_epoch_id).strip()
        if not epoch_id:
            raise ValueError("transactional invocation requires workspace execution epoch")
        if workspace.active_execution_epoch_id != epoch_id:
            raise PermissionError("workspace execution epoch does not authorize transactional invocation")
        core_digest = str(core_contract_digest).strip()
        action_id = self._action_id(agent_id=agent_id, task_id=task_id, idempotency_key=key)
        contract = ExecutionContract(
            action_id=action_id,
            core_id=action.tool_id,
            operation=action.operation,
            input_digest=canonical_digest(action.to_state()),
            risk_class=risk,
            effect_class=effect,
            required_capabilities=tuple(str(x) for x in required_capabilities),
            preconditions=tuple(str(x) for x in preconditions),
            postconditions=tuple(str(x) for x in postconditions),
            idempotency_key=key,
            recovery_plan=str(recovery_plan),
            budget=budget or self._default_budget(effect),
            core_contract_digest=core_digest,
            workspace_epoch_id=epoch_id,
        )
        row = self.protocol.propose(contract)
        if row.action_id != action_id or row.phase is not ActionPhase.PROPOSED:
            return self._replay(
                row,
                expected_action_id=action_id,
                agent_id=str(agent_id),
                task_id=str(task_id),
                workspace=workspace,
                action=action,
                core_contract_digest=core_digest,
                workspace_epoch_id=epoch_id,
            )

        lease_clock_started_ns = time.monotonic_ns()
        base_now_ms = int(now_ms)

        def current_now_ms() -> int:
            elapsed_ms = max(0, (time.monotonic_ns() - lease_clock_started_ns) // 1_000_000)
            return base_now_ms + int(elapsed_ms)

        row = self.protocol.acquire_lease(
            action_id,
            owner_id=str(agent_id),
            authorization_ref=str(authorization_ref),
            capability_grants=tuple(str(x) for x in capability_grants),
            now_ms=base_now_ms,
            ttl_ms=int(lease_ttl_ms),
        )
        row = self.protocol.verify_preconditions(
            action_id,
            evidence_refs=tuple(str(x) for x in precondition_evidence_refs),
            now_ms=current_now_ms(),
        )

        checkpoint: WorkspaceCheckpoint | None = None
        if effect is EffectClass.LOCAL_MUTATION:
            checkpoint = workspace.checkpoint(label=f"{action_id}:before-core")

        receipt: CoreReceipt | None = None
        try:
            self.protocol.begin_execution(action_id, now_ms=current_now_ms())
            dispatch_workspace_digest = workspace.digest
            receipt = self.executor.invoke(
                agent_id=str(agent_id),
                task_id=str(task_id),
                workspace=workspace,
                action=action,
                core_contract_digest=core_digest,
                workspace_epoch_id=epoch_id,
                timeout_seconds=float(timeout_seconds),
                max_output_chars=int(max_output_chars),
            )
            self._validate_core_receipt(
                receipt,
                agent_id=str(agent_id),
                task_id=str(task_id),
                action=action,
                input_digest=contract.input_digest,
                before_workspace_digest=dispatch_workspace_digest,
                after_workspace_digest=workspace.digest,
                core_contract_digest=core_digest,
                workspace_epoch_id=epoch_id,
            )
            self.protocol.observe_outcome(
                action_id,
                outcome_ref=str(receipt.receipt_id),
                success=bool(receipt.success),
                now_ms=current_now_ms(),
            )
            if not receipt.success:
                failure = str(receipt.failure_kind or "core execution failed")
                row = self._recover_after_effect(
                    action_id=action_id,
                    workspace=workspace,
                    checkpoint=checkpoint,
                    effect_class=effect,
                    failure_reason=failure,
                    recovery_evidence_ref=str(receipt.evidence_artifact_id or receipt.receipt_id),
                )
                return ActingInvocationResult(
                    record=row,
                    core_receipt_id=str(receipt.receipt_id),
                    output_artifact_ids=tuple(str(x) for x in receipt.output_artifact_ids),
                    replayed=False,
                )

            postcondition_refs = tuple(
                dict.fromkeys(str(x).strip() for x in postcondition_evidence_refs if str(x).strip())
            )
            receipt_evidence_ref = str(receipt.evidence_artifact_id or receipt.receipt_id).strip()
            if receipt_evidence_ref and receipt_evidence_ref not in postcondition_refs:
                postcondition_refs = postcondition_refs + (receipt_evidence_ref,)
            self.protocol.verify_postconditions(
                action_id,
                evidence_refs=postcondition_refs,
                verifier_level=resolved_verifier_level,
                now_ms=current_now_ms(),
            )
            row = self.protocol.commit(
                action_id,
                commit_ref=str(receipt.receipt_id),
                now_ms=current_now_ms(),
            )
            self._safe_release(workspace, checkpoint)
            return ActingInvocationResult(
                record=row,
                core_receipt_id=str(receipt.receipt_id),
                output_artifact_ids=tuple(str(x) for x in receipt.output_artifact_ids),
                replayed=False,
            )
        except Exception as exc:
            current = self.protocol.get(action_id)
            if current.phase in {
                ActionPhase.EXECUTING,
                ActionPhase.OUTCOME_OBSERVED,
                ActionPhase.POSTCONDITION_VERIFIED,
            }:
                recovery_ref = (
                    str(receipt.evidence_artifact_id)
                    if receipt is not None and str(receipt.evidence_artifact_id).strip()
                    else f"exception:{type(exc).__name__}"
                )
                self._recover_after_effect(
                    action_id=action_id,
                    workspace=workspace,
                    checkpoint=checkpoint,
                    effect_class=effect,
                    failure_reason=f"{type(exc).__name__}: {exc}",
                    recovery_evidence_ref=recovery_ref,
                )
            else:
                self._safe_release(workspace, checkpoint)
            raise

    def reconcile_inflight(
        self,
        *,
        evidence_ref: str,
        reason: str,
    ) -> tuple[ActionRecord, ...]:
        """Fail closed every persisted non-terminal action after a restart.

        This method never calls the concrete executor. The protocol decides whether
        a row can be safely cancelled/discarded or must be degraded because effect
        completion is uncertain.
        """

        ref = str(evidence_ref).strip()
        why = str(reason).strip()
        if not ref or not why:
            raise ValueError("in-flight reconciliation requires evidence and a reason")
        reconciled: list[ActionRecord] = []
        for row in self.protocol.records():
            if row.phase in {
                ActionPhase.COMMITTED,
                ActionPhase.ROLLED_BACK,
                ActionPhase.DEGRADED,
                ActionPhase.CANCELLED,
            }:
                continue
            reconciled.append(
                self.protocol.reconcile_interrupted(
                    row.action_id,
                    evidence_ref=ref,
                    reason=why,
                )
            )
        return tuple(reconciled)

    def to_state(self) -> dict[str, Any]:
        return {"protocol": self.protocol.to_state()}

    @classmethod
    def from_state(
        cls,
        *,
        executor: CoreExecutor,
        state: Mapping[str, Any],
    ) -> "TransactionalExternalCoreExecutor":
        return cls(
            executor=executor,
            protocol=ActingProtocolLedger.from_state(state.get("protocol", {})),
        )


__all__ = (
    "ActingInvocationResult",
    "TransactionalExternalCoreExecutor",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
)
