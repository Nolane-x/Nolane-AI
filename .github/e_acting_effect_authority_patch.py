from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    if old not in source:
        raise SystemExit(f"expected patch anchor missing in {path}: {old[:120]!r}")
    if source.count(old) != 1:
        raise SystemExit(f"patch anchor is not unique in {path}: {old[:120]!r}")
    file_path.write_text(source.replace(old, new, 1), encoding="utf-8")


# Protocol: make risk/effect authority intrinsically coherent.
replace_once(
    "nolane/external_core/acting_protocol.py",
    'COMPONENT_VERSION = "0.1.3"',
    'COMPONENT_VERSION = "0.1.4"',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '''        return cls(int(value))\n\n\n@dataclass(frozen=True, slots=True)\nclass ActionBudget:''',
    '''        return cls(int(value))\n\n\n_EXECUTION_RISK_RANK = {\n    ExecutionRisk.R0: 0,\n    ExecutionRisk.R1: 1,\n    ExecutionRisk.R2: 2,\n    ExecutionRisk.R3: 3,\n    ExecutionRisk.R4: 4,\n}\n_EFFECT_MINIMUM_RISK = {\n    EffectClass.READ: ExecutionRisk.R1,\n    EffectClass.LOCAL_MUTATION: ExecutionRisk.R2,\n    EffectClass.EXTERNAL_MUTATION: ExecutionRisk.R3,\n    EffectClass.IRREVERSIBLE: ExecutionRisk.R4,\n}\n\n\ndef execution_risk_rank(risk_class: ExecutionRisk | str) -> int:\n    return _EXECUTION_RISK_RANK[ExecutionRisk(risk_class)]\n\n\ndef minimum_risk_for_effect(effect_class: EffectClass | str) -> ExecutionRisk:\n    return _EFFECT_MINIMUM_RISK[EffectClass(effect_class)]\n\n\n@dataclass(frozen=True, slots=True)\nclass ActionBudget:''',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '''        object.__setattr__(self, "risk_class", ExecutionRisk(self.risk_class))\n        object.__setattr__(self, "effect_class", EffectClass(self.effect_class))\n        if isinstance(self.budget, Mapping):''',
    '''        object.__setattr__(self, "risk_class", ExecutionRisk(self.risk_class))\n        object.__setattr__(self, "effect_class", EffectClass(self.effect_class))\n        minimum_risk = minimum_risk_for_effect(self.effect_class)\n        if execution_risk_rank(self.risk_class) < execution_risk_rank(minimum_risk):\n            raise ValueError(\n                "risk class understates effect class: "\n                f"{self.risk_class.value} < {minimum_risk.value} for {self.effect_class.value}"\n            )\n        if isinstance(self.budget, Mapping):''',
)
replace_once(
    "nolane/external_core/acting_protocol.py",
    '''    "ProtocolViolation",\n    "VerifierLevel",\n    "COMPONENT_ID",''',
    '''    "ProtocolViolation",\n    "VerifierLevel",\n    "execution_risk_rank",\n    "minimum_risk_for_effect",\n    "COMPONENT_ID",''',
)

# Runtime: classify physical tool effects independently of caller claims and reject downgrades before ledger/effect mutation.
replace_once(
    "nolane/external_core/acting_runtime.py",
    'COMPONENT_VERSION = "0.1.3"',
    'COMPONENT_VERSION = "0.1.4"',
)
replace_once(
    "nolane/external_core/acting_runtime.py",
    '''    ProtocolViolation,\n    VerifierLevel,\n)''',
    '''    ProtocolViolation,\n    VerifierLevel,\n    execution_risk_rank,\n    minimum_risk_for_effect,\n)''',
)
replace_once(
    "nolane/external_core/acting_runtime.py",
    '''    @staticmethod\n    def _action_id(*, agent_id: str, task_id: str, idempotency_key: str) -> str:''',
    '''    @staticmethod\n    def minimum_effect_class(action: ToolAction) -> EffectClass:\n        """Return the fail-closed physical effect floor for a concrete tool action.\n\n        Only built-in operations whose implementations are bounded reads are\n        admitted as READ. Repository-local filesystem writes are reversible local\n        mutations. Process tools, registered/custom handlers, and unknown future\n        operations are external-like because the repository workspace is not an OS\n        sandbox and E cannot prove their side effects stay local.\n        """\n\n        tool_id = str(action.tool_id)\n        operation = str(action.operation)\n        if tool_id == "filesystem":\n            if operation == "read_text" and not action.mutation_paths:\n                return EffectClass.READ\n            if action.mutation_paths:\n                return EffectClass.LOCAL_MUTATION\n            return EffectClass.EXTERNAL_MUTATION\n        if tool_id == "git":\n            if operation in {"status", "diff", "rev-parse-head"} and not action.mutation_paths:\n                return EffectClass.READ\n            return EffectClass.EXTERNAL_MUTATION\n        if tool_id == "code-search":\n            if not action.mutation_paths:\n                return EffectClass.READ\n            return EffectClass.EXTERNAL_MUTATION\n        return EffectClass.EXTERNAL_MUTATION\n\n    @staticmethod\n    def _effect_rank(effect_class: EffectClass | str) -> int:\n        return {\n            EffectClass.READ: 0,\n            EffectClass.LOCAL_MUTATION: 1,\n            EffectClass.EXTERNAL_MUTATION: 2,\n            EffectClass.IRREVERSIBLE: 3,\n        }[EffectClass(effect_class)]\n\n    @staticmethod\n    def _action_id(*, agent_id: str, task_id: str, idempotency_key: str) -> str:''',
)
replace_once(
    "nolane/external_core/acting_runtime.py",
    '''        effect = EffectClass(effect_class)\n        risk = ExecutionRisk(risk_class)\n        resolved_verifier_level = VerifierLevel.coerce(verifier_level)\n        minimum_verifier_level = self.protocol.minimum_verifier_level(risk)''',
    '''        effect = EffectClass(effect_class)\n        risk = ExecutionRisk(risk_class)\n        physical_effect_floor = self.minimum_effect_class(action)\n        if self._effect_rank(effect) < self._effect_rank(physical_effect_floor):\n            raise PermissionError(\n                "effect classification downgrade: "\n                f"{action.tool_id}.{action.operation} requires at least "\n                f"{physical_effect_floor.value}, got {effect.value}"\n            )\n        minimum_risk = minimum_risk_for_effect(effect)\n        if execution_risk_rank(risk) < execution_risk_rank(minimum_risk):\n            raise PermissionError(\n                "risk classification downgrade: "\n                f"{effect.value} requires at least {minimum_risk.value}, got {risk.value}"\n            )\n        resolved_verifier_level = VerifierLevel.coerce(verifier_level)\n        minimum_verifier_level = self.protocol.minimum_verifier_level(risk)''',
)

# Canonical control: consume the runtime classifier instead of maintaining a weaker parallel mapping.
replace_once(
    "nolane/external_core/execution.py",
    'from nolane.external_core.acting_protocol import ActionPhase, EffectClass, ExecutionRisk, VerifierLevel',
    'from nolane.external_core.acting_protocol import ActionPhase, EffectClass, ExecutionRisk, VerifierLevel, minimum_risk_for_effect',
)
replace_once(
    "nolane/external_core/execution.py",
    'COMPONENT_VERSION = "0.0.5"',
    'COMPONENT_VERSION = "0.0.6"',
)
replace_once(
    "nolane/external_core/execution.py",
    '''            is_external = action.tool_action.tool_id in self.executor.external_core_ids\n            unconfined_process_tools = frozenset({'terminal', 'compiler', 'test-runner'})\n            if session.counters.tool_calls >= session.budget.max_tool_calls:\n                return self._budget_terminal(session, 'tool-call budget exhausted')\n            if is_external and session.counters.external_core_calls >= session.budget.max_external_core_calls:\n                return self._budget_terminal(session, 'external-core budget exhausted')\n\n            task = self.tasks.get(session.task_id)\n            identity = self.registry.get(session.agent_id)\n            if task.aborted_by is not None:\n                return self._terminal(session, ExecutionState.ABORTED, task.abort_reason or 'task aborted')\n            if identity.status is AgentStatus.PAUSED:\n                return self._terminal(session, ExecutionState.PAUSED, 'agent paused by authority')\n\n            if is_external or action.tool_action.tool_id in unconfined_process_tools:\n                effect_class = EffectClass.EXTERNAL_MUTATION\n                risk_class = ExecutionRisk.R3\n                verifier_level = VerifierLevel.V3\n                recovery_plan = 'reconcile externally observed effect from core receipt evidence'\n            elif action.tool_action.mutation_paths:\n                effect_class = EffectClass.LOCAL_MUTATION\n                risk_class = ExecutionRisk.R2\n                verifier_level = VerifierLevel.V2\n                recovery_plan = 'restore isolated workspace checkpoint'\n            else:\n                effect_class = EffectClass.READ\n                risk_class = ExecutionRisk.R1\n                verifier_level = VerifierLevel.V1\n                recovery_plan = ''\n''',
    '''            is_external = action.tool_action.tool_id in self.executor.external_core_ids\n            effect_class = self.acting_executor.minimum_effect_class(action.tool_action)\n            risk_class = minimum_risk_for_effect(effect_class)\n            verifier_level = self.acting_executor.protocol.minimum_verifier_level(risk_class)\n            is_external_effect = effect_class in {EffectClass.EXTERNAL_MUTATION, EffectClass.IRREVERSIBLE}\n            if session.counters.tool_calls >= session.budget.max_tool_calls:\n                return self._budget_terminal(session, 'tool-call budget exhausted')\n            if is_external_effect and session.counters.external_core_calls >= session.budget.max_external_core_calls:\n                return self._budget_terminal(session, 'external-effect budget exhausted')\n\n            task = self.tasks.get(session.task_id)\n            identity = self.registry.get(session.agent_id)\n            if task.aborted_by is not None:\n                return self._terminal(session, ExecutionState.ABORTED, task.abort_reason or 'task aborted')\n            if identity.status is AgentStatus.PAUSED:\n                return self._terminal(session, ExecutionState.PAUSED, 'agent paused by authority')\n\n            if is_external_effect:\n                recovery_plan = 'reconcile externally observed effect from core receipt evidence'\n            elif effect_class is EffectClass.LOCAL_MUTATION:\n                recovery_plan = 'restore isolated workspace checkpoint'\n            else:\n                recovery_plan = ''\n''',
)
replace_once(
    "nolane/external_core/execution.py",
    '''                external_core_calls=session.counters.external_core_calls + (1 if is_external else 0),''',
    '''                external_core_calls=session.counters.external_core_calls + (1 if is_external_effect else 0),''',
)

# Canonical component revision and version assertions.
replace_once(
    "nolane/metadata/component_versions.py",
    '"external.execution.control": 5,',
    '"external.execution.control": 6,',
)
replace_once(
    "tests/test_refoundation_component_versions.py",
    '"external.execution.control": 5,',
    '"external.execution.control": 6,',
)
replace_once(
    "tests/test_refoundation_component_versions.py",
    '''    assert str(component_version("external.execution.control")) == "0.0.5"\n    assert str(next_component_version("external.execution.control")) == "0.0.6"''',
    '''    assert str(component_version("external.execution.control")) == "0.0.6"\n    assert str(next_component_version("external.execution.control")) == "0.0.7"''',
)
replace_once(
    "tests/test_refoundation_wave5aa_native_execution_control.py",
    'assert canonical.COMPONENT_VERSION == "0.0.5"',
    'assert canonical.COMPONENT_VERSION == "0.0.6"',
)

# Own the RED contract in both E gates.
for workflow in (
    ".github/workflows/refoundation-e-acting.yml",
    ".github/workflows/e-acting-final-verification.yml",
):
    replace_once(
        workflow,
        '''            tests/test_refoundation_acting_runtime.py \\\n            tests/test_refoundation_acting_receipt_provenance.py \\\n''',
        '''            tests/test_refoundation_acting_runtime.py \\\n            tests/test_refoundation_acting_effect_authority.py \\\n            tests/test_refoundation_acting_receipt_provenance.py \\\n''',
    )

# Current architecture truth.
replace_once(
    "CURRENT/E_ACTING.md",
    '| Transaction Protocol | `nolane/external_core/acting_protocol.py` | `0.1.3` |',
    '| Transaction Protocol | `nolane/external_core/acting_protocol.py` | `0.1.4` |',
)
replace_once(
    "CURRENT/E_ACTING.md",
    '| Transactional Executor | `nolane/external_core/acting_runtime.py` | `0.1.3` |',
    '| Transactional Executor | `nolane/external_core/acting_runtime.py` | `0.1.4` |',
)
replace_once(
    "CURRENT/E_ACTING.md",
    '| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.5` |',
    '| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.6` |',
)
replace_once(
    "CURRENT/E_ACTING.md",
    '''21. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.\n''',
    '''21. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.\n22. Risk authority is monotone with effect authority: READ requires at least R1, local mutation R2, external mutation R3, and irreversible effect R4. An execution contract cannot encode a weaker risk class than its effect class.\n23. Physical effect classification is enforced again at the transactional runtime before any ledger or core mutation. Only bounded built-in reads are admitted as READ; filesystem writes are local mutations; process, external, custom, and unknown handlers are external-like by default. Caller-supplied effect/risk labels cannot downgrade this floor.\n''',
)
