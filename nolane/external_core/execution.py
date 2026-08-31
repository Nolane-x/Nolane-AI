from __future__ import annotations

import time
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.acting_protocol import ActionPhase, EffectClass, ExecutionRisk, VerifierLevel, minimum_risk_for_effect
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
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
COMPONENT_VERSION = "0.0.7"
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
    workspace_provenance_version: int = 1
    initial_workspace_digest: str | None = None
    current_workspace_digest: str | None = None
    execution_proof_version: int = 1
    external_core_registry_digest: str | None = None
    workspace_epoch_id: str | None = None
    decision_receipt_ids: tuple[str, ...] = ()
    step_receipt_ids: tuple[str, ...] = ()
    core_receipt_ids: tuple[str, ...] = ()
    output_artifact_ids: tuple[str, ...] = ()
    terminal_receipt_id: str | None = None
    wall_clock_ms: int = 0

    def __post_init__(self) -> None:
        workspace_version = int(self.workspace_provenance_version)
        if workspace_version not in {1, 2}:
            raise ValueError('unsupported workspace provenance version')
        object.__setattr__(self, 'workspace_provenance_version', workspace_version)
        initial = None if self.initial_workspace_digest is None else str(self.initial_workspace_digest).strip()
        current = None if self.current_workspace_digest is None else str(self.current_workspace_digest).strip()
        if workspace_version == 1:
            if initial or current:
                raise ValueError('legacy execution session cannot carry modern workspace digest')
            object.__setattr__(self, 'initial_workspace_digest', None)
            object.__setattr__(self, 'current_workspace_digest', None)
        else:
            if not initial or not current:
                raise ValueError('modern execution session requires workspace digest')
            object.__setattr__(self, 'initial_workspace_digest', initial)
            object.__setattr__(self, 'current_workspace_digest', current)

        proof_version = int(self.execution_proof_version)
        if proof_version not in {1, 2}:
            raise ValueError('unsupported execution proof version')
        object.__setattr__(self, 'execution_proof_version', proof_version)
        registry_digest = (
            None
            if self.external_core_registry_digest is None
            else str(self.external_core_registry_digest).strip()
        )
        epoch_id = None if self.workspace_epoch_id is None else str(self.workspace_epoch_id).strip()
        if proof_version == 1:
            if registry_digest or epoch_id:
                raise ValueError('legacy execution session cannot carry modern execution proof')
            object.__setattr__(self, 'external_core_registry_digest', None)
            object.__setattr__(self, 'workspace_epoch_id', None)
            return
        if workspace_version < 2:
            raise ValueError('execution proof v2 requires modern workspace provenance')
        if not registry_digest or not epoch_id:
            raise ValueError('execution proof v2 requires registry digest and workspace epoch')
        object.__setattr__(self, 'external_core_registry_digest', registry_digest)
        object.__setattr__(self, 'workspace_epoch_id', epoch_id)

    def to_state(self) -> dict[str, Any]:
        state = {
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
        if self.workspace_provenance_version >= 2:
            state['workspace_provenance_version'] = self.workspace_provenance_version
            state['initial_workspace_digest'] = self.initial_workspace_digest
            state['current_workspace_digest'] = self.current_workspace_digest
        if self.execution_proof_version >= 2:
            state['execution_proof_version'] = self.execution_proof_version
            state['external_core_registry_digest'] = self.external_core_registry_digest
            state['workspace_epoch_id'] = self.workspace_epoch_id
        return state

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
            workspace_provenance_version=int(state.get('workspace_provenance_version', 1)),
            initial_workspace_digest=(
                None if state.get('initial_workspace_digest') is None
                else str(state['initial_workspace_digest'])
            ),
            current_workspace_digest=(
                None if state.get('current_workspace_digest') is None
                else str(state['current_workspace_digest'])
            ),
            execution_proof_version=int(state.get('execution_proof_version', 1)),
            external_core_registry_digest=(
                None if state.get('external_core_registry_digest') is None
                else str(state['external_core_registry_digest'])
            ),
            workspace_epoch_id=(
                None if state.get('workspace_epoch_id') is None
                else str(state['workspace_epoch_id'])
            ),
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
    core_contract_digest: str = ''
    workspace_epoch_id: str = ''

    def __post_init__(self) -> None:
        core_digest = str(self.core_contract_digest).strip()
        epoch_id = str(self.workspace_epoch_id).strip()
        if core_digest and not epoch_id:
            raise ValueError('execution step receipt core proof requires workspace epoch')
        object.__setattr__(self, 'core_contract_digest', core_digest)
        object.__setattr__(self, 'workspace_epoch_id', epoch_id)

    @property
    def execution_proof_version(self) -> int:
        return 2 if self.core_contract_digest or self.workspace_epoch_id else 1

    def payload(self) -> dict[str, Any]:
        payload = {
            'session_id': self.session_id,
            'step_index': self.step_index,
            'decision_receipt_id': self.decision_receipt_id,
            'core_receipt_id': self.core_receipt_id,
            'before_workspace_digest': self.before_workspace_digest,
            'after_workspace_digest': self.after_workspace_digest,
            'state_after': self.state_after.value,
            'output_artifact_ids': list(self.output_artifact_ids),
        }
        if self.execution_proof_version >= 2:
            payload['core_contract_digest'] = self.core_contract_digest
            payload['workspace_epoch_id'] = self.workspace_epoch_id
        return payload

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
        core_contract_digest: str = '',
        workspace_epoch_id: str = '',
    ) -> 'ExecutionStepReceipt':
        core_digest = str(core_contract_digest).strip()
        epoch_id = str(workspace_epoch_id).strip()
        if core_digest and not epoch_id:
            raise ValueError('execution step receipt core proof requires workspace epoch')
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
        if core_digest or epoch_id:
            payload['core_contract_digest'] = core_digest
            payload['workspace_epoch_id'] = epoch_id
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
            core_contract_digest=core_digest,
            workspace_epoch_id=epoch_id,
        )

    def to_state(self) -> dict[str, Any]:
        return {'receipt_id': self.receipt_id, **self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExecutionStepReceipt':
        has_core_proof = 'core_contract_digest' in state
        has_epoch_proof = 'workspace_epoch_id' in state
        if has_core_proof != has_epoch_proof:
            raise ValueError('execution step receipt has incomplete execution proof')
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
            core_contract_digest=str(state.get('core_contract_digest', '')),
            workspace_epoch_id=str(state.get('workspace_epoch_id', '')),
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
        acting_executor: TransactionalExternalCoreExecutor | None = None,
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
        self.acting_executor = acting_executor or TransactionalExternalCoreExecutor(executor=self.executor)
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

            first_workspace_digest: str | None = None
            previous_workspace_digest: str | None = None
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
                if session.execution_proof_version >= 2:
                    if step.execution_proof_version < 2:
                        raise ValueError('modern execution session references legacy step proof')
                    if step.workspace_epoch_id != session.workspace_epoch_id:
                        raise ValueError('execution step receipt workspace epoch binding mismatch')
                    if step.core_receipt_id is not None:
                        try:
                            core = self.executor.get_receipt(step.core_receipt_id)
                        except Exception as exc:
                            raise ValueError('execution step receipt references unavailable core receipt') from exc
                        if str(getattr(core, 'workspace_epoch_id', '')) != str(session.workspace_epoch_id):
                            raise ValueError('execution core receipt workspace epoch binding mismatch')
                        if str(getattr(core, 'core_contract_digest', '')) != step.core_contract_digest:
                            raise ValueError('execution core receipt contract binding mismatch')
                if first_workspace_digest is None:
                    first_workspace_digest = step.before_workspace_digest
                if (
                    previous_workspace_digest is not None
                    and step.before_workspace_digest != previous_workspace_digest
                ):
                    raise ValueError('workspace digest continuity mismatch')
                previous_workspace_digest = step.after_workspace_digest

            if session.workspace_provenance_version >= 2:
                if session.step_receipt_ids:
                    if first_workspace_digest != session.initial_workspace_digest:
                        raise ValueError('workspace digest continuity mismatch at session origin')
                    if previous_workspace_digest != session.current_workspace_digest:
                        raise ValueError('workspace digest continuity mismatch at session frontier')
                elif session.current_workspace_digest != session.initial_workspace_digest:
                    raise ValueError('workspace digest continuity mismatch for empty session')

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

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def _persisted_workspace_fence(self, session: ExecutionSession) -> str | None:
        if session.workspace_provenance_version >= 2:
            return session.current_workspace_digest
        if session.step_receipt_ids:
            return self._steps[session.step_receipt_ids[-1]].after_workspace_digest
        return None

    def _validate_registry_proof(self, session: ExecutionSession) -> None:
        if session.execution_proof_version < 2:
            raise RuntimeError(
                'legacy execution session lacks execution proof; '
                'forward execution requires proof-v2 authority'
            )
        if self.external_cores.contract_digest != session.external_core_registry_digest:
            raise RuntimeError('external core registry differs from persisted execution session')

    def _validate_session_execution_proof(
        self,
        session: ExecutionSession,
        workspace: RepositoryWorkspace,
    ) -> None:
        self._validate_registry_proof(session)
        if workspace.active_execution_epoch_id != session.workspace_epoch_id:
            raise RuntimeError('workspace execution epoch differs from persisted execution session')
        if workspace.active_execution_epoch_owner != session.session_id:
            raise PermissionError('workspace execution epoch is not owned by persisted execution session')

    def _expected_core_contract_digest(self, tool_id: str) -> str:
        if str(tool_id) not in frozenset(getattr(self.executor, 'external_core_ids', ())):
            return ''
        return self.external_cores.get(str(tool_id)).contract_digest

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
        expected_digest = self._persisted_workspace_fence(session)
        if expected_digest is not None and workspace.digest != expected_digest:
            raise ValueError('reattached workspace digest does not match persisted session frontier')
        if session.execution_proof_version >= 2:
            self._validate_registry_proof(session)
            assert session.workspace_epoch_id is not None
            workspace.claim_execution_epoch(
                session.session_id,
                expected_epoch_id=session.workspace_epoch_id,
            )
            self._validate_session_execution_proof(session, workspace)
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
        workspace_digest = str(workspace.digest).strip()
        if not workspace_digest:
            raise ValueError('execution start requires workspace digest')
        next_counter = self._session_counter + 1
        session_id = f'execution-{next_counter:08d}'
        workspace_epoch_id = workspace.claim_execution_epoch(session_id)
        try:
            row = ExecutionSession(
                session_id=session_id,
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
                workspace_provenance_version=2,
                initial_workspace_digest=workspace_digest,
                current_workspace_digest=workspace_digest,
                execution_proof_version=2,
                external_core_registry_digest=self.external_cores.contract_digest,
                workspace_epoch_id=workspace_epoch_id,
            )
            self._sessions[row.session_id] = row
            self._workspaces[row.session_id] = workspace
            self._session_counter = next_counter
            return row
        except Exception:
            if (
                workspace.active_execution_epoch_id == workspace_epoch_id
                and workspace.active_execution_epoch_owner == session_id
            ):
                workspace.release_execution_epoch(session_id, workspace_epoch_id)
            raise

    def _terminal_epoch_preflight(self, session: ExecutionSession) -> RepositoryWorkspace | None:
        if session.execution_proof_version < 2:
            return None
        workspace = self._workspaces.get(session.session_id)
        if workspace is None:
            return None
        if workspace.active_execution_epoch_id is None:
            return workspace
        if workspace.active_execution_epoch_id != session.workspace_epoch_id:
            raise RuntimeError('terminal workspace epoch differs from persisted execution session')
        if workspace.active_execution_epoch_owner != session.session_id:
            raise PermissionError('terminal workspace epoch is owned by another execution session')
        return workspace

    def _terminal(self, session: ExecutionSession, state: ExecutionState, reason: str, *, complete_task: bool = False) -> ExecutionTerminalReceipt:
        if not str(reason).strip():
            raise ValueError('execution termination reason must be explicit')
        terminal_workspace = self._terminal_epoch_preflight(session)
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
        if (
            terminal_workspace is not None
            and terminal_workspace.active_execution_epoch_id is not None
            and session.workspace_epoch_id is not None
        ):
            terminal_workspace.release_execution_epoch(
                session.session_id,
                session.workspace_epoch_id,
            )
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
        if session.workspace_provenance_version < 2:
            raise RuntimeError(
                'legacy execution session lacks workspace provenance; '
                'forward execution requires a modern workspace fence'
            )
        if workspace.digest != session.current_workspace_digest:
            raise RuntimeError('attached workspace digest differs from persisted execution session')
        self._validate_session_execution_proof(session, workspace)
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
            core_contract_digest = self._expected_core_contract_digest(action.tool_action.tool_id)
            effect_class = self.acting_executor.minimum_effect_class(action.tool_action)
            risk_class = minimum_risk_for_effect(effect_class)
            verifier_level = self.acting_executor.protocol.minimum_verifier_level(risk_class)
            is_external_effect = effect_class in {EffectClass.EXTERNAL_MUTATION, EffectClass.IRREVERSIBLE}
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

            if is_external_effect:
                recovery_plan = 'reconcile externally observed effect from core receipt evidence'
            elif effect_class is EffectClass.LOCAL_MUTATION:
                recovery_plan = 'restore isolated workspace checkpoint'
            else:
                recovery_plan = ''

            if workspace.digest != session.current_workspace_digest:
                raise RuntimeError('workspace digest changed before transactional dispatch')
            assert session.workspace_epoch_id is not None
            acting = self.acting_executor.invoke(
                agent_id=session.agent_id,
                task_id=session.task_id,
                workspace=workspace,
                action=action.tool_action,
                risk_class=risk_class,
                effect_class=effect_class,
                required_capabilities=(action.tool_action.tool_id,),
                capability_grants=tuple(dict.fromkeys(identity.tool_permissions + identity.external_core_bindings)),
                authorization_ref=f'decision:{decision.receipt_id}',
                preconditions=('task-lease-valid', 'tool-authorization-present'),
                precondition_evidence_refs=(
                    'task-state:' + canonical_digest(task.to_state()),
                    'identity-state:' + canonical_digest(identity.to_state()),
                ),
                postconditions=('core-outcome-evidenced',),
                postcondition_evidence_refs=(),
                verifier_level=verifier_level,
                idempotency_key=f'{session.session_id}:{decision.receipt_id}',
                recovery_plan=recovery_plan,
                core_contract_digest=core_contract_digest,
                workspace_epoch_id=session.workspace_epoch_id,
                now_ms=int(time.time() * 1000),
                lease_ttl_ms=60_000,
            )
            core = self.executor.get_receipt(acting.core_receipt_id)
            if core.before_workspace_digest != session.current_workspace_digest:
                raise ValueError('core receipt workspace fence mismatch')
            if str(getattr(core, 'workspace_epoch_id', '')) != session.workspace_epoch_id:
                raise ValueError('core receipt workspace epoch mismatch')
            if str(getattr(core, 'core_contract_digest', '')) != core_contract_digest:
                raise ValueError('core receipt contract digest mismatch')
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
                core_contract_digest=core_contract_digest,
                workspace_epoch_id=session.workspace_epoch_id,
            )
            self._steps[step_receipt.receipt_id] = step_receipt
            elapsed = max(0, int((time.perf_counter_ns() - started) / 1_000_000))
            session = replace(
                session,
                counters=counters,
                output_artifact_ids=outputs,
                core_receipt_ids=session.core_receipt_ids + (core.receipt_id,),
                step_receipt_ids=session.step_receipt_ids + (step_receipt.receipt_id,),
                current_workspace_digest=str(core.after_workspace_digest),
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

    @staticmethod
    def _acting_execution_binding(idempotency_key: str) -> tuple[str, str] | None:
        key = str(idempotency_key).strip()
        session_id, sep, decision_id = key.rpartition(':')
        if not sep or not session_id.startswith('execution-') or not decision_id:
            return None
        return session_id, decision_id

    def _acting_row_matches_decision(
        self,
        row: Any,
        session: ExecutionSession,
        decision: AgentDecisionReceipt,
    ) -> bool:
        action = decision.action
        if action.kind is not ExecutionActionKind.TOOL or action.tool_action is None:
            return False
        tool_action = action.tool_action
        if (
            row.contract.core_id != tool_action.tool_id
            or row.contract.operation != tool_action.operation
            or row.contract.input_digest != canonical_digest(tool_action.to_state())
        ):
            return False
        if session.execution_proof_version < 2:
            return True
        expected_core_digest = self._expected_core_contract_digest(tool_action.tool_id)
        return (
            row.contract.workspace_epoch_id == session.workspace_epoch_id
            and row.contract.core_contract_digest == expected_core_digest
        )

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
            if session.execution_proof_version >= 2:
                self._validate_registry_proof(session)
            if decision_id not in session.decision_receipt_ids:
                raise ValueError('interrupted action decision is not owned by execution session')
            decision = self._decisions[decision_id]
            if not self._acting_row_matches_decision(row, session, decision):
                raise ValueError('acting action contract does not match bound decision')
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
                expected_workspace_digest = self._persisted_workspace_fence(session)
                if (
                    expected_workspace_digest is not None
                    and str(core.before_workspace_digest) != expected_workspace_digest
                ):
                    raise ValueError('committed acting action workspace fence mismatch')
                if session.execution_proof_version >= 2:
                    expected_core_digest = self._expected_core_contract_digest(row.contract.core_id)
                    if str(getattr(core, 'workspace_epoch_id', '')) != str(session.workspace_epoch_id):
                        raise ValueError('committed acting action workspace epoch mismatch')
                    if str(getattr(core, 'core_contract_digest', '')) != expected_core_digest:
                        raise ValueError('committed acting action core contract mismatch')
                    if row.contract.workspace_epoch_id != session.workspace_epoch_id:
                        raise ValueError('committed acting contract workspace epoch mismatch')
                    if row.contract.core_contract_digest != expected_core_digest:
                        raise ValueError('committed acting contract core contract mismatch')
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
                    core_contract_digest=(
                        str(getattr(core, 'core_contract_digest', ''))
                        if session.execution_proof_version >= 2
                        else ''
                    ),
                    workspace_epoch_id=(
                        str(session.workspace_epoch_id)
                        if session.execution_proof_version >= 2 and session.workspace_epoch_id is not None
                        else ''
                    ),
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
                    current_workspace_digest=(
                        str(core.after_workspace_digest)
                        if session.workspace_provenance_version >= 2
                        else session.current_workspace_digest
                    ),
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
            'acting_executor': self.acting_executor.to_state(),
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
        acting_executor = TransactionalExternalCoreExecutor.from_state(
            executor=executor,
            state=state.get('acting_executor', {}),
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
            acting_executor=acting_executor,
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
