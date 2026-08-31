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
    '''    def _validate_state(self) -> None:\n        max_counter = 0\n        for session_id, session in self._sessions.items():\n            if session_id != session.session_id:\n                raise ValueError('execution session key mismatch')\n            try:\n                max_counter = max(max_counter, int(session_id.rsplit('-', 1)[1]))\n            except Exception as exc:\n                raise ValueError('non-canonical execution session id') from exc\n            for receipt_id in session.decision_receipt_ids:\n                if receipt_id not in self._decisions:\n                    raise ValueError('execution session references unknown decision receipt')\n            for receipt_id in session.step_receipt_ids:\n                if receipt_id not in self._steps:\n                    raise ValueError('execution session references unknown step receipt')\n            if session.terminal_receipt_id is not None and session.terminal_receipt_id not in self._terminals:\n                raise ValueError('execution session references unknown terminal receipt')\n        if self._session_counter < max_counter:\n            raise ValueError('execution session counter is behind history')\n''',
    '''    def _validate_state(self) -> None:\n        max_counter = 0\n        decision_owners: dict[str, str] = {}\n        step_owners: dict[str, str] = {}\n        terminal_owners: dict[str, str] = {}\n        for session_id, session in self._sessions.items():\n            if session_id != session.session_id:\n                raise ValueError('execution session key mismatch')\n            try:\n                max_counter = max(max_counter, int(session_id.rsplit('-', 1)[1]))\n            except Exception as exc:\n                raise ValueError('non-canonical execution session id') from exc\n            if session.step_index != len(session.decision_receipt_ids):\n                raise ValueError('execution session step index does not match decision history')\n            if session.counters.steps != len(session.decision_receipt_ids):\n                raise ValueError('execution session step counter does not match decision history')\n            if len(set(session.decision_receipt_ids)) != len(session.decision_receipt_ids):\n                raise ValueError('execution session contains duplicate decision receipt')\n            if len(set(session.step_receipt_ids)) != len(session.step_receipt_ids):\n                raise ValueError('execution session contains duplicate step receipt')\n            if len(set(session.core_receipt_ids)) != len(session.core_receipt_ids):\n                raise ValueError('execution session contains duplicate core receipt')\n\n            expected_schema_digest = canonical_digest(list(session.action_schema))\n            for position, receipt_id in enumerate(session.decision_receipt_ids):\n                decision = self._decisions.get(receipt_id)\n                if decision is None:\n                    raise ValueError('execution session references unknown decision receipt')\n                previous_owner = decision_owners.setdefault(receipt_id, session_id)\n                if previous_owner != session_id:\n                    raise ValueError('execution decision receipt is shared across sessions')\n                if decision.agent_id != session.agent_id:\n                    raise ValueError('execution decision agent binding mismatch')\n                if decision.backend_id != session.backend_id:\n                    raise ValueError('execution decision backend binding mismatch')\n                if decision.checkpoint_digest != session.checkpoint_digest:\n                    raise ValueError('execution decision checkpoint binding mismatch')\n                if decision.action_schema_digest != expected_schema_digest:\n                    raise ValueError('execution decision action-schema binding mismatch')\n                if decision.step_index != position:\n                    raise ValueError('execution decision step ordering mismatch')\n\n            for receipt_id in session.step_receipt_ids:\n                step = self._steps.get(receipt_id)\n                if step is None:\n                    raise ValueError('execution session references unknown step receipt')\n                previous_owner = step_owners.setdefault(receipt_id, session_id)\n                if previous_owner != session_id:\n                    raise ValueError('execution step receipt is shared across sessions')\n                if step.session_id != session_id:\n                    raise ValueError('execution step receipt session binding mismatch')\n                if step.decision_receipt_id not in session.decision_receipt_ids:\n                    raise ValueError('execution step receipt decision binding mismatch')\n                decision = self._decisions[step.decision_receipt_id]\n                if step.step_index != decision.step_index:\n                    raise ValueError('execution step receipt index binding mismatch')\n                if step.core_receipt_id is not None and step.core_receipt_id not in session.core_receipt_ids:\n                    raise ValueError('execution step receipt core binding mismatch')\n\n            if session.terminal_receipt_id is not None:\n                terminal = self._terminals.get(session.terminal_receipt_id)\n                if terminal is None:\n                    raise ValueError('execution session references unknown terminal receipt')\n                previous_owner = terminal_owners.setdefault(terminal.receipt_id, session_id)\n                if previous_owner != session_id:\n                    raise ValueError('execution terminal receipt is shared across sessions')\n                if terminal.session_id != session_id:\n                    raise ValueError('execution terminal receipt session binding mismatch')\n                if terminal.agent_id != session.agent_id:\n                    raise ValueError('execution terminal receipt agent binding mismatch')\n                if terminal.task_id != session.task_id:\n                    raise ValueError('execution terminal receipt task binding mismatch')\n                if terminal.state is not session.state:\n                    raise ValueError('execution terminal receipt state binding mismatch')\n                terminal_counters = (\n                    terminal.steps,\n                    terminal.tool_calls,\n                    terminal.external_core_calls,\n                    terminal.compute_units,\n                )\n                session_counters = (\n                    session.counters.steps,\n                    session.counters.tool_calls,\n                    session.counters.external_core_calls,\n                    session.counters.compute_units,\n                )\n                if terminal_counters != session_counters:\n                    raise ValueError('execution terminal receipt counter binding mismatch')\n                if terminal.wall_clock_ms != session.wall_clock_ms:\n                    raise ValueError('execution terminal receipt wall-clock binding mismatch')\n                if terminal.decision_receipt_ids != session.decision_receipt_ids:\n                    raise ValueError('execution terminal receipt decision-history mismatch')\n                if terminal.step_receipt_ids != session.step_receipt_ids:\n                    raise ValueError('execution terminal receipt step-history mismatch')\n                if terminal.core_receipt_ids != session.core_receipt_ids:\n                    raise ValueError('execution terminal receipt core-history mismatch')\n                if terminal.output_artifact_ids != session.output_artifact_ids:\n                    raise ValueError('execution terminal receipt output-history mismatch')\n        if self._session_counter < max_counter:\n            raise ValueError('execution session counter is behind history')\n''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''    @staticmethod\n    def _acting_execution_binding(idempotency_key: str) -> tuple[str, str] | None:\n        key = str(idempotency_key).strip()\n        session_id, sep, decision_id = key.rpartition(':')\n        if not sep or not session_id.startswith('execution-') or not decision_id:\n            return None\n        return session_id, decision_id\n\n    def _acting_row_is_projected''',
    '''    @staticmethod\n    def _acting_execution_binding(idempotency_key: str) -> tuple[str, str] | None:\n        key = str(idempotency_key).strip()\n        session_id, sep, decision_id = key.rpartition(':')\n        if not sep or not session_id.startswith('execution-') or not decision_id:\n            return None\n        return session_id, decision_id\n\n    @staticmethod\n    def _acting_row_matches_decision(row: Any, decision: AgentDecisionReceipt) -> bool:\n        action = decision.action\n        if action.kind is not ExecutionActionKind.TOOL or action.tool_action is None:\n            return False\n        tool_action = action.tool_action\n        return (\n            row.contract.core_id == tool_action.tool_id\n            and row.contract.operation == tool_action.operation\n            and row.contract.input_digest == canonical_digest(tool_action.to_state())\n        )\n\n    def _acting_row_is_projected''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''            if decision_id not in session.decision_receipt_ids:\n                raise ValueError('interrupted action decision is not owned by execution session')\n            if self._acting_row_is_projected(row, session, decision_id):\n''',
    '''            if decision_id not in session.decision_receipt_ids:\n                raise ValueError('interrupted action decision is not owned by execution session')\n            decision = self._decisions[decision_id]\n            if not self._acting_row_matches_decision(row, decision):\n                raise ValueError('acting action contract does not match bound decision')\n            if self._acting_row_is_projected(row, session, decision_id):\n''',
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
    '''    assert str(component_version("external.execution.control")) == "0.0.4"\n    assert str(next_component_version("external.execution.control")) == "0.0.5"''',
    '''    assert str(component_version("external.execution.control")) == "0.0.5"\n    assert str(next_component_version("external.execution.control")) == "0.0.6"''',
)
replace_once(
    "tests/test_refoundation_wave5aa_native_execution_control.py",
    '    assert canonical.COMPONENT_VERSION == "0.0.4"',
    '    assert canonical.COMPONENT_VERSION == "0.0.5"',
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
    '''18. Crash recovery is projected across the acting/control boundary: ownership is preflighted before mutation, uncertain recovered effects terminalize only their owning session, and already-committed effects are reconstructed as step receipts without re-invocation.\n18. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.''',
    '''18. Crash recovery is projected across the acting/control boundary: ownership is preflighted before mutation, uncertain recovered effects terminalize only their owning session, and already-committed effects are reconstructed as step receipts without re-invocation.\n19. Persisted execution provenance is closed across session → decision → step/terminal ownership. Existing receipt IDs are not sufficient evidence: agent/backend/checkpoint/action-schema/step ordering and terminal snapshot bindings must agree before restored state is accepted.\n20. Recovery binds the acting contract back to the exact selected tool action by `core_id`, `operation`, and canonical input digest before any acting mutation or terminal evidence write. A valid-looking `session:decision` idempotency key cannot authorize a semantically different effect.\n21. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.''',
)

print("E Acting execution provenance closure patch applied deterministically")
