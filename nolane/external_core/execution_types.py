from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json


class ExecutionActionKind(str, Enum):
    TOOL = 'tool'
    COMPLETE = 'complete'
    WAIT = 'wait'
    FAIL = 'fail'


@dataclass(frozen=True, slots=True)
class ToolAction:
    tool_id: str
    operation: str
    arguments_json: str
    mutation_paths: tuple[str, ...] = ()

    @staticmethod
    def _required_mutation_paths(tool_id: str, operation: str, arguments: Mapping[str, Any]) -> tuple[str, ...]:
        if str(tool_id) == 'filesystem' and str(operation) in {'write_text', 'append_text'}:
            path = str(arguments.get('path', '')).strip()
            return () if not path else (path,)
        return ()

    def __post_init__(self) -> None:
        if not self.tool_id.strip() or not self.operation.strip():
            raise ValueError('tool action requires tool id and operation')
        value = json.loads(self.arguments_json)
        if not isinstance(value, dict):
            raise ValueError('tool action arguments must decode to an object')
        if canonical_json(value) != self.arguments_json:
            raise ValueError('tool action arguments must be canonical json')
        for path in self.mutation_paths:
            if not str(path).strip():
                raise ValueError('mutation paths must be explicit')
        required = self._required_mutation_paths(self.tool_id, self.operation, value)
        if required and tuple(self.mutation_paths) != required:
            raise ValueError('filesystem mutation scope must be derived from operation arguments')

    @property
    def arguments(self) -> dict[str, Any]:
        value = json.loads(self.arguments_json)
        if not isinstance(value, dict):
            raise ValueError('tool action arguments must decode to an object')
        return value

    @classmethod
    def from_arguments(
        cls,
        tool_id: str,
        operation: str,
        arguments: Mapping[str, Any],
        *,
        mutation_paths: tuple[str, ...] = (),
    ) -> 'ToolAction':
        tool = str(tool_id)
        op = str(operation)
        args = dict(arguments)
        required = cls._required_mutation_paths(tool, op, args)
        declared = tuple(str(x) for x in mutation_paths)
        if required:
            if declared and declared != required:
                raise ValueError('declared mutation scope conflicts with filesystem operation path')
            declared = required
        return cls(
            tool_id=tool,
            operation=op,
            arguments_json=canonical_json(args),
            mutation_paths=declared,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            'tool_id': self.tool_id,
            'operation': self.operation,
            'arguments_json': self.arguments_json,
            'mutation_paths': list(self.mutation_paths),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ToolAction':
        arguments_json = str(state['arguments_json'])
        value = json.loads(arguments_json)
        if not isinstance(value, dict):
            raise ValueError('tool action arguments must decode to an object')
        tool = str(state['tool_id'])
        operation = str(state['operation'])
        required = cls._required_mutation_paths(tool, operation, value)
        stored = tuple(str(x) for x in state.get('mutation_paths', ()))
        if required and stored != required:
            raise ValueError('snapshot omits or corrupts authoritative filesystem mutation scope')
        return cls(
            tool_id=tool,
            operation=operation,
            arguments_json=arguments_json,
            mutation_paths=stored,
        )


@dataclass(frozen=True, slots=True)
class ExecutionAction:
    kind: ExecutionActionKind
    tool_action: ToolAction | None = None
    reason: str = ''
    output_artifact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind is ExecutionActionKind.TOOL and self.tool_action is None:
            raise ValueError('tool execution action requires tool action')
        if self.kind is not ExecutionActionKind.TOOL and self.tool_action is not None:
            raise ValueError('non-tool execution action cannot carry tool action')
        if self.kind in {ExecutionActionKind.COMPLETE, ExecutionActionKind.FAIL} and not self.reason.strip():
            raise ValueError(f'{self.kind.value} action requires reason')

    @classmethod
    def tool(cls, action: ToolAction) -> 'ExecutionAction':
        return cls(kind=ExecutionActionKind.TOOL, tool_action=action)

    @classmethod
    def complete(cls, *, reason: str, output_artifact_ids: tuple[str, ...] = ()) -> 'ExecutionAction':
        return cls(
            kind=ExecutionActionKind.COMPLETE,
            reason=str(reason),
            output_artifact_ids=tuple(str(x) for x in output_artifact_ids),
        )

    @classmethod
    def wait(cls, *, reason: str = 'waiting') -> 'ExecutionAction':
        return cls(kind=ExecutionActionKind.WAIT, reason=str(reason))

    @classmethod
    def fail(cls, *, reason: str) -> 'ExecutionAction':
        return cls(kind=ExecutionActionKind.FAIL, reason=str(reason))

    def to_state(self) -> dict[str, Any]:
        return {
            'kind': self.kind.value,
            'tool_action': None if self.tool_action is None else self.tool_action.to_state(),
            'reason': self.reason,
            'output_artifact_ids': list(self.output_artifact_ids),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExecutionAction':
        tool = state.get('tool_action')
        return cls(
            kind=ExecutionActionKind(str(state['kind'])),
            tool_action=None if tool is None else ToolAction.from_state(tool),
            reason=str(state.get('reason', '')),
            output_artifact_ids=tuple(str(x) for x in state.get('output_artifact_ids', ())),
        )


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    max_steps: int
    max_tool_calls: int
    max_external_core_calls: int
    max_compute_units: int

    def __post_init__(self) -> None:
        for value in (self.max_steps, self.max_tool_calls, self.max_external_core_calls, self.max_compute_units):
            if isinstance(value, bool) or int(value) <= 0:
                raise ValueError('execution budgets must be positive integers')

    def to_state(self) -> dict[str, int]:
        return {
            'max_steps': self.max_steps,
            'max_tool_calls': self.max_tool_calls,
            'max_external_core_calls': self.max_external_core_calls,
            'max_compute_units': self.max_compute_units,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExecutionBudget':
        return cls(
            max_steps=int(state['max_steps']),
            max_tool_calls=int(state['max_tool_calls']),
            max_external_core_calls=int(state['max_external_core_calls']),
            max_compute_units=int(state['max_compute_units']),
        )


@dataclass(frozen=True, slots=True)
class ExecutionCounters:
    steps: int = 0
    tool_calls: int = 0
    external_core_calls: int = 0
    compute_units: int = 0

    def __post_init__(self) -> None:
        for value in (self.steps, self.tool_calls, self.external_core_calls, self.compute_units):
            if isinstance(value, bool) or int(value) < 0:
                raise ValueError('execution counters must be non-negative integers')

    def to_state(self) -> dict[str, int]:
        return {
            'steps': self.steps,
            'tool_calls': self.tool_calls,
            'external_core_calls': self.external_core_calls,
            'compute_units': self.compute_units,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExecutionCounters':
        return cls(
            steps=int(state.get('steps', 0)),
            tool_calls=int(state.get('tool_calls', 0)),
            external_core_calls=int(state.get('external_core_calls', 0)),
            compute_units=int(state.get('compute_units', 0)),
        )


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    agent_id: str
    neural_version: str
    task_id: str
    context_digest: str
    encoder_version: str
    checkpoint_digest: str
    action_schema: tuple[str, ...]
    action_schema_digest: str
    counters: ExecutionCounters
    step_index: int

    def __post_init__(self) -> None:
        for value, label in (
            (self.agent_id, 'agent id'),
            (self.neural_version, 'neural version'),
            (self.task_id, 'task id'),
            (self.context_digest, 'context digest'),
            (self.encoder_version, 'encoder version'),
            (self.checkpoint_digest, 'checkpoint digest'),
        ):
            if not str(value).strip():
                raise ValueError(f'{label} must be explicit')
        if self.step_index < 0:
            raise ValueError('step index must be non-negative')
        if not self.action_schema:
            raise ValueError('inference request requires action schema')
        if self.action_schema_digest != canonical_digest(list(self.action_schema)):
            raise ValueError('action schema digest mismatch')

    def payload(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'neural_version': self.neural_version,
            'task_id': self.task_id,
            'context_digest': self.context_digest,
            'encoder_version': self.encoder_version,
            'checkpoint_digest': self.checkpoint_digest,
            'action_schema': list(self.action_schema),
            'action_schema_digest': self.action_schema_digest,
            'counters': self.counters.to_state(),
            'step_index': self.step_index,
        }

    @property
    def digest(self) -> str:
        return canonical_digest(self.payload())

    def to_state(self) -> dict[str, Any]:
        return self.payload()

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'InferenceRequest':
        return cls(
            agent_id=str(state['agent_id']),
            neural_version=str(state['neural_version']),
            task_id=str(state['task_id']),
            context_digest=str(state['context_digest']),
            encoder_version=str(state['encoder_version']),
            checkpoint_digest=str(state['checkpoint_digest']),
            action_schema=tuple(str(x) for x in state.get('action_schema', ())),
            action_schema_digest=str(state['action_schema_digest']),
            counters=ExecutionCounters.from_state(state.get('counters', {})),
            step_index=int(state['step_index']),
        )


@dataclass(frozen=True, slots=True)
class AgentDecisionReceipt:
    receipt_id: str
    backend_id: str
    request_digest: str
    agent_id: str
    neural_version: str
    checkpoint_digest: str
    encoder_version: str
    context_digest: str
    action_schema_digest: str
    step_index: int
    action: ExecutionAction
    compute_units: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'backend_id': self.backend_id,
            'request_digest': self.request_digest,
            'agent_id': self.agent_id,
            'neural_version': self.neural_version,
            'checkpoint_digest': self.checkpoint_digest,
            'encoder_version': self.encoder_version,
            'context_digest': self.context_digest,
            'action_schema_digest': self.action_schema_digest,
            'step_index': self.step_index,
            'action': self.action.to_state(),
            'compute_units': self.compute_units,
        }

    @classmethod
    def create(
        cls,
        *,
        backend_id: str,
        request: InferenceRequest,
        action: ExecutionAction,
        compute_units: int = 1,
    ) -> 'AgentDecisionReceipt':
        if not str(backend_id).strip():
            raise ValueError('backend id must be explicit')
        if int(compute_units) <= 0:
            raise ValueError('decision compute units must be positive')
        payload = {
            'backend_id': str(backend_id),
            'request_digest': request.digest,
            'agent_id': request.agent_id,
            'neural_version': request.neural_version,
            'checkpoint_digest': request.checkpoint_digest,
            'encoder_version': request.encoder_version,
            'context_digest': request.context_digest,
            'action_schema_digest': request.action_schema_digest,
            'step_index': request.step_index,
            'action': action.to_state(),
            'compute_units': int(compute_units),
        }
        digest = canonical_digest(payload)
        return cls(
            receipt_id='decision-' + digest[:24],
            backend_id=str(backend_id),
            request_digest=request.digest,
            agent_id=request.agent_id,
            neural_version=request.neural_version,
            checkpoint_digest=request.checkpoint_digest,
            encoder_version=request.encoder_version,
            context_digest=request.context_digest,
            action_schema_digest=request.action_schema_digest,
            step_index=request.step_index,
            action=action,
            compute_units=int(compute_units),
            digest=digest,
        )

    def to_state(self) -> dict[str, Any]:
        return {'receipt_id': self.receipt_id, **self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AgentDecisionReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']),
            backend_id=str(state['backend_id']),
            request_digest=str(state['request_digest']),
            agent_id=str(state['agent_id']),
            neural_version=str(state['neural_version']),
            checkpoint_digest=str(state['checkpoint_digest']),
            encoder_version=str(state['encoder_version']),
            context_digest=str(state['context_digest']),
            action_schema_digest=str(state['action_schema_digest']),
            step_index=int(state['step_index']),
            action=ExecutionAction.from_state(state['action']),
            compute_units=int(state['compute_units']),
            digest=str(state['digest']),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != 'decision-' + expected[:24]:
            raise ValueError('decision receipt digest/id mismatch')
        if row.compute_units <= 0:
            raise ValueError('decision compute units must be positive')
        return row


__all__ = (
    'ExecutionActionKind',
    'ToolAction',
    'ExecutionAction',
    'ExecutionBudget',
    'ExecutionCounters',
    'InferenceRequest',
    'AgentDecisionReceipt',
)
