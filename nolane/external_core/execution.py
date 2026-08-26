from __future__ import annotations

import time
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.artifacts import ArtifactStore
from nolane.external_core.execution_executor import ExternalCoreExecutor
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionActionKind,
    ExecutionBudget,
    ExecutionCounters,
)
from nolane.external_core.execution_workspace import RepositoryWorkspace
from nolane.external_core.invokable import ExternalCoreRegistry
from nolane.neural.inference_bridge import AgentInferenceBackend, CognitiveStateEncoder
from nolane.organization.identity import AgentRegistry
from nolane.organization.tasks import TaskGraph
from nolane.schemas.identity import AgentStatus


COMPONENT_ID = "external.execution.control"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.execution"


class ExecutionState(str, Enum):
    RUNNING = 'running'
    WAITING = 'waiting'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ABORTED = 'aborted'
    PAUSED = 'paused'
    BUDGET_EXHAUSTED = 'budget_exhausted'


@dataclass(frozen=True, slots=True)
class ExecutionSession:
    session_id: str
    agent_id: str
    task_id: str
    action_schema: tuple[str, ...]
    budget: ExecutionBudget
    counters: ExecutionCounters
    step_index: int
    state: ExecutionState
    backend_id: str
    checkpoint_digest: str
    workspace_base_revision: str
    decision_receipt_ids: tuple[str, ...] = ()
    step_receipt_ids: tuple[str, ...] = ()
    core_receipt_ids: tuple[str, ...] = ()
    output_artifact_ids: tuple[str, ...] = ()
    terminal_receipt_id: str | None = None
    wall_clock_ms: int = 0

    def to_state(self) -> dict[str, Any]:
        return {
            'session_id': self.session_id,
            'agent_id': self.agent_id,
            'task_id': self.task_id,
            'action_schema': list(self.action_schema),
            'budget': self.budget.to_state(),
            'counters': self.counters.to_state(),
            'step_index': self.step_index,
            'state': self.state.value,
            'backend_id': self.backend_id,
            'checkpoint_digest': self.checkpoint_digest,
            'workspace_base_revision': self.workspace_base_revision,
            'decision_receipt_ids': list(self.decision_receipt_ids),
            'step_receipt_ids': list(self.step_receipt_ids),
            'core_receipt_ids': list(self.core_receipt_ids),
            'output_artifact_ids': list(self.output_artifact_ids),
            'terminal_receipt_id': self.terminal_receipt_id,
            'wall_clock_ms': self.wall_clock_ms,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExecutionSession':
        return cls(
            session_id=str(state['session_id']),
            agent_id=str(state['agent_id']),
            task_id=str(state['task_id']),
            action_schema=tuple(str(x) for x in state.get('action_schema', ())),
            budget=ExecutionBudget.from_state(state['budget']),
            counters=ExecutionCounters.from_state(state.get('counters', {})),
            step_index=int(state['step_index']),
            state=ExecutionState(str(state['state'])),
            backend_id=str(state['backend_id']),
            checkpoint_digest=str(state['checkpoint_digest']),
            workspace_base_revision=str(state['workspace_base_revision']),
            decision_receipt_ids=tuple(str(x) for x in state.get('decision_receipt_ids', ())),
            step_receipt_ids=tuple(str(x) for x in state.get('step_receipt_ids', ())),
            core_receipt_ids=tuple(str(x) for x in state.get('core_receipt_ids', ())),
            output_artifact_ids=tuple(str(x) for x in state.get('output_artifact_ids', ())),
            terminal_receipt_id=None if state.get('terminal_receipt_id') is None else str(state['terminal_receipt_id']),
            wall_clock_ms=int(state.get('wall_clock_ms', 0)),
        )


@dataclass(frozen=True, slots=True)
class ExecutionStepReceipt:
    receipt_id: str
    session_id: str
    step_index: int
    decision_receipt_id: str
    core_receipt_id: str | None
    before_workspace_digest: str
    after_workspace_digest: str
    state_after: ExecutionState
    output_artifact_ids: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'session_id': self.session_id,
            'step_index': self.step_index,
            'decision_receipt_id': self.decision_receipt_id,
            'core_receipt_id': self.core_receipt_id,
            'before_workspace_digest': self.before_workspace_digest,
            'after_workspace_digest': self.after_workspace_digest,
            'state_after': self.state_after.value,
            'output_artifact_ids': list(self.output_artifact_ids),
        }

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        step_index: int,
        decision_receipt_id: str,
        core_receipt_id: str | None,
        before_workspace_digest: str,
        after_workspace_digest: str,
        state_after: ExecutionState,
        output_artifact_ids: Sequence[str] = (),
    ) -> 'ExecutionStepReceipt':
        payload = {
            'session_id': str(session_id),
            'step_index': int(step_index),
            'decision_receipt_id': str(decision_receipt_id),
            'core_receipt_id': None if core_receipt_id is None else str(core_receipt_id),
            'before_workspace_digest': str(before_workspace_digest),
            'after_workspace_digest': str(after_workspace_digest),
            'state_after': ExecutionState(state_after).value,
            'output_artifact_ids': [str(x) for x in output_artifact_ids],
        }
        digest = canonical_digest(payload)
        return cls(
            receipt_id='step-' + digest[:24],
            session_id=str(session_id),
            step_index=int(step_index),
            decision_receipt_id=str(decision_receipt_id),
            core_receipt_id=None if core_receipt_id is None else str(core_receipt_id),
            before_workspace_digest=str(before_workspace_digest),
            after_workspace_digest=str(after_workspace_digest),
            state_after=ExecutionState(state_after),
            output_artifact_ids=tuple(str(x) for x in output_artifact_ids),
            digest=digest,
        )

    def to_state(self) -> dict[str, Any]:
        return {'receipt_id': self.receipt_id, **self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExecutionStepReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']),
            session_id=str(state['session_id']),
            step_index=int(state['step_index']),
            decision_receipt_id=str(state['decision_receipt_id']),
            core_receipt_id=None if state.get('core_receipt_id') is None else str(state['core_receipt_id']),
            before_workspace_digest=str(state['before_workspace_digest']),
            after_workspace_digest=str(state['after_workspace_digest']),
            state_after=ExecutionState(str(state['state_after'])),
            output_artifact_ids=tuple(str(x) for x in state.get('output_artifact_ids', ())),
            digest=str(state['digest']),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != 'step-' + expected[:24]:
            raise ValueError('execution step receipt digest/id mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ExecutionTerminalReceipt:
    receipt_id: str
    session_id: str
    agent_id: str
    task_id: str
    state: ExecutionState
    termination_reason: str
    steps: int
    tool_calls: int
    external_core_calls: int
    compute_units: int
    wall_clock_ms: int
    decision_receipt_ids: tuple[str, ...]
    step_receipt_ids: tuple[str, ...]
    core_receipt_ids: tuple[str, ...]
    output_artifact_ids: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'session_id': self.session_id,
            'agent_id': self.agent_id,
            'task_id': self.task_id,
            'state': self.state.value,
            'termination_reason': self.termination_reason,
            'steps': self.steps,
            'tool_calls': self.tool_calls,
            'external_core_calls': self.external_core_calls,
            'compute_units': self.compute_units,
            'wall_clock_ms': self.wall_clock_ms,
            'decision_receipt_ids': list(self.decision_receipt_ids),
            'step_receipt_ids': list(self.step_receipt_ids),
            'core_receipt_ids': list(self.core_receipt_ids),
            'output_artifact_ids': list(self.output_artifact_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {'receipt_id': self.receipt_id, **self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExecutionTerminalReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']),
            session_id=str(state['session_id']),
            agent_id=str(state['agent_id']),
            task_id=str(state['task_id']),
            state=ExecutionState(str(state['state'])),
            termination_reason=str(state['termination_reason']),
            steps=int(state['steps']),
            tool_calls=int(state['tool_calls']),
            external_core_calls=int(state['external_core_calls']),
            compute_units=int(state['compute_units']),
            wall_clock_ms=int(state['wall_clock_ms']),
            decision_receipt_ids=tuple(str(x) for x in state.get('decision_receipt_ids', ())),
            step_receipt_ids=tuple(str(x) for x in state.get('step_receipt_ids', ())),
            core_receipt_ids=tuple(str(x) for x in state.get('core_receipt_ids', ())),
            output_artifact_ids=tuple(str(x) for x in state.get('output_artifact_ids', ())),
            digest=str(state['digest']),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != 'terminal-' + expected[:24]:
            raise ValueError('execution terminal receipt digest/id mismatch')
        return row


class OrganizationExecutionControlPlane:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        tasks: TaskGraph,
        context: Any,
        artifacts: ArtifactStore,
        external_cores: ExternalCoreRegistry,
        coding: Any,
        encoder: CognitiveStateEncoder | None = None,
        executor: ExternalCoreExecutor | None = None,
        sessions: tuple[ExecutionSession, ...] = (),
        decisions: tuple[AgentDecisionReceipt, ...] = (),
        steps: tuple[ExecutionStepReceipt, ...] = (),
        terminals: tuple[ExecutionTerminalReceipt, ...] = (),
        session_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.tasks = tasks
        self.context = context
        self.artifacts = artifacts
        self.external_cores = external_cores
        self.coding = coding
        self.encoder = encoder or CognitiveStateEncoder(version='organization-context-digest-v1')
        self.executor = executor or ExternalCoreExecutor(
            registry=registry,
            external_cores=external_cores,
            artifacts=artifacts,
            coding_patches=getattr(coding, 'patches', None),
            code_claims=getattr(coding, 'claims', None),
        )
        self._sessions = {row.session_id: row for row in sessions}
        self._decisions = {row.receipt_id: row for row in decisions}
        self._steps = {row.receipt_id: row for row in steps}
        self._terminals = {row.receipt_id: row for row in terminals}
        self._session_counter = int(session_counter)
        self._backends: dict[str, AgentInferenceBackend] = {}
        self._workspaces: dict[str, RepositoryWorkspace] = {}
        self._validate_state()

    def _validate_state(self) -> None:
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

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def bind_backend(self, agent_id: str, backend: AgentInferenceBackend) -> None:
        identity = self.registry.get(agent_id)
        if not str(backend.backend_id).strip() or not str(backend.checkpoint_digest).strip():
            raise ValueError('inference backend identity/checkpoint digest must be explicit')
        active = [s for s in self._sessions.values() if s.agent_id == identity.agent_id and s.terminal_receipt_id is None]
        for session in active:
            if session.backend_id != backend.backend_id or session.checkpoint_digest != backend.checkpoint_digest:
                raise ValueError('rebound backend does not match persisted execution session')
        self._backends[identity.agent_id] = backend

    def attach_workspace(self, session_id: str, workspace: RepositoryWorkspace) -> None:
        session = self.get_session(session_id)
        if workspace.base_revision != session.workspace_base_revision:
            raise ValueError('reattached workspace revision does not match persisted session')
        self._workspaces[session.session_id] = workspace

    def sessions(self) -> tuple[ExecutionSession, ...]:
        return tuple(self._sessions[k] for k in sorted(self._sessions))

    def terminal_receipts(self) -> tuple[ExecutionTerminalReceipt, ...]:
        return tuple(self._terminals[k] for k in sorted(self._terminals))

    def get_session(self, session_id: str) -> ExecutionSession:
        try:
            return self._sessions[str(session_id)]
        except KeyError as exc:
            raise KeyError(f'unknown execution session: {session_id}') from exc

    def get_decision(self, receipt_id: str) -> AgentDecisionReceipt:
        return self._decisions[str(receipt_id)]

    def get_step_receipt(self, receipt_id: str) -> ExecutionStepReceipt:
        return self._steps[str(receipt_id)]

    def get_terminal_receipt(self, receipt_id: str) -> ExecutionTerminalReceipt:
        return self._terminals[str(receipt_id)]

    def start(
        self,
        *,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action_schema: Sequence[str],
        budget: ExecutionBudget,
    ) -> ExecutionSession:
        identity = self.registry.get(agent_id)
        task = self.tasks.get(task_id)
        if task.aborted_by is not None:
            raise ValueError(f'task {task_id} is aborted')
        if task.leased_to != identity.agent_id:
            raise PermissionError('execution start requires current task lease')
        backend = self._backends.get(identity.agent_id)
        if backend is None:
            raise RuntimeError(f'no inference backend bound for {identity.agent_id}')
        schema = tuple(str(x) for x in action_schema if str(x).strip())
        if not schema:
            raise ValueError('execution action schema must be non-empty')
        self._session_counter += 1
        row = ExecutionSession(
            session_id=f'execution-{self._session_counter:08d}',
            agent_id=identity.agent_id,
            task_id=str(task_id),
            action_schema=schema,
            budget=budget,
            counters=ExecutionCounters(),
            step_index=0,
            state=ExecutionState.RUNNING,
            backend_id=str(backend.backend_id),
            checkpoint_digest=str(backend.checkpoint_digest),
            workspace_base_revision=workspace.base_revision,
        )
        self._sessions[row.session_id] = row
        self._workspaces[row.session_id] = workspace
        return row

    def _terminal(self, session: ExecutionSession, state: ExecutionState, reason: str, *, complete_task: bool = False) -> ExecutionTerminalReceipt:
        if not str(reason).strip():
            raise ValueError('execution termination reason must be explicit')
        summary = {
            'session_id': session.session_id,
            'agent_id': session.agent_id,
            'task_id': session.task_id,
            'state': state.value,
            'reason': str(reason),
            'counters': session.counters.to_state(),
            'decision_receipt_ids': list(session.decision_receipt_ids),
            'step_receipt_ids': list(session.step_receipt_ids),
            'core_receipt_ids': list(session.core_receipt_ids),
        }
        evidence = self.artifacts.put(
            kind='execution-terminal-evidence',
            producer_agent_id=session.agent_id,
            content=canonical_json(summary),
            evidence_refs=session.output_artifact_ids,
            metadata={'task_id': session.task_id, 'state': state.value},
        )
        outputs = tuple(dict.fromkeys(session.output_artifact_ids + (evidence.artifact_id,)))
        terminal_payload = {
            'session_id': session.session_id,
            'agent_id': session.agent_id,
            'task_id': session.task_id,
            'state': state.value,
            'termination_reason': str(reason),
            'steps': session.counters.steps,
            'tool_calls': session.counters.tool_calls,
            'external_core_calls': session.counters.external_core_calls,
            'compute_units': session.counters.compute_units,
            'wall_clock_ms': session.wall_clock_ms,
            'decision_receipt_ids': list(session.decision_receipt_ids),
            'step_receipt_ids': list(session.step_receipt_ids),
            'core_receipt_ids': list(session.core_receipt_ids),
            'output_artifact_ids': list(outputs),
        }
        digest = canonical_digest(terminal_payload)
        receipt = ExecutionTerminalReceipt(
            receipt_id='terminal-' + digest[:24],
            session_id=session.session_id,
            agent_id=session.agent_id,
            task_id=session.task_id,
            state=state,
            termination_reason=str(reason),
            steps=session.counters.steps,
            tool_calls=session.counters.tool_calls,
            external_core_calls=session.counters.external_core_calls,
            compute_units=session.counters.compute_units,
            wall_clock_ms=session.wall_clock_ms,
            decision_receipt_ids=session.decision_receipt_ids,
            step_receipt_ids=session.step_receipt_ids,
            core_receipt_ids=session.core_receipt_ids,
            output_artifact_ids=outputs,
            digest=digest,
        )
        existing = self._terminals.get(receipt.receipt_id)
        if existing is not None and existing != receipt:
            raise ValueError('execution terminal receipt id collision')
        self._terminals[receipt.receipt_id] = receipt
        updated = replace(
            session,
            state=state,
            output_artifact_ids=outputs,
            terminal_receipt_id=receipt.receipt_id,
        )
        self._sessions[session.session_id] = updated
        if complete_task:
            task = self.tasks.get(session.task_id)
            if task.completed_by is None:
                self.tasks.complete(session.task_id, session.agent_id, output_artifact_ids=outputs)
        return receipt

    def _budget_terminal(self, session: ExecutionSession, reason: str) -> ExecutionTerminalReceipt:
        return self._terminal(session, ExecutionState.BUDGET_EXHAUSTED, reason)

    def step(self, session_id: str) -> ExecutionStepReceipt | ExecutionTerminalReceipt:
        session = self.get_session(session_id)
        if session.terminal_receipt_id is not None:
            return self.get_terminal_receipt(session.terminal_receipt_id)
        workspace = self._workspaces.get(session.session_id)
        if workspace is None:
            raise RuntimeError('execution workspace must be attached before stepping')
        task = self.tasks.get(session.task_id)
        if task.aborted_by is not None:
            return self._terminal(session, ExecutionState.ABORTED, task.abort_reason or 'task aborted')
        identity = self.registry.get(session.agent_id)
        if identity.status is AgentStatus.PAUSED:
            return self._terminal(session, ExecutionState.PAUSED, 'agent paused by authority')
        if task.leased_to != session.agent_id:
            return self._terminal(session, ExecutionState.FAILED, 'task lease no longer belongs to executing agent')
        if session.counters.steps >= session.budget.max_steps:
            return self._budget_terminal(session, 'step budget exhausted')
        if session.counters.compute_units >= session.budget.max_compute_units:
            return self._budget_terminal(session, 'compute budget exhausted')
        backend = self._backends.get(session.agent_id)
        if backend is None:
            raise RuntimeError(f'no inference backend rebound for {session.agent_id}')
        if backend.backend_id != session.backend_id or backend.checkpoint_digest != session.checkpoint_digest:
            raise RuntimeError('active backend differs from persisted execution session')

        started = time.perf_counter_ns()
        capsule = self.context.compile(session.agent_id, task_id=session.task_id)
        request = self.encoder.build_request(
            identity=identity,
            capsule=capsule,
            task_id=session.task_id,
            action_schema=session.action_schema,
            counters=session.counters,
            step_index=session.step_index,
            checkpoint_digest=session.checkpoint_digest,
        )
        decision = backend.decide(request)
        if decision.receipt_id in self._decisions and self._decisions[decision.receipt_id] != decision:
            raise ValueError('decision receipt id collision')
        self._decisions[decision.receipt_id] = decision
        counters = ExecutionCounters(
            steps=session.counters.steps + 1,
            tool_calls=session.counters.tool_calls,
            external_core_calls=session.counters.external_core_calls,
            compute_units=session.counters.compute_units + decision.compute_units,
        )
        session = replace(
            session,
            counters=counters,
            step_index=session.step_index + 1,
            decision_receipt_ids=session.decision_receipt_ids + (decision.receipt_id,),
        )
        self._sessions[session.session_id] = session
        if counters.compute_units > session.budget.max_compute_units:
            elapsed = max(0, int((time.perf_counter_ns() - started) / 1_000_000))
            session = replace(session, wall_clock_ms=session.wall_clock_ms + elapsed)
            self._sessions[session.session_id] = session
            return self._budget_terminal(session, 'decision exceeded compute budget')

        action = decision.action
        if action.kind is ExecutionActionKind.TOOL:
            assert action.tool_action is not None
            schema_key = f'{action.tool_action.tool_id}.{action.tool_action.operation}'
            if schema_key not in session.action_schema:
                elapsed = max(0, int((time.perf_counter_ns() - started) / 1_000_000))
                session = replace(session, wall_clock_ms=session.wall_clock_ms + elapsed)
                self._sessions[session.session_id] = session
                return self._terminal(session, ExecutionState.FAILED, f'action outside declared schema: {schema_key}')
            is_external = action.tool_action.tool_id in self.executor.external_core_ids
            if session.counters.tool_calls >= session.budget.max_tool_calls:
                return self._budget_terminal(session, 'tool-call budget exhausted')
            if is_external and session.counters.external_core_calls >= session.budget.max_external_core_calls:
                return self._budget_terminal(session, 'external-core budget exhausted')

            task = self.tasks.get(session.task_id)
            identity = self.registry.get(session.agent_id)
            if task.aborted_by is not None:
                return self._terminal(session, ExecutionState.ABORTED, task.abort_reason or 'task aborted')
            if identity.status is AgentStatus.PAUSED:
                return self._terminal(session, ExecutionState.PAUSED, 'agent paused by authority')

            core = self.executor.invoke(
                agent_id=session.agent_id,
                task_id=session.task_id,
                workspace=workspace,
                action=action.tool_action,
            )
            counters = ExecutionCounters(
                steps=session.counters.steps,
                tool_calls=session.counters.tool_calls + 1,
                external_core_calls=session.counters.external_core_calls + (1 if is_external else 0),
                compute_units=session.counters.compute_units,
            )
            outputs = tuple(dict.fromkeys(session.output_artifact_ids + core.output_artifact_ids))
            state_after = ExecutionState.RUNNING if core.success else ExecutionState.FAILED
            step_receipt = ExecutionStepReceipt.create(
                session_id=session.session_id,
                step_index=decision.step_index,
                decision_receipt_id=decision.receipt_id,
                core_receipt_id=core.receipt_id,
                before_workspace_digest=core.before_workspace_digest,
                after_workspace_digest=core.after_workspace_digest,
                state_after=state_after,
                output_artifact_ids=core.output_artifact_ids,
            )
            self._steps[step_receipt.receipt_id] = step_receipt
            elapsed = max(0, int((time.perf_counter_ns() - started) / 1_000_000))
            session = replace(
                session,
                counters=counters,
                output_artifact_ids=outputs,
                core_receipt_ids=session.core_receipt_ids + (core.receipt_id,),
                step_receipt_ids=session.step_receipt_ids + (step_receipt.receipt_id,),
                wall_clock_ms=session.wall_clock_ms + elapsed,
                state=state_after,
            )
            self._sessions[session.session_id] = session
            if not core.success:
                return self._terminal(session, ExecutionState.FAILED, core.failure_kind or 'tool execution failed')
            return step_receipt

        elapsed = max(0, int((time.perf_counter_ns() - started) / 1_000_000))
        session = replace(session, wall_clock_ms=session.wall_clock_ms + elapsed)
        self._sessions[session.session_id] = session
        if action.kind is ExecutionActionKind.COMPLETE:
            known = {a.artifact_id for a in self.artifacts.records()}
            missing = [x for x in action.output_artifact_ids if x not in known]
            if missing:
                return self._terminal(session, ExecutionState.FAILED, 'completion references unknown output artifacts')
            if action.output_artifact_ids:
                session = replace(
                    session,
                    output_artifact_ids=tuple(dict.fromkeys(session.output_artifact_ids + action.output_artifact_ids)),
                )
                self._sessions[session.session_id] = session
            return self._terminal(session, ExecutionState.COMPLETED, action.reason, complete_task=True)
        if action.kind is ExecutionActionKind.WAIT:
            return self._terminal(session, ExecutionState.WAITING, action.reason or 'waiting')
        return self._terminal(session, ExecutionState.FAILED, action.reason or 'inference backend reported failure')

    def run(self, session_id: str) -> ExecutionTerminalReceipt:
        while True:
            result = self.step(session_id)
            if isinstance(result, ExecutionTerminalReceipt):
                return result

    def execute(
        self,
        *,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action_schema: Sequence[str],
        budget: ExecutionBudget,
    ) -> ExecutionTerminalReceipt:
        session = self.start(
            agent_id=agent_id,
            task_id=task_id,
            workspace=workspace,
            action_schema=action_schema,
            budget=budget,
        )
        return self.run(session.session_id)

    def to_state(self) -> dict[str, Any]:
        return {
            'encoder_version': self.encoder.version,
            'session_counter': self._session_counter,
            'sessions': [row.to_state() for row in self.sessions()],
            'decisions': [self._decisions[k].to_state() for k in sorted(self._decisions)],
            'steps': [self._steps[k].to_state() for k in sorted(self._steps)],
            'terminals': [self._terminals[k].to_state() for k in sorted(self._terminals)],
            'executor': self.executor.to_state(),
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        tasks: TaskGraph,
        context: Any,
        artifacts: ArtifactStore,
        external_cores: ExternalCoreRegistry,
        coding: Any,
        state: Mapping[str, Any],
    ) -> 'OrganizationExecutionControlPlane':
        encoder = CognitiveStateEncoder(version=str(state.get('encoder_version', 'organization-context-digest-v1')))
        executor = ExternalCoreExecutor.from_state(
            registry=registry,
            external_cores=external_cores,
            artifacts=artifacts,
            coding_patches=getattr(coding, 'patches', None),
            code_claims=getattr(coding, 'claims', None),
            state=state.get('executor', {}),
        )
        return cls(
            registry=registry,
            tasks=tasks,
            context=context,
            artifacts=artifacts,
            external_cores=external_cores,
            coding=coding,
            encoder=encoder,
            executor=executor,
            sessions=tuple(ExecutionSession.from_state(x) for x in state.get('sessions', ())),
            decisions=tuple(AgentDecisionReceipt.from_state(x) for x in state.get('decisions', ())),
            steps=tuple(ExecutionStepReceipt.from_state(x) for x in state.get('steps', ())),
            terminals=tuple(ExecutionTerminalReceipt.from_state(x) for x in state.get('terminals', ())),
            session_counter=int(state.get('session_counter', 0)),
        )


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
