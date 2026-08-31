from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "nolane/external_core/acting_runtime.py",
    'COMPONENT_VERSION = "0.1.2"',
    'COMPONENT_VERSION = "0.1.3"',
)

replace_once(
    "nolane/external_core/acting_runtime.py",
    '''class CoreReceipt(Protocol):
    receipt_id: str
    success: bool
    failure_kind: str | None
    output_artifact_ids: tuple[str, ...]
    evidence_artifact_id: str
''',
    '''class CoreReceipt(Protocol):
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
''',
)

replace_once(
    "nolane/external_core/acting_runtime.py",
    '''    @staticmethod
    def _action_id(*, agent_id: str, task_id: str, idempotency_key: str) -> str:
        digest = canonical_digest(
            {
                "agent_id": str(agent_id),
                "task_id": str(task_id),
                "idempotency_key": str(idempotency_key),
            }
        )
        return "acting-action-" + digest[:24]

    def _replay''',
    '''    @staticmethod
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
    ) -> None:
        expected = {
            "agent_id": str(agent_id),
            "task_id": str(task_id),
            "tool_id": action.tool_id,
            "operation": action.operation,
            "input_digest": str(input_digest),
            "before_workspace_digest": str(before_workspace_digest),
            "after_workspace_digest": str(after_workspace_digest),
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

    def _replay''',
)

replace_once(
    "nolane/external_core/acting_runtime.py",
    '''        try:
            self.protocol.begin_execution(action_id, now_ms=current_now_ms())
            receipt = self.executor.invoke(
                agent_id=str(agent_id),
                task_id=str(task_id),
                workspace=workspace,
                action=action,
                timeout_seconds=float(timeout_seconds),
                max_output_chars=int(max_output_chars),
            )
            self.protocol.observe_outcome(
''',
    '''        try:
            self.protocol.begin_execution(action_id, now_ms=current_now_ms())
            dispatch_workspace_digest = workspace.digest
            receipt = self.executor.invoke(
                agent_id=str(agent_id),
                task_id=str(task_id),
                workspace=workspace,
                action=action,
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
            )
            self.protocol.observe_outcome(
''',
)

# Bring forward-execution test doubles up to the canonical receipt contract.
replace_once(
    "tests/test_refoundation_acting_runtime.py",
    '''@dataclass(frozen=True)
class _Receipt:
    receipt_id: str
    success: bool
    failure_kind: str | None
    output_artifact_ids: tuple[str, ...]
    evidence_artifact_id: str
''',
    '''@dataclass(frozen=True)
class _Receipt:
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
''',
)

replace_once(
    "tests/test_refoundation_acting_runtime.py",
    '''    def invoke(self, *, workspace: RepositoryWorkspace, action: ToolAction, **_: object) -> _Receipt:
        self.calls += 1
        workspace.write_text(str(action.arguments["path"]), str(action.arguments["content"]))
        receipt = _Receipt(
            receipt_id=f"core-receipt-{self.calls}",
            success=self.success,
            failure_kind=None if self.success else "simulated_failure",
            output_artifact_ids=(f"artifact-{self.calls}",),
            evidence_artifact_id=f"evidence-{self.calls}",
        )
''',
    '''    def invoke(self, *, workspace: RepositoryWorkspace, action: ToolAction, **kwargs: object) -> _Receipt:
        self.calls += 1
        before = workspace.digest
        workspace.write_text(str(action.arguments["path"]), str(action.arguments["content"]))
        receipt = _Receipt(
            receipt_id=f"core-receipt-{self.calls}",
            agent_id=str(kwargs["agent_id"]),
            task_id=str(kwargs["task_id"]),
            tool_id=action.tool_id,
            operation=action.operation,
            input_digest=canonical_digest(action.to_state()),
            authorized=True,
            success=self.success,
            failure_kind=None if self.success else "simulated_failure",
            before_workspace_digest=before,
            after_workspace_digest=workspace.digest,
            output_artifact_ids=(f"artifact-{self.calls}",),
            evidence_artifact_id=f"evidence-{self.calls}",
        )
''',
)

replace_once(
    "tests/test_refoundation_acting_runtime.py",
    '''    def invoke(self, **_: object) -> _Receipt:
        self.calls += 1
        time.sleep(self.sleep_seconds)
        receipt = _Receipt(
            receipt_id=f"read-receipt-{self.calls}",
            success=True,
            failure_kind=None,
            output_artifact_ids=(),
            evidence_artifact_id=f"read-evidence-{self.calls}",
        )
''',
    '''    def invoke(
        self,
        *,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action: ToolAction,
        **_: object,
    ) -> _Receipt:
        self.calls += 1
        before = workspace.digest
        time.sleep(self.sleep_seconds)
        receipt = _Receipt(
            receipt_id=f"read-receipt-{self.calls}",
            agent_id=str(agent_id),
            task_id=str(task_id),
            tool_id=action.tool_id,
            operation=action.operation,
            input_digest=canonical_digest(action.to_state()),
            authorized=True,
            success=True,
            failure_kind=None,
            before_workspace_digest=before,
            after_workspace_digest=workspace.digest,
            output_artifact_ids=(),
            evidence_artifact_id=f"read-evidence-{self.calls}",
        )
''',
)

replace_once(
    "tests/test_refoundation_acting_runtime.py",
    '''import pytest

from nolane.external_core.acting_protocol import (''',
    '''import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (''',
)

replace_once(
    "CURRENT/E_ACTING.md",
    '| Transactional Executor | `nolane/external_core/acting_runtime.py` | `0.1.2` | checkpoint/invoke/verify/commit or restore/recover around the concrete core executor, monotonic elapsed-time lease enforcement, and executor-free in-flight restart reconciliation |',
    '| Transactional Executor | `nolane/external_core/acting_runtime.py` | `0.1.3` | checkpoint/invoke/verify/commit or restore/recover around the concrete core executor, monotonic elapsed-time lease enforcement, executor-free restart reconciliation, and fail-closed concrete receipt provenance validation |',
)
replace_once(
    "CURRENT/E_ACTING.md",
    '''20. Recovery binds the acting contract back to the exact selected tool action by `core_id`, `operation`, and canonical input digest before any acting mutation or terminal evidence write. A valid-looking `session:decision` idempotency key cannot authorize a semantically different effect.
21. Persisted non-terminal actions are never blindly resumed after process/runtime interruption.''',
    '''20. Recovery binds the acting contract back to the exact selected tool action by `core_id`, `operation`, and canonical input digest before any acting mutation or terminal evidence write. A valid-looking `session:decision` idempotency key cannot authorize a semantically different effect.
21. Forward execution validates the concrete core receipt before outcome projection or commit. Agent, task, tool, operation, canonical input digest, authorization, and before/after workspace digests must all match the dispatched effect; substituted receipts fail closed through the existing rollback/degraded recovery path.
22. Persisted non-terminal actions are never blindly resumed after process/runtime interruption.''',
)

print("E Acting core receipt provenance patch applied deterministically")
