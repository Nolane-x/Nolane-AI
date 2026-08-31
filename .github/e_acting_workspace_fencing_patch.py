from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    if old not in source:
        raise SystemExit(f"expected patch anchor missing in {path}: {old[:160]!r}")
    if source.count(old) != 1:
        raise SystemExit(f"patch anchor is not unique in {path}: {old[:160]!r}")
    file_path.write_text(source.replace(old, new, 1), encoding="utf-8")


# Canonical execution-control revision: persisted workspace identity becomes payload-bound.
replace_once(
    "nolane/external_core/execution.py",
    'COMPONENT_VERSION = "0.0.6"',
    'COMPONENT_VERSION = "0.0.7"',
)

replace_once(
    "nolane/external_core/execution.py",
    '''    workspace_base_revision: str\n    decision_receipt_ids: tuple[str, ...] = ()''',
    '''    workspace_base_revision: str\n    workspace_provenance_version: int = 1\n    initial_workspace_digest: str | None = None\n    current_workspace_digest: str | None = None\n    decision_receipt_ids: tuple[str, ...] = ()''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''    wall_clock_ms: int = 0\n\n    def to_state(self) -> dict[str, Any]:\n        return {\n            'session_id': self.session_id,\n            'agent_id': self.agent_id,\n            'task_id': self.task_id,\n            'action_schema': list(self.action_schema),\n            'budget': self.budget.to_state(),\n            'counters': self.counters.to_state(),\n            'step_index': self.step_index,\n            'state': self.state.value,\n            'backend_id': self.backend_id,\n            'checkpoint_digest': self.checkpoint_digest,\n            'workspace_base_revision': self.workspace_base_revision,\n            'decision_receipt_ids': list(self.decision_receipt_ids),\n            'step_receipt_ids': list(self.step_receipt_ids),\n            'core_receipt_ids': list(self.core_receipt_ids),\n            'output_artifact_ids': list(self.output_artifact_ids),\n            'terminal_receipt_id': self.terminal_receipt_id,\n            'wall_clock_ms': self.wall_clock_ms,\n        }\n''',
    '''    wall_clock_ms: int = 0\n\n    def __post_init__(self) -> None:\n        version = int(self.workspace_provenance_version)\n        if version not in {1, 2}:\n            raise ValueError('unsupported workspace provenance version')\n        object.__setattr__(self, 'workspace_provenance_version', version)\n        initial = None if self.initial_workspace_digest is None else str(self.initial_workspace_digest).strip()\n        current = None if self.current_workspace_digest is None else str(self.current_workspace_digest).strip()\n        if version == 1:\n            if initial or current:\n                raise ValueError('legacy execution session cannot carry modern workspace digest')\n            object.__setattr__(self, 'initial_workspace_digest', None)\n            object.__setattr__(self, 'current_workspace_digest', None)\n            return\n        if not initial or not current:\n            raise ValueError('modern execution session requires workspace digest')\n        object.__setattr__(self, 'initial_workspace_digest', initial)\n        object.__setattr__(self, 'current_workspace_digest', current)\n\n    def to_state(self) -> dict[str, Any]:\n        state = {\n            'session_id': self.session_id,\n            'agent_id': self.agent_id,\n            'task_id': self.task_id,\n            'action_schema': list(self.action_schema),\n            'budget': self.budget.to_state(),\n            'counters': self.counters.to_state(),\n            'step_index': self.step_index,\n            'state': self.state.value,\n            'backend_id': self.backend_id,\n            'checkpoint_digest': self.checkpoint_digest,\n            'workspace_base_revision': self.workspace_base_revision,\n            'decision_receipt_ids': list(self.decision_receipt_ids),\n            'step_receipt_ids': list(self.step_receipt_ids),\n            'core_receipt_ids': list(self.core_receipt_ids),\n            'output_artifact_ids': list(self.output_artifact_ids),\n            'terminal_receipt_id': self.terminal_receipt_id,\n            'wall_clock_ms': self.wall_clock_ms,\n        }\n        if self.workspace_provenance_version >= 2:\n            state['workspace_provenance_version'] = self.workspace_provenance_version\n            state['initial_workspace_digest'] = self.initial_workspace_digest\n            state['current_workspace_digest'] = self.current_workspace_digest\n        return state\n''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''            workspace_base_revision=str(state['workspace_base_revision']),\n            decision_receipt_ids=tuple(str(x) for x in state.get('decision_receipt_ids', ())),''',
    '''            workspace_base_revision=str(state['workspace_base_revision']),\n            workspace_provenance_version=int(state.get('workspace_provenance_version', 1)),\n            initial_workspace_digest=(\n                None if state.get('initial_workspace_digest') is None\n                else str(state['initial_workspace_digest'])\n            ),\n            current_workspace_digest=(\n                None if state.get('current_workspace_digest') is None\n                else str(state['current_workspace_digest'])\n            ),\n            decision_receipt_ids=tuple(str(x) for x in state.get('decision_receipt_ids', ())),''',
)

# Persisted receipt history must form one workspace-digest chain.
replace_once(
    "nolane/external_core/execution.py",
    '''            for receipt_id in session.step_receipt_ids:\n                step = self._steps.get(receipt_id)''',
    '''            first_workspace_digest: str | None = None\n            previous_workspace_digest: str | None = None\n            for receipt_id in session.step_receipt_ids:\n                step = self._steps.get(receipt_id)''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''                if step.core_receipt_id is not None and step.core_receipt_id not in session.core_receipt_ids:\n                    raise ValueError('execution step receipt core binding mismatch')\n\n            if session.terminal_receipt_id is not None:''',
    '''                if step.core_receipt_id is not None and step.core_receipt_id not in session.core_receipt_ids:\n                    raise ValueError('execution step receipt core binding mismatch')\n                if first_workspace_digest is None:\n                    first_workspace_digest = step.before_workspace_digest\n                if (\n                    previous_workspace_digest is not None\n                    and step.before_workspace_digest != previous_workspace_digest\n                ):\n                    raise ValueError('workspace digest continuity mismatch')\n                previous_workspace_digest = step.after_workspace_digest\n\n            if session.workspace_provenance_version >= 2:\n                if session.step_receipt_ids:\n                    if first_workspace_digest != session.initial_workspace_digest:\n                        raise ValueError('workspace digest continuity mismatch at session origin')\n                    if previous_workspace_digest != session.current_workspace_digest:\n                        raise ValueError('workspace digest continuity mismatch at session frontier')\n                elif session.current_workspace_digest != session.initial_workspace_digest:\n                    raise ValueError('workspace digest continuity mismatch for empty session')\n\n            if session.terminal_receipt_id is not None:''',
)

# One helper defines the currently authoritative persisted workspace frontier.
replace_once(
    "nolane/external_core/execution.py",
    '''    @property\n    def digest(self) -> str:\n        return canonical_digest(self.to_state())\n\n    def bind_backend''',
    '''    @property\n    def digest(self) -> str:\n        return canonical_digest(self.to_state())\n\n    def _persisted_workspace_fence(self, session: ExecutionSession) -> str | None:\n        if session.workspace_provenance_version >= 2:\n            return session.current_workspace_digest\n        if session.step_receipt_ids:\n            return self._steps[session.step_receipt_ids[-1]].after_workspace_digest\n        return None\n\n    def bind_backend''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''    def attach_workspace(self, session_id: str, workspace: RepositoryWorkspace) -> None:\n        session = self.get_session(session_id)\n        if workspace.base_revision != session.workspace_base_revision:\n            raise ValueError('reattached workspace revision does not match persisted session')\n        self._workspaces[session.session_id] = workspace\n''',
    '''    def attach_workspace(self, session_id: str, workspace: RepositoryWorkspace) -> None:\n        session = self.get_session(session_id)\n        if workspace.base_revision != session.workspace_base_revision:\n            raise ValueError('reattached workspace revision does not match persisted session')\n        expected_digest = self._persisted_workspace_fence(session)\n        if expected_digest is not None and workspace.digest != expected_digest:\n            raise ValueError('reattached workspace digest does not match persisted session frontier')\n        self._workspaces[session.session_id] = workspace\n''',
)

# New sessions mint provenance-v2 at the exact payload digest they start from.
replace_once(
    "nolane/external_core/execution.py",
    '''        if not schema:\n            raise ValueError('execution action schema must be non-empty')\n        self._session_counter += 1\n        row = ExecutionSession(''',
    '''        if not schema:\n            raise ValueError('execution action schema must be non-empty')\n        workspace_digest = str(workspace.digest).strip()\n        if not workspace_digest:\n            raise ValueError('execution start requires workspace digest')\n        self._session_counter += 1\n        row = ExecutionSession(''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''            checkpoint_digest=str(backend.checkpoint_digest),\n            workspace_base_revision=workspace.base_revision,\n        )''',
    '''            checkpoint_digest=str(backend.checkpoint_digest),\n            workspace_base_revision=workspace.base_revision,\n            workspace_provenance_version=2,\n            initial_workspace_digest=workspace_digest,\n            current_workspace_digest=workspace_digest,\n        )''',
)

# Historical state remains readable/reconcilable, but cannot be downgraded into forward authority.
replace_once(
    "nolane/external_core/execution.py",
    '''        workspace = self._workspaces.get(session.session_id)\n        if workspace is None:\n            raise RuntimeError('execution workspace must be attached before stepping')\n        task = self.tasks.get(session.task_id)''',
    '''        workspace = self._workspaces.get(session.session_id)\n        if workspace is None:\n            raise RuntimeError('execution workspace must be attached before stepping')\n        if session.workspace_provenance_version < 2:\n            raise RuntimeError(\n                'legacy execution session lacks workspace provenance; '\n                'forward execution requires a modern workspace fence'\n            )\n        if workspace.digest != session.current_workspace_digest:\n            raise RuntimeError('attached workspace digest differs from persisted execution session')\n        task = self.tasks.get(session.task_id)''',
)

# Re-check the fence immediately before transactional dispatch, and bind the observed core-before digest back to it.
replace_once(
    "nolane/external_core/execution.py",
    '''            acting = self.acting_executor.invoke(\n                agent_id=session.agent_id,''',
    '''            if workspace.digest != session.current_workspace_digest:\n                raise RuntimeError('workspace digest changed before transactional dispatch')\n            acting = self.acting_executor.invoke(\n                agent_id=session.agent_id,''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''            core = self.executor.get_receipt(acting.core_receipt_id)\n            counters = ExecutionCounters(''',
    '''            core = self.executor.get_receipt(acting.core_receipt_id)\n            if core.before_workspace_digest != session.current_workspace_digest:\n                raise ValueError('core receipt workspace fence mismatch')\n            counters = ExecutionCounters(''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''                step_receipt_ids=session.step_receipt_ids + (step_receipt.receipt_id,),\n                wall_clock_ms=session.wall_clock_ms + elapsed,\n                state=state_after,''',
    '''                step_receipt_ids=session.step_receipt_ids + (step_receipt.receipt_id,),\n                current_workspace_digest=str(core.after_workspace_digest),\n                wall_clock_ms=session.wall_clock_ms + elapsed,\n                state=state_after,''',
)

# Crash recovery must prove the committed core starts at the same persisted frontier and advance v2 state.
replace_once(
    "nolane/external_core/execution.py",
    '''                if not bool(core.success):\n                    raise ValueError('committed acting action references unsuccessful core receipt')\n                committed_receipts[row.action_id] = core''',
    '''                if not bool(core.success):\n                    raise ValueError('committed acting action references unsuccessful core receipt')\n                expected_workspace_digest = self._persisted_workspace_fence(session)\n                if (\n                    expected_workspace_digest is not None\n                    and str(core.before_workspace_digest) != expected_workspace_digest\n                ):\n                    raise ValueError('committed acting action workspace fence mismatch')\n                committed_receipts[row.action_id] = core''',
)

replace_once(
    "nolane/external_core/execution.py",
    '''                    core_receipt_ids=session.core_receipt_ids + (str(core.receipt_id),),\n                    step_receipt_ids=session.step_receipt_ids + (step_receipt.receipt_id,),\n                )''',
    '''                    core_receipt_ids=session.core_receipt_ids + (str(core.receipt_id),),\n                    step_receipt_ids=session.step_receipt_ids + (step_receipt.receipt_id,),\n                    current_workspace_digest=(\n                        str(core.after_workspace_digest)\n                        if session.workspace_provenance_version >= 2\n                        else session.current_workspace_digest\n                    ),\n                )''',
)

# Component revision authority.
replace_once(
    "nolane/metadata/component_versions.py",
    '"external.execution.control": 6,',
    '"external.execution.control": 7,',
)
replace_once(
    "tests/test_refoundation_component_versions.py",
    '"external.execution.control": 6,',
    '"external.execution.control": 7,',
)
replace_once(
    "tests/test_refoundation_component_versions.py",
    '''    assert str(component_version("external.execution.control")) == "0.0.6"\n    assert str(next_component_version("external.execution.control")) == "0.0.7"''',
    '''    assert str(component_version("external.execution.control")) == "0.0.7"\n    assert str(next_component_version("external.execution.control")) == "0.0.8"''',
)
replace_once(
    "tests/test_refoundation_wave5aa_native_execution_control.py",
    'assert canonical.COMPONENT_VERSION == "0.0.6"',
    'assert canonical.COMPONENT_VERSION == "0.0.7"',
)
replace_once(
    "tests/test_refoundation_wave5aa_native_execution_control.py",
    '''    assert row.component_version == "0.0.6"\n    assert str(component_version("external.execution.control")) == "0.0.6"''',
    '''    assert row.component_version == "0.0.7"\n    assert str(component_version("external.execution.control")) == "0.0.7"''',
)

# Current architecture truth.
replace_once(
    "CURRENT/E_ACTING.md",
    '| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.6` |',
    '| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.7` |',
)
replace_once(
    "CURRENT/E_ACTING.md",
    '''24. Physical effect classification is enforced again at the transactional runtime before any ledger or core mutation. Only bounded built-in reads are admitted as READ; filesystem writes are local mutations; process, external, custom, and unknown handlers are external-like by default. Caller-supplied effect/risk labels cannot downgrade this floor.\n''',
    '''24. Physical effect classification is enforced again at the transactional runtime before any ledger or core mutation. Only bounded built-in reads are admitted as READ; filesystem writes are local mutations; process, external, custom, and unknown handlers are external-like by default. Caller-supplied effect/risk labels cannot downgrade this floor.\n25. Modern execution sessions bind both the initial and current full workspace payload digest in provenance-v2 state. Reattachment requires the same base revision and the exact current payload digest; a same-revision substituted worktree is not execution authority.\n26. Persisted step receipts form one workspace chain: every step's `before_workspace_digest` must equal the previous step's `after_workspace_digest`; modern session origin/frontier digests must agree with the first/last receipt.\n27. Legacy execution sessions remain loadable for historical inspection and crash reconciliation but cannot resume forward execution. Stripping modern workspace-provenance fields therefore cannot downgrade a v2 session into effect authority. Normal commits and committed crash projections both advance the v2 current workspace fence.\n''',
)
replace_once(
    "CURRENT/E_ACTING.md",
    'Protocol `0.1.3` keeps acting schema version 1 for backward compatibility.',
    'Protocol `0.1.4` keeps acting schema version 1 for backward compatibility.',
)
replace_once(
    "CURRENT/E_ACTING.md",
    '''- persisted in-flight actions reconcile without effect re-invocation: pre-effect rows cancel, read-only rows close with explicit no-side-effect rollback, and uncertain mutating rows degrade.\n''',
    '''- persisted in-flight actions reconcile without effect re-invocation: pre-effect rows cancel, read-only rows close with explicit no-side-effect rollback, and uncertain mutating rows degrade; and\n- workspace provenance-v2 rejects same-revision payload substitution, enforces receipt-to-receipt digest continuity, advances the frontier on normal/recovered commits, and prevents legacy-state forward-execution downgrade.\n''',
)
