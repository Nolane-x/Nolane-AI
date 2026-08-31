from __future__ import annotations

from pathlib import Path


EXECUTION = Path("nolane/external_core/execution.py")
text = EXECUTION.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"execution.py expected one match, found {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)


replace_once(
    "from nolane.external_core.acting_protocol import EffectClass, ExecutionRisk, VerifierLevel",
    "from nolane.external_core.acting_protocol import ActionPhase, EffectClass, ExecutionRisk, VerifierLevel",
)
replace_once('COMPONENT_VERSION = "0.0.3"', 'COMPONENT_VERSION = "0.0.4"')

marker = "    def run(self, session_id: str) -> ExecutionTerminalReceipt:\n"
bridge = '''    @staticmethod
    def _acting_execution_binding(idempotency_key: str) -> tuple[str, str] | None:
        key = str(idempotency_key).strip()
        session_id, sep, decision_id = key.rpartition(':')
        if not sep or not session_id.startswith('execution-') or not decision_id:
            return None
        return session_id, decision_id

    def _acting_row_is_projected(self, row: Any, session: ExecutionSession, decision_id: str) -> bool:
        if row.outcome_ref:
            for receipt_id in session.step_receipt_ids:
                step = self._steps[receipt_id]
                if step.decision_receipt_id == decision_id and step.core_receipt_id == row.outcome_ref:
                    return True
        if row.phase in {ActionPhase.CANCELLED, ActionPhase.ROLLED_BACK, ActionPhase.DEGRADED}:
            if session.terminal_receipt_id is None:
                return False
            terminal = self._terminals[session.terminal_receipt_id]
            return f'acting-action={row.action_id}' in terminal.termination_reason
        return False

    def reconcile_interrupted_sessions(
        self,
        *,
        evidence_ref: str,
        reason: str,
    ) -> tuple[ExecutionStepReceipt | ExecutionTerminalReceipt, ...]:
        """Project persisted acting outcomes into their owning execution sessions.

        Recovery is explicit. It never asks an inference backend for a new action and
        never invokes a concrete side effect. All ownership is preflighted before any
        acting lifecycle mutation so an orphan cannot partially reconcile valid rows.
        """

        ref = str(evidence_ref).strip()
        why = str(reason).strip()
        if not ref or not why:
            raise ValueError('control-plane reconciliation requires evidence and a reason')

        terminal_phases = {
            ActionPhase.COMMITTED,
            ActionPhase.ROLLED_BACK,
            ActionPhase.DEGRADED,
            ActionPhase.CANCELLED,
        }
        candidates: list[tuple[Any, ExecutionSession, str]] = []
        per_session: dict[str, str] = {}
        committed_receipts: dict[str, Any] = {}

        # Preflight the complete ownership set before mutating the acting ledger.
        for row in self.acting_executor.protocol.records():
            binding = self._acting_execution_binding(row.contract.idempotency_key)
            if binding is None:
                continue
            session_id, decision_id = binding
            session = self._sessions.get(session_id)
            if session is None:
                raise ValueError('interrupted action has no owning execution session')
            if decision_id not in session.decision_receipt_ids:
                raise ValueError('interrupted action decision is not owned by execution session')
            if self._acting_row_is_projected(row, session, decision_id):
                continue
            if session.state is not ExecutionState.RUNNING or session.terminal_receipt_id is not None:
                raise ValueError('interrupted action belongs to non-running execution session')
            previous = per_session.get(session_id)
            if previous is not None and previous != row.action_id:
                raise ValueError('execution session has multiple unprojected acting actions')
            per_session[session_id] = row.action_id
            if row.phase is ActionPhase.COMMITTED:
                if not row.outcome_ref:
                    raise ValueError('committed acting action is missing its core receipt')
                try:
                    core = self.executor.get_receipt(row.outcome_ref)
                except Exception as exc:
                    raise ValueError('committed acting action references unavailable core receipt') from exc
                if not bool(core.success):
                    raise ValueError('committed acting action references unsuccessful core receipt')
                committed_receipts[row.action_id] = core
            candidates.append((row, session, decision_id))

        results: list[ExecutionStepReceipt | ExecutionTerminalReceipt] = []
        for original, session, decision_id in candidates:
            row = original
            if row.phase not in terminal_phases:
                row = self.acting_executor.protocol.reconcile_interrupted(
                    row.action_id,
                    evidence_ref=ref,
                    reason=why,
                )

            if row.phase is ActionPhase.COMMITTED:
                core = committed_receipts[row.action_id]
                decision = self._decisions[decision_id]
                step_receipt = ExecutionStepReceipt.create(
                    session_id=session.session_id,
                    step_index=int(decision.step_index),
                    decision_receipt_id=decision_id,
                    core_receipt_id=str(core.receipt_id),
                    before_workspace_digest=str(core.before_workspace_digest),
                    after_workspace_digest=str(core.after_workspace_digest),
                    state_after=ExecutionState.RUNNING,
                    output_artifact_ids=tuple(str(x) for x in core.output_artifact_ids),
                )
                existing = self._steps.get(step_receipt.receipt_id)
                if existing is not None and existing != step_receipt:
                    raise ValueError('execution step receipt id collision during recovery')
                self._steps[step_receipt.receipt_id] = step_receipt
                external_ids = frozenset(getattr(self.executor, 'external_core_ids', ()))
                counters = ExecutionCounters(
                    steps=session.counters.steps,
                    tool_calls=session.counters.tool_calls + 1,
                    external_core_calls=session.counters.external_core_calls
                    + (1 if row.contract.core_id in external_ids else 0),
                    compute_units=session.counters.compute_units,
                )
                outputs = tuple(
                    dict.fromkeys(
                        session.output_artifact_ids
                        + tuple(str(x) for x in core.output_artifact_ids)
                    )
                )
                updated = replace(
                    session,
                    counters=counters,
                    state=ExecutionState.RUNNING,
                    output_artifact_ids=outputs,
                    core_receipt_ids=session.core_receipt_ids + (str(core.receipt_id),),
                    step_receipt_ids=session.step_receipt_ids + (step_receipt.receipt_id,),
                )
                self._sessions[session.session_id] = updated
                results.append(step_receipt)
                continue

            if row.phase is ActionPhase.DEGRADED:
                state = ExecutionState.FAILED
            elif row.phase in {ActionPhase.CANCELLED, ActionPhase.ROLLED_BACK}:
                state = ExecutionState.ABORTED
            else:
                raise ValueError(f'acting reconciliation produced unsupported phase: {row.phase.value}')
            termination = (
                f'{why}; acting-action={row.action_id}; phase={row.phase.value}; '
                f'decision={decision_id}; recovery-evidence={ref}'
            )
            results.append(self._terminal(session, state, termination))

        return tuple(results)

'''
if text.count(marker) != 1:
    raise SystemExit("execution.py run marker not found exactly once")
text = text.replace(marker, bridge + marker, 1)
EXECUTION.write_text(text, encoding="utf-8")

meta = Path("nolane/metadata/component_versions.py")
data = meta.read_text(encoding="utf-8")
old = '        "external.execution.control": 3,'
if data.count(old) != 1:
    raise SystemExit("component version revision entry mismatch")
meta.write_text(data.replace(old, '        "external.execution.control": 4,', 1), encoding="utf-8")

versions = Path("tests/test_refoundation_component_versions.py")
data = versions.read_text(encoding="utf-8")
replacements = {
    '    "external.execution.control": 3,': '    "external.execution.control": 4,',
    'assert str(component_version("external.execution.control")) == "0.0.3"': 'assert str(component_version("external.execution.control")) == "0.0.4"',
    'assert str(next_component_version("external.execution.control")) == "0.0.4"': 'assert str(next_component_version("external.execution.control")) == "0.0.5"',
}
for old, new in replacements.items():
    if data.count(old) != 1:
        raise SystemExit(f"component-version test mismatch: {old}")
    data = data.replace(old, new, 1)
versions.write_text(data, encoding="utf-8")

wave = Path("tests/test_refoundation_wave5aa_native_execution_control.py")
data = wave.read_text(encoding="utf-8")
if data.count('"0.0.3"') < 2:
    raise SystemExit("wave5aa version witnesses not found")
data = data.replace('"0.0.3"', '"0.0.4"')
wave.write_text(data, encoding="utf-8")

current = Path("CURRENT/E_ACTING.md")
data = current.read_text(encoding="utf-8")
old = '| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.3` |'
new = '| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.4` |'
if data.count(old) != 1:
    raise SystemExit("CURRENT execution-control version row mismatch")
data = data.replace(old, new, 1)
anchor = "17. `terminal`, `compiler`, and `test-runner` are treated as external-like R3/V3 effects by the compatibility adapter because a disposable repository copy is not an operating-system sandbox; their failure therefore cannot be disguised as a no-effect read rollback.\n"
addition = anchor + "18. Crash recovery is projected across the acting/control boundary: ownership is preflighted before mutation, uncertain recovered effects terminalize only their owning session, and already-committed effects are reconstructed as step receipts without re-invocation.\n"
if data.count(anchor) != 1:
    raise SystemExit("CURRENT invariant anchor mismatch")
current.write_text(data.replace(anchor, addition, 1), encoding="utf-8")
