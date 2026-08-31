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
    "nolane/external_core/execution.py",
    'COMPONENT_VERSION = "0.0.4"',
    'COMPONENT_VERSION = "0.0.5"',
)

replace_once(
    "nolane/external_core/execution.py",
    '''    def _validate_state(self) -> None:
        max_counter = 0
        for session_id, session in self._sessions.items():
            if session_id != session.session_id:
                raise ValueError('execution session key mismatch')
            try:
                max_counter = max(max_counter, int(session_id.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical execution session id') from exc
            for receipt_id in session.decision_receipt_ids:
                if receipt_id not in self._decisions:
                    raise ValueError('execution session references unknown decision receipt')
            for receipt_id in session.step_receipt_ids:
                if receipt_id not in self._steps:
                    raise ValueError('execution session references unknown step receipt')
            if session.terminal_receipt_id is not None and session.terminal_receipt_id not in self._terminals:
                raise ValueError('execution session references unknown terminal receipt')
        if self._session_counter < max_counter:
            raise ValueError('execution session counter is behind history')
''',
    '''    def _validate_state(self) -> None:
        max_counter = 0
        decision_owners: dict[str, str] = {}
        step_owners: dict[str, str] = {}
        terminal_owners: dict[str, str] = {}
        for session_id, session in self._sessions.items():
            if session_id != session.session_id:
                raise ValueError('execution session key mismatch')
            try:
                max_counter = max(max_counter, int(session_id.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical execution session id') from exc
            if session.step_index != len(session.decision_receipt_ids):
                raise ValueError('execution session step index does not match decision history')
            if session.counters.steps != len(session.decision_receipt_ids):
                raise ValueError('execution session step counter does not match decision history')
            if len(set(session.decision_receipt_ids)) != len(session.decision_receipt_ids):
                raise ValueError('execution session contains duplicate decision receipt')
            if len(set(session.step_receipt_ids)) != len(session.step_receipt_ids):
                raise ValueError('execution session contains duplicate step receipt')
            if len(set(session.core_receipt_ids)) != len(session.core_receipt_ids):
                raise ValueError('execution session contains duplicate core receipt')

            expected_schema_digest = canonical_digest(list(session.action_schema))
            for position, receipt_id in enumerate(session.decision_receipt_ids):
                decision = self._decisions.get(receipt_id)
                if decision is None:
                    raise ValueError('execution session references unknown decision receipt')
                previous_owner = decision_owners.setdefault(receipt_id, session_id)
                if previous_owner != session_id:
                    raise ValueError('execution decision receipt is shared across sessions')
                if decision.agent_id != session.agent_id:
                    raise ValueError('execution decision agent binding mismatch')
                if decision.backend_id != session.backend_id:
                    raise ValueError('execution decision backend binding mismatch')
                if decision.checkpoint_digest != session.checkpoint_digest:
                    raise ValueError('execution decision checkpoint binding mismatch')
                if decision.action_schema_digest != expected_schema_digest:
                    raise ValueError('execution decision action-schema binding mismatch')
                if decision.step_index != position:
                    raise ValueError('execution decision step ordering mismatch')

            for receipt_id in session.step_receipt_ids:
                step = self._steps.get(receipt_id)
                if step is None:
                    raise ValueError('execution session references unknown step receipt')
                previous_owner = step_owners.setdefault(receipt_id, session_id)
                if previous_owner != session_id:
                    raise ValueError('execution step receipt is shared across sessions')
                if step.session_id != session_id:
                    raise ValueError('execution step receipt session binding mismatch')
                if step.decision_receipt_id not in session.decision_receipt_ids:
                    raise ValueError('execution step receipt decision binding mismatch')
                decision = self._decisions[step.decision_receipt_id]
                if step.step_index != decision.step_index:
                    raise ValueError('execution step receipt index binding mismatch')
                if step.core_receipt_id is not None and step.core_receipt_id not in session.core_receipt_ids:
                    raise ValueError('execution step receipt core binding mismatch')

            if session.terminal_receipt_id is not None:
                terminal = self._terminals.get(session.terminal_receipt_id)
                if terminal is None:
                    raise ValueError('execution session references unknown terminal receipt')
                previous_owner = terminal_owners.setdefault(terminal.receipt_id, session_id)
                if previous_owner != session_id:
                    raise ValueError('execution terminal receipt is shared across sessions')
                if terminal.session_id != session_id:
                    raise ValueError('execution terminal receipt session binding mismatch')
                if terminal.agent_id != session.agent_id:
                    raise ValueError('execution terminal receipt agent binding mismatch')
                if terminal.task_id != session.task_id:
                    raise ValueError('execution terminal receipt task binding mismatch')
                if terminal.state is not session.state:
                    raise ValueError('execution terminal receipt state binding mismatch')
                terminal_counters = (
                    terminal.steps,
                    terminal.tool_calls,
                    terminal.external_core_calls,
                    terminal.compute_units,
                )
                session_counters = (
                    session.counters.steps,
                    session.counters.tool_calls,
                    session.counters.external_core_calls,
                    session.counters.compute_units,
                )
                if terminal_counters != session_counters:
                    raise ValueError('execution terminal receipt counter binding mismatch')
                if terminal.wall_clock_ms != session.wall_clock_ms:
                    raise ValueError('execution terminal receipt wall-clock binding mismatch')
                if terminal.decision_receipt_ids != session.decision_receipt_ids:
                    raise ValueError('execution terminal receipt decision-history mismatch')
                if terminal.step_receipt_ids != session.step_receipt_ids:
                    raise ValueError('execution terminal receipt step-history mismatch')
                if terminal.core_receipt_ids != session.core_receipt_ids:
                    raise ValueError('execution terminal receipt core-history mismatch')
                if terminal.output_artifact_ids != session.output_artifact_ids:
                    raise ValueError('execution terminal receipt output-history mismatch')
        if self._session_counter < max_counter:
            raise ValueError('execution session counter is behind history')
''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''    @staticmethod
    def _acting_execution_binding(idempotency_key: str) -> tuple[str, str] | None:
        key = str(idempotency_key).strip()
        session_id, sep, decision_id = key.rpartition(':')
        if not sep or not session_id.startswith('execution-') or not decision_id:
            return None
        return session_id, decision_id

    def _acting_row_is_projected''',
    '''    @staticmethod
    def _acting_execution_binding(idempotency_key: str) -> tuple[str, str] | None:
        key = str(idempotency_key).strip()
        session_id, sep, decision_id = key.rpartition(':')
        if not sep or not session_id.startswith('execution-') or not decision_id:
            return None
        return session_id, decision_id

    @staticmethod
    def _acting_row_matches_decision(row: Any, decision: AgentDecisionReceipt) -> bool:
        action = decision.action
        if action.kind is not ExecutionActionKind.TOOL or action.tool_action is None:
            return False
        tool_action = action.tool_action
        return (
            row.contract.core_id == tool_action.tool_id
            and row.contract.operation == tool_action.operation
            and row.contract.input_digest == canonical_digest(tool_action.to_state())
        )

    def _acting_row_is_projected''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''            if decision_id not in session.decision_receipt_ids:
                raise ValueError('interrupted action decision is not owned by execution session')
            if self._acting_row_is_projected(row, session, decision_id):
''',
    '''            if decision_id not in session.decision_receipt_ids:
                raise ValueError('interrupted action decision is not owned by execution session')
            decision = self._decisions[decision_id]
            if not self._acting_row_matches_decision(row, decision):
                raise ValueError('acting action contract does not match bound decision')
            if self._acting_row_is_projected(row, session, decision_id):
''',
)

replace_once(
    "nolane/metadata/component_versions.py",
    '        "external.execution.control": 4,',
    '        "external.execution.control": 5,',
)
replace_once(
    "tests/test_refoundation_component_versions.py",
    '    "external.execution.control": 4,',
    '    "external.execution.control": 5,',
)
replace_once(
    "tests/test_refoundation_component_versions.py",
    '''    assert str(component_version("external.execution.control")) == "0.0.4"
    assert str(next_component_version("external.execution.control")) == "0.0.5"''',
    '''    assert str(component_version("external.execution.control")) == "0.0.5"
    assert str(next_component_version("external.execution.control")) == "0.0.6"''',
)
replace_once(
    "tests/test_refoundation_wave5aa_native_execution_control.py",
    '    assert canonical.COMPONENT_VERSION == "0.0.4"',
    '    assert canonical.COMPONENT_VERSION == "0.0.5"',
)
replace_once(
    "tests/test_refoundation_wave5aa_native_execution_control.py",
    '    assert row.component_version == "0.0.4"',
    '    assert row.component_version == "0.0.5"',
)
replace_once(
    "tests/test_refoundation_wave5aa_native_execution_control.py",
    '    assert str(component_version("external.execution.control")) == "0.0.4"',
    '    assert str(component_version("external.execution.control")) == "0.0.5"',
)

# Upgrade legacy recovery fixtures so they exercise the new provenance invariant
# without weakening production validation.
replace_once(
    "tests/test_refoundation_acting_control_reconciliation.py",
    '''import pytest

from nolane.external_core.acting_protocol import (''',
    '''import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (''',
)
replace_once(
    "tests/test_refoundation_acting_control_reconciliation.py",
    'from nolane.external_core.execution_types import ExecutionBudget, ExecutionCounters',
    '''from nolane.external_core.execution_types import (
    ExecutionAction,
    ExecutionBudget,
    ExecutionCounters,
    ToolAction,
)''',
)
replace_once(
    "tests/test_refoundation_acting_control_reconciliation.py",
    '''@dataclass(frozen=True)
class _Decision:
    receipt_id: str
''',
    '''_TOOL_ACTION = ToolAction.from_arguments(
    "filesystem",
    "write_text",
    {"path": "README.md", "content": "changed\\n"},
)
_ACTION_SCHEMA = ("filesystem.write_text",)
_ACTION_SCHEMA_DIGEST = canonical_digest(list(_ACTION_SCHEMA))
_TOOL_INPUT_DIGEST = canonical_digest(_TOOL_ACTION.to_state())


@dataclass(frozen=True)
class _Decision:
    receipt_id: str
    agent_id: str = "agent-1"
    backend_id: str = "backend-v1"
    checkpoint_digest: str = "checkpoint-v1"
    action_schema_digest: str = _ACTION_SCHEMA_DIGEST
    step_index: int = 0
    action: ExecutionAction = ExecutionAction.tool(_TOOL_ACTION)
''',
)
replace_once(
    "tests/test_refoundation_acting_control_reconciliation.py",
    '        action_schema=("filesystem.write_text",),',
    '        action_schema=_ACTION_SCHEMA,',
)
replace_once(
    "tests/test_refoundation_acting_control_reconciliation.py",
    '''        counters=ExecutionCounters(steps=1, compute_units=1),
        step_index=1,''',
    '''        counters=ExecutionCounters(
            steps=len(decision_ids),
            compute_units=len(decision_ids),
        ),
        step_index=len(decision_ids),''',
)
replace_once(
    "tests/test_refoundation_acting_control_reconciliation.py",
    '        input_digest=f"input:{session_id}",',
    '        input_digest=_TOOL_INPUT_DIGEST,',
)

replace_once(
    "tests/test_refoundation_acting_control_commit_projection.py",
    '''from dataclasses import dataclass

from nolane.external_core.acting_protocol import (''',
    '''from dataclasses import dataclass

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (''',
)
replace_once(
    "tests/test_refoundation_acting_control_commit_projection.py",
    'from nolane.external_core.execution_types import ExecutionBudget, ExecutionCounters',
    '''from nolane.external_core.execution_types import (
    ExecutionAction,
    ExecutionBudget,
    ExecutionCounters,
    ToolAction,
)''',
)
replace_once(
    "tests/test_refoundation_acting_control_commit_projection.py",
    '''@dataclass(frozen=True)
class _Decision:
    receipt_id: str
    step_index: int = 0
''',
    '''_TOOL_ACTION = ToolAction.from_arguments(
    "filesystem",
    "write_text",
    {"path": "README.md", "content": "changed\\n"},
)
_ACTION_SCHEMA = ("filesystem.write_text",)
_ACTION_SCHEMA_DIGEST = canonical_digest(list(_ACTION_SCHEMA))
_TOOL_INPUT_DIGEST = canonical_digest(_TOOL_ACTION.to_state())


@dataclass(frozen=True)
class _Decision:
    receipt_id: str
    agent_id: str = "agent-1"
    backend_id: str = "backend-v1"
    checkpoint_digest: str = "checkpoint-v1"
    action_schema_digest: str = _ACTION_SCHEMA_DIGEST
    step_index: int = 0
    action: ExecutionAction = ExecutionAction.tool(_TOOL_ACTION)
''',
)
replace_once(
    "tests/test_refoundation_acting_control_commit_projection.py",
    '''class _CoreReceipt:
    receipt_id: str
    success: bool = True
    failure_kind: str | None = None
    output_artifact_ids: tuple[str, ...] = ("artifact-1",)
    evidence_artifact_id: str = "evidence-core-1"
    before_workspace_digest: str = "workspace-before"
    after_workspace_digest: str = "workspace-after"
''',
    '''class _CoreReceipt:
    receipt_id: str
    agent_id: str = "agent-1"
    task_id: str = "task-1"
    tool_id: str = "filesystem"
    operation: str = "write_text"
    input_digest: str = _TOOL_INPUT_DIGEST
    authorized: bool = True
    success: bool = True
    failure_kind: str | None = None
    output_artifact_ids: tuple[str, ...] = ("artifact-1",)
    evidence_artifact_id: str = "evidence-core-1"
    before_workspace_digest: str = "workspace-before"
    after_workspace_digest: str = "workspace-after"
''',
)
replace_once(
    "tests/test_refoundation_acting_control_commit_projection.py",
    '        action_schema=("filesystem.write_text",),',
    '        action_schema=_ACTION_SCHEMA,',
)
replace_once(
    "tests/test_refoundation_acting_control_commit_projection.py",
    '        input_digest="input:commit-projection",',
    '        input_digest=_TOOL_INPUT_DIGEST,',
)

replace_once(
    "CURRENT/E_ACTING.md",
    '**Revision:** transactional baseline with canonical execution integration, fail-closed hardening, and crash-safe in-flight reconciliation',
    '**Revision:** transactional baseline with canonical execution integration, crash-safe reconciliation, and provenance-closed persisted execution graphs',
)
replace_once(
    "CURRENT/E_ACTING.md",
    '| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.4` | compatibility-facing organization controller whose effectful tool path is forced through `TransactionalExternalCoreExecutor`; persists/restores the transactional ledger and conservatively classifies unconfined process tools |',
    '| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.5` | compatibility-facing organization controller whose effectful tool path is forced through `TransactionalExternalCoreExecutor`; persists/restores the transactional ledger, validates receipt provenance, and conservatively classifies unconfined process tools |',
)
replace_once(
    "CURRENT/E_ACTING.md",
    '''18. Crash recovery is projected across the acting/control boundary: ownership is preflighted before mutation, uncertain recovered effects terminalize only their owning session, and already-committed effects are reconstructed as step receipts without re-invocation.
18. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.''',
    '''18. Crash recovery is projected across the acting/control boundary: ownership is preflighted before mutation, uncertain recovered effects terminalize only their owning session, and already-committed effects are reconstructed as step receipts without re-invocation.
19. Persisted execution provenance is closed across session → decision → step/terminal ownership. Existing receipt IDs are not sufficient evidence: agent/backend/checkpoint/action-schema/step ordering and terminal snapshot bindings must agree before restored state is accepted.
20. Recovery binds the acting contract back to the exact selected tool action by `core_id`, `operation`, and canonical input digest before any acting mutation or terminal evidence write. A valid-looking `session:decision` idempotency key cannot authorize a semantically different effect.
21. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.''',
)

print("E Acting execution provenance closure patch applied deterministically")
