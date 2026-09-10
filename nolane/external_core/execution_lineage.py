from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    OrganizationExecutionControlPlane as _CanonicalExecutionControlPlane,
)
from nolane.external_core.execution_types import ExecutionActionKind
from nolane.schemas.identity import AgentStatus


_RESTORE_EXECUTION_LINEAGE: ContextVar[tuple[str, ...] | None] = ContextVar(
    "nolane-restore-execution-lineage",
    default=None,
)


def _lineage_ids(
    raw: object,
    *,
    require_nonempty: bool = False,
    require_sorted: bool = False,
) -> tuple[str, ...]:
    if not isinstance(raw, (list, tuple)):
        raise ValueError("execution lineage session binding is missing")
    rows = tuple(str(session_id).strip() for session_id in raw)
    if (
        (require_nonempty and not rows)
        or any(not session_id for session_id in rows)
        or len(set(rows)) != len(rows)
        or (require_sorted and rows != tuple(sorted(rows)))
    ):
        raise ValueError("execution lineage session binding is non-canonical")
    return rows


def _extend_unique(target: list[str], values: object) -> None:
    for value in values:
        artifact_id = str(value)
        if artifact_id not in target:
            target.append(artifact_id)


class _ExecutionLineageEncoder:
    """Inject one active execution lineage into otherwise canonical requests."""

    def __init__(self, base: Any) -> None:
        self._base = base
        self._active: ContextVar[tuple[str, str] | None] = ContextVar(
            f"nolane-active-execution-lineage-{id(self)}",
            default=None,
        )

    @property
    def version(self):
        return self._base.version

    def bind(self, session_id: str, workspace_epoch_id: str):
        normalized_session = str(session_id).strip()
        normalized_epoch = str(workspace_epoch_id).strip()
        if not normalized_session or not normalized_epoch:
            raise ValueError(
                "execution lineage binding requires session and workspace epoch"
            )
        return self._active.set((normalized_session, normalized_epoch))

    def reset(self, token: Any) -> None:
        self._active.reset(token)

    def build_request(self, **kwargs: Any):
        lineage = self._active.get()
        if lineage is not None:
            execution_session_id, workspace_epoch_id = lineage
            kwargs["execution_lineage_version"] = 2
            kwargs["execution_session_id"] = execution_session_id
            kwargs["workspace_epoch_id"] = workspace_epoch_id
        return self._base.build_request(**kwargs)


class OrganizationExecutionControlPlane(_CanonicalExecutionControlPlane):
    """Runtime execution authority that binds decisions and results to session lineage."""

    def __init__(
        self,
        *args: Any,
        execution_lineage_session_ids: tuple[str, ...] = (),
        **kwargs: Any,
    ) -> None:
        supplied = _lineage_ids(tuple(execution_lineage_session_ids))
        restoring = _RESTORE_EXECUTION_LINEAGE.get()
        if restoring is not None:
            if supplied and supplied != restoring:
                raise ValueError("execution lineage restore authority mismatch")
            supplied = restoring
        self._execution_lineage_session_ids = set(supplied)
        super().__init__(*args, **kwargs)

        base_encoder = getattr(self.encoder, "_base", None)
        if base_encoder is None:
            raise TypeError("execution encoder does not expose canonical base authority")
        if not isinstance(base_encoder, _ExecutionLineageEncoder):
            self.encoder._base = _ExecutionLineageEncoder(base_encoder)

    def start(self, **kwargs: Any) -> ExecutionSession:
        task_id = str(kwargs.get("task_id", "")).strip()
        if task_id:
            task = self.tasks.get(task_id)
            if task.completed_by is not None:
                raise ValueError(f"task {task_id} is already completed")
        session = super().start(**kwargs)
        self._execution_lineage_session_ids.add(session.session_id)
        return session

    def step(self, session_id: str):
        session = self.get_session(session_id)
        if session.session_id not in self._execution_lineage_session_ids:
            raise RuntimeError(
                "legacy execution session lacks decision lineage; "
                "forward execution requires lineage-v2 authority"
            )
        if session.execution_proof_version < 2 or not session.workspace_epoch_id:
            raise RuntimeError(
                "execution lineage-v2 requires proof-v2 workspace epoch authority"
            )
        task = self.tasks.get(session.task_id)
        if session.terminal_receipt_id is None and task.completed_by is not None:
            raise ValueError(
                "task completion authority already claimed outside execution terminal"
            )
        binding_encoder = getattr(self.encoder, "_base", None)
        if not isinstance(binding_encoder, _ExecutionLineageEncoder):
            raise RuntimeError("execution lineage encoder authority is unavailable")
        token = binding_encoder.bind(
            session.session_id,
            session.workspace_epoch_id,
        )
        try:
            return super().step(session_id)
        finally:
            binding_encoder.reset(token)

    def _core_output_projection(self, session: ExecutionSession) -> tuple[str, ...]:
        projected: list[str] = []
        for step_receipt_id in session.step_receipt_ids:
            step = self._steps[step_receipt_id]
            if step.core_receipt_id is None:
                continue
            try:
                core = self.executor.get_receipt(step.core_receipt_id)
            except Exception as exc:
                raise ValueError(
                    "execution result projection references unavailable core receipt"
                ) from exc
            core_outputs = tuple(
                str(artifact_id)
                for artifact_id in getattr(core, "output_artifact_ids", ())
            )
            if step.output_artifact_ids != core_outputs:
                raise ValueError("execution step output binding mismatch")
            _extend_unique(projected, core_outputs)
        return tuple(projected)

    def _attest_completion_output_authority(
        self,
        session: ExecutionSession,
        output_artifact_ids: object,
        *,
        grounded_output_artifact_ids: object,
    ) -> None:
        grounded = {str(artifact_id) for artifact_id in grounded_output_artifact_ids}
        for raw_artifact_id in output_artifact_ids:
            artifact_id = str(raw_artifact_id)
            try:
                artifact = self.artifacts.get(artifact_id)
            except KeyError as exc:
                raise ValueError(
                    "completion output authority references unavailable artifact"
                ) from exc
            try:
                metadata = artifact.metadata
            except Exception as exc:
                raise ValueError("completion output provenance metadata is invalid") from exc
            artifact_payload = {
                "kind": artifact.kind,
                "producer_agent_id": artifact.producer_agent_id,
                "content": artifact.content,
                "evidence_refs": sorted({str(x) for x in artifact.evidence_refs}),
                "metadata": metadata,
            }
            artifact_digest = canonical_digest(artifact_payload)
            if (
                artifact.digest != artifact_digest
                or artifact.artifact_id != "artifact-" + artifact_digest[:24]
                or artifact.metadata_json != canonical_json(metadata)
                or tuple(artifact.evidence_refs) != tuple(artifact_payload["evidence_refs"])
            ):
                raise ValueError("completion output artifact digest/id authority mismatch")
            if artifact_id in grounded:
                continue
            if artifact.producer_agent_id != session.agent_id:
                raise ValueError("completion output producer authority binding mismatch")
            if str(metadata.get("task_id", "")).strip() != session.task_id:
                raise ValueError("completion output task provenance binding mismatch")

    def _attest_post_inference_task_authority(self, request: Any) -> None:
        if int(getattr(request, "execution_lineage_version", 1)) < 2:
            return
        session_id = str(getattr(request, "execution_session_id", "") or "").strip()
        if not session_id:
            raise ValueError(
                "post-inference task authority requires execution session lineage"
            )
        session = self.get_session(session_id)
        if session.session_id not in self._execution_lineage_session_ids:
            raise ValueError(
                "post-inference task authority requires lineage-v2 execution session"
            )
        if (
            request.agent_id != session.agent_id
            or request.task_id != session.task_id
            or request.workspace_epoch_id != session.workspace_epoch_id
        ):
            raise ValueError("post-inference task execution authority binding mismatch")
        identity = self.registry.get(session.agent_id)
        if identity.status is AgentStatus.PAUSED:
            raise PermissionError("agent pause authority changed during inference")
        if identity.neural_version != request.neural_version:
            raise ValueError("neural version authority changed during inference")
        task = self.tasks.get(session.task_id)
        if task.completed_by is not None:
            raise ValueError(
                "task completion authority already claimed during inference"
            )
        if task.aborted_by is not None:
            raise ValueError("task abort authority already claimed during inference")
        if task.leased_to != session.agent_id:
            raise PermissionError("task lease authority changed during inference")
        workspace = self._workspaces.get(session.session_id)
        if workspace is None:
            raise RuntimeError(
                "post-inference workspace authority requires attached execution workspace"
            )
        if workspace.digest != session.current_workspace_digest:
            raise RuntimeError("workspace digest changed during inference")
        self._validate_session_execution_proof(session, workspace)

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
        self._attest_post_inference_task_authority(request)
        if canonical.action.kind is not ExecutionActionKind.COMPLETE:
            return canonical

        session_id = str(getattr(request, "execution_session_id", "") or "").strip()
        if not session_id:
            raise ValueError(
                "completion output authority requires execution session lineage"
            )
        session = self.get_session(session_id)
        if session.session_id not in self._execution_lineage_session_ids:
            raise ValueError(
                "completion output authority requires lineage-v2 execution session"
            )
        if (
            request.agent_id != session.agent_id
            or request.task_id != session.task_id
            or request.workspace_epoch_id != session.workspace_epoch_id
        ):
            raise ValueError("completion output execution authority binding mismatch")

        task = self.tasks.get(session.task_id)
        if task.completed_by is not None:
            raise ValueError(
                "task completion authority already claimed during inference"
            )

        output_ids = tuple(str(x) for x in canonical.action.output_artifact_ids)
        known = {artifact.artifact_id for artifact in self.artifacts.records()}
        if any(artifact_id not in known for artifact_id in output_ids):
            # Keep the canonical execution contract: missing declared outputs are
            # converted into a FAILED terminal by the base step path.
            return canonical

        self._attest_completion_output_authority(
            session,
            output_ids,
            grounded_output_artifact_ids=session.output_artifact_ids,
        )
        return canonical

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        if self._execution_lineage_session_ids:
            state["execution_lineage_version"] = 2
            state["execution_lineage_session_ids"] = sorted(
                self._execution_lineage_session_ids
            )
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
        version = int(state.get("execution_lineage_version", 1))
        if version not in {1, 2}:
            raise ValueError("unsupported execution lineage version")
        raw_ids = state.get("execution_lineage_session_ids")
        if version >= 2:
            lineage_session_ids = _lineage_ids(
                raw_ids,
                require_nonempty=True,
                require_sorted=True,
            )
        else:
            if raw_ids is not None:
                raise ValueError(
                    "legacy execution lineage state contains modern binding"
                )
            lineage_session_ids = ()

        token = _RESTORE_EXECUTION_LINEAGE.set(lineage_session_ids)
        try:
            restored = super().from_state(
                registry=registry,
                tasks=tasks,
                context=context,
                artifacts=artifacts,
                external_cores=external_cores,
                coding=coding,
                state=state,
            )
        finally:
            _RESTORE_EXECUTION_LINEAGE.reset(token)
        if not isinstance(restored, cls):
            raise TypeError("execution lineage restore returned wrong authority type")
        return restored

    def _validate_state(self) -> None:
        super()._validate_state()
        unknown = self._execution_lineage_session_ids - set(self._sessions)
        if unknown:
            raise ValueError("execution lineage references unknown execution session")

        known_artifact_ids = {artifact.artifact_id for artifact in self.artifacts.records()}
        for session in self._sessions.values():
            lineaged = session.session_id in self._execution_lineage_session_ids
            if lineaged and (
                session.execution_proof_version < 2 or not session.workspace_epoch_id
            ):
                raise ValueError(
                    "modern execution lineage requires proof-v2 workspace epoch authority"
                )

            projected_output_artifact_ids: list[str] = []
            if lineaged:
                _extend_unique(
                    projected_output_artifact_ids,
                    self._core_output_projection(session),
                )

            for receipt_id in session.decision_receipt_ids:
                decision = self._decisions[receipt_id]
                request = None
                if getattr(decision, "request_provenance_version", 1) >= 2:
                    request = self.get_inference_request(receipt_id)

                if lineaged:
                    if request is None or request.execution_lineage_version < 2:
                        raise ValueError(
                            "execution lineage downgrade detected for persisted inference request"
                        )
                    if request.execution_session_id != session.session_id:
                        raise ValueError(
                            "persisted inference request execution session binding mismatch"
                        )
                    if request.workspace_epoch_id != session.workspace_epoch_id:
                        raise ValueError(
                            "persisted inference request workspace epoch binding mismatch"
                        )
                    if decision.action.kind is ExecutionActionKind.COMPLETE:
                        completion_outputs = tuple(
                            str(artifact_id)
                            for artifact_id in decision.action.output_artifact_ids
                        )
                        missing_outputs = tuple(
                            artifact_id
                            for artifact_id in completion_outputs
                            if artifact_id not in known_artifact_ids
                        )
                        if missing_outputs:
                            if session.terminal_receipt_id is None:
                                raise ValueError(
                                    "missing completion output lacks failed terminal authority"
                                )
                            terminal = self._terminals[session.terminal_receipt_id]
                            if (
                                terminal.state is not ExecutionState.FAILED
                                or terminal.termination_reason
                                != "completion references unknown output artifacts"
                                or any(
                                    artifact_id in session.output_artifact_ids
                                    for artifact_id in missing_outputs
                                )
                            ):
                                raise ValueError(
                                    "missing completion output failed-terminal binding mismatch"
                                )
                        else:
                            self._attest_completion_output_authority(
                                session,
                                completion_outputs,
                                grounded_output_artifact_ids=projected_output_artifact_ids,
                            )
                            _extend_unique(
                                projected_output_artifact_ids,
                                completion_outputs,
                            )
                elif (
                    request is not None
                    and request.execution_lineage_version >= 2
                ):
                    raise ValueError(
                        "modern decision lineage belongs to legacy execution session"
                    )

            if not lineaged:
                continue
            if session.terminal_receipt_id is not None:
                terminal = self._terminals[session.terminal_receipt_id]
                evidence_artifact_id = str(
                    getattr(terminal, "terminal_evidence_artifact_id", "") or ""
                ).strip()
                if not evidence_artifact_id:
                    raise ValueError(
                        "modern execution result projection lacks terminal evidence authority"
                    )
                _extend_unique(projected_output_artifact_ids, (evidence_artifact_id,))
                if terminal.state is ExecutionState.COMPLETED:
                    task = self.tasks.get(session.task_id)
                    if task.completed_by != session.agent_id:
                        raise ValueError("task completion authority binding mismatch")
                    if task.output_artifact_ids != terminal.output_artifact_ids:
                        raise ValueError("task completion output projection binding mismatch")
            if tuple(projected_output_artifact_ids) != session.output_artifact_ids:
                raise ValueError("execution session output projection mismatch")


__all__ = ("OrganizationExecutionControlPlane",)
