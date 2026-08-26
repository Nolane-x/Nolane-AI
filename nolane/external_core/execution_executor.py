from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.artifacts import ArtifactStore
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.coding_patches import CodingPatchLedger
from nolane.external_core.execution_types import ToolAction
from nolane.external_core.execution_workspace import RepositoryWorkspace
from nolane.external_core.invokable import ExternalCoreRegistry
from nolane.organization.identity import AgentRegistry


COMPONENT_ID = "external.execution.executor"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.execution_tools"


CoreHandler = Callable[[RepositoryWorkspace, Mapping[str, Any]], Mapping[str, Any]]


class ExecutionToolFailure(RuntimeError):
    def __init__(self, kind: str, message: str, output_artifact_ids: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.kind = str(kind)
        self.output_artifact_ids = tuple(str(x) for x in output_artifact_ids)


@dataclass(frozen=True, slots=True)
class CoreInvocationReceipt:
    receipt_id: str
    agent_id: str
    task_id: str
    tool_id: str
    operation: str
    authorized: bool
    success: bool
    external_core: bool
    failure_kind: str | None
    before_workspace_digest: str
    after_workspace_digest: str
    input_digest: str
    output_artifact_ids: tuple[str, ...]
    evidence_artifact_id: str
    mirrored_tool_receipt_id: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'task_id': self.task_id,
            'tool_id': self.tool_id,
            'operation': self.operation,
            'authorized': self.authorized,
            'success': self.success,
            'external_core': self.external_core,
            'failure_kind': self.failure_kind,
            'before_workspace_digest': self.before_workspace_digest,
            'after_workspace_digest': self.after_workspace_digest,
            'input_digest': self.input_digest,
            'output_artifact_ids': list(self.output_artifact_ids),
            'evidence_artifact_id': self.evidence_artifact_id,
            'mirrored_tool_receipt_id': self.mirrored_tool_receipt_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {'receipt_id': self.receipt_id, **self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CoreInvocationReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']),
            agent_id=str(state['agent_id']),
            task_id=str(state['task_id']),
            tool_id=str(state['tool_id']),
            operation=str(state['operation']),
            authorized=bool(state['authorized']),
            success=bool(state['success']),
            external_core=bool(state['external_core']),
            failure_kind=None if state.get('failure_kind') is None else str(state['failure_kind']),
            before_workspace_digest=str(state['before_workspace_digest']),
            after_workspace_digest=str(state['after_workspace_digest']),
            input_digest=str(state['input_digest']),
            output_artifact_ids=tuple(str(x) for x in state.get('output_artifact_ids', ())),
            evidence_artifact_id=str(state['evidence_artifact_id']),
            mirrored_tool_receipt_id=None if state.get('mirrored_tool_receipt_id') is None else str(state['mirrored_tool_receipt_id']),
            digest=str(state['digest']),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != 'core-' + expected[:24]:
            raise ValueError('core invocation receipt digest/id mismatch')
        return row


class ExternalCoreExecutor:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        external_cores: ExternalCoreRegistry,
        artifacts: ArtifactStore,
        coding_patches: CodingPatchLedger | None = None,
        code_claims: CodeClaimLedger | None = None,
        receipts: tuple[CoreInvocationReceipt, ...] = (),
    ) -> None:
        self.registry = registry
        self.external_cores = external_cores
        self.artifacts = artifacts
        self.coding_patches = coding_patches
        self.code_claims = code_claims
        self._handlers: dict[str, CoreHandler] = {}
        self._receipts: dict[str, CoreInvocationReceipt] = {}
        for row in receipts:
            existing = self._receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError('duplicate execution core receipt')
            self._receipts[row.receipt_id] = row

    @property
    def external_core_ids(self) -> frozenset[str]:
        return frozenset(row.core_id for row in self.external_cores.specs())

    def register_handler(self, tool_id: str, handler: CoreHandler) -> None:
        key = str(tool_id).strip()
        if not key:
            raise ValueError('handler tool id must be explicit')
        if key in self._handlers and self._handlers[key] is not handler:
            raise ValueError(f'execution handler already registered: {key}')
        self._handlers[key] = handler

    def receipts(self) -> tuple[CoreInvocationReceipt, ...]:
        return tuple(self._receipts[k] for k in sorted(self._receipts))

    def get_receipt(self, receipt_id: str) -> CoreInvocationReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f'unknown execution core receipt: {receipt_id}') from exc

    def _is_authorized(self, agent_id: str, tool_id: str) -> bool:
        identity = self.registry.get(agent_id)
        return tool_id in identity.tool_permissions or tool_id in identity.external_core_bindings

    def _persist(
        self,
        *,
        agent_id: str,
        task_id: str,
        action: ToolAction,
        authorized: bool,
        success: bool,
        external_core: bool,
        failure_kind: str | None,
        before: str,
        after: str,
        output_artifact_ids: tuple[str, ...],
        evidence_kind: str,
        evidence_content: Mapping[str, Any],
    ) -> CoreInvocationReceipt:
        evidence = self.artifacts.put(
            kind=evidence_kind,
            producer_agent_id=agent_id,
            content=canonical_json(dict(evidence_content)),
            evidence_refs=output_artifact_ids,
            metadata={
                'task_id': task_id,
                'tool_id': action.tool_id,
                'operation': action.operation,
                'authorized': authorized,
                'success': success,
            },
        )
        mirrored: str | None = None
        if self.coding_patches is not None:
            tool_receipt = self.coding_patches.record_tool_invocation(
                agent_id=agent_id,
                task_id=task_id,
                tool_id=action.tool_id,
                input_artifact_refs=(),
                output_artifact_refs=output_artifact_ids,
                success=success,
                evidence_refs=(evidence.artifact_id,),
            )
            mirrored = tool_receipt.receipt_id
        payload = {
            'agent_id': str(agent_id),
            'task_id': str(task_id),
            'tool_id': action.tool_id,
            'operation': action.operation,
            'authorized': bool(authorized),
            'success': bool(success),
            'external_core': bool(external_core),
            'failure_kind': failure_kind,
            'before_workspace_digest': before,
            'after_workspace_digest': after,
            'input_digest': canonical_digest(action.to_state()),
            'output_artifact_ids': list(output_artifact_ids),
            'evidence_artifact_id': evidence.artifact_id,
            'mirrored_tool_receipt_id': mirrored,
        }
        digest = canonical_digest(payload)
        row = CoreInvocationReceipt(
            receipt_id='core-' + digest[:24],
            agent_id=str(agent_id),
            task_id=str(task_id),
            tool_id=action.tool_id,
            operation=action.operation,
            authorized=bool(authorized),
            success=bool(success),
            external_core=bool(external_core),
            failure_kind=failure_kind,
            before_workspace_digest=before,
            after_workspace_digest=after,
            input_digest=payload['input_digest'],
            output_artifact_ids=tuple(output_artifact_ids),
            evidence_artifact_id=evidence.artifact_id,
            mirrored_tool_receipt_id=mirrored,
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError('execution core receipt id collision')
        self._receipts[row.receipt_id] = row
        return row

    def _failure(
        self,
        *,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action: ToolAction,
        authorized: bool,
        failure_kind: str,
        message: str,
        before: str | None = None,
        output_artifact_ids: tuple[str, ...] = (),
    ) -> CoreInvocationReceipt:
        initial = workspace.digest if before is None else before
        return self._persist(
            agent_id=agent_id,
            task_id=task_id,
            action=action,
            authorized=authorized,
            success=False,
            external_core=action.tool_id in self.external_core_ids,
            failure_kind=str(failure_kind),
            before=initial,
            after=workspace.digest,
            output_artifact_ids=output_artifact_ids,
            evidence_kind='execution-core-failure',
            evidence_content={'failure_kind': failure_kind, 'message': message, 'output_artifact_ids': list(output_artifact_ids)},
        )

    def invoke(
        self,
        *,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action: ToolAction,
        timeout_seconds: float = 30.0,
        max_output_chars: int = 200_000,
    ) -> CoreInvocationReceipt:
        identity = self.registry.get(agent_id)
        before = workspace.digest
        tool_authorized = self._is_authorized(agent_id, action.tool_id)
        if not tool_authorized:
            return self._failure(
                agent_id=agent_id, task_id=task_id, workspace=workspace, action=action,
                authorized=False, failure_kind='permission_denied',
                message=f'{agent_id} is not authorized for {action.tool_id}', before=before,
            )
        if identity.current_task != str(task_id):
            return self._failure(
                agent_id=agent_id, task_id=task_id, workspace=workspace, action=action,
                authorized=True, failure_kind='task_lease_required',
                message='tool execution requires the agent current task lease', before=before,
            )

        if action.mutation_paths and self.code_claims is not None:
            if not self.code_claims.covers(
                agent_id=agent_id,
                task_id=task_id,
                file_paths=tuple(action.mutation_paths),
                symbol_ids=(),
            ):
                return self._failure(
                    agent_id=agent_id, task_id=task_id, workspace=workspace, action=action,
                    authorized=True, failure_kind='code_claim_required',
                    message='source mutation requires active code-claim coverage', before=before,
                )

        try:
            outputs, evidence = self._dispatch(
                agent_id=agent_id,
                task_id=task_id,
                workspace=workspace,
                action=action,
                timeout_seconds=timeout_seconds,
                max_output_chars=max_output_chars,
            )
        except ExecutionToolFailure as exc:
            return self._failure(
                agent_id=agent_id, task_id=task_id, workspace=workspace, action=action,
                authorized=True, failure_kind=exc.kind, message=str(exc), before=before,
                output_artifact_ids=exc.output_artifact_ids,
            )
        except Exception as exc:
            return self._failure(
                agent_id=agent_id, task_id=task_id, workspace=workspace, action=action,
                authorized=True, failure_kind='execution_failure', message=f'{type(exc).__name__}: {exc}', before=before,
            )

        return self._persist(
            agent_id=agent_id,
            task_id=task_id,
            action=action,
            authorized=True,
            success=True,
            external_core=action.tool_id in self.external_core_ids,
            failure_kind=None,
            before=before,
            after=workspace.digest,
            output_artifact_ids=outputs,
            evidence_kind='execution-core-success',
            evidence_content=evidence,
        )

    def _dispatch(
        self,
        *,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action: ToolAction,
        timeout_seconds: float,
        max_output_chars: int,
    ) -> tuple[tuple[str, ...], Mapping[str, Any]]:
        arguments = action.arguments
        if action.tool_id == 'filesystem':
            return self._filesystem(agent_id, workspace, action.operation, arguments)
        if action.tool_id == 'git':
            return self._git(agent_id, workspace, action.operation, arguments, timeout_seconds, max_output_chars)
        if action.tool_id == 'code-search':
            return self._code_search(agent_id, workspace, arguments)
        if action.tool_id in {'terminal', 'compiler', 'test-runner'}:
            return self._argv_tool(agent_id, workspace, action, timeout_seconds, max_output_chars)
        handler = self._handlers.get(action.tool_id)
        if handler is None:
            raise ExecutionToolFailure('core_unavailable', f'authorized core is unavailable: {action.tool_id}')
        result = dict(handler(workspace, arguments))
        artifact = self.artifacts.put(
            kind='execution-core-output', producer_agent_id=agent_id,
            content=canonical_json(result), metadata={'tool_id': action.tool_id, 'operation': action.operation},
        )
        return (artifact.artifact_id,), {'handler_result_digest': canonical_digest(result)}

    def _filesystem(
        self,
        agent_id: str,
        workspace: RepositoryWorkspace,
        operation: str,
        arguments: Mapping[str, Any],
    ) -> tuple[tuple[str, ...], Mapping[str, Any]]:
        path = str(arguments.get('path', ''))
        if operation == 'read_text':
            content = workspace.read_text(path)
        elif operation == 'write_text':
            workspace.write_text(path, str(arguments.get('content', '')))
            content = workspace.read_text(path)
        elif operation == 'append_text':
            workspace.append_text(path, str(arguments.get('content', '')))
            content = workspace.read_text(path)
        else:
            raise ValueError(f'unsupported filesystem operation: {operation}')
        artifact = self.artifacts.put(
            kind='execution-file-content', producer_agent_id=agent_id, content=content,
            metadata={'path': path, 'operation': operation},
        )
        return (artifact.artifact_id,), {'path': path, 'content_sha256': canonical_digest(content)}

    def _git(
        self,
        agent_id: str,
        workspace: RepositoryWorkspace,
        operation: str,
        arguments: Mapping[str, Any],
        timeout_seconds: float,
        max_output_chars: int,
    ) -> tuple[tuple[str, ...], Mapping[str, Any]]:
        allowed = {
            'status': ('git', 'status', '--porcelain=v1'),
            'diff': ('git', 'diff', '--no-ext-diff'),
            'rev-parse-head': ('git', 'rev-parse', 'HEAD'),
        }
        if operation not in allowed:
            raise ValueError(f'unsupported bounded git operation: {operation}')
        result = workspace.run_argv(allowed[operation], timeout_seconds=timeout_seconds, max_output_chars=max_output_chars)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or f'git returned {result.returncode}')
        artifact = self.artifacts.put(
            kind='execution-command-output', producer_agent_id=agent_id, content=result.stdout,
            metadata={'tool_id': 'git', 'operation': operation, 'returncode': result.returncode},
        )
        return (artifact.artifact_id,), {'returncode': result.returncode, 'stderr': result.stderr}

    @staticmethod
    def _run_disposable_argv(
        workspace: RepositoryWorkspace,
        argv: tuple[str, ...],
        *,
        timeout_seconds: float,
        max_output_chars: int,
    ) -> tuple[int, str, str, bool]:
        if timeout_seconds <= 0 or max_output_chars <= 0:
            raise ValueError('subprocess bounds must be positive')
        with tempfile.TemporaryDirectory(prefix='nolane-exec-') as tmp:
            sandbox = Path(tmp) / 'repository'
            shutil.copytree(
                workspace.root,
                sandbox,
                symlinks=True,
                ignore=shutil.ignore_patterns('.git'),
            )
            try:
                proc = subprocess.run(
                    list(argv),
                    cwd=sandbox,
                    text=True,
                    capture_output=True,
                    timeout=float(timeout_seconds),
                    check=False,
                )
                return (
                    int(proc.returncode),
                    proc.stdout[:max_output_chars],
                    proc.stderr[:max_output_chars],
                    False,
                )
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or '')
                stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or '')
                return 124, stdout[:max_output_chars], stderr[:max_output_chars], True

    def _argv_tool(
        self,
        agent_id: str,
        workspace: RepositoryWorkspace,
        action: ToolAction,
        timeout_seconds: float,
        max_output_chars: int,
    ) -> tuple[tuple[str, ...], Mapping[str, Any]]:
        raw = action.arguments.get('argv')
        if not isinstance(raw, (list, tuple)) or not raw:
            raise ValueError(f'{action.tool_id} requires non-empty argv list')
        argv = tuple(str(x) for x in raw)
        if any('\x00' in x for x in argv):
            raise ValueError(f'{action.tool_id} argv contains invalid NUL')
        returncode, stdout, stderr, timed_out = self._run_disposable_argv(
            workspace,
            argv,
            timeout_seconds=timeout_seconds,
            max_output_chars=max_output_chars,
        )
        artifact = self.artifacts.put(
            kind='execution-command-output', producer_agent_id=agent_id,
            content=canonical_json({'stdout': stdout, 'stderr': stderr}),
            metadata={
                'tool_id': action.tool_id, 'operation': action.operation,
                'argv_digest': canonical_digest(list(argv)), 'returncode': returncode,
                'timed_out': timed_out, 'workspace_mode': 'disposable-copy',
            },
        )
        if timed_out:
            raise ExecutionToolFailure('timeout', f'{action.tool_id} timed out', (artifact.artifact_id,))
        if returncode != 0:
            raise ExecutionToolFailure('command_failed', f'{action.tool_id} returned {returncode}: {stderr}', (artifact.artifact_id,))
        return (artifact.artifact_id,), {
            'returncode': returncode,
            'timed_out': timed_out,
            'workspace_mode': 'disposable-copy',
        }

    def _code_search(
        self,
        agent_id: str,
        workspace: RepositoryWorkspace,
        arguments: Mapping[str, Any],
    ) -> tuple[tuple[str, ...], Mapping[str, Any]]:
        query = str(arguments.get('query', ''))
        if not query:
            raise ValueError('code-search requires query')
        max_matches = int(arguments.get('max_matches', 100))
        if max_matches <= 0 or max_matches > 1000:
            raise ValueError('code-search max_matches must lie in 1..1000')
        matches: list[dict[str, Any]] = []
        files = workspace.run_argv(('git', 'ls-files'), max_output_chars=1_000_000)
        for relative in files.stdout.splitlines():
            path = workspace.resolve_repo_path(relative)
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if query in line:
                    matches.append({'path': relative, 'line': lineno, 'text': line[:1000]})
                    if len(matches) >= max_matches:
                        break
            if len(matches) >= max_matches:
                break
        artifact = self.artifacts.put(
            kind='execution-code-search', producer_agent_id=agent_id,
            content=canonical_json({'query': query, 'matches': matches}),
            metadata={'match_count': len(matches)},
        )
        return (artifact.artifact_id,), {'match_count': len(matches)}

    def to_state(self) -> dict[str, Any]:
        return {'receipts': [row.to_state() for row in self.receipts()]}

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        external_cores: ExternalCoreRegistry,
        artifacts: ArtifactStore,
        coding_patches: CodingPatchLedger | None,
        code_claims: CodeClaimLedger | None,
        state: Mapping[str, Any],
    ) -> 'ExternalCoreExecutor':
        return cls(
            registry=registry,
            external_cores=external_cores,
            artifacts=artifacts,
            coding_patches=coding_patches,
            code_claims=code_claims,
            receipts=tuple(CoreInvocationReceipt.from_state(x) for x in state.get('receipts', ())),
        )
