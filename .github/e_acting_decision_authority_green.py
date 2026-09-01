from pathlib import Path


def _replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old in text:
        text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")
        return
    if new in text:
        return
    raise SystemExit(f"guard failed: {label}")


execution = Path("nolane/external_core/execution.py")

_replace_once(
    execution,
    '''    ExecutionBudget,\n    ExecutionCounters,\n)\n''',
    '''    ExecutionBudget,\n    ExecutionCounters,\n    InferenceRequest,\n)\n''',
    "execution request type import",
)

_replace_once(
    execution,
    'COMPONENT_VERSION = "0.0.8"',
    'COMPONENT_VERSION = "0.0.9"',
    "execution control component version",
)

old_anchor = '''    def _expected_core_contract_digest(self, tool_id: str) -> str:\n        if str(tool_id) not in frozenset(getattr(self.executor, 'external_core_ids', ())):\n            return ''\n        return self.external_cores.get(str(tool_id)).contract_digest\n\n    def bind_backend(self, agent_id: str, backend: AgentInferenceBackend) -> None:\n'''

new_anchor = '''    def _expected_core_contract_digest(self, tool_id: str) -> str:\n        if str(tool_id) not in frozenset(getattr(self.executor, 'external_core_ids', ())):\n            return ''\n        return self.external_cores.get(str(tool_id)).contract_digest\n\n    @staticmethod\n    def _attest_decision_receipt(\n        receipt: AgentDecisionReceipt,\n        *,\n        request: InferenceRequest,\n        backend: AgentInferenceBackend,\n    ) -> AgentDecisionReceipt:\n        try:\n            canonical = AgentDecisionReceipt.from_state(receipt.to_state())\n        except Exception as exc:\n            raise ValueError('decision receipt integrity validation failed') from exc\n        if canonical != receipt:\n            raise ValueError('decision receipt integrity validation failed')\n\n        expected = {\n            'backend_id': str(backend.backend_id),\n            'request_digest': request.digest,\n            'agent_id': request.agent_id,\n            'neural_version': request.neural_version,\n            'checkpoint_digest': request.checkpoint_digest,\n            'encoder_version': request.encoder_version,\n            'context_digest': request.context_digest,\n            'action_schema_digest': request.action_schema_digest,\n            'step_index': request.step_index,\n        }\n        mismatches = [\n            field\n            for field, expected_value in expected.items()\n            if getattr(canonical, field, None) != expected_value\n        ]\n        if mismatches:\n            raise ValueError(\n                'decision receipt authority mismatch: ' + ', '.join(mismatches)\n            )\n        return canonical\n\n    def bind_backend(self, agent_id: str, backend: AgentInferenceBackend) -> None:\n'''

_replace_once(
    execution,
    old_anchor,
    new_anchor,
    "decision authority attestor",
)

_replace_once(
    execution,
    '''        decision = backend.decide(request)\n        if decision.receipt_id in self._decisions and self._decisions[decision.receipt_id] != decision:\n''',
    '''        decision = self._attest_decision_receipt(\n            backend.decide(request),\n            request=request,\n            backend=backend,\n        )\n        if decision.receipt_id in self._decisions and self._decisions[decision.receipt_id] != decision:\n''',
    "pre-persistence decision attestation",
)

versions = Path("nolane/metadata/component_versions.py")
_replace_once(
    versions,
    '        "external.execution.control": 8,',
    '        "external.execution.control": 9,',
    "execution control revision authority",
)

native_test = Path("tests/test_refoundation_wave5aa_native_execution_control.py")
_replace_once(
    native_test,
    '    assert canonical.COMPONENT_VERSION == "0.0.8"',
    '    assert canonical.COMPONENT_VERSION == "0.0.9"',
    "native execution module version assertion",
)
_replace_once(
    native_test,
    '    assert row.component_version == "0.0.8"',
    '    assert row.component_version == "0.0.9"',
    "native execution ledger version assertion",
)
_replace_once(
    native_test,
    '    assert str(component_version("external.execution.control")) == "0.0.8"',
    '    assert str(component_version("external.execution.control")) == "0.0.9"',
    "native execution component version assertion",
)
